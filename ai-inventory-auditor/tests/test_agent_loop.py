import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from agent.agent_loop import AgentLoop


def make_agent(tools=None):
    """Tạo AgentLoop không khởi tạo Groq client thật."""
    agent = AgentLoop.__new__(AgentLoop)

    agent.tools = tools or {}
    agent.system_prompt = "Test system prompt"
    agent.model = "test-model"
    agent.max_steps = 5

    agent.tool_schemas = [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": "Test tool",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
        }
        for name in [
            "get_stock_data",
            "create_audit_request",
            "get_audit_request",
        ]
        if name in agent.tools
    ]

    return agent


def make_tool_call(name, arguments, call_id="call-1"):
    """Tạo tool call giả lập theo cấu trúc Groq."""
    function = SimpleNamespace(
        name=name,
        arguments=json.dumps(arguments),
    )

    return SimpleNamespace(
        id=call_id,
        function=function,
        model_dump=lambda exclude_none=True: {
            "id": call_id,
            "type": "function",
            "function": {
                "name": name,
                "arguments": json.dumps(arguments),
            },
        },
    )


def make_response(tool_calls=None, content=None, finish_reason="stop"):
    message = SimpleNamespace(
        tool_calls=tool_calls or [],
        content=content,
    )

    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=message,
                finish_reason=finish_reason,
            )
        ]
    )


class TestAgentPermissions(unittest.TestCase):

    def test_read_only_question_does_not_allow_write(self):
        agent = make_agent()

        self.assertFalse(
            agent._allows_audit_creation(
                "Kiểm tra tồn kho sản phẩm SP001"
            )
        )

    def test_explicit_audit_request_allows_write(self):
        agent = make_agent()

        self.assertTrue(
            agent._allows_audit_creation(
                "Tạo phiếu kiểm toán cho SP001"
            )
        )

    def test_negative_request_does_not_allow_write(self):
        agent = make_agent()

        self.assertFalse(
            agent._allows_audit_creation(
                "Kiểm tra SP001, không tạo phiếu kiểm toán"
            )
        )

    def test_write_tool_is_blocked_without_permission(self):
        write_tool = Mock(return_value={"success": True})
        agent = make_agent(
            {"create_audit_request": write_tool}
        )

        success, output = agent._execute_tool(
            "create_audit_request",
            {"product_id": "SP001", "reason": "Test"},
            allow_write=False,
        )

        self.assertFalse(success)
        self.assertIn("người dùng chưa yêu cầu tạo phiếu", output.lower())
        write_tool.assert_not_called()


class TestAgentLoop(unittest.TestCase):

    def test_read_only_question_does_not_expose_write_tool(self):
        get_stock = Mock(return_value={
            "product_id": "SP001",
            "expected_stock": 85,
            "variance": -5,
        })
        create_audit = Mock()

        agent = make_agent({
            "get_stock_data": get_stock,
            "create_audit_request": create_audit,
        })

        read_call = make_tool_call(
            "get_stock_data",
            {"product_id": "SP001"},
        )

        agent.client = Mock()
        agent.client.chat.completions.create.side_effect = [
            make_response([read_call], finish_reason="tool_calls"),
            make_response(content="Tồn dự kiến 85, độ lệch -5."),
        ]

        result = agent.run(
            "Kiểm tra tồn kho sản phẩm SP001"
        )

        sent_tools = (
            agent.client.chat.completions.create
            .call_args_list[0].kwargs["tools"]
        )
        sent_names = [
            schema["function"]["name"] for schema in sent_tools
        ]

        self.assertNotIn("create_audit_request", sent_names)
        create_audit.assert_not_called()
        self.assertTrue(result.success)

    def test_created_audit_must_be_read_back(self):
        audit_id = "AUD-TEST1234"

        get_stock = Mock(return_value={
            "product_id": "SP001",
            "expected_stock": 85,
            "variance": -5,
        })
        create_audit = Mock(return_value={
            "success": True,
            "audit": {
                "audit_id": audit_id,
                "product_id": "SP001",
            },
        })
        get_audit = Mock(return_value={
            "success": True,
            "audit": {
                "audit_id": audit_id,
                "product_id": "SP001",
            },
        })

        agent = make_agent({
            "get_stock_data": get_stock,
            "create_audit_request": create_audit,
            "get_audit_request": get_audit,
        })

        agent.client = Mock()
        agent.client.chat.completions.create.side_effect = [
            make_response([
                make_tool_call(
                    "create_audit_request",
                    {
                        "product_id": "SP001",
                        "reason": "Variance detected",
                    },
                    "call-create",
                )
            ], finish_reason="tool_calls"),
            make_response([
                make_tool_call(
                    "get_audit_request",
                    {"audit_id": audit_id},
                    "call-verify",
                )
            ], finish_reason="tool_calls"),
            make_response(
                content=f"Phiếu {audit_id} đã được xác minh."
            ),
        ]

        result = agent.run(
            "Tạo phiếu kiểm toán cho SP001"
        )

        self.assertTrue(result.success)
        create_audit.assert_called_once()
        get_audit.assert_called_once_with(audit_id=audit_id)


if __name__ == "__main__":
    unittest.main()
