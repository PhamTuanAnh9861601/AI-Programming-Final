
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


class NegativeStockFlagTests(unittest.TestCase):
    def test_negative_expected_stock_is_flagged(self):
        service = InventoryService()
        flagged = service.get_stock_data("SP038")
        self.assertLess(flagged.expected_stock, 0)
        self.assertEqual(flagged.data_quality_flag, "NEGATIVE_EXPECTED_STOCK")

    def test_normal_product_has_no_flag(self):
        self.assertIsNone(InventoryService().get_stock_data("SP001").data_quality_flag)


class TransactionsToolTests(unittest.TestCase):
    def test_draft_transaction_is_listed_but_not_counted(self):
        rows = InventoryService().get_transactions("SP001")
        draft = [r for r in rows if r["status"] == "DRAFT"]
        self.assertEqual(len(draft), 1)
        self.assertFalse(draft[0]["counted_in_stock"])
        self.assertTrue(all(r["counted_in_stock"] for r in rows if r["status"] == "POSTED"))

    def test_unknown_product_raises(self):
        with self.assertRaises(ValueError):
            InventoryService().get_transactions("SP999")


class DataQualityNoteTests(unittest.TestCase):
    def test_note_only_present_for_flagged_product(self):
        from tools.inventory_tools import InventoryTools
        tools = InventoryTools()
        self.assertIn("data_quality_note", tools.get_stock_data("SP038"))
        self.assertNotIn("data_quality_note", tools.get_stock_data("SP001"))


class MinEvidenceAndNoteTests(unittest.TestCase):
    def test_transactions_note_only_for_negative_stock_product(self):
        from tools.inventory_tools import InventoryTools
        tools = InventoryTools()
        self.assertIn("data_quality_note", tools.get_transactions("SP038"))
        self.assertNotIn("data_quality_note", tools.get_transactions("SP001"))
