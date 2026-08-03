"""Print summary statistics for the built corpus (DuckDB).

Run: uv run python -m pubmed_rag.inspect_corpus
"""
from __future__ import annotations

import duckdb

DB = "data/kb.duckdb"


def main() -> None:
    con = duckdb.connect(DB, read_only=True)
    t = "pubmed.articles"
    n, ft = con.execute(f"select count(*), sum(has_full_text::int) from {t}").fetchone()
    print(f"Articles:            {n:,}")
    print(f"With full text:      {ft:,} ({ft / n:.0%})")

    ab_chars, ft_chars = con.execute(
        f"select avg(length(abstract)), avg(length(full_text)) filter (where has_full_text) from {t}"
    ).fetchone()
    print(f"Avg abstract chars:  {ab_chars:,.0f}")
    print(f"Avg full-text chars: {ft_chars:,.0f}")

    n_abs = con.execute(f"select count(*) from {t} where coalesce(abstract,'')<>''").fetchone()[0]
    print(f"With any abstract:   {n_abs:,} ({n_abs / n:.0%})")

    print("\nBy year:")
    for yr, c, f in con.execute(
        f"select pub_year, count(*), sum(has_full_text::int) from {t} "
        f"group by pub_year order by pub_year"
    ).fetchall():
        print(f"  {yr or '?'}: {c:>4}  (full text {f})")

    print("\nTop journals:")
    for j, c in con.execute(
        f"select journal, count(*) c from {t} group by journal order by c desc limit 8"
    ).fetchall():
        print(f"  {c:>4}  {j}")


if __name__ == "__main__":
    main()
