# Product Requirements — Anesthesiology PubMed Q&A (RAG)

> Capstone project for the LLM Engineering course. This document defines **what** we
> are building and **why**, and maps every academic evaluation criterion to a concrete
> technical component so nothing required is left out. See
> [`component_coverage.md`](component_coverage.md) for the criterion-by-criterion matrix.

---

## 1. Problem statement

Anesthesiologists, residents, and clinical researchers need to answer specific clinical
and pharmacological questions ("What is the recommended dexmedetomidine dose for
pediatric sedation?", "Does sugammadex reduce residual neuromuscular blockade vs
neostigmine?") from the primary literature. Doing this manually means searching PubMed,
skimming dozens of abstracts, and stitching together an answer — slow, and easy to miss
relevant work.

**This project builds a Q&A system that answers anesthesiology questions grounded in
PubMed literature and returns every answer with citations** (PMID, title, journal, year,
link). The system retrieves the most relevant passages from a curated corpus, assembles a
grounded prompt, and asks an LLM to answer *only* from retrieved evidence — refusing or
flagging when the evidence is insufficient. This reduces hallucination risk and keeps the
clinician one click away from the source paper.

**Non-goals:** This is a literature-retrieval assistant, **not** a clinical decision-making
tool. It does not give patient-specific medical advice; every answer is framed as "what the
literature says" with citations, and the UI carries a disclaimer.

## 2. Target users & primary use cases

| User | Use case |
|------|----------|
| Anesthesiology resident | Quick evidence lookup while studying or on rotation |
| Practicing anesthesiologist | Check current evidence on a drug, dose, or technique |
| Clinical researcher | Find and summarize literature on a narrow topic |

**Core user flow:** ask a natural-language question → system retrieves relevant passages →
LLM produces a grounded answer with inline citations → user sees answer + source list →
user gives 👍/👎 feedback.

## 3. Scope

- **Domain:** Anesthesiology and closely related topics (sedation, analgesia, neuromuscular
  blockade, regional/general anesthesia, perioperative care, anesthetic pharmacology).
- **Corpus:** Hybrid content depth:
  - **Breadth** — abstracts + metadata for anesthesiology papers via NCBI **Entrez
    E-utilities** (`esearch` → `efetch`).
  - **Depth** — full text for the subset available in the **PubMed Central Open Access
    (PMC OA)** set, fetched and enriched onto the same records.
- **Corpus size (target):** ~3,000–10,000 articles from a defined query + date window
  (e.g. `"anesthesiology"[MeSH] AND 2015:2025[dp]`), tunable via config. Full text where
  available; abstract-only otherwise.
- **Languages:** English only.

## 4. Functional requirements

1. **Ingestion** — Automated dlt pipeline pulls articles from Entrez (breadth) and PMC OA
   (depth), normalizes them, chunks text, computes embeddings, and loads into Postgres.
   Re-runnable and incremental (dedupe by PMID; skip already-embedded chunks).
2. **Retrieval** — Given a query, return the top-k most relevant chunks. Must support:
   - keyword / full-text search (Postgres FTS),
   - semantic / vector search (pgvector),
   - **hybrid** search combining both,
   - **re-ranking** of candidates,
   - **query rewriting** before retrieval.
3. **Answer generation** — Assemble retrieved chunks into a grounded prompt, call the LLM,
   return an answer with inline citations mapped to source records. Must refuse / hedge when
   retrieved evidence is weak.
4. **Agentic behavior (stretch, module 1)** — Expose retrieval as a tool via function calling
   so the LLM can decide to search (and optionally re-search with a rewritten query) rather
   than always retrieving once.
5. **Interface** — Streamlit UI: question box, streamed answer, expandable source cards
   (title, authors, journal, year, PMID link), and 👍/👎 + optional comment feedback.
6. **Feedback & monitoring** — Persist every query, retrieved sources, answer, latency, token
   usage, and user feedback. Surface health + quality in a Grafana dashboard (≥5 charts).
7. **Evaluation** — Offline scripts to measure retrieval quality (multiple approaches
   compared) and answer quality (LLM-as-a-judge across multiple prompt/config variants).

## 5. Non-functional requirements

- **Reproducibility:** one `docker-compose up` brings up app + Postgres + Grafana; pinned
  dependency versions; `.env.example`; documented dataset access; a `make ingest` (or
  equivalent) that populates the KB from scratch.
- **Grounding / safety:** answers cite sources; system prompt forbids answering beyond
  retrieved context; medical-disclaimer shown in UI.
- **Cost/latency:** default to `gpt-4o-mini` + `text-embedding-3-small`; typical answer
  under ~10s.
- **Config-driven:** corpus query, top-k, model names, and retrieval strategy set via
  env/config, not hardcoded.
- **Portability:** cloud deployment mirrors the compose setup.

## 6. Architecture & tech stack

```
                     ┌─────────────────────────────────────────────┐
                     │  Ingestion (dlt pipeline, scheduled)          │
   Entrez API ──────▶│  esearch/efetch → normalize → chunk →         │
   PMC OA  API ──────▶│  embed (OpenAI) → load                       │
                     └───────────────────────┬─────────────────────┘
                                              ▼
                             ┌───────────────────────────────┐
                             │ PostgreSQL + pgvector          │
                             │  • articles / chunks           │
                             │  • embeddings (vector)         │
                             │  • FTS index (tsvector)        │
                             │  • query_logs / feedback       │
                             └───────┬───────────────┬────────┘
              retrieve (hybrid+rerank)│               │ read metrics
                                      ▼               ▼
   User ──▶ Streamlit UI ──▶ RAG service ──▶ OpenAI      Grafana dashboard
              ▲   feedback         │  (rewrite→retrieve→rerank→answer)
              └────────────────────┘
```

| Concern | Choice | Rationale |
|---------|--------|-----------|
| LLM + embeddings | **OpenAI** (`gpt-4o-mini`, `text-embedding-3-small`) | Cheap, strong, easy LLM-as-judge |
| Data store | **PostgreSQL + pgvector** | One store for vectors, keyword FTS, logs, and Grafana source → simplifies hybrid search & monitoring |
| Ingestion | **dlt** (REST sources) + scheduler (cron/Kestra) | Automated, incremental, API-native |
| Retrieval libs | **LangChain** for orchestration; cross-encoder / Cohere / LLM reranker | Covers module 6 best practices |
| UI | **Streamlit** | Course-recommended, fast, records preview video |
| Monitoring | **Grafana** over Postgres | Live dashboards, ≥5 charts |
| Packaging | **docker-compose** (+ cloud host) | Full containerization + cloud bonus |

## 7. Data model (Postgres)

- `articles` — `pmid` (PK), `pmcid`, `title`, `abstract`, `authors`, `journal`, `pub_year`,
  `mesh_terms`, `has_full_text`, `source_url`, `ingested_at`.
- `chunks` — `id` (PK), `pmid` (FK), `chunk_index`, `section`, `text`, `token_count`,
  `embedding vector(1536)`, `tsv tsvector` (generated), indexes: ivfflat/hnsw on `embedding`,
  GIN on `tsv`.
- `query_logs` — `id`, `ts`, `question`, `rewritten_question`, `strategy`, `top_k`,
  `retrieved_pmids`, `answer`, `latency_ms`, `prompt_tokens`, `completion_tokens`, `cost`.
- `feedback` — `id`, `query_log_id` (FK), `rating` (+1/-1), `comment`, `ts`.

## 8. Evaluation plan

- **Retrieval (multiple approaches → pick best):** compare keyword-only, vector-only, hybrid,
  and hybrid+rerank on a labeled question→relevant-PMID set (generated via LLM from the
  corpus, spot-checked). Metrics: Hit Rate / Recall@k and MRR.
- **Answer (multiple prompts/configs → pick best):** LLM-as-a-judge scores answers on
  groundedness, relevance, and completeness across ≥2 prompt variants and/or model settings;
  best config ships.
- Results and the chosen configuration are documented in the README.

## 9. Monitoring plan (Grafana, ≥5 charts)

1. Query volume over time. 2. Answer latency (p50/p95). 3. Token usage & estimated cost.
4. 👍/👎 feedback ratio over time. 5. Retrieval strategy usage / avg similarity score.
6. (bonus) Share of answers flagged low-confidence / "insufficient evidence".

## 10. Milestones

1. **Ingestion + KB** — dlt pipeline, Postgres schema, embeddings loaded.
2. **Retrieval + generation** — keyword→vector→hybrid→rerank→query-rewrite; grounded answers with citations.
3. **Interface** — Streamlit app with feedback capture.
4. **Evaluation** — retrieval + answer eval scripts and results.
5. **Monitoring** — Grafana dashboard on Postgres.
6. **Packaging** — docker-compose, README/docs, cloud deploy, preview video.

## 11. Open decisions (defaults chosen; revisit if needed)

- Vector index: start `ivfflat`, move to `hnsw` if recall needs it.
- Reranker: cross-encoder (local, free) vs Cohere Rerank (API) — decide during module 6.
- Scheduler: cron in-container by default; upgrade to Kestra if we want a stronger orchestration story.
- Agentic function-calling: stretch goal after the linear RAG flow works.
