# Stand-up Comedy Analyzer — Product Requirements

Status: Draft v0.1  
Audience: capstone reviewers, developers, and future contributors  
Source of truth: `agent_context/project_academic_requirements.txt`

## 1. Product summary

The Stand-up Comedy Analyzer is a retrieval-augmented search and cultural analytics application built from legally usable stand-up transcript data.

It has two user experiences backed by the same corpus:

1. **Vibe Matcher** — finds individual comedy bits that match a nuanced premise, applies metadata filters, and produces a grounded comparison with citations.
2. **Cultural Horizon Scanner** — compares how often topics appear across regions and time using transparent, normalized SQL aggregations.

The product is intended for comedy fans, writers, researchers, and students who want to discover relevant material or explore cultural patterns without manually reading entire transcripts.

## 2. Problem statement

Existing streaming and search products organize stand-up at the level of a comedian, special, or broad genre. They do not reliably answer questions such as:

- “How do comedians in different countries talk about dating in their thirties?”
- “Did political comedy become more common in the UK than in the US over the last five years?”
- “Show me bits about becoming like your parents, but only from women comedians after 2020.”

The useful unit is usually a **bit**, not a complete special. Raw transcripts do not provide reliable bit boundaries, consistent topic labels, semantic search, or analysis-ready regional metadata. The product solves this by turning transcripts into a structured, searchable corpus and grounding every generated answer in retrieved bits.

## 3. Product goals

### 3.1 User goals

- Find a specific comedic premise even when the transcript uses different words.
- Filter results by relevant comedian, production, geography, and time metadata.
- Compare how multiple comedians or regions approach the same premise.
- Explore topic trends without confusing corpus size with cultural prevalence.
- Inspect the exact evidence behind every search answer or chart.

### 3.2 Capstone goals

- Demonstrate an end-to-end RAG flow over a real knowledge base.
- Demonstrate keyword, vector, hybrid, rewritten-query, and reranked retrieval.
- Use function calling to route between retrieval and analytics tools.
- Automate ingestion with a dedicated data-pipeline tool.
- Evaluate both retrieval and final answer quality using multiple approaches.
- Collect feedback and expose system and product-health monitoring.
- Run the complete local stack through Docker Compose with pinned dependencies.

### 3.3 Success measures

The MVP is successful when:

- hybrid retrieval with the selected enhancements beats both keyword-only and vector-only baselines on the primary offline retrieval metric;
- the selected answer prompt beats the baseline prompt on groundedness and citation correctness;
- at least 90% of factual claims in the final evaluation sample are supported by cited bits;
- at least 95% of tested chart values match independently computed SQL fixtures;
- users can complete the two primary journeys without a CLI or notebook;
- queries, latency, errors, feedback, and retrieval health are visible in a dashboard;
- a new reviewer can start the full system from documented steps and an accessible sample dataset.

These are launch targets, not claims about the finished system.

## 4. Scope

### 4.1 MVP scope

- English-language transcripts only.
- A documented, legally usable starter dataset.
- Transcript ingestion from files; a REST source may be added if a suitable legal source exists.
- Bit segmentation, topic classification, metadata normalization, embedding, and indexing.
- Natural-language bit search with filters.
- Keyword, vector, and hybrid retrieval modes available for evaluation.
- Query rewriting and result reranking in the production retrieval path if evaluation shows an improvement.
- A cited, LLM-generated comparison of retrieved bits.
- Topic, geography, and year trend charts backed by SQL.
- Corpus-coverage indicators and low-sample warnings.
- Per-answer feedback and optional free-text feedback.
- Offline evaluation commands and an online monitoring dashboard.
- Local deployment using Docker Compose.

### 4.2 Explicit non-goals for the MVP

