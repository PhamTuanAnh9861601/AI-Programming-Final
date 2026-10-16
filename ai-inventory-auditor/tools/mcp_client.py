"""MCP client đồng bộ để AgentLoop gọi các tool qua server chạy bằng stdio."""

from __future__ import annotations

import asyncio
import json
import sys
import threading
from concurrent.futures import Future, TimeoutError
from pathlib import Path
from typing import Any

from mcp import Client, StdioServerParameters


class MCPClient:
    """Duy trì kết nối MCP và cung cấp adapter đồng bộ cho AgentLoop."""

    def __init__(self, project_root: str | Path | None = None):
        self.project_root = Path(
            project_root or Path(__file__).resolve().parents[1]
        ).resolve()
        self.server_parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_server.server"],
            cwd=str(self.project_root),
        )
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._loop_ready = threading.Event()
        self._client: Client | None = None
        self._tools: list[Any] = []

    def __enter__(self) -> "MCPClient":
        self._thread = threading.Thread(
            target=self._run_event_loop,
            name="inventory-mcp-client",
            daemon=True,
        )
        self._thread.start()
        if not self._loop_ready.wait(timeout=10):
            raise TimeoutError("Không khởi tạo được event loop cho MCP client.")

        try:
            self._submit(self._connect()).result(timeout=60)
        except Exception:
            self.close()
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def _run_event_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._loop_ready.set()
        loop.run_forever()

        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()

    def _submit(self, coroutine) -> Future:
        if self._loop is None or not self._loop.is_running():
            raise RuntimeError("MCP client chưa được kết nối.")
        return asyncio.run_coroutine_threadsafe(coroutine, self._loop)

    async def _connect(self) -> None:
        self._client = Client(self.server_parameters)
        await self._client.__aenter__()
        listing = await self._client.list_tools()
        self._tools = list(listing.tools)

    @property
    def available_tools(self) -> list[str]:
        """Tên các tool mà MCP server đã công bố."""
        return [tool.name for tool in self._tools]

    def get_groq_tool_schemas(self) -> list[dict[str, Any]]:
        """Chuyển schema MCP đã khám phá sang schema function của Groq."""
        if self._client is None:
            raise RuntimeError("Hãy kết nối MCP client trước khi lấy schema.")

        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or tool.name,
                    "parameters": tool.input_schema,
                },
            }
            for tool in self._tools
        ]

    def build_tool_registry(self) -> dict[str, Any]:
        """Tạo registry các hàm đồng bộ để AgentLoop gọi qua MCP."""
        if self._client is None:
            raise RuntimeError("Hãy kết nối MCP client trước khi tạo registry.")

        return {
            tool.name: self._make_tool_adapter(tool.name)
            for tool in self._tools
        }

    def _make_tool_adapter(self, tool_name: str):
        def call_tool(**arguments):
            return self.call_tool(tool_name, arguments)

        return call_tool

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Gọi một tool đã được khám phá và trả kết quả dạng Python."""
        if tool_name not in self.available_tools:
            raise ValueError(f"MCP server không có tool '{tool_name}'.")
        result = self._submit(
            self._client.call_tool(tool_name, arguments)
        ).result(timeout=120)

        text_blocks = [
            block.text
            for block in result.content
            if isinstance(getattr(block, "text", None), str)
        ]
        if result.is_error:
            raise RuntimeError("\n".join(text_blocks) or "MCP tool báo lỗi.")

        if result.structured_content is not None:
            return result.structured_content
        if not text_blocks:
            return None

        text = "\n".join(text_blocks)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def close(self) -> None:
        """Đóng kết nối MCP và dừng event loop nền."""
        if self._client is not None and self._loop is not None:
            try:
                self._submit(self._client.__aexit__(None, None, None)).result(
                    timeout=10
                )
            except Exception:
                pass
            self._client = None

        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=10)
        self._loop = None
        self._thread = None
