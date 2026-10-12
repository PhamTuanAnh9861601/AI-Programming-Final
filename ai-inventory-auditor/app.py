
from tools.inventory_tools import build_tool_registry
from agent.agent_loop import AgentLoop


def main():
    # 1. Đăng ký các tool nghiệp vụ
    tools = build_tool_registry()

    # 2. Khởi tạo Agent với registry
    agent = AgentLoop(tools=tools)

    # 3. Nhận câu hỏi từ người dùng
    question = input("Nhập câu hỏi kiểm toán tồn kho: ").strip()

    if not question:
        print("Vui lòng nhập câu hỏi.")
        return

    # 4. Chạy vòng lặp ReAct
    result = agent.run(question)

    # 5. Hiển thị kết quả
    print("\n===== KẾT QUẢ AGENT =====")
    print(result.answer)
    print(f"Số bước: {result.steps}")
    print(f"Số lần gọi tool: {result.tool_calls}")
    print(f"Thành công: {result.success}")


if __name__ == "__main__":
    main()
