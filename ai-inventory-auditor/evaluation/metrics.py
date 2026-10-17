"""Metrics for evidence citation and conservative faithfulness proxy.

The faithfulness metric is a transparent lexical proxy, not a semantic judge.
It estimates whether factual sentences contain a cited retrieved doc_id.
"""
from __future__ import annotations
import re

DOC_ID_RE = re.compile(r"\bINV-DOC-\d{3}\b", re.IGNORECASE)
_DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2212"), "-")


def _ascii_dashes(text: str) -> str:
    """Đổi các loại gạch nối Unicode về '-' để regex nhận ra doc_id."""
    return (text or "").translate(_DASHES)

def citation_doc_ids(answer: str) -> list[str]:
    return list(dict.fromkeys(match.upper() for match in DOC_ID_RE.findall(_ascii_dashes(answer))))

def faithfulness_proxy(answer: str, doc_ids: list[str] | None = None) -> float | None:
    """Tỷ lệ câu có doc_id; đây là citation coverage, không đo semantic entailment."""
    text = _ascii_dashes(answer).strip()
    if not text:
        return None
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ỵ])|\n+", text) if s.strip()]
    factual = [s for s in sentences if len(s.split()) >= 4]
    if not factual:
        return 1.0
    # Count only sentences that themselves carry an explicit doc_id citation.
    # This is a conservative citation proxy, not semantic entailment.
    supported = sum(bool(DOC_ID_RE.search(sentence)) for sentence in factual)
    return round(supported / len(factual), 4)
