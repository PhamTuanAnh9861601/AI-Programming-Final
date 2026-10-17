"""MCP server công bố các công cụ kiểm toán tồn kho."""

import os
import sys
import threading

from mcp.server import MCPServer

from tools.inventory_tools import InventoryTools


mcp = MCPServer("ai-inventory-auditor")
inventory_tools = InventoryTools()


@mcp.tool()
def get_stock_data(product_id: str) -> dict:
    """Lấy tồn kho dự kiến (đầu kỳ + nhập POSTED - xuất POSTED), số kiểm đếm, độ lệch và mức ưu tiên của MỘT sản phẩm theo mã (vd SP001). Có data_quality_flag nếu tồn dự kiến âm."""
    return inventory_tools.get_stock_data(product_id)


@mcp.tool()
def get_all_stock_data() -> list[dict]:
    """Lấy dữ liệu tồn kho của TẤT CẢ sản phẩm; chỉ dùng khi cần tổng quan nhiều sản phẩm."""
    return inventory_tools.get_all_stock_data()


@mcp.tool()
def get_transactions(product_id: str) -> dict:
    """Liệt kê giao dịch của một sản phẩm kèm trạng thái (POSTED/DRAFT) và việc có được tính vào tồn kho."""
    return inventory_tools.get_transactions(product_id)


@mcp.tool()
def search_inventory_policy(query: str, top_k: int = 5) -> dict:
    """Tra cứu chính sách/quy trình kho; trả bằng chứng gồm doc_id, version, date, content. Viết truy vấn tiếng Việt bám thuật ngữ quy tắc (vd 'không có physical_count thì có tạo phiếu không'), không chỉ gõ mã sản phẩm. evidence_count = 0 nghĩa là tài liệu không có thông tin đó."""
    return inventory_tools.search_inventory_policy(query, top_k=top_k)


@mcp.tool()
def create_audit_request(product_id: str, reason: str) -> dict:
    """GHI DỮ LIỆU: tạo phiếu kiểm toán cho sản phẩm có chênh lệch. Chỉ gọi khi người dùng yêu cầu rõ ràng; sau đó phải gọi get_audit_request với audit_id vừa nhận để xác minh."""
    return inventory_tools.create_audit_request(product_id, reason)


@mcp.tool()
def get_audit_request(audit_id: str) -> dict:
    """Đọc lại phiếu kiểm toán theo audit_id để xác minh dữ liệu đã lưu. Chỉ dùng audit_id có trong câu hỏi hoặc kết quả create_audit_request."""
    return inventory_tools.get_audit_request(audit_id)


def _warm_up_in_background() -> None:
    """Nạp sẵn mô hình embedding để câu hỏi tra cứu đầu tiên không bị chậm."""
    try:
        inventory_tools.warm_up()
    except Exception as exc:  # nạp lỗi thì để lần gọi tool đầu tiên báo lỗi rõ ràng
        print(f"[warm-up] bỏ qua: {exc}", file=sys.stderr)


if __name__ == "__main__":
    # MCP dùng stdout làm kênh giao tiếp, vì vậy chỉ ghi log ra stderr.
    if os.getenv("MCP_WARMUP", "1") != "0":
        threading.Thread(target=_warm_up_in_background, daemon=True).start()
    mcp.run(transport="stdio")
