"""Evaluate AgentLoop through MCP against data/tests/testset.jsonl."""

import argparse
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.mcp_client import MCPClient
from agent.agent_loop import AgentLoop
from evaluation.metrics import faithfulness_proxy, citation_doc_ids

TESTSET_PATH = ROOT / "data" / "tests" / "testset.jsonl"
RESULT_PATH = ROOT / "evaluation" / "results.json"
INCOMPLETE_PATH = ROOT / "evaluation" / "results_incomplete.json"  # lần chạy đầy đủ có lỗi
PARTIAL_PATH = ROOT / "evaluation" / "results_partial.json"      # khi chỉ chạy một số câu
REGRADED_PATH = ROOT / "evaluation" / "results_regraded.json"    # khi chấm lại offline
# Nghỉ giữa các câu để không vượt giới hạn token/phút của Groq.
EVAL_PAUSE_SECONDS = float(os.getenv("EVAL_PAUSE_SECONDS", "8"))


# Expressions that clearly communicate missing or insufficient evidence.
UNCERTAINTY_PHRASES = (
    # Vietnamese
    "không đủ dữ liệu",
    "chưa đủ dữ liệu",
    "không thể xác định",
    "không thể kết luận",
    "không thể xác nhận",
    "chưa thể xác định",
    "chưa thể kết luận",
    "không có thông tin",
    "không tìm thấy trong tài liệu",
    "không tìm thấy bằng chứng",
    "không có bằng chứng",
    "không tìm thấy dữ liệu",
    "không có dữ liệu",
    "chưa có dữ liệu",
    "chưa được ghi nhận",
    "không đủ căn cứ",
    "chưa đủ để xác định",
    "chưa đủ thông tin để",
    "không đủ thông tin để",
    "chưa có bằng chứng",
    "không có bằng chứng",
    "không có thông tin nào xác định",
    "không có thông tin xác định",
    "không ghi lại thời gian cụ thể",
    "không có thông tin về thời điểm",
    "không thể xác định xem",
    "chưa có thông tin nào xác định người chịu trách nhiệm",
    "chưa có bằng chứng nào xác định người chịu trách nhiệm",
    "không có dữ liệu tồn kho thực tế",
    "không có dữ liệu cho sản phẩm",
    # English
    "cannot determine",
    "cannot confirm",
    "cannot conclude",
    "not enough information",
    "insufficient information",
    "not enough data",
    "insufficient data",
    "do not have enough",
    "don't have enough",
    "does not have enough",
    "no data available",
    "not recorded",
    "the data itself does not specify",
    "the data does not specify",
    "does not specify the exact cause",
    "does not provide enough evidence",
    "unable to determine",
    "unable to confirm",
    "not enough evidence",
    "no evidence to determine",
)

# Only used for questions that ask for a cause, a responsible person, or an
# exact time. These indicate that the answer is speculating rather than citing
# evidence. Avoid generic words such as "loss" that may appear in the question.
SPECULATION_PHRASES = (
    "possible reasons",
    "possible causes",
    "could be caused by",
    "might be caused by",
    "may have been caused by",
    "possible explanation",
    "could have been caused by",
    "might have happened because",
    "may have happened because",
    "nguyên nhân có thể",
    "có thể do",
    "có thể là do",
    "có khả năng do",
    "trộm cắp",
    "bị trộm",
    "đếm nhầm",
    "mis-count",
    "miscount",
    "spoilage",
    "unrecorded losses",
    "counting errors",
    "or theft",
    "theft",
    "stolen",
    "damaged or expired",
)


def normalize(text):
    """Normalize text for matching without changing its meaning."""
    text = str(text or "").lower()
    text = text.replace("’", "'").replace("‘", "'")
    return " ".join(text.split())


