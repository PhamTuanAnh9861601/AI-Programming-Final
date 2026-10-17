"""Bước truy xuất của RAG: trả về bằng chứng chính sách đã xếp hạng và nguồn."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .document_store import DocumentChunk
from .hybrid_search import hybrid_search
from .vector_store import VectorStore


@dataclass(frozen=True)
class Evidence:
    chunk_id: str
    doc_id: str
    title: str
    source: str
    score: float
    content: str
    metadata: dict


def current_doc_ids(store) -> list[str]:
    """Chọn tài liệu hiện hành: với mỗi tiêu đề, giữ bản có ngày (date) mới nhất.

    Dùng metadata date/version trước khi truy xuất để bản cũ không thắng chỉ vì
    trùng từ khóa với câu hỏi hơn.
    """
    latest_by_title = {}
    for document in store.documents.values():
        key = document.title.strip().casefold()
        previous = latest_by_title.get(key)
        item_date = str(document.metadata.get("date", ""))
        prev_date = str(previous.metadata.get("date", "")) if previous else ""
        if previous is None or item_date > prev_date:
            latest_by_title[key] = document
    return [document.doc_id for document in latest_by_title.values()]


class RAGPipeline:
    """Nạp tệp chính sách một lần, sau đó truy xuất bằng chứng theo từng câu hỏi."""
    def __init__(self, store: VectorStore):
        self.store = store

    @classmethod
    def from_directory(cls, directory: str | Path, **store_options) -> "RAGPipeline":
        return cls(VectorStore.from_directory(str(directory), **store_options))

    def retrieve(self, query: str, *, top_k: int = 5,
                 search_mode: str = "cosine",
                 metadata_filter: dict | None = None,
                 min_score: float | None = None) -> list[Evidence]:
        if not query or not query.strip():
            raise ValueError("query must not be empty")
        if top_k < 1:
            return []
        if search_mode in {"cosine", "dense"}:
            results = self.store.search(
                query, top_k=top_k,
                min_score=min_score,
                metadata_filter=metadata_filter,
            )
        elif search_mode == "hybrid":
            results = hybrid_search(
                query, self.store, top_k=top_k,
                metadata_filter=metadata_filter, min_score=min_score,
            )
        else:
            raise ValueError("search_mode must be 'cosine' or 'hybrid'")
        return [self._evidence(chunk, score) for chunk, score in results]

    @staticmethod
    def _evidence(chunk: DocumentChunk, score: float) -> Evidence:
        return Evidence(
            chunk_id=chunk.chunk_id,
            doc_id=chunk.doc_id,
            title=str(chunk.metadata.get("title", chunk.doc_id)),
            source=str(chunk.metadata.get("source", "")),
            score=score,
            content=chunk.content,
            metadata=dict(chunk.metadata),
        )

    @staticmethod
    def format_context(evidence: list[Evidence]) -> str:
        """Định dạng trích dẫn để chuyển sang bước tạo câu trả lời."""
        return "\n\n".join(
            f"[{index}] {item.title} (doc_id={item.doc_id}, "
            f"version={item.metadata.get('version', 'unknown')}, "
            f"date={item.metadata.get('date', 'unknown')}, chunk_id={item.chunk_id})\n"
            f"{item.content}"
            for index, item in enumerate(evidence, start=1)
        )


def retrieve_evidence(query: str, store: VectorStore, top_k: int = 5,
                      search_mode: str = "cosine", metadata_filter: dict | None = None,
                      min_score: float | None = None) -> list[Evidence]:
    """Hàm tiện ích dành cho nơi gọi đã quản lý sẵn một VectorStore."""
    return RAGPipeline(store).retrieve(
        query, top_k=top_k, search_mode=search_mode,
        metadata_filter=metadata_filter, min_score=min_score,
    )


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    pipeline = RAGPipeline.from_directory(project_root / "data" / "documents")
    question = "Chênh lệch tồn kho bao nhiêu thì cần ưu tiên HIGH?"
    evidence = pipeline.retrieve(question, top_k=3)
    print(f"Question: {question}\n")
    for item in evidence:
        print(f"[{item.score:.3f}] {item.doc_id} — {item.title}\n{item.content}\n")


if __name__ == "__main__":
    main()
