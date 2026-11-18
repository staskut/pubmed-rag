# Data and corpus details

## Sources

- **[NCBI PubMed / Entrez](https://www.ncbi.nlm.nih.gov/books/NBK25501/)** — article titles,
  abstracts, and metadata (journal, year, PMID).
- **PubMed Central Open Access (PMC OA)** — full text where an open-access version is
  available, fetched via the BioC REST API.

## Corpus

- **~5,000 anesthesiology articles**, publication years **2015–2026**.
- **~55%** of articles have full text; the rest fall back to title + abstract.
- **47,934 embedded chunks** after token-based chunking.

The built corpus ships in the repo at `data/kb.duckdb.gz` (~54 MB) so the knowledge base can
be loaded without re-fetching from NCBI. Embeddings are regenerated locally (`make embed`)
and are not shipped.

## Ingestion

Ingestion is an automated [dlt](https://dlthub.com/) pipeline (`pipeline.py`) with two REST
sources (Entrez + PMC). It runs in two passes — a broad sweep and a deeper fetch — then
normalizes, chunks (`chunk.py`, token-based via tiktoken), and loads into Postgres. Rebuild
from public APIs with:

```bash
make build-kb MAX=5000     # full corpus; MAX smaller for a quick sample
```

## Schema

`sql/schema.sql` defines the Postgres schema: `articles`, `chunks` (with embeddings and
full-text search vectors), `query_logs`, and `feedback`.

## Usage policy

Article text and metadata come from NCBI PubMed and PubMed Central Open Access. Respect
[NCBI's usage policies](https://www.ncbi.nlm.nih.gov/home/about/policies/). This project is
for research and educational use and is not a medical decision tool.