def load_testset():
    if not TESTSET_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy: {TESTSET_PATH}")

    cases = []
    with TESTSET_PATH.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"JSONL lỗi ở dòng {line_number}: {error}"
                ) from error

            if not isinstance(case, dict):
                raise ValueError(f"Dòng {line_number} phải là JSON object.")
            if not case.get("id") or not case.get("question"):
                raise ValueError(
                    f"Dòng {line_number} thiếu id hoặc question."
                )
            cases.append(case)

    no_answer_count = sum(
        case.get("no_answer") is True or normalize(case.get("category")) == "no_answer"
        for case in cases
    )
    if len(cases) < 12:
        raise ValueError(f"Cần ít nhất 12 câu, hiện có {len(cases)}.")
    if no_answer_count < 4:
        raise ValueError(
            f"Cần ít nhất 4 câu no_answer, hiện có {no_answer_count}."
        )
    return cases


def is_explicit_write_request(question):
    """Skip only commands that would actually write an audit request."""
    q = normalize(question)
    inquiry_prefixes = (
        "có cần",
        "có nên",
        "có phải",
        "liệu có cần",
        "should we",
        "do we need",
        "does it need",
        "is it necessary",
    )
    if any(q.startswith(prefix) for prefix in inquiry_prefixes):
        return False

    commands = (
        "hãy tạo phiếu kiểm toán",
        "tạo phiếu kiểm toán cho",
        "lập phiếu kiểm toán cho",
        "hãy lập phiếu kiểm toán",
        "tạo yêu cầu kiểm toán cho",
        "create an audit request for",
        "create an audit ticket for",
    )
    return any(command in q for command in commands)