- Generating new jokes in a comedian’s style.
- Judging whether a joke or comedian is objectively funny.
- Sentiment, offensiveness, plagiarism, or joke-quality scoring.
- Audio/video transcription as a required ingestion path.
- Multilingual semantic comparison.
- User accounts, personalized history, payments, or social features.
- Claiming that the corpus represents an entire country or culture.
- Exposing or redistributing full copyrighted transcripts without permission.

### 4.3 Candidate stretch goals

- Cloud deployment with a public demo.
- Timestamped playback links for licensed video sources.
- Multilingual transcripts and cross-lingual embeddings.
- Named-entity, setup/punchline, and comedic-device annotations.
- Saved searches and personalized recommendations.
- Statistical confidence intervals for trend comparisons.

## 5. Users and primary journeys

### Persona A: comedy explorer

Wants to discover bits matching a very specific situation or mood.

**Journey:** enter a premise → optionally add filters → inspect ranked bits → read a cited comparison → open a result’s source → provide feedback.

### Persona B: cultural researcher or student

Wants to compare topic prevalence across regions and years.

**Journey:** choose a topic → choose region dimension and date range → select a normalized metric → inspect trends and coverage → drill into supporting bits.

### Persona C: project reviewer

Wants to verify the engineering work.

**Journey:** start the stack → load the sample corpus → try both user experiences → run evaluation → inspect monitoring and documentation.

## 6. Key product definitions

### 6.1 Bit

A bit is a contiguous transcript segment centered on one primary comedic premise. It must preserve its source transcript ID and character or timestamp boundaries.

Recommended automatic boundaries are 80–800 words. Segments outside that range may be allowed but must be flagged. Human correction is optional for the MVP, while an evaluation subset must have human-reviewed boundaries.

### 6.2 Topic

A topic is a controlled, versioned label such as `dating`, `parenting`, `politics`, or `work`. A bit may have one primary topic and multiple secondary topics. The system stores classifier version and confidence so labels can be reproduced or regenerated.

Free-form tags may supplement the controlled taxonomy but cannot replace it in dashboard aggregations.

### 6.3 Geographic dimensions

“Country” is not a single field. The data model must keep these separate:

- **comedian origin/country affiliation**;
- **performance location**;
- **production or release market**.

The dashboard must name the selected dimension. Its default should be **comedian country affiliation**, subject to confirmation after the dataset is selected. Records may have multiple affiliations or an unknown value.

### 6.4 Topic prevalence

Raw topic counts are shown only alongside corpus coverage. The default comparison metric is:

`bits assigned to topic / all classified bits in the selected group`

The product may also offer topic bits per 10,000 transcript words and raw bit count. It must not compare raw counts across differently sized corpora as though they were prevalence.

## 7. Functional requirements

### 7.1 Corpus ingestion and enrichment

| ID | Requirement | MVP acceptance criterion |
|---|---|---|
| DATA-01 | Ingest supported transcript and metadata files through an automated dlt pipeline orchestrated by Kestra. | A documented command or scheduled workflow loads the sample corpus without a notebook. |
| DATA-02 | Validate required metadata and quarantine invalid records. | Invalid transcript, date, or source records appear in a rejected-record report and do not silently enter the index. |
| DATA-03 | Preserve provenance and rights metadata. | Every transcript stores source URL or file reference, acquisition date, rights/license status, and a stable source ID. |
| DATA-04 | Normalize text while retaining the original source. | Clean text and original text/source offsets can be traced to the same transcript. |
| DATA-05 | Segment transcripts into bits. | Every indexed bit has stable ID, transcript ID, order, text, and source boundaries; a reviewed sample is scored for boundary quality. |
| DATA-06 | Classify bits using a controlled topic taxonomy. | Each classified bit stores primary topic, optional secondary topics, confidence, taxonomy version, model, and prompt version. |
| DATA-07 | Create keyword and vector indexes. | Successfully ingested bits become searchable through both PostgreSQL full-text search and pgvector. |
| DATA-08 | Make ingestion idempotent and observable. | Rerunning an unchanged source creates no duplicate bits; the run records counts, failures, duration, and version information. |
| DATA-09 | Support incremental reprocessing. | A changed transcript, taxonomy, segmentation prompt, or embedding model can be reprocessed without rebuilding unrelated data. |
| DATA-10 | Publish corpus coverage. | The UI can show transcript and bit counts by year and geographic dimension, including unknown values. |

