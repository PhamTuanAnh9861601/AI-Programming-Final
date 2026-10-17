"""Embedding Sentence-Transformer và kho vector trong bộ nhớ."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from .document_store import Document, DocumentChunk, DocumentStore


DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


@lru_cache(maxsize=2)
def _load_embedding_model(model_name: str):
    """Nạp mô hình cục bộ một lần; lần đầu có thể tải các trọng số mô hình."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Sentence Transformers is required for semantic retrieval. "
            "Install the project requirements first."
        ) from exc
    return SentenceTransformer(model_name)


def embed_text(text: str, model_name: str = DEFAULT_EMBEDDING_MODEL) -> list[float]:
    """Mã hóa một văn bản bằng cùng mô hình dùng để lập chỉ mục các đoạn."""
    vector = _load_embedding_model(model_name).encode(text, convert_to_numpy=True)
    return [float(value) for value in vector.tolist()]


def embed_texts(texts: list[str], model_name: str = DEFAULT_EMBEDDING_MODEL) -> list[list[float]]:
    """Mã hóa một nhóm văn bản trong một lần gọi mô hình."""
    if not texts:
        return []
    vectors = _load_embedding_model(model_name).encode(texts, convert_to_numpy=True)
    return [[float(value) for value in vector.tolist()] for vector in vectors]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Vectors must have the same dimensions")
    norm_left = math.sqrt(sum(value * value for value in left))
    norm_right = math.sqrt(sum(value * value for value in right))
    if norm_left == 0.0 or norm_right == 0.0:
        return 0.0
    score = sum(a * b for a, b in zip(left, right)) / (norm_left * norm_right)
    return max(-1.0, min(1.0, score))


@dataclass
class VectorStore(DocumentStore):
    """DocumentStore được mở rộng để tìm kiếm ngữ nghĩa và lưu dữ liệu JSON."""
    model_name: str = DEFAULT_EMBEDDING_MODEL

    def add_chunk(self, chunk: DocumentChunk) -> str:
        if chunk.embedding is None:
            chunk.embedding = embed_text(chunk.content, self.model_name)
        return super().add_chunk(chunk)

    @classmethod
    def from_directory(
        cls, directory: str | Path, *, chunk_size: int = 150, overlap: int = 30,
        model_name: str = DEFAULT_EMBEDDING_MODEL, chunk_mode: str = "line",
    ) -> "VectorStore":
        document_store = DocumentStore.from_directory(
            directory, chunk_size=chunk_size, overlap=overlap, chunk_mode=chunk_mode
        )
        store = cls(
            documents=document_store.documents,
            chunks=document_store.chunks,
            chunk_size=chunk_size,
            overlap=overlap,
            chunk_mode=chunk_mode,
            model_name=model_name,
        )
        all_chunks = list(store.chunks.values())
        vectors = embed_texts([chunk.content for chunk in all_chunks], model_name)
        for chunk, vector in zip(all_chunks, vectors):
            chunk.embedding = vector
        return store

    def search(
        self, query: str, top_k: int = 3, min_score: float | None = None,
        metadata_filter: dict | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        from .dense_search import dense_search
        return dense_search(
            query, self, top_k=top_k, min_score=min_score,
            metadata_filter=metadata_filter,
        )

    def batch_search(
        self, queries: list[str], top_k: int = 3, min_score: float | None = None,
    ) -> list[list[tuple[DocumentChunk, float]]]:
        if top_k < 1:
            return [[] for _ in queries]
        if not queries or not self.chunks:
            return [[] for _ in queries]
        query_vectors = embed_texts(queries, self.model_name)
        chunks = list(self.chunks.values())
        # Tạo embedding còn thiếu cho các đoạn được thêm trực tiếp vào kho tài liệu.
        missing = [chunk for chunk in chunks if chunk.embedding is None]
        if missing:
            vectors = embed_texts([chunk.content for chunk in missing], self.model_name)
            for chunk, vector in zip(missing, vectors):
                chunk.embedding = vector
        results = []
        for query_vector in query_vectors:
            ranked = []
            for chunk in chunks:
                score = cosine_similarity(query_vector, chunk.embedding)
                if min_score is None or score >= min_score:
                    ranked.append((chunk, score))
            ranked.sort(key=lambda item: (-item[1], item[0].doc_id, item[0].chunk_index))
            results.append(ranked[:top_k])
        return results

    def save(self, path: str | Path, *, include_embeddings: bool = False) -> None:
        """Lưu tài liệu/đoạn dưới dạng JSON; mặc định bỏ embedding để giảm dung lượng."""
        payload = {
            "model_name": self.model_name,
            "chunk_size": self.chunk_size,
            "overlap": self.overlap,
            "chunk_mode": self.chunk_mode,
            "documents": [],
            "chunks": [],
        }
        for document in self.documents.values():
            item = asdict(document)
            item["created_at"] = document.created_at.isoformat()
            payload["documents"].append(item)
        for chunk in self.chunks.values():
            item = asdict(chunk)
            if not include_embeddings:
                item["embedding"] = None
            payload["chunks"].append(item)
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, path: str | Path) -> None:
        """Thay nội dung kho bằng dữ liệu JSON và tạo lại các embedding bị lược bỏ."""
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        self.model_name = payload.get("model_name", self.model_name)
        self.documents = {}
        self.chunks = {}
        self.chunk_size = payload.get("chunk_size", 150)
        self.overlap = payload.get("overlap", 30)
        self.chunk_mode = payload.get("chunk_mode", "fixed")
        for item in payload.get("documents", []):
            item["created_at"] = datetime.fromisoformat(item["created_at"])
            document = Document(**item)
            self.documents[document.doc_id] = document
        missing_embeddings = []
        for item in payload.get("chunks", []):
            chunk = DocumentChunk(**item)
            self.chunks[chunk.chunk_id] = chunk
            if chunk.embedding is None:
                missing_embeddings.append(chunk)
        if missing_embeddings:
            vectors = embed_texts(
                [chunk.content for chunk in missing_embeddings], self.model_name
            )
            for chunk, vector in zip(missing_embeddings, vectors):
                chunk.embedding = vector
