# Setup, ports, and operations

Detailed setup, configuration, and operational reference. For the fast path see the
[README Quick start](../README.md#quick-start).

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (Compose v2)
- [uv](https://docs.astral.sh/uv/) — manages Python 3.12 and dependencies
- An [OpenAI API key](https://platform.openai.com/) for embeddings and generation
- Optionally an `NCBI_API_KEY` to speed up ingestion (NCBI works without one)

## Building the knowledge base

Pick **one** of the two options.

**Option A — use the shipped corpus (fast, recommended):**

```bash
make restore-data          # decompress + load data/kb.duckdb.gz (~5k articles)
make embed                 # add embeddings (needs OPENAI_API_KEY; ~$0.38 full corpus)
```

**Option B — fetch fresh from NCBI:**

```bash
make build-kb MAX=2000     # ~2k articles; MAX=5000 for the full corpus (~80 min)
make embed
```

> **Shipped data:** the repo includes the built corpus at `data/kb.duckdb.gz` (~54 MB), so
> reviewers can skip the slow NCBI fetch — `make restore-data` decompresses and loads it.
> Embeddings are *not* shipped (they'd be ~300 MB); `make embed` regenerates them.

## Ports

All ports are configurable in `.env`.

| Service | Host port | Notes |
|---------|-----------|-------|
| Postgres | **5433** | Host 5432 is often already taken locally, so the container publishes 5433. |
| Grafana | **3000** | Monitoring dashboard. |
| Streamlit | **8501** | The app UI. |

## Running

```bash
make up            # start Postgres + Grafana (schema auto-applied)
make install       # uv sync — install Python deps
make ui            # run the Streamlit app → http://localhost:8501
make seed          # populate demo monitoring data
make eval          # run retrieval + answer evaluations
make test          # run unit tests
```

- **App:** http://localhost:8501
- **Monitoring:** http://localhost:3000 (`make seed` first to populate demo data)

## Monitoring

The Grafana dashboard is auto-provisioned over the live Postgres logs. Panels:

1. Total queries
2. Average latency
3. Cost
4. Satisfaction rate
5. Query volume over time
6. Latency p50 / p95
7. Token usage
8. Strategy mix
9. Feedback over time
10. Recent questions

Feedback is collected via the UI's 👍/👎 buttons and stored in the `feedback` table.

## Project structure

```
src/pubmed_rag/
  config.py            # env-driven configuration
  entrez.py            # NCBI Entrez + PMC BioC fetch/parse
  pipeline.py          # dlt ingestion (two-pass broad+deep corpus)
  load_to_postgres.py  # DuckDB → Postgres loader (no re-fetch)
  chunk.py             # token-based chunking (tiktoken)
  embed.py             # chunks → pgvector embeddings
  retrieval.py         # keyword / vector / hybrid (RRF)
  rerank.py            # cross-encoder rerank + dedupe
  rag.py               # rewrite → retrieve → answer → log
  llm.py               # OpenAI wrapper + cost tracking
  seed_monitoring.py   # demo data for the dashboard
  evaluation/          # ground truth, retrieval eval, answer eval
app.py                 # Streamlit UI
sql/schema.sql         # Postgres schema (articles, chunks, logs, feedback)
grafana/               # datasource + dashboard provisioning
docs/                  # product requirements, evaluation, data, setup
```

## Reproducibility

- Python pinned to **3.12** (`uv` manages it); all deps pinned in `pyproject.toml` /
  `uv.lock`.
- The dataset is rebuildable from public APIs via `make build-kb` — no private data.
- `make test` runs the unit tests; CI runs them on every push.