### 7.2 Vibe Matcher

| ID | Requirement | MVP acceptance criterion |
|---|---|---|
| SEARCH-01 | Accept nuanced natural-language premise queries. | A user can submit a non-empty query from the web UI. |
| SEARCH-02 | Support filters. | Users can filter at minimum by comedian, comedian country affiliation, release year/range, and topic; filters are applied before final ranking where possible. |
| SEARCH-03 | Rewrite suitable queries for retrieval. | The system creates a structured retrieval query containing the core premise, keyword alternatives, and explicit filters while preserving the original query. |
| SEARCH-04 | Retrieve with keyword and vector search. | Both result sets and their scores can be produced independently for offline evaluation. |
| SEARCH-05 | Fuse hybrid results. | The production candidate set combines keyword and vector rankings using a documented method such as reciprocal-rank fusion. |
| SEARCH-06 | Rerank candidates. | A cross-encoder or LLM reranker scores the fused candidates before the top results are presented, if offline evaluation validates it. |
| SEARCH-07 | Return inspectable evidence. | Each result shows snippet, comedian, source title, year, selected geographic metadata, topics, and source/timestamp link when available. |
| SEARCH-08 | Generate a grounded answer. | The LLM compares only the retrieved bits, uses bit-level citations, distinguishes evidence from inference, and says when evidence is insufficient. |
| SEARCH-09 | Prevent citation mismatch. | Every citation maps to a returned bit ID and the cited bit supports the associated claim in the evaluation sample. |
| SEARCH-10 | Handle weak or empty retrieval. | Below a configurable evidence threshold, the UI explains that evidence is insufficient and suggests changing the query or filters. |
| SEARCH-11 | Expose useful controls. | The UI lets users view the selected filters, retrieval mode in evaluation/debug mode, and cited source cards. |
| SEARCH-12 | Collect feedback. | Each generated answer supports thumbs up/down plus an optional reason; feedback is linked to the query, response, and pipeline version. |

### 7.3 Cultural Horizon Scanner

| ID | Requirement | MVP acceptance criterion |
|---|---|---|
| ANALYTICS-01 | Compare topic prevalence. | Users can select one or more topics, groups, and a year range and view the normalized result. |
| ANALYTICS-02 | Make geography explicit. | Users can choose an available geographic dimension; chart title, labels, and help text state which dimension is used. |
| ANALYTICS-03 | Offer transparent metrics. | Users can switch among share of bits, bits per 10,000 words, and raw count, with a definition for each. |
| ANALYTICS-04 | Show time trends. | A line or area chart displays the selected metric by year and group. |
| ANALYTICS-05 | Show coverage and uncertainty. | Every view includes corpus size, unknown metadata counts, and warnings/suppression for groups below the minimum sample threshold. |
| ANALYTICS-06 | Support evidence drill-down. | Selecting a chart series or point opens the underlying matching bits and their source metadata. |
| ANALYTICS-07 | Use reproducible SQL. | Aggregations execute through parameterized, tested SQL; an LLM never generates unrestricted production SQL. |
| ANALYTICS-08 | Export aggregated results. | Users can download the current aggregated, non-transcript result as CSV. |

### 7.4 Agent and RAG behavior

The application uses schema-constrained function calling to select among:

- `search_bits(query, filters, limit)` for premise retrieval;
- `compare_topic_trends(topics, groups, geography_dimension, start_year, end_year, metric)` for aggregation;
- `get_corpus_coverage(filters)` for coverage and caveat checks.

