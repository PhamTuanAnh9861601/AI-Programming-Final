
import unittest

from business.inventory_service import InventoryService


class TestInventoryService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.service = InventoryService()

    def test_sp001_stock_and_variance(self):
        result = self.service.get_stock_data("SP001")

        self.assertEqual(result.expected_stock, 85)
        self.assertEqual(result.physical_count, 80)
        self.assertEqual(result.variance, -5)
        self.assertEqual(result.severity, "NORMAL")

    def test_sp002_stock_and_variance(self):
        result = self.service.get_stock_data("SP002")

        self.assertEqual(result.expected_stock, 55)
        self.assertEqual(result.variance, -3)
        self.assertEqual(result.severity, "NORMAL")

    def test_sp003_no_discrepancy(self):
        result = self.service.get_stock_data("SP003")

        self.assertEqual(result.expected_stock, 75)
        self.assertEqual(result.variance, 0)
        self.assertEqual(result.severity, "NONE")

    def test_sp004_missing_physical_count(self):
        result = self.service.get_stock_data("SP004")

        self.assertEqual(result.expected_stock, 47)
        self.assertIsNone(result.physical_count)
        self.assertIsNone(result.variance)
        self.assertEqual(result.severity, "UNKNOWN")

    def test_unknown_product(self):
        with self.assertRaises(ValueError):
            self.service.get_stock_data("SP999")


if __name__ == "__main__":
    unittest.main(verbosity=2)
