"""MCP server công bố các công cụ kiểm toán tồn kho."""

from mcp.server import MCPServer

from tools.inventory_tools import InventoryTools


mcp = MCPServer("ai-inventory-auditor")
inventory_tools = InventoryTools()


@mcp.tool()
def get_stock_data(product_id: str) -> dict:
    """Lấy tồn kho dự kiến, số lượng kiểm đếm và độ lệch của một sản phẩm."""
    return inventory_tools.get_stock_data(product_id)


@mcp.tool()
def get_all_stock_data() -> list[dict]:
    """Lấy dữ liệu tồn kho của tất cả sản phẩm."""
    return inventory_tools.get_all_stock_data()


@mcp.tool()
def get_transactions(product_id: str) -> dict:
    """Liệt kê giao dịch của một sản phẩm kèm trạng thái (POSTED/DRAFT) và việc có được tính vào tồn kho."""
    return inventory_tools.get_transactions(product_id)


@mcp.tool()
def search_inventory_policy(
    query: str, top_k: int = 3, search_mode: str = "hybrid",
    min_score: float = 0.25,
) -> dict:
    """Tìm bằng chứng theo dense/hybrid; chỉ trả đoạn đạt min_score (0..1)."""
    return inventory_tools.search_inventory_policy(
        query, top_k=top_k, search_mode=search_mode, min_score=min_score
    )


@mcp.tool()
def create_audit_request(product_id: str, reason: str) -> dict:
    """Tạo phiếu kiểm toán nếu sản phẩm có chênh lệch tồn kho."""
    return inventory_tools.create_audit_request(product_id, reason)


@mcp.tool()
def get_audit_request(audit_id: str) -> dict:
    """Đọc lại phiếu kiểm toán theo mã để xác minh dữ liệu đã lưu."""
    return inventory_tools.get_audit_request(audit_id)


if __name__ == "__main__":
    # MCP dùng stdout làm kênh giao tiếp, vì vậy không in thông báo tại đây.
    mcp.run(transport="stdio")
