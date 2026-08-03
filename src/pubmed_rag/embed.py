"""Embedding stage: fill in `chunks.embedding` for rows that lack it.

Idempotent — only embeds chunks where embedding IS NULL, so it can resume after
interruption and top up after new chunks are written.

Run: uv run python -m pubmed_rag.embed
"""
from __future__ import annotations

from pgvector.psycopg2 import register_vector
from psycopg2.extras import execute_values
from tqdm import tqdm

from .db import connect
from .llm import Usage, embed_texts

BATCH = 128  # texts per embedding request


def _pending_count(cur) -> int:
    cur.execute("SELECT count(*) FROM chunks WHERE embedding IS NULL")
    return cur.fetchone()[0]


def main(batch: int = BATCH) -> None:
    conn = connect()
    register_vector(conn)
    total_usage = Usage()
    try:
        with conn.cursor() as cur:
            pending = _pending_count(cur)
        if not pending:
            print("Nothing to embed — all chunks already have embeddings.")
            return
        print(f"Embedding {pending:,} chunks in batches of {batch} ...")

        done = 0
        with tqdm(total=pending, unit="chunk") as bar:
            while True:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, content FROM chunks WHERE embedding IS NULL "
                        "ORDER BY id LIMIT %s",
                        (batch,),
                    )
                    rows = cur.fetchall()
                if not rows:
                    break
                ids = [r[0] for r in rows]
                vectors, usage = embed_texts([r[1] for r in rows])
                total_usage.add(usage)
                with conn, conn.cursor() as cur:
                    execute_values(
                        cur,
                        "UPDATE chunks SET embedding = data.embedding "
                        "FROM (VALUES %s) AS data(id, embedding) WHERE chunks.id = data.id",
                        list(zip(ids, vectors)),
                        template="(%s, %s::vector)",
                    )
                done += len(rows)
                bar.update(len(rows))

        print(f"Embedded {done:,} chunks. "
              f"Tokens={total_usage.prompt_tokens:,}  cost≈${total_usage.cost_usd:.4f}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
