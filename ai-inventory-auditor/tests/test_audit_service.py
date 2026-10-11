
import unittest
from unittest.mock import Mock, patch

from business.audit_service import AuditService
from business.inventory_service import InventoryResult


def make_inventory_result(
    product_id,
    expected_stock,
    physical_count,
    variance,
    severity,
):
    return InventoryResult(
        product_id=product_id,
        product_name="San pham test",
        category="Sensor",
        opening_stock=100.0,
        total_in=0.0,
        total_out=0.0,
        expected_stock=expected_stock,
        physical_count=physical_count,
        variance=variance,
        severity=severity,
        unit="cai",
    )


class TestAuditService(unittest.TestCase):

    def setUp(self):
        # Mock các thành phần bên ngoài để không ghi vào database thật.
        self.inventory_patcher = patch(
            "business.audit_service.InventoryService"
        )
        self.repository_patcher = patch(
            "business.audit_service.AuditRepository"
        )

        self.mock_inventory_class = self.inventory_patcher.start()
        self.mock_repository_class = self.repository_patcher.start()

        self.addCleanup(self.inventory_patcher.stop)
        self.addCleanup(self.repository_patcher.stop)

        self.inventory = self.mock_inventory_class.return_value
        self.repository = self.mock_repository_class.return_value

        self.service = AuditService()

        self.repository.create.return_value = {
            "audit_id": "AUD-TEST001",
            "product_id": "SP001",
            "expected_stock": 85.0,
            "physical_count": 80.0,
            "variance": -5.0,
            "severity": "NORMAL",
            "status": "OPEN",
        }

    def test_discrepancy_creates_audit(self):
        self.inventory.get_stock_data.return_value = (
            make_inventory_result("SP001", 85, 80, -5, "NORMAL")
        )

        result = self.service.audit_product("SP001")

        self.assertTrue(result["audit_created"])
        self.assertEqual(result["audit"]["audit_id"], "AUD-TEST001")
        self.repository.create.assert_called_once()

    def test_no_discrepancy_does_not_create_audit(self):
        self.inventory.get_stock_data.return_value = (
            make_inventory_result("SP003", 75, 75, 0, "NONE")
        )

        result = self.service.audit_product("SP003")

        self.assertFalse(result["audit_created"])
        self.assertIsNone(result["audit"])
        self.repository.create.assert_not_called()

    def test_missing_physical_count_does_not_create_audit(self):
        self.inventory.get_stock_data.return_value = (
            make_inventory_result("SP004", 47, None, None, "UNKNOWN")
        )

        result = self.service.audit_product("SP004")

        self.assertFalse(result["audit_created"])
        self.assertIsNone(result["audit"])
        self.repository.create.assert_not_called()

    def test_unknown_product_error_is_propagated(self):
        self.inventory.get_stock_data.side_effect = ValueError(
            "Không tìm thấy sản phẩm"
        )

        with self.assertRaises(ValueError):
            self.service.audit_product("SP999")

        self.repository.create.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
