"""dlt ingestion pipeline: PubMed/PMC -> knowledge base.

Loads normalized article records into a `pubmed` schema. Defaults to a local
DuckDB file for fast iteration; pass ``--destination postgres`` for the
containerized store (credentials come from dlt secrets / env).

Run:
    uv run python -m pubmed_rag.pipeline                 # -> data/pubmed.duckdb
    uv run python -m pubmed_rag.pipeline --max 500        # bigger corpus
    uv run python -m pubmed_rag.pipeline --destination postgres
"""
from __future__ import annotations

import argparse

import dlt

from .config import config
from .entrez import iter_corpus


def _corpus_specs(total: int, with_full_text: bool) -> list[tuple[str, int]]:
    """Build the (query, cap) passes for a 'broad + deep' corpus.

    Pass 1 (deep): restrict to articles with a PMC copy to maximise full-text
    coverage. Pass 2 (broad): the general query, deduped, for breadth.
    """
    base = config.full_query
    if not with_full_text:
        return [(base, total)]
    deep = min(int(total * 0.6), total)  # ~60% from the full-text-rich subset
    return [
        (f"({base}) AND \"pubmed pmc\"[sb]", deep),
        (base, total - deep),  # dedup skips the deep pass; tops up to `total`
    ]


@dlt.resource(
    name="articles",
    primary_key="pmid",
    write_disposition="merge",  # incremental: re-runs upsert by PMID
    columns={
        # keep these as JSON on the articles table instead of child tables
        "authors": {"data_type": "json"},
        "mesh_terms": {"data_type": "json"},
    },
)
def articles_resource(max_articles: int | None = None, with_full_text: bool = True):
    total = max_articles or config.max_articles
    yield from iter_corpus(_corpus_specs(total, with_full_text), with_full_text)


@dlt.source(name="pubmed")
def pubmed_source(max_articles: int | None = None, with_full_text: bool = True):
    return articles_resource(max_articles=max_articles, with_full_text=with_full_text)


def run(destination: str = "duckdb", max_articles: int | None = None,
        with_full_text: bool = True) -> None:
    kwargs = {}
    if destination == "duckdb":
        # NB: file stem must differ from the dataset name ("pubmed"), else DuckDB
        # raises an ambiguous catalog/schema error at load time.
        kwargs["credentials"] = "data/kb.duckdb"
    pipeline = dlt.pipeline(
        pipeline_name="pubmed_rag",
        destination=dlt.destinations.duckdb(**kwargs) if destination == "duckdb"
        else destination,
        dataset_name="pubmed",
        progress="log",
    )
    info = pipeline.run(
        pubmed_source(max_articles=max_articles, with_full_text=with_full_text)
    )
    print(info)


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest PubMed/PMC anesthesiology corpus")
    ap.add_argument("--destination", default="duckdb", choices=["duckdb", "postgres"])
    ap.add_argument("--max", type=int, default=config.max_articles,
                    help="max articles (0 = no cap)")
    ap.add_argument("--no-full-text", action="store_true",
                    help="skip PMC full-text enrichment (faster, abstracts only)")
    args = ap.parse_args()
    run(
        destination=args.destination,
        max_articles=args.max or None,
        with_full_text=not args.no_full_text,
    )


if __name__ == "__main__":
    main()
