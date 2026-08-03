"""Cross-encoder reranking (best-practice: document re-ranking).

Retrieval (hybrid) is recall-oriented and returns near-duplicate chunks from the
same article. This stage rescoring each candidate against the query with a
cross-encoder, then dedupes to the best chunk per article, yielding a small,
diverse, high-precision source set.

Uses fastembed's ONNX cross-encoder (no PyTorch) to keep the image light. The
model is loaded lazily and cached for the process.
"""
from __future__ import annotations

import os

from .retrieval import Hit, hybrid_search

RERANK_MODEL = os.getenv("RERANK_MODEL", "Xenova/ms-marco-MiniLM-L-6-v2")

_encoder = None


def _model():
    global _encoder
    if _encoder is None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        _encoder = TextCrossEncoder(model_name=RERANK_MODEL)
    return _encoder


def rerank_hits(
    query: str, hits: list[Hit], top_n: int = 8, dedupe_by_pmid: bool = True
) -> list[Hit]:
    """Rescore hits with the cross-encoder; optionally keep one chunk per article."""
    if not hits:
        return []
    scores = list(_model().rerank(query, [h.content for h in hits]))
    ranked = sorted(zip(hits, scores), key=lambda hs: hs[1], reverse=True)

    out: list[Hit] = []
    seen: set[str] = set()
    for hit, score in ranked:
        if dedupe_by_pmid and hit.pmid in seen:
            continue
        seen.add(hit.pmid)
        hit.score = float(score)
        out.append(hit)
        if len(out) >= top_n:
            break
    return out


def hybrid_rerank_search(query: str, k: int = 8, conn=None, candidates: int = 40) -> list[Hit]:
    """Hybrid retrieval of a wide candidate pool, then cross-encoder rerank + dedupe."""
    pool = hybrid_search(query, k=candidates, conn=conn)
    return rerank_hits(query, pool, top_n=k)
