
from agent.agent_loop import AgentLoop
from tools.mcp_client import MCPClient


def main():
    # 1. Nhận câu hỏi từ người dùng
    question = input("Nhập câu hỏi kiểm toán tồn kho: ").strip()

    if not question:
        print("Vui lòng nhập câu hỏi.")
        return

    # 2. Kết nối MCP server, khám phá tool và chuyển sang Agent.
    try:
        with MCPClient() as mcp_client:
            print(
                "Đã kết nối MCP. Tool khả dụng: "
                + ", ".join(mcp_client.available_tools)
            )
            agent = AgentLoop(
                tools=mcp_client.build_tool_registry(),
                tool_schemas=mcp_client.get_groq_tool_schemas(),
            )

            # 3. Chạy vòng lặp ReAct
            result = agent.run(question)
    except Exception as exc:
        print(f"Không thể khởi chạy MCP client/server: {exc}")
        return

    # 4. Hiển thị kết quả
    print("\n===== KẾT QUẢ AGENT =====")
    print(result.answer)
    print(f"Số bước: {result.steps}")
    print(f"Số lần gọi tool: {result.tool_calls}")
    print(f"Thành công: {result.success}")


if __name__ == "__main__":
    main()