| ID | Requirement | MVP acceptance criterion |
|---|---|---|
| AGENT-01 | Route the user’s intent to the correct tool. | A labeled intent test set measures routing accuracy; unsupported requests receive a scoped explanation. |
| AGENT-02 | Validate every tool argument. | Tool inputs use typed schemas, allowed metric and dimension enums, bounded limits, and validated dates. |
| AGENT-03 | Ground answers in tool output. | The assistant does not answer corpus-specific questions from model memory. |
| AGENT-04 | Preserve determinism for analytics. | Numerical claims come from the analytics tool response and are not recomputed by the LLM. |
| AGENT-05 | Record traceability. | Each request records anonymized query, selected tool, rewritten query, retrieved IDs/scores, prompt/model versions, token use, latency, outcome, and errors. |

### 7.5 Interface

The recommended MVP interface is Streamlit, backed by a FastAPI service.

Required pages:

1. **Vibe Matcher** — query, filters, cited answer, result cards, and feedback.
2. **Cultural Horizon Scanner** — controls, trend/comparison charts, coverage, and drill-down.
3. **About the Data** — data sources, rights status, corpus composition, taxonomy, limitations, and metric definitions.
4. **Monitoring** — reviewer-accessible operational and feedback dashboard, or a link to the bundled Grafana dashboard.

FastAPI must expose health, search/answer, analytics, feedback, and corpus-coverage endpoints. Interactive API documentation is part of the reviewer experience.

## 8. Data requirements

### 8.1 Minimum useful sample corpus

Final thresholds depend on lawful data availability. The target for a credible demonstration is:

- at least 30 complete transcripts;
- at least 4 geographic groups;
- at least 3 distinct release years;
- enough material for at least 500 extracted bits;
- no geographic trend point displayed as representative below a configurable minimum, initially 3 transcripts and 30 bits per group-period.

If these thresholds cannot be met legally, the project must narrow its cultural claims and present the dashboard as a corpus explorer rather than a culture-level conclusion.

### 8.2 Core entities

| Entity | Selected fields |
|---|---|
| `comedian` | ID, display name, country affiliations, optional demographic metadata with source |
| `special` | ID, title, release date, production market, performance location, comedian ID |
| `transcript` | ID, special ID, language, original/clean text reference, word count, source, rights status, content hash |
| `bit` | ID, transcript ID, sequence, text, start/end offsets or timestamps, word count, segmentation version |
| `topic` | ID, canonical label, description, taxonomy version |
| `bit_topic` | bit ID, topic ID, primary flag, confidence, classifier/prompt version |
| `bit_embedding` | bit ID, embedding, model, dimensions, content hash |
| `query_trace` | request ID, anonymized query, filters, tool, result IDs/scores, versions, latency, token/cost fields, status |
| `feedback` | request ID, rating, optional reason, timestamp |
| `ingestion_run` | run ID, source/version, started/finished, counts, failures, pipeline version |

### 8.3 Rights, privacy, and responsible use

- Only public-domain, permissively licensed, explicitly authorized, or otherwise legally usable transcripts may be included in the distributable sample dataset.
- The repository must not silently scrape or redistribute copyrighted transcripts.
- Source and license/rights status must be documented per transcript.
- The UI should display only the amount of source text necessary for evidence and follow the source’s permitted use.
- Optional demographic data must be sourced, nullable, and never inferred from names.
- Stored query text may contain sensitive information; the UI must disclose logging, and production logs should support retention limits or anonymization.
- Cultural claims must be phrased as observations about the indexed corpus, not universal claims about a nationality or culture.

## 9. Retrieval and answer design

### 9.1 Production retrieval candidate