def contains_uncertainty(answer):
    text = normalize(answer)
    if any(phrase in text for phrase in UNCERTAINTY_PHRASES):
        return True

    patterns = (
        r"\bi (?:do not|don't) have enough information\b",
        r"\bnot enough information to\b",
        r"\bnot enough data to\b",
        r"\bcannot (?:determine|confirm|conclude)\b",
        r"\bunable to (?:determine|confirm|conclude)\b",
        r"\bdoes not (?:specify|include|contain)\b",
        r"\bhas not been recorded\b",
        r"\bwithout (?:a )?(?:the )?physical count\b",
        r"\bno evidence (?:to|for) determine\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def contains_unsupported_speculation(answer):
    text = normalize(answer)
    return any(phrase in text for phrase in SPECULATION_PHRASES)


def extract_numbers(text):
    """Extract signed integer/decimal values from a response."""
    pattern = r"(?<![A-Za-z])[-+]?\d+(?:[.,]\d+)?"
    # Dấu trừ Unicode (U+2212, U+2010-2012) trước chữ số -> "-" để nhận ra số âm.
    text = re.sub(r"[\u2212\u2010\u2011\u2012]\s*(?=\d)", "-", str(text or ""))
    # En dash/em dash dính liền chữ số và không đứng sau chữ/số ("–3"), khác khoảng "1–9".
    text = re.sub(r"(?<![\w])[\u2013\u2014](?=\d)", "-", text)
    numbers = []
    for match in re.finditer(pattern, text):
        raw = match.group().replace(",", ".")
        try:
            numbers.append(float(raw))
        except ValueError:
            pass
    return numbers


def has_expected_number(answer, expected):
    try:
        target = float(expected)
    except (TypeError, ValueError):
        return str(expected).lower() in normalize(answer)

    return any(
        math.isclose(number, target, rel_tol=0, abs_tol=1e-6)
        for number in extract_numbers(answer)
    )


def evaluate_answer(case, answer):
    """Return (passed, reason) using category-specific acceptance criteria."""
    category = normalize(case.get("category"))
    question = normalize(case.get("question"))
    answer = answer or ""
    normalized = normalize(answer)
    expected_values = case.get("expected_values") or {}

    if not answer.strip():
        return False, "Agent trả lời rỗng."

    # Questions that must not be answered by inventing causes, people, or times.
    if case.get("no_answer") is True or category == "no_answer":
        asks_unsupported_detail = any(
            phrase in question
            for phrase in (
                "tại sao",
                "nguyên nhân",
                "ai là người",
                "thời điểm chính xác",
                "why ",
                "who caused",
                "exact time",
            )
        )
        forbidden = [normalize(item) for item in case.get("forbidden_any") or []]
        if any(item in normalized for item in forbidden):
            return False, "Kết luận nguyên nhân/giao dịch cụ thể khi chưa đủ bằng chứng."
        if asks_unsupported_detail and contains_unsupported_speculation(answer):
            return False, "Agent suy đoán nguyên nhân chưa có bằng chứng."
        if not contains_uncertainty(answer):
            return False, "Chưa thể hiện rõ việc thiếu dữ liệu."
        # Từ chối đúng được chấm riêng; việc có căn cứ (doc_id) đo qua actual_doc_ids.
        return True, "Từ chối kết luận khi chưa đủ dữ liệu."

    # Severity must be checked before numeric fields, because eval_006 asks
    # specifically for the classification, not for repeating the variance.
    if category == "severity_classification" or (
        "mức độ nghiêm trọng" in question or "severity" in question
    ):
        expected_severity = str(
            expected_values.get("severity", "NORMAL")
        ).upper()
        if expected_severity in answer.upper():
            return True, f"Đúng mức độ nghiêm trọng: {expected_severity}."
        return False, f"Không tìm thấy severity={expected_severity}."

    # Missing physical count: never accept a made-up variance.
    if category == "missing_data":
        has_missing_count = (
            "physical_count" in normalized
            or "kiểm đếm" in normalized
            or "số lượng thực tế" in normalized
        )
        states_uncertainty = contains_uncertainty(answer) or any(
            phrase in normalized
            for phrase in ("không thể tính", "không thể xác định", "cannot calculate")
        )
        states_no_ticket = any(
            phrase in normalized
            for phrase in ("không thể tạo phiếu", "không được tạo phiếu", "không tạo phiếu", "= null", "là null")
        )
        cited_docs = set(citation_doc_ids(answer))
        expected_docs = set(case.get("expected_doc_ids", []))
        if has_missing_count and (states_uncertainty or states_no_ticket):
            if expected_docs and not (cited_docs & expected_docs):
                return False, "Đúng kết luận nhưng chưa trích dẫn tài liệu chính sách về dữ liệu thiếu."
            return True, "Đúng: thiếu physical_count nên chưa xác định variance."
        return False, "Chưa xác nhận đúng quy tắc xử lý dữ liệu thiếu."

    # Listing all products with non-zero variance.
    if category == "inventory_analysis":
        expected_products = expected_values.get("product_ids", [])
        if not expected_products:
            return False, "Testset thiếu expected_values.product_ids."
        missing_products = [
            product_id
            for product_id in expected_products
            if str(product_id).upper() not in answer.upper()
        ]
        if missing_products:
            return False, f"Thiếu sản phẩm: {', '.join(missing_products)}."
        return True, "Có đủ các mã sản phẩm kỳ vọng."

    # No variance means no audit request.
    if category == "audit_policy":
        no_ticket_phrases = (
            "không cần tạo phiếu",
            "không tạo phiếu",
            "không cần phiếu",
            "no audit",
            "no ticket",
            "does not need an audit",
        )
        if any(phrase in normalized for phrase in no_ticket_phrases):
            return True, "Đúng chính sách không tạo phiếu."
        return False, "Chưa xác nhận chính sách không tạo phiếu."

    # Dataset-driven checks: only values explicitly named in expected_values are
    # scored numerically; policy document/version numbers are not mistaken for stock.
    numeric_keys = ("expected_stock", "physical_count", "variance")
    checked_numeric = 0
    for key in numeric_keys:
        if key not in expected_values:
            continue
        expected = expected_values[key]
        checked_numeric += 1
        if not has_expected_number(answer, expected):
            return False, f"Không tìm thấy giá trị {key}={expected}."

    if category == "status_filter":
        if "draft" not in normalized or "posted" not in normalized:
            return False, "Cần giải thích trạng thái DRAFT và quy tắc chỉ tính POSTED."
    elif category in {"policy", "threshold_boundary", "policy_version_conflict"}:
        if category == "policy_version_conflict" and "2.0" not in normalized:
            return False, "Chưa chọn rõ phiên bản chính sách hiện hành 2.0."
        if category == "threshold_boundary" and "high" not in normalized:
            return False, "Chưa nêu mức ưu tiên HIGH tại ngưỡng biên."
        if category == "policy" and "normal" not in normalized:
            return False, "Chưa nêu mức ưu tiên NORMAL."
    elif category in {"evidence_reasoning", "data_quality", "multi_evidence"}:
        required = tuple(case.get("must_contain_any") or ("không đủ", "chưa đủ", "không thể kết luận", "không thể xác định", "cần điều tra", "rà soát", "kiểm tra thủ công"))
        if not any(word in normalized for word in required):
            return False, "Chưa nêu giới hạn bằng chứng hoặc nhu cầu điều tra."
    elif category == "side_effect_verify":
        if "get_audit_request" not in normalized and "đọc lại" not in normalized and "xác minh" not in normalized:
            return False, "Chưa nêu bước đọc lại để xác minh phiếu."

    expected_doc_ids = case.get("expected_doc_ids", [])
    cited = set(citation_doc_ids(answer))
    if expected_doc_ids and not cited and category not in {"calculation"}:
        return False, "Câu trả lời không trích dẫn doc_id từ bằng chứng RAG."
    if checked_numeric:
        return True, "Các giá trị tồn kho kỳ vọng khớp và có kiểm tra bằng chứng."
    if expected_doc_ids and cited.intersection(expected_doc_ids):
        return True, "Đạt kiểm tra nội dung sơ bộ và trích dẫn ít nhất một tài liệu kỳ vọng."
    return False, f"Chưa đạt tiêu chí chấm category={category!r} hoặc thiếu bằng chứng kỳ vọng."



def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Đánh giá agent trên testset.")
    parser.add_argument("--only", nargs="+", metavar="ID",
                        help="Chỉ chạy các câu này, ví dụ: --only Q04 Q09")
    parser.add_argument("--failed", action="store_true",
                        help="Chỉ chạy lại các câu FAILED/ERROR trong results.json")
    parser.add_argument("--merge", action="store_true",
                        help="Ghép kết quả chạy lại vào results.json (đánh dấu rerun=true)")
    parser.add_argument("--regrade", action="store_true",
                        help="Chấm lại câu trả lời đã lưu trong results.json, KHÔNG gọi API")
    return parser.parse_args(argv)


def load_previous_results():
    """Đọc results.json; nếu chưa có kết quả đầy đủ thì dùng results_incomplete.json."""
    for path in (RESULT_PATH, INCOMPLETE_PATH):
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if data.get("results"):
            return data
    return {}


def is_daily_limit_error(error):
    """Lỗi hết hạn mức token/request theo ngày của Groq."""
    text = str(error).lower()
    return any(key in text for key in ("tokens per day", "(tpd)", "requests per day", "(rpd)"))


def choose_output_path(full_run, errors):
    """Chỉ lần chạy đầy đủ KHÔNG lỗi mới được ghi vào results.json."""
    if not full_run:
        return PARTIAL_PATH
    return RESULT_PATH if errors == 0 else INCOMPLETE_PATH


def select_cases(cases, only=None, failed=False, previous=None):
    """Chọn tập câu cần chạy. Trả về (danh sách câu, có phải chạy đầy đủ không)."""
    if not only and not failed:
        return cases, True
    wanted = {str(item).upper() for item in (only or [])}
    if failed:
        for result in (previous or {}).get("results", []):
            if result.get("status") in ("FAILED", "ERROR"):
                wanted.add(str(result["id"]).upper())
    return [case for case in cases if str(case["id"]).upper() in wanted], False


def build_summary(results, total):
    def count(status):
        return sum(item.get("status") == status for item in results)

    def mean(key):
        values = [item[key] for item in results if item.get(key) is not None]
        return round(sum(values) / len(values), 4) if values else None

    passed, failed = count("PASSED"), count("FAILED")
    run = passed + failed
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "testset": str(TESTSET_PATH),
        "total": total,
        "run": run,
        "passed": passed,
        "failed": failed,
        "errors": count("ERROR"),
        "skipped": count("SKIPPED"),
        "pass_rate_on_run": round(passed / run * 100, 2) if run else 0,
        "mean_doc_id_recall": mean("doc_id_recall"),
        "mean_faithfulness_proxy": mean("faithfulness_proxy"),
        "results": results,
    }


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_into_full(new_results):
    """Thay các câu đã chạy lại vào results.json; mỗi câu được đánh dấu rerun=true."""
    full = load_previous_results()
    if not full.get("results"):
        print("Chưa có results.json đầy đủ để ghép; chỉ lưu file kết quả riêng.")
        return None
    merged = {item["id"]: item for item in full["results"]}
    for item in new_results:
        merged[item["id"]] = {**item, "rerun": True}
    ordered = [merged[key] for key in merged]
    summary = build_summary(ordered, full.get("total", len(ordered)))
    write_json(RESULT_PATH if summary["errors"] == 0 else INCOMPLETE_PATH, summary)
    return summary


