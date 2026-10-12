
from email.mime import message
import json
from pathlib import Path
from typing import Any, Callable

from groq import Groq

from config import (
    GROQ_API_KEY,
    MODEL,
    MAX_STEPS,
    API_TIMEOUT,
    MAX_RETRIES,
    SYSTEM_PROMPT_PATH,
)
from agent.schemas import AgentResult


ToolFunction = Callable[..., Any]


class AgentLoop:
    """Điều phối ReAct Agent sử dụng native tool calling của Groq."""

    def __init__(
        self,
        tools: dict[str, ToolFunction],
        client: Groq | None = None,
    ):
        if client is None and not GROQ_API_KEY:
            raise ValueError("Thiếu GROQ_API_KEY. Hãy kiểm tra file .env.")

        self.client = client or Groq(
            api_key=GROQ_API_KEY,
            timeout=API_TIMEOUT,
            max_retries=MAX_RETRIES,
        )
        self.tools = tools
        self.model = MODEL
        self.max_steps = MAX_STEPS

        prompt_path = Path(SYSTEM_PROMPT_PATH)
        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Không tìm thấy system prompt: {prompt_path}"
            )

        self.system_prompt = prompt_path.read_text(encoding="utf-8")

        # Schema native tool calling gửi cho Groq.
        self.tool_schemas = [
            {
                "type": "function",
                "function": {
                    "name": "get_stock_data",
                    "description": (
                        "Lấy dữ liệu tồn kho, tồn dự kiến và độ lệch "
                        "của một sản phẩm."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_id": {
                                "type": "string",
                                "description": "Mã sản phẩm, ví dụ SP001.",
                            }
                        },
                        "required": ["product_id"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_all_stock_data",
                    "description": "Lấy dữ liệu tồn kho của tất cả sản phẩm.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_audit_request",
                    "description": (
                        "Tạo phiếu kiểm toán cho sản phẩm khi đủ điều kiện."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_id": {
                                "type": "string",
                                "description": "Mã sản phẩm cần kiểm toán.",
                            },
                            "reason": {
                                "type": "string",
                                "description": "Lý do yêu cầu kiểm toán.",
                            },
                        },
                        "required": ["product_id", "reason"],
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_audit_request",
                    "description": (
                        "Đọc lại phiếu kiểm toán theo audit_id "
                        "để xác minh dữ liệu đã lưu."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "audit_id": {
                                "type": "string",
                                "description": "Mã phiếu kiểm toán.",
                            }
                        },
                        "required": ["audit_id"],
                        "additionalProperties": False,
                    },
                },
            },
        ]

        # Chỉ công bố schema cho tool thực sự có trong registry.
        self.tool_schemas = [
            schema
            for schema in self.tool_schemas
            if schema["function"]["name"] in self.tools
        ]

    def _execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> tuple[bool, str]:
        """Kiểm tra registry rồi thực thi tool."""
        tool = self.tools.get(tool_name)

        if tool is None:
            return False, f"Error: Tool '{tool_name}' không tồn tại."

        try:
            result = tool(**arguments)

            if isinstance(result, str):
                output = result
            else:
                output = json.dumps(
                    result,
                    ensure_ascii=False,
                    default=str,
                )

            return True, output

        except Exception as exc:
            return False, f"Error: {type(exc).__name__}: {exc}"

    def run(self, question: str) -> AgentResult:
        """Chạy vòng lặp ReAct cho một câu hỏi."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": question},
        ]

        tool_calls_count = 0

        for step in range(1, self.max_steps + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=self.tool_schemas,
                    tool_choice="auto",
                    temperature=0,
                )
            except Exception as exc:
                return AgentResult(
                    question=question,
                    answer=f"Lỗi khi gọi Groq API: {exc}",
                    steps=step,
                    success=False,
                    tool_calls=tool_calls_count,
                )

            message = response.choices[0].message
            finish_reason = response.choices[0].finish_reason
            # Ghi log để debug, có thể tắt nếu muốn.
            print(f"\n[STEP {step}] Groq đã phản hồi.")

            if message.tool_calls:
                for call in message.tool_calls:
                    print(f"[TOOL CALL] {call.function.name}")
                    print(f"[ARGUMENTS] {call.function.arguments}")
            else:
                print("[FINAL ANSWER]")
                print(message.content or "")

            # Có yêu cầu gọi tool: thực thi từng tool được model đề xuất.
            if message.tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": [
                            call.model_dump(exclude_none=True)
                            for call in message.tool_calls
                        ],
                    }
                )

                for call in message.tool_calls:
                    tool_name = call.function.name

                    try:
                        arguments = json.loads(call.function.arguments or "{}")
                    except json.JSONDecodeError:
                        success = False
                        output = "Error: Tham số tool không phải JSON hợp lệ."
                    else:
                        if not isinstance(arguments, dict):
                            success = False
                            output = "Error: Tham số tool phải là JSON object."
                        else:
                            success, output = self._execute_tool(
                                tool_name,
                                arguments,
                            )

                    tool_calls_count += 1

                    # Kết quả phải gắn với đúng tool_call_id.
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps(
                                {
                                    "success": success,
                                    "output": output,
                                },
                                ensure_ascii=False,
                            ),
                        }
                    )

                # Gọi LLM lại để xử lý kết quả tool.
                continue

            # Không có tool call: đọc câu trả lời cuối cùng.
            content = message.content or ""

            if content.strip() and finish_reason == "stop":
                return AgentResult(
                    question=question,
                    answer=content.strip(),
                    steps=step,
                    success=True,
                    tool_calls=tool_calls_count,
                )

            return AgentResult(
                question=question,
                answer=(
                    "Model không trả về câu trả lời cuối cùng hợp lệ. "
                    f"finish_reason={finish_reason}"
                ),
                steps=step,
                success=False,
                tool_calls=tool_calls_count,
            )

        return AgentResult(
            question=question,
            answer=(
                f"Agent đã đạt giới hạn {self.max_steps} bước "
                "mà chưa hoàn thành yêu cầu."
            ),
            steps=self.max_steps,
            success=False,
            tool_calls=tool_calls_count,
        )
