# Convenience targets for the PubMed RAG project.
# Corpus size for a fresh build (override: make build-kb MAX=5000)
MAX ?= 2000

.PHONY: install up down logs ingest embed build-kb ui eval seed test fmt

install:            ## install Python deps (uv, Python 3.12)
	uv sync

up:                 ## start Postgres + Grafana (schema auto-applied)
	docker compose up -d

down:               ## stop containers (keeps data volumes)
	docker compose down

logs:               ## tail container logs
	docker compose logs -f

ingest:             ## fetch corpus from NCBI -> DuckDB -> Postgres -> chunks
	uv run python -m pubmed_rag.pipeline --max $(MAX)
	uv run python -m pubmed_rag.load_to_postgres
	uv run python -m pubmed_rag.chunk

restore-data:       ## use the SHIPPED corpus (skips the ~80-min fetch): unzip -> Postgres -> chunks
	gunzip -kf data/kb.duckdb.gz
	uv run python -m pubmed_rag.load_to_postgres
	uv run python -m pubmed_rag.chunk

embed:              ## embed chunks into pgvector (needs OPENAI_API_KEY)
	uv run python -m pubmed_rag.embed

build-kb: ingest embed  ## full knowledge base build (fetch -> chunk -> embed)

ui:                 ## run the Streamlit app
	uv run streamlit run app.py

eval:               ## run retrieval + answer evaluations (needs OPENAI_API_KEY)
	uv run python -m pubmed_rag.evaluation.ground_truth --n 50
	uv run python -m pubmed_rag.evaluation.retrieval_eval --k 10
	uv run python -m pubmed_rag.evaluation.answer_eval --n 15

seed:               ## seed demo monitoring data for the dashboard
	uv run python -m pubmed_rag.seed_monitoring --n 150 --clear

test:               ## run unit tests
	uv run --extra dev pytest tests/ -q
