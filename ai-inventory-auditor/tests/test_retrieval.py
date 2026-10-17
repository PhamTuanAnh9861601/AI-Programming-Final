import hashlib
import importlib.util
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from retrieval.document_store import Document, DocumentStore, chunk_document_by_lines
from retrieval.rag_pipeline import current_doc_ids


class FakeModel:
    """Embedding băm theo từ: đủ để kiểm tra đường đi mã nguồn, không phải chất lượng thật."""

    def encode(self, text, convert_to_numpy=True):
        import numpy as np

        def vec(value):
            v = np.zeros(128)
            for word in re.findall(r"\w+", value.lower()):
                v[int(hashlib.md5(word.encode()).hexdigest(), 16) % 128] += 1
            norm = np.linalg.norm(v)
            return v / norm if norm else v

        return np.array([vec(t) for t in text]) if isinstance(text, list) else vec(text)


class LineChunkingTests(unittest.TestCase):
    def test_one_chunk_per_non_empty_line(self):
        doc = Document(content="1. Quy tắc một.\n\n2. Quy tắc hai về audit_id.\n", doc_id="D1", title="T")
        chunks = chunk_document_by_lines(doc)
        self.assertEqual([c.content for c in chunks], ["1. Quy tắc một.", "2. Quy tắc hai về audit_id."])
        self.assertEqual(chunks[1].metadata["line_number"], 3)

    def test_real_corpus_has_no_chunk_cut_mid_word(self):
        store = DocumentStore.from_directory(Path("data/documents"))
        for document in store.list_all():
            body_lines = {line.strip() for line in document.content.splitlines() if line.strip()}
            chunk_texts = {chunk.content for chunk in store.get_chunks_by_doc(document.doc_id)}
            self.assertEqual(chunk_texts, body_lines, document.doc_id)  # mỗi đoạn là một dòng nguyên vẹn

    def test_fixed_mode_still_available_and_invalid_mode_rejected(self):
        fixed = DocumentStore.from_directory(Path("data/documents"), chunk_mode="fixed")
        line = DocumentStore.from_directory(Path("data/documents"), chunk_mode="line")
        self.assertNotEqual(len(fixed.chunks), len(line.chunks))
        with self.assertRaises(ValueError):
            DocumentStore(chunk_mode="bad").add(Document(content="x", doc_id="X"))


class CurrentVersionTests(unittest.TestCase):
    def test_keeps_latest_version_per_title(self):
        store = DocumentStore()
        store.add(Document(content="a", doc_id="OLD", title="Chính sách", metadata={"date": "2026-01-01"}))
        store.add(Document(content="b", doc_id="NEW", title="chính sách", metadata={"date": "2026-10-01"}))
        store.add(Document(content="c", doc_id="OTHER", title="Khác", metadata={"date": "2026-02-01"}))
        self.assertEqual(sorted(current_doc_ids(store)), ["NEW", "OTHER"])


class RetrievalEvalTests(unittest.TestCase):
    def test_eval_runs_all_four_configurations(self):
        from evaluation.eval_retrieval import evaluate_retrieval

        with patch("retrieval.vector_store._load_embedding_model", lambda name: FakeModel()):
            report = evaluate_retrieval(model_name="fake", k_values=(3, 5))
        self.assertEqual(len(report["rows"]), 4)
        for row in report["rows"]:
            self.assertGreater(row["cases"], 5)
            self.assertIn("hit@5", row)
            self.assertIn("mrr", row)
        self.assertIsNotNone(report["rows"][0]["no_answer_max_top1"])


@unittest.skipUnless(importlib.util.find_spec("mcp"), "cần cài mcp")
class SecondClientTests(unittest.TestCase):
    def test_raw_jsonrpc_client_discovers_tools_and_stdout_is_clean(self):
        from mcp_server.second_client import run

        report = run(timeout=90)
        self.assertTrue(report["stdout_clean"], report["bad_lines"])
        self.assertIn("get_stock_data", report["tools"])
        self.assertIn("search_inventory_policy", report["tools"])
        self.assertFalse(report["tool_is_error"])
        self.assertIn("85", str(report["tool_result"]))


if __name__ == "__main__":
    unittest.main()
