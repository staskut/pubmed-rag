"""Retrieval over the chunks table: keyword, vector, and hybrid.

  * keyword_search  — Postgres full-text search (lexical arm).
  * vector_search   — pgvector cosine similarity (semantic arm); needs embeddings.
  * hybrid_search   — Reciprocal Rank Fusion of the two lists (no score scaling).

Each returns a ranked list of :class:`Hit`. These are the retrieval strategies
compared in the evaluation module.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from pgvector.psycopg2 import register_vector

from .db import connect
from .llm import embed_query

RRF_K = 60  # standard reciprocal-rank-fusion constant


def _or_tsquery(query: str) -> str:
    """Build an OR tsquery from a natural-language question.

    ``websearch_to_tsquery`` ANDs every term, so a long question requires all
    terms in one chunk and usually matches nothing. We OR the terms instead and
    let ``ts_rank_cd`` reward chunks that match more of them. The 'english'
    config still stems and drops stopwords.
    """
    words = re.findall(r"[a-zA-Z0-9]+", query.lower())
    return " | ".join(dict.fromkeys(w for w in words if len(w) >= 2))

_SELECT = """
    SELECT c.id, c.pmid, c.section, c.content,
           a.title, a.journal, a.pub_year, a.source_url
    FROM chunks c JOIN articles a ON a.pmid = c.pmid
"""


@dataclass
class Hit:
    chunk_id: int
    pmid: str
    section: str
    content: str
    title: str
    journal: str
    pub_year: int | None
    source_url: str
    score: float

    def citation(self) -> str:
        yr = f", {self.pub_year}" if self.pub_year else ""
        return f"{self.title} ({self.journal}{yr}) PMID:{self.pmid}"


def _row_to_hit(row, score: float) -> Hit:
    return Hit(*row[:8], score=score)


def keyword_search(query: str, k: int = 10, conn=None) -> list[Hit]:
    tsq = _or_tsquery(query)
    if not tsq:
        return []
    own = conn is None
    conn = conn or connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                _SELECT
                + " WHERE c.tsv @@ to_tsquery('english', %s)"
                  " ORDER BY ts_rank_cd(c.tsv, to_tsquery('english', %s)) DESC"
                  " LIMIT %s",
                (tsq, tsq, k),
            )
            rows = cur.fetchall()
        return [_row_to_hit(r, score=1.0 / (i + 1)) for i, r in enumerate(rows)]
    finally:
        if own:
            conn.close()


def vector_search(query: str, k: int = 10, conn=None, query_vector=None) -> list[Hit]:
    own = conn is None
    conn = conn or connect()
    try:
        register_vector(conn)
        qvec = query_vector if query_vector is not None else embed_query(query)
        with conn.cursor() as cur:
            cur.execute(
                _SELECT
                + " WHERE c.embedding IS NOT NULL"
                  " ORDER BY c.embedding <=> %s::vector LIMIT %s",
                (qvec, k),
            )
            rows = cur.fetchall()
        return [_row_to_hit(r, score=1.0 / (i + 1)) for i, r in enumerate(rows)]
    finally:
        if own:
            conn.close()


def hybrid_search(query: str, k: int = 10, candidates: int = 50, conn=None) -> list[Hit]:
    """Fuse keyword + vector rankings with Reciprocal Rank Fusion."""
    own = conn is None
    conn = conn or connect()
    try:
        kw = keyword_search(query, candidates, conn=conn)
        vec = vector_search(query, candidates, conn=conn)
        scores: dict[int, float] = {}
        hits: dict[int, Hit] = {}
        for ranked in (kw, vec):
            for rank, hit in enumerate(ranked):
                scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (RRF_K + rank)
                hits[hit.chunk_id] = hit
        fused = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:k]
        out = []
        for cid, s in fused:
            h = hits[cid]
            h.score = s
            out.append(h)
        return out
    finally:
        if own:
            conn.close()


STRATEGIES = {
    "keyword": keyword_search,
    "vector": vector_search,
    "hybrid": hybrid_search,
}
