"""Đánh giá RAG tách riêng khỏi LLM: không gọi Groq nên KHÔNG tốn token.

So sánh 2 chế độ truy vấn (dense, hybrid) và 2 cách chia đoạn (line, fixed) bằng
hit@k, recall@k và MRR trên các câu có expected_doc_ids. Với câu no_answer, in điểm
top-1 để chọn ngưỡng RETRIEVAL_MIN_SCORE.

Chạy: python evaluation/eval_retrieval.py [--embedding-model TÊN] [--k 3 5]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import EMBEDDING_MODEL  # noqa: E402
from retrieval.rag_pipeline import RAGPipeline, current_doc_ids  # noqa: E402
from retrieval.vector_store import VectorStore  # noqa: E402

DOCUMENTS_DIR = ROOT / "data" / "documents"
TESTSET_PATH = ROOT / "data" / "tests" / "testset.jsonl"
OUTPUT_PATH = ROOT / "evaluation" / "retrieval_results.json"
# Câu tính toán thuần số liệu không cần tài liệu để trả lời nên không đưa vào hit@k.
SKIP_CATEGORIES = {"calculation"}


def load_cases(path: Path = TESTSET_PATH) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def is_no_answer(case: dict) -> bool:
    return case.get("no_answer") is True or str(case.get("category", "")).startswith("no_answer")


def evaluate_retrieval(
    model_name: str = EMBEDDING_MODEL,
    k_values: tuple[int, ...] = (3, 5),
    chunk_modes: tuple[str, ...] = ("line", "fixed"),
    modes: tuple[str, ...] = ("dense", "hybrid"),
    cases: list[dict] | None = None,
    documents_dir: Path = DOCUMENTS_DIR,
) -> dict:
    cases = cases if cases is not None else load_cases()
    answerable = [
        c for c in cases
        if not is_no_answer(c) and c.get("category") not in SKIP_CATEGORIES and c.get("expected_doc_ids")
    ]
    no_answer = [c for c in cases if is_no_answer(c)]
    biggest_k = max(k_values)
    rows = []

    for chunk_mode in chunk_modes:
        store = VectorStore.from_directory(documents_dir, model_name=model_name, chunk_mode=chunk_mode)
        pipeline = RAGPipeline(store)
        current = current_doc_ids(store)
        flt = {"doc_id": current}

        for mode in modes:
            hit = {k: [] for k in k_values}
            recall = {k: [] for k in k_values}
            reciprocal_ranks = []
            answerable_top1 = []
            misses = []
            for case in answerable:
                # Bản chính sách đã bị thay thế không thể truy xuất nên không tính vào kỳ vọng.
                expected = [d for d in case["expected_doc_ids"] if d in current]
                if not expected:
                    continue
                evidence = pipeline.retrieve(case["question"], top_k=biggest_k, search_mode=mode, metadata_filter=flt)
                ranked = [item.doc_id for item in evidence]
                answerable_top1.append(evidence[0].score if evidence else 0.0)
                for k in k_values:
                    found = [d for d in expected if d in set(ranked[:k])]
                    hit[k].append(1.0 if found else 0.0)
                    recall[k].append(len(found) / len(expected))
                first = next((i for i, d in enumerate(ranked, 1) if d in expected), None)
                reciprocal_ranks.append(1.0 / first if first else 0.0)
                if first is None or first > min(k_values):
                    misses.append(case["id"])

            no_answer_top1 = []
            for case in no_answer:
                evidence = pipeline.retrieve(case["question"], top_k=1, search_mode=mode, metadata_filter=flt)
                no_answer_top1.append(evidence[0].score if evidence else 0.0)

            def mean(values):
                return round(sum(values) / len(values), 4) if values else None

            rows.append({
                "chunk_mode": chunk_mode,
                "search_mode": mode,
                "chunks": len(store.chunks),
                "cases": len(reciprocal_ranks),
                **{f"hit@{k}": mean(hit[k]) for k in k_values},
                **{f"recall@{k}": mean(recall[k]) for k in k_values},
                "mrr": mean(reciprocal_ranks),
                "answerable_min_top1": round(min(answerable_top1), 4) if answerable_top1 else None,
                "no_answer_max_top1": round(max(no_answer_top1), 4) if no_answer_top1 else None,
                "missed_in_top_min_k": misses,
            })

    for row in rows:
        low, high = row["no_answer_max_top1"], row["answerable_min_top1"]
        row["suggested_min_score"] = round((low + high) / 2, 3) if low is not None and high is not None and low < high else None
    return {"embedding_model": model_name, "k_values": list(k_values), "rows": rows}


def print_report(report: dict) -> None:
    ks = report["k_values"]
    print(f"Mô hình embedding: {report['embedding_model']}")
    header = ["chunk", "mode", "n_chunk", "n_case"] + [f"hit@{k}" for k in ks] + [f"rec@{k}" for k in ks] + ["MRR"]
    print(" | ".join(f"{h:>8}" for h in header))
    for row in report["rows"]:
        values = [row["chunk_mode"], row["search_mode"], row["chunks"], row["cases"]]
        values += [row[f"hit@{k}"] for k in ks] + [row[f"recall@{k}"] for k in ks] + [row["mrr"]]
        print(" | ".join(f"{str(v):>8}" for v in values))
    print("\nHiệu chỉnh ngưỡng RETRIEVAL_MIN_SCORE (điểm top-1):")
    for row in report["rows"]:
        print(
            f"  {row['chunk_mode']}/{row['search_mode']}: câu có đáp án thấp nhất={row['answerable_min_top1']}, "
            f"câu no_answer cao nhất={row['no_answer_max_top1']}, gợi ý ngưỡng={row['suggested_min_score']}"
        )
    print("  (gợi ý = None nghĩa là hai nhóm chồng lấn: chưa thể tách bằng một ngưỡng điểm.)")
    for row in report["rows"]:
        if row["missed_in_top_min_k"]:
            print(f"  Câu chưa có tài liệu đúng trong top-{min(report['k_values'])} ({row['chunk_mode']}/{row['search_mode']}): "
                  f"{', '.join(row['missed_in_top_min_k'])}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Đánh giá retrieval (không tốn token LLM).")
    parser.add_argument("--embedding-model", default=EMBEDDING_MODEL)
    parser.add_argument("--k", nargs="+", type=int, default=[3, 5])
    args = parser.parse_args(argv)
    report = evaluate_retrieval(model_name=args.embedding_model, k_values=tuple(args.k))
    print_report(report)
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nĐã lưu: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
