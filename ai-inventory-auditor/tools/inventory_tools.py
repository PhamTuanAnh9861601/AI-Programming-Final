
from typing import Any

from business.inventory_service import InventoryService
from business.audit_service import AuditService
from storage.audit_repository import AuditRepository


class InventoryTools:
    """Cung cấp các tool nghiệp vụ cho AI Agent."""

    def __init__(self):
        self.inventory_service = InventoryService()
        self.audit_service = AuditService()
        self.audit_repository = AuditRepository()

    def get_stock_data(self, product_id: str) -> dict[str, Any]:
        """Lấy dữ liệu tồn kho và độ lệch của một sản phẩm."""
        result = self.inventory_service.get_stock_data(product_id)

        if hasattr(result, "__dataclass_fields__"):
            return {
                field: getattr(result, field)
                for field in result.__dataclass_fields__
            }

        if isinstance(result, dict):
            return result

        raise TypeError(
            "InventoryService trả về kiểu dữ liệu không được hỗ trợ."
        )

    def get_all_stock_data(self) -> list[dict[str, Any]]:
        """Lấy dữ liệu tồn kho của tất cả sản phẩm."""
        results = self.inventory_service.get_all_stock_data()
        output = []

        for result in results:
            if hasattr(result, "__dataclass_fields__"):
                output.append({
                    field: getattr(result, field)
                    for field in result.__dataclass_fields__
                })
            elif isinstance(result, dict):
                output.append(result)
            else:
                raise TypeError(
                    "Có kết quả tồn kho không đúng kiểu dữ liệu."
                )

        return output

    def create_audit_request(
        self,
        product_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Tạo phiếu kiểm toán qua AuditService."""
        result = self.audit_service.audit_product(product_id)

        if not result.get("audit_created"):
            return {
                "success": False,
                "product_id": product_id,
                "message": result.get(
                    "message",
                    "Không tạo phiếu kiểm toán.",
                ),
            }

        audit = result.get("audit")
        if not audit:
            return {
                "success": False,
                "product_id": product_id,
                "message": (
                    "AuditService báo đã tạo phiếu nhưng "
                    "không trả về thông tin phiếu."
                ),
            }

        # Lý do được cung cấp bởi người gọi tool.
        # Không tự suy luận nguyên nhân chênh lệch.
        return {
            "success": True,
            "product_id": product_id,
            "reason": reason,
            "audit": audit,
            "message": "Đã yêu cầu tạo phiếu kiểm toán.",
        }

    def get_audit_request(
        self,
        audit_id: str,
    ) -> dict[str, Any]:
        """Đọc lại phiếu theo ID để xác minh dữ liệu đã lưu."""
        result = self.audit_repository.get_by_id(audit_id)

        if result is None:
            return {
                "success": False,
                "audit_id": audit_id,
                "message": "Không tìm thấy phiếu kiểm toán.",
            }

        if hasattr(result, "keys"):
            result = dict(result)

        return {
            "success": True,
            "audit": result,
            "message": "Đã đọc được phiếu kiểm toán từ storage.",
        }


def build_tool_registry(
    inventory_tools: InventoryTools | None = None,
):
    """Tạo registry ánh xạ tên tool sang hàm thực thi."""
    inventory_tools = inventory_tools or InventoryTools()

    return {
        "get_stock_data": inventory_tools.get_stock_data,
        "get_all_stock_data": inventory_tools.get_all_stock_data,
        "create_audit_request": inventory_tools.create_audit_request,
        "get_audit_request": inventory_tools.get_audit_request,
    }
