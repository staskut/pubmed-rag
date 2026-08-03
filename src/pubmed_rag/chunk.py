"""Turn articles into retrieval chunks.

Strategy (token-based, tokenizer matches OpenAI embeddings):
  * A "header" chunk = title + abstract, so titles are searchable and every
    abstract carries its title as context.
  * Body chunks from PMC full text, packed on paragraph boundaries up to a
    token target with a small overlap so ideas aren't split mid-thought.

Pure functions here have no DB/network dependency and are unit-tested; the
Postgres writer at the bottom uses them to populate the ``chunks`` table
(embeddings are filled in later by the embedding stage).
"""
from __future__ import annotations

from dataclasses import dataclass

import tiktoken

# text-embedding-3-small / gpt-4o-mini both use the o200k/cl100k family; cl100k
# is a close, stable proxy for counting and is always available offline.
_ENC = tiktoken.get_encoding("cl100k_base")

TARGET_TOKENS = 512
OVERLAP_TOKENS = 64


def n_tokens(text: str) -> int:
    return len(_ENC.encode(text))


@dataclass
class Chunk:
    chunk_index: int
    section: str          # "abstract" | "body"
    content: str
    token_count: int


def _split_long_paragraph(para: str, target: int) -> list[str]:
    """Hard-split a paragraph that alone exceeds the token target."""
    tokens = _ENC.encode(para)
    out = []
    for i in range(0, len(tokens), target):
        out.append(_ENC.decode(tokens[i : i + target]))
    return out


def pack_paragraphs(text: str, target: int, overlap: int) -> list[str]:
    """Greedily pack paragraphs into ~target-token chunks with token overlap."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    # pre-split any paragraph that is itself larger than the target
    units: list[str] = []
    for p in paras:
        units.extend(_split_long_paragraph(p, target) if n_tokens(p) > target else [p])

    chunks: list[str] = []
    cur: list[str] = []
    cur_tok = 0
    for unit in units:
        ut = n_tokens(unit)
        if cur and cur_tok + ut > target:
            chunks.append("\n\n".join(cur))
            # carry over a tail of the previous chunk for overlap continuity
            carry, ctok = [], 0
            for prev in reversed(cur):
                pt = n_tokens(prev)
                if ctok + pt > overlap:
                    break
                carry.insert(0, prev)
                ctok += pt
            cur, cur_tok = carry[:], ctok
        cur.append(unit)
        cur_tok += ut
    if cur:
        chunks.append("\n\n".join(cur))
    return chunks


def chunk_article(
    article: dict, target: int = TARGET_TOKENS, overlap: int = OVERLAP_TOKENS
) -> list[Chunk]:
    """Produce ordered chunks for one article record."""
    title = (article.get("title") or "").strip()
    abstract = (article.get("abstract") or "").strip()
    full_text = (article.get("full_text") or "").strip()

    chunks: list[Chunk] = []
    idx = 0

    # header: title + abstract (title always present so it is searchable)
    header = f"{title}\n\n{abstract}".strip() if abstract else title
    if header:
        for piece in pack_paragraphs(header, target, overlap):
            chunks.append(Chunk(idx, "abstract", piece, n_tokens(piece)))
            idx += 1

    # body: PMC full text, if any
    if full_text:
        for piece in pack_paragraphs(full_text, target, overlap):
            chunks.append(Chunk(idx, "body", piece, n_tokens(piece)))
            idx += 1

    return chunks


# --------------------------------------------------------------------------- #
# Postgres writer: articles -> chunks (embeddings left NULL for the next stage)
# --------------------------------------------------------------------------- #
def write_chunks(batch_size: int = 200, replace: bool = True) -> None:
    from psycopg2.extras import execute_values

    from .db import connect

    conn = connect()
    try:
        with conn, conn.cursor() as cur:
            if replace:
                cur.execute("TRUNCATE chunks RESTART IDENTITY")
            cur.execute("SELECT pmid, title, abstract, full_text FROM articles")
            articles = cur.fetchall()

        total = 0
        with conn, conn.cursor() as cur:
            rows = []
            for pmid, title, abstract, full_text in articles:
                for ch in chunk_article(
                    {"title": title, "abstract": abstract, "full_text": full_text}
                ):
                    rows.append((pmid, ch.chunk_index, ch.section, ch.content, ch.token_count))
                    if len(rows) >= batch_size:
                        _flush(cur, execute_values, rows)
                        total += len(rows)
                        rows = []
            if rows:
                _flush(cur, execute_values, rows)
                total += len(rows)
        print(f"Wrote {total:,} chunks from {len(articles):,} articles")
    finally:
        conn.close()


def _flush(cur, execute_values, rows) -> None:
    execute_values(
        cur,
        "INSERT INTO chunks (pmid, chunk_index, section, content, token_count) "
        "VALUES %s ON CONFLICT (pmid, chunk_index) DO UPDATE SET "
        "section=EXCLUDED.section, content=EXCLUDED.content, token_count=EXCLUDED.token_count",
        rows,
    )


if __name__ == "__main__":
    write_chunks()
