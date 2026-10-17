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


class EmptyAnswerRetryTests(unittest.TestCase):
    def test_retries_once_when_model_returns_empty_content(self):
        agent = make_agent(tools={})
        empty = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="", tool_calls=None), finish_reason="stop")],
            usage=None,
        )
        final = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Trả lời cuối.", tool_calls=None), finish_reason="stop")],
            usage=None,
        )
        agent.client = Mock()
        agent.client.chat.completions.create.side_effect = [empty, final]
        result = agent.run("Câu hỏi thử")
        self.assertTrue(result.success)
        self.assertEqual(result.answer, "Trả lời cuối.")
        self.assertEqual(agent.client.chat.completions.create.call_count, 2)


class NoToolNudgeTests(unittest.TestCase):
    def test_nudges_once_when_answering_without_any_tool(self):
        agent = make_agent(tools={"get_stock_data": Mock(return_value={"ok": 1})})
        def reply(content, tool_calls=None):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls), finish_reason="stop")],
                usage=None,
            )
        agent.client = Mock()
        agent.client.chat.completions.create.side_effect = [
            reply("Trả lời bịa không dùng tool."),
            reply(None, [make_tool_call("get_stock_data", {"product_id": "SP001"})]),
            reply("Trả lời có dùng tool."),
        ]
        result = agent.run("Câu hỏi thử")
        self.assertEqual(result.answer, "Trả lời có dùng tool.")
        self.assertEqual(result.tool_calls, 1)


def _reply(content, tool_calls=None):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls), finish_reason="stop")],
        usage=None,
    )


class RateLimitRetryTests(unittest.TestCase):
    def test_retries_after_429_then_succeeds(self):
        from unittest.mock import patch
        agent = make_agent(tools={"get_stock_data": Mock(return_value={"ok": 1})})
        agent.client = Mock()
        agent.client.chat.completions.create.side_effect = [
            Exception("Error code: 429 - Rate limit reached ... Please try again in 15ms."),
            _reply(None, [make_tool_call("get_stock_data", {"product_id": "SP001"})]),
            _reply("Xong."),
        ]
        with patch("agent.agent_loop.time.sleep") as fake_sleep:
            result = agent.run("Câu hỏi thử")
        self.assertTrue(result.success)
        self.assertEqual(result.answer, "Xong.")
        fake_sleep.assert_called_once()

    def test_gives_up_after_max_retries(self):
        from unittest.mock import patch
        agent = make_agent(tools={"get_stock_data": Mock()})
        agent.client = Mock()
        agent.client.chat.completions.create.side_effect = Exception("Error code: 429 rate_limit_exceeded try again in 1s")
        with patch("agent.agent_loop.time.sleep"):
            result = agent.run("Câu hỏi thử")
        self.assertFalse(result.success)


class SearchCapTests(unittest.TestCase):
    def test_fourth_search_is_refused_with_error_string(self):
        search = Mock(return_value={"doc_ids": []})
        agent = make_agent(tools={"search_inventory_policy": search})
        agent.tool_schemas = [{
            "type": "function",
            "function": {"name": "search_inventory_policy", "description": "t",
                         "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
        }]
        agent.max_steps = 8
        agent.client = Mock()
        agent.client.chat.completions.create.side_effect = [
            *[_reply(None, [make_tool_call("search_inventory_policy", {"query": f"q{i}"}, call_id=f"c{i}")]) for i in range(4)],
            _reply("Không tìm thấy trong tài liệu."),
        ]
        result = agent.run("Câu hỏi thử")
        self.assertEqual(search.call_count, 3)
        self.assertEqual(result.answer, "Không tìm thấy trong tài liệu.")


def _search_schema():
    return [{
        "type": "function",
        "function": {"name": "search_inventory_policy", "description": "t",
                     "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
    }]


class AnswerGuardTests(unittest.TestCase):
    def test_nudges_for_review_when_negative_stock_answer_omits_it(self):
        agent = make_agent(tools={"get_stock_data": Mock(return_value={"data_quality_flag": "NEGATIVE_EXPECTED_STOCK"})})
        agent.client = Mock()
        agent.client.chat.completions.create.side_effect = [
            _reply(None, [make_tool_call("get_stock_data", {"product_id": "SP038"}, call_id="a1")]),
            _reply("SP038 âm do giao dịch TX1."),
            _reply("Tồn âm là bất thường dữ liệu, cần rà soát theo INV-DOC-011."),
        ]
        result = agent.run("SP038 âm vì sao?")
        self.assertIn("rà soát", result.answer)
        self.assertEqual(agent.client.chat.completions.create.call_count, 3)

    def test_nudges_for_citation_when_evidence_found_but_not_cited(self):
        search = Mock(return_value={"evidence_count": 2, "doc_ids": ["INV-DOC-006"]})
        agent = make_agent(tools={"search_inventory_policy": search})
        agent.tool_schemas = _search_schema()
        agent.client = Mock()
        agent.client.chat.completions.create.side_effect = [
            _reply(None, [make_tool_call("search_inventory_policy", {"query": "q"}, call_id="b1")]),
            _reply("Đọc lại bằng audit_id."),
            _reply("Đọc lại bằng audit_id [doc_id=INV-DOC-006, version=1.0, date=2026-09-01]."),
        ]
        result = agent.run("Sau khi tạo phiếu làm gì?")
        self.assertIn("doc_id=INV-DOC-006", result.answer)
        self.assertEqual(agent.client.chat.completions.create.call_count, 3)

    def test_no_citation_nudge_when_search_returned_nothing(self):
        search = Mock(return_value={"evidence_count": 0, "doc_ids": []})
        agent = make_agent(tools={"search_inventory_policy": search})
        agent.tool_schemas = _search_schema()
        agent.client = Mock()
        agent.client.chat.completions.create.side_effect = [
            _reply(None, [make_tool_call("search_inventory_policy", {"query": "q"}, call_id="c1")]),
            _reply("Chưa có thông tin về việc này."),
        ]
        result = agent.run("Giá bán là bao nhiêu?")
        self.assertEqual(result.answer, "Chưa có thông tin về việc này.")
        self.assertEqual(agent.client.chat.completions.create.call_count, 2)


class DailyLimitTests(unittest.TestCase):
    def test_daily_token_limit_is_not_retried(self):
        from unittest.mock import patch
        agent = make_agent(tools={"get_stock_data": Mock()})
        agent.client = Mock()
        agent.client.chat.completions.create.side_effect = Exception(
            "Error code: 429 - Rate limit reached ... on tokens per day (TPD): Limit 200000 ... try again in 2m43s"
        )
        with patch("agent.agent_loop.time.sleep") as fake_sleep:
            result = agent.run("Câu hỏi thử")
        self.assertFalse(result.success)
        self.assertEqual(agent.client.chat.completions.create.call_count, 1)
        fake_sleep.assert_not_called()