1. Validate the original query and explicit UI filters.
2. Rewrite the query into a core premise, keyword variants, and filters.
3. Retrieve top candidates using PostgreSQL full-text search.
4. Retrieve top candidates using pgvector cosine similarity.
5. Fuse the rankings using reciprocal-rank fusion.
6. Rerank the fused candidates.
7. Reject or qualify the answer if evidence scores or corpus coverage are too weak.
8. Assemble a prompt with stable bit IDs and metadata.
9. Generate a concise comparison whose corpus claims cite bit IDs.
10. Persist the trace and return evidence cards with the answer.

The exact rewriting, fusion, reranking, top-k, and threshold settings are selected through evaluation rather than assumed to be beneficial.

### 9.2 Grounded answer contract

A generated answer must:

- directly answer the requested premise;
- compare only dimensions supported by the retrieved records;
- cite a bit ID for each corpus-specific claim;
- never invent quotations, dates, identities, countries, or statistics;
- identify sparse or conflicting evidence;
- avoid long verbatim excerpts;
- label broader interpretation as interpretation;
- return a useful no-answer response when context is insufficient.

## 10. Evaluation requirements

### 10.1 Retrieval evaluation

Create a versioned golden set of at least 100 query judgments spanning:

- exact keyword queries;
- paraphrases and implicit premises;
- queries with metadata filters;
- cross-region comparison queries;
- rare-topic and expected-no-result queries.

Each query should have one or more relevant bit IDs, graded relevance where feasible, and expected filters. At least a representative subset must be human-reviewed.

Compare these retrieval configurations:

1. keyword only;
2. vector only;
3. hybrid;
4. hybrid plus query rewriting;
5. hybrid plus query rewriting and reranking.

Report Recall@5, Recall@10, MRR@10, nDCG@10, filter correctness, no-result correctness, and latency. Select the production configuration using a documented primary metric and a latency guardrail.

### 10.2 LLM answer evaluation

Use at least two prompt/answer-flow variants:

1. baseline RAG prompt;
2. structured grounded prompt with citation and insufficiency rules.

Evaluate at least 50 representative questions using:

- groundedness/faithfulness;
- citation correctness;
- answer relevance;
- completeness;
- unsupported-claim rate;
- appropriate refusal/insufficient-evidence behavior;
- latency and token cost.

Use an LLM-as-a-judge rubric and manually audit at least 20% of the sample. The judge model, prompt, temperature, inputs, outputs, and pipeline versions must be reproducible. Choose the production variant based on the results.

### 10.3 Component evaluation

- **Segmentation:** boundary precision/recall or an explicit human rating rubric on a reviewed sample.
- **Topic classification:** macro F1 and per-topic precision/recall on a multilabel labeled sample.
- **Agent routing:** intent/tool accuracy and tool-argument validity.
- **Analytics:** fixture-based SQL tests for exact counts, denominators, filtering, unknown values, and minimum-sample suppression.

### 10.4 Online evaluation

Track:

- thumbs-up rate and feedback reasons;
- zero-result and insufficient-evidence rate;
- click-through to evidence/source;
- query and answer latency;
- request/error volume;
- retrieval-score and result-count distributions.

Online metrics diagnose usage and regressions; they do not replace the offline golden sets.

## 11. Monitoring requirements

The monitoring page or Grafana dashboard must contain at least these charts:

1. requests per day, split by tool or page;
2. p50 and p95 end-to-end latency over time;
3. error rate over time by error class;
4. thumbs-up/down rate and feedback reasons;
5. zero-result/insufficient-evidence rate;
6. most requested topics or query clusters;
7. retrieval score or result-count distribution over time;
8. LLM token usage and estimated cost over time;
9. ingestion success/failure and duration;
10. corpus size and coverage by year/geographic group.

Each trace must carry a request ID and pipeline version. Monitoring must avoid exposing full sensitive query text by default.

## 12. Non-functional requirements

