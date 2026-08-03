# Component Coverage — mapping the rubric to our build

This table maps **every** academic evaluation criterion (and each course module's
techniques) to a concrete component in this project, so we can confirm nothing required is
missing and target maximum points. See [`product_requirements.md`](product_requirements.md)
for the full design.

## Scored criteria (target: full marks)

| Criterion | Max | How we earn it |
|-----------|-----|----------------|
| **Problem description** | 2 | PRD §1 + README: clear problem, users, data, flow — written for readers who didn't take the course. |
| **Retrieval flow** | 2 | Both a knowledge base (Postgres/pgvector corpus) **and** an LLM are used: retrieve → assemble prompt → LLM → grounded answer. |
| **Retrieval evaluation** | 2 | Evaluate **multiple** approaches (keyword, vector, hybrid, hybrid+rerank) on Hit Rate & MRR; ship the best. |
| **LLM evaluation** | 2 | LLM-as-a-judge over **multiple** prompt/config variants (groundedness/relevance/completeness); ship the best. |
| **Interface** | 2 | **Streamlit UI** (question box, streamed answer, source cards, feedback). |
| **Ingestion pipeline** | 2 | **Automated dlt pipeline** from Entrez + PMC REST sources into Postgres, scheduled. |
| **Monitoring** | 2 | User feedback (👍/👎 + comment) **and** Grafana dashboard with **≥5 charts**. |
| **Containerization** | 2 | **Everything in docker-compose** (app + Postgres + Grafana). |
| **Reproducibility** | 2 | Clear run instructions, accessible dataset (rebuildable from API), **pinned versions**, `.env.example`, one-command ingest + up. |
| **Best practices — hybrid search** | 1 | Combine Postgres FTS + pgvector; evaluated against single-mode retrieval. |
| **Best practices — re-ranking** | 1 | Re-rank retrieved candidates (cross-encoder or Cohere Rerank). |
| **Best practices — query rewriting** | 1 | Rewrite the user query before retrieval. |
| **Bonus — cloud deployment** | 2 | Deploy the compose stack to a cloud host. |
| **Bonus — extra** | ≤3 | Candidates: agentic function-calling retrieval, medical safety/grounding guardrail, incremental ingestion, cost tracking. |

**Projected total: 24 / 21 base points (+ up to 5 bonus).**

## Course-module technique checklist

Confirms each module's material is exercised somewhere in the project.

| Module | Technique | Where it's applied |
|--------|-----------|--------------------|
| 1. Agentic RAG | RAG with keyword search | Postgres FTS retrieval path |
| 1. Agentic RAG | Function calling / agentic | Retrieval exposed as an LLM tool (stretch goal) |
| 2. Vector Search | Embeddings + semantic search | `text-embedding-3-small` + pgvector |
| 2. Vector Search | minsearch/sqlite/**PGVector** | **pgvector** as the vector store |
| 3. Orchestration | Scheduling / Kestra | Scheduled ingestion (cron, optionally Kestra) |
| Workshop | **dlt** ingestion from REST/API | dlt pipeline (Entrez + PMC), loading Postgres |
| 4. Evaluation | Retrieval + answer, offline/online | Offline eval scripts + online feedback loop |
| 5. Monitoring | User feedback + live dashboard | Feedback table + Grafana |
| 6. Best Practices | **LangChain** | Orchestrates rewrite→retrieve→rerank→answer |
| 6. Best Practices | Hybrid search | FTS + vector combined |
| 6. Best Practices | Re-ranking | Cross-encoder / Cohere reranker |

## Gaps / risks to watch

- **DuckDB & marimo** (workshop) aren't in the core path — optional: use marimo/DuckDB for
  the offline evaluation analysis notebook to touch that material.
- **PMC OA coverage** for anesthesiology may be modest; abstract-only fallback keeps corpus
  breadth. Verify coverage early during ingestion.
- **Labeled eval set** is LLM-generated — must spot-check to keep retrieval metrics honest.
- **Cloud cost** — keep the deployed instance small; document teardown.
