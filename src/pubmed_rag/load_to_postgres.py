"""Copy the built corpus from DuckDB into the Postgres knowledge base.

Keeps the expensive network fetch (DuckDB) separate from the store, so we can
(re)load Postgres without hitting NCBI again.

Run: uv run python -m pubmed_rag.load_to_postgres
"""
from __future__ import annotations

import json

import duckdb
from psycopg2.extras import Json, execute_values

from .db import connect

DUCKDB = "data/kb.duckdb"
BATCH = 500

COLUMNS = [
    "pmid", "pmcid", "doi", "title", "abstract", "full_text",
    "has_full_text", "authors", "journal", "pub_year", "mesh_terms", "source_url",
]

UPSERT = f"""
INSERT INTO articles ({", ".join(COLUMNS)})
VALUES %s
ON CONFLICT (pmid) DO UPDATE SET
    pmcid = EXCLUDED.pmcid, doi = EXCLUDED.doi, title = EXCLUDED.title,
    abstract = EXCLUDED.abstract, full_text = EXCLUDED.full_text,
    has_full_text = EXCLUDED.has_full_text, authors = EXCLUDED.authors,
    journal = EXCLUDED.journal, pub_year = EXCLUDED.pub_year,
    mesh_terms = EXCLUDED.mesh_terms, source_url = EXCLUDED.source_url;
"""


def _year(val) -> int | None:
    s = str(val or "").strip()[:4]
    return int(s) if s.isdigit() else None


def _jsonb(val):
    """DuckDB returns JSON columns as strings; wrap for psycopg2 as JSONB."""
    if val is None:
        return Json([])
    if isinstance(val, str):
        try:
            return Json(json.loads(val))
        except json.JSONDecodeError:
            return Json([])
    return Json(val)


def main(duckdb_path: str = DUCKDB) -> None:
    duck = duckdb.connect(duckdb_path, read_only=True)
    rows = duck.execute(
        "select pmid, pmcid, doi, title, abstract, full_text, has_full_text, "
        "authors, journal, pub_year, mesh_terms, source_url from pubmed.articles"
    ).fetchall()
    print(f"Read {len(rows):,} articles from DuckDB")

    prepared = [
        (
            r[0], r[1], r[2], r[3], r[4], r[5], bool(r[6]),
            _jsonb(r[7]), r[8], _year(r[9]), _jsonb(r[10]), r[11],
        )
        for r in rows
    ]

    conn = connect()
    try:
        with conn, conn.cursor() as cur:
            execute_values(cur, UPSERT, prepared, page_size=BATCH)
            cur.execute("select count(*), sum(has_full_text::int) from articles")
            n, ft = cur.fetchone()
        print(f"Postgres articles now: {n:,} ({ft:,} with full text)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
