import unittest
from evaluation.metrics import citation_doc_ids, faithfulness_proxy

class TestEvidenceMetrics(unittest.TestCase):
    def test_extracts_unique_document_ids(self):
        self.assertEqual(citation_doc_ids("[doc_id=INV-DOC-002] and INV-DOC-002"), ["INV-DOC-002"])

    def test_faithfulness_proxy_requires_sentence_citation(self):
        self.assertEqual(faithfulness_proxy("This supported statement has citation [doc_id=INV-DOC-002]. This unsupported statement has no citation."), 0.5)

if __name__ == "__main__":
    unittest.main()


class UnicodeHyphenTests(unittest.TestCase):
    def test_non_breaking_hyphen_doc_id_is_recognised(self):
        from evaluation.metrics import citation_doc_ids
        self.assertEqual(citation_doc_ids("[doc_id=INV\u2011DOC\u2011011, version=1.0]"), ["INV-DOC-011"])
