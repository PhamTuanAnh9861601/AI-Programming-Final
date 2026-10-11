
from uuid import uuid4

from storage.database import get_connection, init_database


class AuditRepository:
    def create(
        self,
        product_id: str,
        expected_stock: float,
        physical_count: float,
        variance: float,
        severity: str,
        reason: str,
    ) -> dict:
        """Lưu phiếu kiểm kê và trả về phiếu vừa tạo."""
        init_database()

        audit_id = f"AUD-{uuid4().hex[:8].upper()}"

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO audit_requests (
                    audit_id,
                    product_id,
                    expected_stock,
                    physical_count,
                    variance,
                    severity,
                    reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    product_id,
                    expected_stock,
                    physical_count,
                    variance,
                    severity,
                    reason,
                ),
            )

        # Đọc lại từ database để xác minh dữ liệu thực sự đã lưu.
        saved_audit = self.get_by_id(audit_id)

        if saved_audit is None:
            raise RuntimeError(
                f"Không xác minh được phiếu vừa tạo: {audit_id}"
            )

        return saved_audit

    def get_by_id(self, audit_id: str) -> dict | None:
        """Tìm phiếu theo mã phiếu."""
        init_database()

        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM audit_requests
                WHERE audit_id = ?
                """,
                (audit_id,),
            ).fetchone()

        return dict(row) if row else None


if __name__ == "__main__":
    repository = AuditRepository()

    audit = repository.create(
        product_id="SP001",
        expected_stock=85,
        physical_count=80,
        variance=-5,
        severity="NORMAL",
        reason="Kiểm thử chức năng lưu và đọc lại phiếu.",
    )

    print("Phiếu đã được lưu và đọc lại:")
    print(audit)
