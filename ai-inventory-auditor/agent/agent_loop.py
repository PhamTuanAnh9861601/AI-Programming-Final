
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

    
    def _allows_audit_creation(self, question: str) -> bool:
        """Chỉ cho phép ghi database khi người dùng yêu cầu tạo phiếu rõ ràng."""
        text = question.lower().strip()

        # Các cách diễn đạt phủ định: không được phép ghi dữ liệu.
        negative_phrases = [
            "không tạo phiếu",
            "không lập phiếu",
            "đừng tạo phiếu",
            "chỉ kiểm tra",
            "chỉ xem",
            "không ghi dữ liệu",
        ]
        if any(phrase in text for phrase in negative_phrases):
            return False

        # Chỉ cấp quyền ghi khi có yêu cầu tạo/lập phiếu cụ thể.
        write_phrases = [
            "tạo phiếu kiểm toán",
            "lập phiếu kiểm toán",
            "tạo phiếu audit",
            "lập phiếu audit",
            "tạo yêu cầu kiểm toán",
            "lập yêu cầu kiểm toán",
            "create audit request",
        ]
        return any(phrase in text for phrase in write_phrases)


    
    def _execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        allow_write: bool = False,
    ) -> tuple[bool, str]:
        """Kiểm tra quyền rồi mới thực thi tool."""

        # Chặn ghi dữ liệu nếu người dùng không yêu cầu rõ ràng.
        if tool_name == "create_audit_request" and not allow_write:
            return False, (
                "Error: Không được tạo phiếu kiểm toán vì "
                "người dùng chưa yêu cầu tạo phiếu."
            )

        # Kiểm tra tool có tồn tại trong registry không.
        tool = self.tools.get(tool_name)

        if tool is None:
            return False, f"Error: Tool '{tool_name}' không tồn tại."

        # Thực thi tool và chuẩn hóa kết quả thành chuỗi.
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
        allow_write = self._allows_audit_creation(question)

        allowed_tools = [
            schema
            for schema in self.tool_schemas
            if allow_write
            or schema["function"]["name"] != "create_audit_request"
        ]

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": question},
        ]

        tool_calls_count = 0

        # Theo dõi trạng thái xác minh phiếu kiểm toán.
        pending_audit_id = None
        verified_audit_id = None

        for step in range(1, self.max_steps + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=allowed_tools,
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
                                allow_write=allow_write,
                            )
                    tool_calls_count += 1

                    # Theo dõi việc tạo phiếu kiểm toán.
                    if success and tool_name == "create_audit_request":
                        try:
                            payload = json.loads(output)
                            audit = payload.get("audit")
                    

                            if payload.get("success") is True and isinstance(audit, dict):
                                audit_id = audit.get("audit_id")

                                if isinstance(audit_id, str) and audit_id.strip():
                                    pending_audit_id = audit_id
                                    verified_audit_id = None
                        except (json.JSONDecodeError, AttributeError):
                            pass

                    # Chỉ xác nhận khi đọc lại đúng phiếu đang chờ.
                    elif success and tool_name == "get_audit_request":
                        try:
                            payload = json.loads(output)
                            audit = payload.get("audit")

                            if (
                                pending_audit_id is not None
                                and payload.get("success") is True
                                and isinstance(audit, dict)
                                and audit.get("audit_id") == pending_audit_id
                            ):
                                verified_audit_id = pending_audit_id
                        except (json.JSONDecodeError, AttributeError):
                            pass

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

            if (
                pending_audit_id is not None
                and verified_audit_id != pending_audit_id
            ):
                messages.append({
                    "role": "user",
                    "content": (
                        "Chưa xác minh được phiếu kiểm toán vừa tạo. "
                        f"Hãy gọi get_audit_request với audit_id="
                        f"{json.dumps(pending_audit_id)} để đọc lại đúng phiếu. "
                        "Không được tuyên bố phiếu đã được xác minh thành công."
                    ),
                })
                continue


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
