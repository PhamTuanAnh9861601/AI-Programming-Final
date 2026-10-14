
from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class AgentAction:
    """Hành động mà agent yêu cầu thực hiện."""

    action_type: Literal["tool_call", "final_answer"]
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None
    answer: str | None = None


@dataclass
class ToolResult:
    """Kết quả thực thi một tool."""

    tool_name: str
    success: bool
    output: str


@dataclass
class AgentResult:
    """Kết quả cuối cùng của một lượt chạy agent."""

    question: str
    answer: str
    steps: int
    success: bool
    tool_calls: int