| Area | Requirement |
|---|---|
| Performance | Target p95 under 3 seconds for retrieval-only search, under 12 seconds for a generated answer, and under 3 seconds for cached/common dashboard queries on the sample corpus. |
| Reliability | Health endpoints cover API, database, and model configuration; a model failure still returns retrieved evidence when possible. |
| Reproducibility | Dependencies and image versions are pinned; seed/sample data is accessible; migrations, ingestion, evaluation, and startup commands are documented. |
| Security | Secrets stay in environment variables; SQL is parameterized; LLM tool arguments are schema-validated; user input is length-limited. |
| Observability | Structured logs and traces include request/run IDs, versions, duration, status, and safe diagnostic fields. |
| Accessibility | Core controls have labels, charts have textual summaries, and meaning is not encoded by color alone. |
| Portability | The full local application and its dependencies start through Docker Compose. |
| Maintainability | Taxonomy, prompts, models, schemas, and pipeline versions are explicit and testable. |

## 13. Proposed technical architecture

| Concern | Proposed component | Purpose |
|---|---|---|
| UI | Streamlit | Search, analytics, feedback, corpus information |
| API | FastAPI + Pydantic | Typed application and tool endpoints |
| Relational knowledge base | PostgreSQL | Metadata, transcript/bit records, analytics, traces, feedback |
| Keyword retrieval | PostgreSQL full-text search | Lexical baseline and hybrid component |
| Vector retrieval | pgvector | Semantic retrieval |
| RAG/orchestration | LangChain or small explicit Python services | Prompt assembly, model calls, and schema-constrained tools |
| Ingestion | dlt | Validated, incremental loads |
| Workflow orchestration | Kestra | Repeatable ingestion/enrichment/evaluation workflow |
| Monitoring | Grafana over PostgreSQL, or a dedicated Streamlit monitoring page | Required charts and feedback/health visibility |
| Packaging | Dockerfiles + Docker Compose | One-command local stack |
| Evaluation | Python test/evaluation package with versioned JSON/CSV fixtures | Repeatable offline comparisons |

Expected Docker Compose services are `ui`, `api`, `postgres` with pgvector, `ingestion-worker`, `kestra`, and `grafana` if Grafana is selected. One-off migration, ingestion, and evaluation jobs should also run through Compose profiles or documented container commands.

## 14. Academic requirements traceability

The distinction below matters: the course syllabus describes available techniques, while the scoring rubric states what must be evidenced. The project uses the relevant syllabus techniques without requiring every database demonstrated in the course.

| Academic criterion | Planned evidence | Target |
|---|---|---|
| Problem description | README summary plus Sections 1–3 of this PRD | 2/2 |
| Retrieval flow | PostgreSQL/pgvector knowledge base, retrieval trace, grounded LLM answer, working UI demo | 2/2 |
| Retrieval evaluation | Keyword vs vector vs hybrid vs enhanced variants with metrics and selection rationale | 2/2 |
| LLM evaluation | Baseline vs grounded prompt with LLM-judge and manual audit | 2/2 |
| Interface | Streamlit product UI and FastAPI endpoints/docs | 2/2 |
| Ingestion pipeline | Automated dlt pipeline run by Kestra, with run history and idempotence | 2/2 |
| Monitoring | Stored user feedback plus dashboard with at least five required charts | 2/2 |
| Containerization | All runtime dependencies and jobs represented in Docker Compose | 2/2 |
| Reproducibility | Accessible sample data, pinned versions, `.env.example`, setup/run/evaluation instructions | 2/2 |
| Hybrid search | Evaluated keyword/vector fusion and production use if it wins | 1/1 |
| Document reranking | Evaluated reranker and production use if it wins | 1/1 |
| User query rewriting | Structured rewrite, preserved original query, evaluation ablation | 1/1 |
| Cloud deployment | Optional public deployment with secrets and data rights handled correctly | 0–2 bonus |

### Syllabus coverage

