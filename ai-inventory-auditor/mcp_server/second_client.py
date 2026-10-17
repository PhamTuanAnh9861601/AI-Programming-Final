"""Client MCP thứ hai, KHÔNG dùng mcp SDK: chứng minh server dùng được từ host khác.

Nói chuyện JSON-RPC thô qua stdio (mỗi thông điệp một dòng), tự khám phá danh sách
tool, gọi thử một tool và kiểm tra stdout của server chỉ chứa JSON-RPC (stdout sạch).

Chạy: python -m mcp_server.second_client
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_VERSION = "2025-06-18"


def run(tool_name: str = "get_stock_data", arguments: dict[str, Any] | None = None, timeout: float = 60) -> dict:
    arguments = arguments or {"product_id": "SP001"}
    env = {**os.environ, "MCP_WARMUP": "0", "PYTHONIOENCODING": "utf-8"}
    process = subprocess.Popen(
        [sys.executable, "-m", "mcp_server.server"],
        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, encoding="utf-8", env=env, bufsize=1,
    )
    lines: "queue.Queue[str | None]" = queue.Queue()

    def reader() -> None:
        for line in process.stdout:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=reader, daemon=True).start()
    report = {"stdout_clean": True, "bad_lines": [], "messages": 0, "tools": [], "tool_result": None}

    def send(message: dict) -> None:
        process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        process.stdin.flush()

    def receive(expected_id: int) -> dict:
        while True:
            line = lines.get(timeout=timeout)
            if line is None:
                raise RuntimeError("Server đã đóng stdout trước khi trả lời.")
            try:
                message = json.loads(line)
                if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
                    raise ValueError("không phải thông điệp JSON-RPC 2.0")
            except ValueError:
                report["stdout_clean"] = False
                report["bad_lines"].append(line.strip()[:200])
                continue
            report["messages"] += 1
            if message.get("id") == expected_id:
                return message

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "second-client", "version": "0.1"}}})
        receive(1)
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        listing = receive(2)
        report["tools"] = [tool["name"] for tool in listing["result"]["tools"]]
        send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
              "params": {"name": tool_name, "arguments": arguments}})
        call = receive(3)
        result = call.get("result", {})
        report["tool_is_error"] = bool(result.get("isError"))
        report["tool_result"] = result.get("structuredContent") or result.get("content")
    finally:
        try:
            process.stdin.close()
            process.wait(timeout=10)
        except Exception:
            process.kill()
        finally:
            if process.stdout:
                process.stdout.close()
    return report


def main() -> None:
    report = run()
    print("Tool khám phá được:", ", ".join(report["tools"]))
    print("Kết quả get_stock_data(SP001):", json.dumps(report["tool_result"], ensure_ascii=False)[:300])
    print("stdout sạch (chỉ JSON-RPC):", "ĐÚNG" if report["stdout_clean"] else f"SAI -> {report['bad_lines']}")
    sys.exit(0 if report["stdout_clean"] and not report.get("tool_is_error") else 1)


if __name__ == "__main__":
    main()
