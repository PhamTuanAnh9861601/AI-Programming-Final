
from dataclasses import asdict

from business.inventory_service import InventoryService
from storage.audit_repository import AuditRepository


class AuditService:
    def __init__(self):
        self.inventory_service = InventoryService()
        self.audit_repository = AuditRepository()

    def audit_product(self, product_id: str) -> dict:
        """Kiểm tra tồn kho và tạo phiếu nếu có chênh lệch."""

        # 1. Tính tồn kho từ dữ liệu CSV.
        inventory = self.inventory_service.get_stock_data(product_id)

        result = {
            "inventory": asdict(inventory),
            "audit_created": False,
            "audit": None,
            "message": "",
        }

        # 2. Chưa kiểm đếm thực tế thì chưa thể xác định sai lệch.
        if inventory.physical_count is None:
            result["message"] = (
                "Chưa có số liệu kiểm đếm thực tế. "
                "Không tạo phiếu kiểm kê."
            )
            return result

        # 3. Không tạo phiếu nếu tồn kho thực tế khớp dự kiến.
        if inventory.variance == 0:
            result["message"] = (
                "Tồn kho thực tế khớp với tồn kho dự kiến. "
                "Không cần tạo phiếu."
            )
            return result

        # 4. Có chênh lệch: tạo phiếu.
        audit = self.audit_repository.create(
            product_id=inventory.product_id,
            expected_stock=inventory.expected_stock,
            physical_count=inventory.physical_count,
            variance=inventory.variance,
            severity=inventory.severity,
            reason=(
                f"Chênh lệch tồn kho: {inventory.variance:g} "
                f"{inventory.unit}."
            ),
        )

        # Repository đã đọc lại phiếu sau khi ghi.
        result["audit_created"] = True
        result["audit"] = audit
        result["message"] = (
            "Đã tạo phiếu và đọc lại dữ liệu để xác minh."
        )

        return result


if __name__ == "__main__":
    service = AuditService()

    for product_id in ["SP001", "SP003", "SP004"]:
        print(f"\n{'=' * 15} {product_id} {'=' * 15}")

        try:
            result = service.audit_product(product_id)
            print("Thông báo:", result["message"])
            print("Đã tạo phiếu:", result["audit_created"])

            if result["audit"] is not None:
                print("Phiếu:", result["audit"])

        except (ValueError, FileNotFoundError, RuntimeError) as exc:
            print("Lỗi:", exc)
