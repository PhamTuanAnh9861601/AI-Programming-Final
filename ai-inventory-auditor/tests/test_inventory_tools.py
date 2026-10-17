import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from tools.inventory_tools import InventoryTools


class TestInventoryPolicyTool(unittest.TestCase):
    def setUp(self):
        self.tools = InventoryTools()
        self.tools.rag_pipeline = Mock()
        self.tools.rag_pipeline.retrieve.return_value = [
            SimpleNamespace(
                doc_id="INV-DOC-001", title="Chính sách", chunk_id="old",
                score=0.8, content="Bản cũ", metadata={"version": "1.0", "date": "2026-08-01"},
            ),
            SimpleNamespace(
                doc_id="INV-DOC-002", title="Chính sách", chunk_id="new",
                score=0.9, content="Bản mới", metadata={"version": "2.0", "date": "2026-10-01"},
            ),
        ]

    def test_keeps_conflicting_versions_and_passes_retrieval_threshold(self):
        result = self.tools.search_inventory_policy(
            "so sánh hai phiên bản", top_k=3, search_mode="hybrid", min_score=0.6
        )

        self.tools.rag_pipeline.retrieve.assert_called_once_with(
            "so sánh hai phiên bản", top_k=3, search_mode="hybrid", min_score=0.6
        )
        self.assertEqual(result["doc_ids"], ["INV-DOC-001", "INV-DOC-002"])
        self.assertEqual([item["version"] for item in result["evidence"]], ["1.0", "2.0"])

    def test_rejects_invalid_threshold(self):
        with self.assertRaises(ValueError):
            self.tools.search_inventory_policy("query", min_score=1.1)
        self.tools.rag_pipeline.retrieve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
