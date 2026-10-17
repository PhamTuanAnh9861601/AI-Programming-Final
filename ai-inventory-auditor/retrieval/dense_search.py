from __future__ import annotations

from collections.abc import Iterable

from .document_store import DocumentChunk
from .vector_store import cosine_similarity, embed_text, embed_texts


def matches_metadata(chunk: DocumentChunk, metadata_filter: dict | None) -> bool:
    if not metadata_filter:
        return True
    for field, expected in metadata_filter.items():
        actual = chunk.doc_id if field == "doc_id" else chunk.metadata.get(field)
        if isinstance(expected, (list, tuple, set, frozenset)):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def dense_search(
    query: str, store_or_chunks, top_k: int = 3, min_score: float | None = None,
    metadata_filter: dict | None = None,
) -> list[tuple[DocumentChunk, float]]:
    """Trả về các đoạn gần nghĩa nhất, sắp xếp điểm từ cao xuống thấp."""
    if top_k < 1 or not query.strip():
        return []
    chunks: Iterable[DocumentChunk] = (
        store_or_chunks.chunks.values()
        if hasattr(store_or_chunks, "chunks")
        else store_or_chunks
    )
    eligible = [chunk for chunk in chunks if matches_metadata(chunk, metadata_filter)]
    if not eligible:
        return []
    model_name = getattr(store_or_chunks, "model_name", "all-MiniLM-L6-v2")
    query_vector = embed_text(query, model_name)
    missing = [chunk for chunk in eligible if chunk.embedding is None]
    if missing:
        vectors = embed_texts([chunk.content for chunk in missing], model_name)
        for chunk, vector in zip(missing, vectors):
            chunk.embedding = vector
    ranked = [
        (chunk, cosine_similarity(query_vector, chunk.embedding))
        for chunk in eligible
        if len(query_vector) == len(chunk.embedding)
        and (
            min_score is None
            or cosine_similarity(query_vector, chunk.embedding) >= min_score
        )
    ]
    ranked.sort(key=lambda item: (-item[1], item[0].doc_id, item[0].chunk_index))
    return ranked[:top_k]


def search_with_filter(
    query: str, store, metafilter: dict, top_k: int = 3,
    min_score: float | None = None,
) -> list[tuple[DocumentChunk, float]]:
    """Chỉ tìm trong các đoạn khớp với tất cả trường metadata được yêu cầu."""
    return dense_search(
        query, store, top_k=top_k, min_score=min_score,
        metadata_filter=metafilter,
    )
