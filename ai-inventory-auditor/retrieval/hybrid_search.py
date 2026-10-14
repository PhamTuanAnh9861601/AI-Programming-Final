"""Truy xuất từ khóa BM25Okapi kết hợp với độ tương đồng Sentence-Transformer."""

from __future__ import annotations

from rank_bm25 import BM25Okapi

from .dense_search import matches_metadata
from .document_store import DocumentChunk
from .vector_store import cosine_similarity, embed_text, embed_texts


def normalise_scores(scores: list[float]) -> list[float]:
    """Chuẩn hóa điểm về [0, 1] bằng phương pháp min-max."""
    if not scores:
        return []
    min_score, max_score = min(scores), max(scores)
    if max_score == min_score:
        return [1.0] * len(scores)
    return [(score - min_score) / (max_score - min_score) for score in scores]

# ===== Bước 1: Tạo chỉ mục BM25 trên các đoạn =====

def build_bm25_index(chunks: list[DocumentChunk]) -> BM25Okapi:
    """Tạo chỉ mục BM25 từ nội dung các đoạn, tách từ theo khoảng trắng."""
    tokenized = [chunk.content.lower().split() for chunk in chunks]
    return BM25Okapi(tokenized)

# ===== Bước 2: Tìm kiếm kết hợp =====

def hybrid_search(
    query: str,
    chunks_or_store,
    top_k: int = 3,
    metadata_filter: dict | None = None,
    w_bm25: float = 0.3,
    w_vector: float = 0.7,
    min_score: float | None = None,
) -> list[tuple[DocumentChunk, float]]:
    
    """Xếp hạng đoạn theo điểm BM25 và cosine có trọng số, có thể lọc metadata."""
    if top_k < 1 or not query.strip():
        return []
    
    if w_bm25 < 0 or w_vector < 0 or w_bm25 + w_vector <= 0:
        raise ValueError("Search weights must be non-negative and have a positive sum")
    
    chunks = list(
        chunks_or_store.chunks.values()

        if hasattr(chunks_or_store, "chunks") else chunks_or_store
    )
    eligible = [chunk for chunk in chunks if matches_metadata(chunk, metadata_filter)]
    if not eligible:
        return []

    model_name = getattr(chunks_or_store, "model_name", "all-MiniLM-L6-v2")
    bm25_index = build_bm25_index(eligible)
    bm25_scores = list(bm25_index.get_scores(query.lower().split()))
    bm25_norm = normalise_scores(bm25_scores)

    query_vector = embed_text(query, model_name)
    missing = [chunk for chunk in eligible if chunk.embedding is None]

    if missing:
        vectors = embed_texts([chunk.content for chunk in missing], model_name)

        for chunk, vector in zip(missing, vectors):
            chunk.embedding = vector

    vector_scores = [
        cosine_similarity(query_vector, chunk.embedding)
        if len(query_vector) == len(chunk.embedding) else 0.0
        for chunk in eligible
    ]

    ranked = []
    for chunk, keyword_score, vector_score in zip(eligible, bm25_norm, vector_scores):
        score = w_bm25 * keyword_score + w_vector * vector_score
        
        if min_score is None or score >= min_score:
            ranked.append((chunk, score))
    ranked.sort(key=lambda item: (-item[1], item[0].doc_id, item[0].chunk_index))
    return ranked[:top_k]