def regrade(cases):
    """Chấm lại các câu trả lời đã lưu bằng bộ chấm hiện tại, không tốn token."""
    previous = load_previous_results()
    if not previous.get("results"):
        print("results.json chưa có câu trả lời nào để chấm lại. Hãy chạy eval đầy đủ một lần.")
        return
    by_id = {case["id"]: case for case in cases}
    regraded = []
    for item in previous["results"]:
        case = by_id.get(item["id"])
        if case is None or item.get("answer") is None or item.get("status") in ("ERROR", "SKIPPED"):
            regraded.append(item)
            continue
        passed, reason = evaluate_answer(case, item["answer"])
        new_item = dict(item)
        new_item["status_before"] = item.get("status")
        new_item["status"] = "PASSED" if passed else "FAILED"
        new_item["reason"] = reason
        ids = citation_doc_ids(item["answer"])
        expected = case.get("expected_doc_ids", [])
        new_item["actual_doc_ids"] = ids
        new_item["doc_id_recall"] = (
            len(set(ids) & set(expected)) / len(set(expected)) if expected else None
        )
        new_item["faithfulness_proxy"] = faithfulness_proxy(item["answer"], ids)
        regraded.append(new_item)
        changed = "" if new_item["status"] == item.get("status") else f"  (trước: {item.get('status')})"
        print(f"{item['id']}: {new_item['status']}{changed} - {reason}")
    summary = build_summary(regraded, previous.get("total", len(cases)))
    summary["regraded_offline"] = True
    write_json(REGRADED_PATH, summary)
    print(f"\nĐạt {summary['passed']}/{summary['run']} câu có đáp án ({summary['pass_rate_on_run']}%). "
          f"Lỗi/bỏ qua giữ nguyên. Đã lưu: {REGRADED_PATH}")