| Course topic | Where it appears |
|---|---|
| Keyword RAG | PostgreSQL full-text baseline and grounded answer flow |
| Agentic function calling | Typed search, analytics, and coverage tools |
| Semantic/vector search | Embeddings stored and queried with pgvector |
| Minsearch/sqlitesearch/PGVector | PGVector is the selected production technology; the course does not require all alternatives |
| Kestra orchestration | Automated ingestion/enrichment/evaluation workflow |
| dlt ingestion | Incremental, idempotent loading from the selected data source |
| Filesystem and REST sources | Filesystem is required; REST is used only if a lawful stable source is selected |
| DuckDB and marimo | Not required for the product; may be used for exploratory analysis but are not substitutes for the production evaluation/dashboard |
| Offline and online evaluation | Golden-set experiments plus feedback and operational metrics |
| Live dashboards | Product analytics plus monitoring dashboard |
| LangChain | Optional implementation layer; use is documented if selected |
| Hybrid search, reranking, rewriting | Explicit evaluation variants and production selection |

## 15. Documentation and reviewer artifacts

The repository must contain:

- a concise README with problem, architecture, features, screenshots, rubric links, quick start, and example inputs/outputs;
- setup documentation including prerequisites, environment variables, migrations, ingestion, and teardown;
- data documentation with sources, access method, rights, schema, coverage, and limitations;
- architecture and data-flow documentation;
- retrieval and LLM evaluation reports with commands, fixtures, results, and selected configurations;
- monitoring screenshot(s) and metric definitions;
- API examples or generated FastAPI documentation;
- pinned Python and container dependencies;
- an `.env.example` containing names but no secrets;
- optional short preview video.

## 16. Definition of done

The capstone is done only when all of the following are true:

- [ ] A lawful, documented sample corpus is accessible to reviewers.
- [ ] Automated ingestion creates stable bits, topics, keyword indexes, and vector indexes.
- [ ] Rerunning unchanged ingestion is idempotent.
- [ ] Vibe Matcher returns filtered evidence and a grounded, cited answer.
- [ ] Cultural Horizon Scanner returns normalized, coverage-aware SQL analytics with drill-down.
- [ ] Agent tools are schema-constrained and tested.
- [ ] Retrieval evaluation compares multiple approaches and justifies the selected one.
- [ ] LLM evaluation compares multiple answer approaches and justifies the selected one.
- [ ] Segmentation, topic, routing, and analytics have component-level checks.
- [ ] Feedback is persisted and connected to request and pipeline versions.
- [ ] Monitoring has at least five working charts.
- [ ] All required services run through Docker Compose.
- [ ] A clean-machine run using the documented instructions has been verified.
- [ ] README links directly to all evidence reviewers need.

## 17. Decisions required before implementation

These are the only major product decisions still open:

1. **Dataset and rights:** identify the distributable transcript source(s) and verify permitted storage/display. This is the critical path.
2. **Regional meaning:** confirm whether the main comparison dimension should be comedian affiliation, performance location, or release market. The recommendation is comedian affiliation with a visible selector.
3. **Topic taxonomy:** approve an initial controlled list and annotation guidelines before large-scale classification.
4. **Model provider:** choose hosted OpenAI-compatible models or local models based on budget and deployment constraints.
5. **Monitoring UI:** choose Grafana for stronger operational evidence or a simpler Streamlit monitoring page.
6. **Deployment:** decide whether local Docker Compose is sufficient or whether a public cloud demo is worth the bonus scope.

## 18. Recommended delivery sequence

1. Resolve dataset rights and create a small representative corpus.
2. Define schemas, geographic semantics, topic taxonomy, and golden evaluation samples.
3. Build an idempotent ingestion slice through bit indexing.
4. Implement and evaluate retrieval baselines before building the generated answer.
5. Implement the grounded answer, agent tools, and LLM evaluation.
6. Build analytics from tested SQL and add corpus-coverage warnings.
7. Add the UI, feedback, tracing, and monitoring.
8. Complete Docker Compose, clean-machine verification, screenshots, and reviewer-facing documentation.
