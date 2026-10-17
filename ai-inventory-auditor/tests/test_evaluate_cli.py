import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation import evaluate


CASES = [{"id": f"Q0{i}"} for i in range(1, 6)]


class SelectCasesTests(unittest.TestCase):
    def test_no_filter_runs_everything(self):
        selected, full = evaluate.select_cases(CASES)
        self.assertTrue(full)
        self.assertEqual(len(selected), 5)

    def test_only_selects_given_ids_case_insensitively(self):
        selected, full = evaluate.select_cases(CASES, only=["q02", "Q04"])
        self.assertFalse(full)
        self.assertEqual([c["id"] for c in selected], ["Q02", "Q04"])

    def test_failed_uses_previous_failed_and_error_only(self):
        previous = {"results": [
            {"id": "Q01", "status": "PASSED"},
            {"id": "Q02", "status": "FAILED"},
            {"id": "Q03", "status": "ERROR"},
            {"id": "Q04", "status": "SKIPPED"},
        ]}
        selected, full = evaluate.select_cases(CASES, failed=True, previous=previous)
        self.assertFalse(full)
        self.assertEqual([c["id"] for c in selected], ["Q02", "Q03"])


class SummaryAndRegradeTests(unittest.TestCase):
    def test_build_summary_counts_by_status(self):
        results = [
            {"id": "Q01", "status": "PASSED", "faithfulness_proxy": 1.0},
            {"id": "Q02", "status": "FAILED", "faithfulness_proxy": 0.0},
            {"id": "Q03", "status": "ERROR"},
        ]
        summary = evaluate.build_summary(results, 3)
        self.assertEqual((summary["passed"], summary["failed"], summary["errors"], summary["run"]), (1, 1, 1, 2))
        self.assertEqual(summary["pass_rate_on_run"], 50.0)
        self.assertEqual(summary["mean_faithfulness_proxy"], 0.5)

    def test_regrade_does_not_call_api_and_keeps_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            result_path = Path(tmp) / "results.json"
            regraded_path = Path(tmp) / "results_regraded.json"
            result_path.write_text(json.dumps({"total": 2, "results": [
                {"id": "Q05", "status": "FAILED", "answer": "SP006 có expected_stock 74.0 và variance -17.0."},
                {"id": "Q14", "status": "ERROR", "answer": None},
            ]}), encoding="utf-8")
            cases = evaluate.load_testset()
            with patch.object(evaluate, "RESULT_PATH", result_path), \
                 patch.object(evaluate, "REGRADED_PATH", regraded_path):
                evaluate.regrade(cases)
            data = json.loads(regraded_path.read_text(encoding="utf-8"))
        statuses = {r["id"]: r["status"] for r in data["results"]}
        self.assertEqual(statuses["Q05"], "PASSED")
        self.assertEqual(statuses["Q14"], "ERROR")
        self.assertTrue(data["regraded_offline"])


if __name__ == "__main__":
    unittest.main()


class UnicodeMinusTests(unittest.TestCase):
    def test_unicode_minus_is_read_as_negative_number(self):
        self.assertTrue(evaluate.has_expected_number("độ lệch \u22123 đơn vị", -3))
        self.assertTrue(evaluate.has_expected_number("độ lệch -3 đơn vị", -3))
        self.assertFalse(evaluate.has_expected_number("độ lệch 3 đơn vị", -3))


class EnDashTests(unittest.TestCase):
    def test_en_dash_before_digit_is_negative_but_ranges_are_not(self):
        self.assertTrue(evaluate.has_expected_number("độ lệch là \u20133 đơn vị", -3))
        self.assertEqual(evaluate.extract_numbers("từ 1\u20139 đơn vị"), [1.0, 9.0])
        self.assertEqual(evaluate.extract_numbers("76 + 0 \u2013 119"), [76.0, 0.0, 119.0])


class ForbiddenPhrasesTests(unittest.TestCase):
    def test_blaming_a_transaction_fails_no_answer_case(self):
        case = next(c for c in evaluate.load_testset() if c["id"] == "Q18")
        blame = "Giao dịch gây ra số tồn âm đầu tiên: TX00223. Không có thông tin về người thực hiện."
        honest = "Không đủ dữ liệu để xác định giao dịch hay người gây ra; cần rà soát theo quy trình bất thường."
        self.assertFalse(evaluate.evaluate_answer(case, blame)[0])
        self.assertTrue(evaluate.evaluate_answer(case, honest)[0])


class ProtectResultsTests(unittest.TestCase):
    def test_full_run_with_errors_does_not_overwrite_results(self):
        self.assertEqual(evaluate.choose_output_path(True, 0), evaluate.RESULT_PATH)
        self.assertEqual(evaluate.choose_output_path(True, 3), evaluate.INCOMPLETE_PATH)
        self.assertEqual(evaluate.choose_output_path(False, 0), evaluate.PARTIAL_PATH)

    def test_detects_daily_limit_error(self):
        self.assertTrue(evaluate.is_daily_limit_error("Error code: 429 ... on tokens per day (TPD): Limit 200000"))
        self.assertFalse(evaluate.is_daily_limit_error("Error code: 429 ... on tokens per minute (TPM): Limit 8000"))

    def test_load_previous_falls_back_to_incomplete_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result_path = Path(tmp) / "results.json"
            incomplete_path = Path(tmp) / "results_incomplete.json"
            result_path.write_text(json.dumps({"status": "not_run"}), encoding="utf-8")
            incomplete_path.write_text(json.dumps({"results": [{"id": "Q01", "status": "ERROR"}]}), encoding="utf-8")
            with patch.object(evaluate, "RESULT_PATH", result_path), \
                 patch.object(evaluate, "INCOMPLETE_PATH", incomplete_path):
                previous = evaluate.load_previous_results()
        self.assertEqual(previous["results"][0]["id"], "Q01")