def main(argv=None):
    args = parse_args(argv)
    cases = load_testset()
    print(f"Đã tải {len(cases)} câu hỏi.")

    if args.regrade:
        regrade(cases)
        return

    cases, full_run = select_cases(
        cases, only=args.only, failed=args.failed, previous=load_previous_results()
    )
    if not cases:
        print("Không có câu nào khớp để chạy.")
        return
    if not full_run:
        print(f"Chỉ chạy {len(cases)} câu: {', '.join(c['id'] for c in cases)}")

    results = []
    passed_count = 0
    failed_count = 0
    error_count = 0
    skipped_count = 0
    run_count = 0

    mcp_context = MCPClient()
    mcp_context.__enter__()
    try:
        for index, case in enumerate(cases, start=1):
            case_id = case["id"]
            question = case["question"]
            print(f"\n[{index}/{len(cases)}] {case_id}: {question}")
            if index > 1:
                time.sleep(EVAL_PAUSE_SECONDS)

            if is_explicit_write_request(question):
                status = "SKIPPED"
                reason = (
                    "Yêu cầu có thể ghi dữ liệu thật; "
                    "bỏ qua để tránh tạo phiếu ngoài ý muốn."
                )
                skipped_count += 1
                print(f"  => SKIP: {reason}")
                results.append({
                    "id": case_id,
                    "question": question,
                    "status": status,
                    "reason": reason,
                    "answer": None,
                })
                continue

            try:
                tools = mcp_context.build_tool_registry()
                agent = AgentLoop(
                    tools=tools, tool_schemas=mcp_context.get_groq_tool_schemas()
                )
                result = agent.run(question)

                if getattr(result, "success", True) is False:
                    raise RuntimeError(f"Agent không hoàn thành: {result.answer}")
                answer = getattr(result, "answer", "") or ""
                run_count += 1
                passed, reason = evaluate_answer(case, answer)
                actual_doc_ids = citation_doc_ids(answer)
                expected_doc_ids = case.get("expected_doc_ids", [])
                doc_recall = (
                    len(set(actual_doc_ids) & set(expected_doc_ids)) / len(set(expected_doc_ids))
                    if expected_doc_ids else None
                )
                faithfulness = faithfulness_proxy(answer, actual_doc_ids)
                token_usage = getattr(result, "token_usage", None) or {}
                input_rate = os.getenv("GROQ_INPUT_USD_PER_MILLION")
                output_rate = os.getenv("GROQ_OUTPUT_USD_PER_MILLION")
                estimated_cost_usd = None
                if input_rate and output_rate:
                    estimated_cost_usd = round(
                        (int(token_usage.get("prompt_tokens", 0)) * float(input_rate)
                         + int(token_usage.get("completion_tokens", 0)) * float(output_rate))
                        / 1_000_000, 8
                    )
                # Keep answer-quality pass/fail separate from evidence recall.
                status = "PASSED" if passed else "FAILED"

                if passed:
                    passed_count += 1
                else:
                    failed_count += 1

                print(f"  => {status}: {reason}")
                results.append({
                    "id": case_id,
                    "question": question,
                    "status": status,
                    "reason": reason,
                    "answer": answer,
                    "steps": getattr(result, "steps", None),
                    "tool_calls": getattr(result, "tool_calls", None),
                    "agent_success": getattr(result, "success", None),
                    "expected_doc_ids": expected_doc_ids,
                    "actual_doc_ids": actual_doc_ids,
                    "doc_id_recall": doc_recall,
                    "faithfulness_proxy": faithfulness,
                    "token_usage": token_usage,
                    "estimated_cost_usd": estimated_cost_usd,
                })
            except Exception as error:
                error_count += 1
                print(f"  => ERROR: {error}")
                results.append({
                    "id": case_id,
                    "question": question,
                    "status": "ERROR",
                    "reason": str(error),
                    "answer": None,
                })
                if is_daily_limit_error(error):
                    print("\nĐã hết hạn mức token/ngày của Groq. Dừng eval; các câu còn lại chưa chạy.")
                    print("Chờ hạn mức hồi lại (hoặc đổi model/gói) rồi chạy: python evaluation/evaluate.py --failed")
                    break

    finally:
        mcp_context.close()

    summary = build_summary(results, len(cases))
    out_path = choose_output_path(full_run, summary["errors"])
    write_json(out_path, summary)
    if full_run and out_path == INCOMPLETE_PATH:
        print("\nLần chạy có lỗi nên KHÔNG ghi đè results.json. Kết quả lưu ở results_incomplete.json.")
    if not full_run and args.merge:
        merged = merge_into_full(results)
        if merged:
            print(f"Đã ghép vào {RESULT_PATH}: {merged['passed']}/{merged['run']} đạt.")

    print("\n===== EVALUATION SUMMARY =====")
    print(f"Số câu đã chọn: {len(cases)}")
    print(f"Đã chạy: {summary['run']}")
    print(f"Đạt: {summary['passed']}")
    print(f"Không đạt: {summary['failed']}")
    print(f"Lỗi: {summary['errors']}")
    print(f"Bỏ qua để an toàn: {summary['skipped']}")
    print(f"Tỷ lệ đạt trên số câu đã chạy: {summary['pass_rate_on_run']}%")
    print(f"Báo cáo: {out_path}")


if __name__ == "__main__":
    main()
