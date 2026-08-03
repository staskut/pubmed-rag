# Evaluation

Two evaluations, matching the rubric: **retrieval** (which search strategy) and
**answer quality** (which prompt). Both compare multiple approaches and the winner is
what the app ships. Everything here is reproducible from the commands shown.

## Ground-truth set

`ground_truth.py` samples 50 articles deterministically (`ORDER BY md5(pmid)`) and asks
the LLM to write one natural clinical question each article answers — without copying
abstract phrasing. The article's PMID is the single relevant document.

```bash
uv run python -m pubmed_rag.evaluation.ground_truth --n 50
```

Output: `data/eval/ground_truth.jsonl` — e.g.
> *"What is the recommended maximum dose of epidural sufentanil to avoid high placental concentrations during labor analgesia?"* → PMID 39963603

## Retrieval evaluation

Each strategy retrieves top-k; we score **Hit Rate@k** (relevant PMID in top-k) and
**MRR** (mean reciprocal rank), deduping by article.

```bash
uv run python -m pubmed_rag.evaluation.retrieval_eval --k 10
```

Results on the **raw question** (50 questions, k=10):

| Strategy | Hit Rate | MRR |
|----------|:--------:|:---:|
| keyword | 0.760 | 0.532 |
| vector | 0.920 | 0.867 |
| hybrid | 0.920 | 0.799 |
| **hybrid_rerank** | **0.940** | **0.882** |

**Decision:** ship **`hybrid_rerank`** — it has the best hit rate *and* MRR, and (unlike the
single-doc metric can show) returns a de-duplicated, diverse source set (8/8 unique articles
vs 6/8 for plain hybrid on a sample query).

### Why keyword was originally weak — and the fix

Our first run scored keyword at **0.30 / 0.30**. Diagnosing it revealed the cause was *query
semantics*, not a weakness of lexical search: `websearch_to_tsquery` **ANDs every term**, so
a ~11-word question required all terms in one ~400-token chunk — **66% of questions matched
zero chunks** (avg 0.7 chunks matched). Switching to an **OR** query (`to_tsquery` with `|`,
ranked by `ts_rank_cd`) lifted keyword to **0.76 / 0.53**, and — because the keyword arm now
contributes to the fusion — pushed `hybrid_rerank` ahead of vector.

| Keyword variant | Hit Rate | MRR |
|---|:--:|:--:|
| AND (`websearch_to_tsquery`, original) | 0.30 | 0.30 |
| **OR (`to_tsquery` with `\|`, shipped)** | **0.76** | **0.53** |

### Query rewriting (the production path)

Retrieval eval above uses the raw question, but the app **rewrites the query first**
(`rag.answer` → `rewrite_query`). Re-running with rewriting (`--rewrite`) mirrors production:

| Strategy | raw HR / MRR | +rewrite HR / MRR |
|----------|:---:|:---:|
| keyword (OR) | 0.76 / 0.53 | 0.82 / 0.55 |
| vector | 0.92 / 0.87 | 0.90 / 0.85 |
| hybrid | 0.92 / 0.80 | 0.90 / 0.79 |
| **hybrid_rerank** | 0.94 / 0.88 | **0.94 / 0.93** |

Rewriting **helps the lexical/hybrid arms** (condensing to salient terms) but **slightly
hurts pure vector** (the full question is already good semantic input). The production combo,
**rewrite + hybrid_rerank, is the best configuration at MRR 0.93.** Reproduce with:

```bash
uv run python -m pubmed_rag.evaluation.retrieval_eval --k 10            # raw
uv run python -m pubmed_rag.evaluation.retrieval_eval --k 10 --rewrite  # production path
```

## Answer evaluation (LLM-as-a-judge)

Three system-prompt variants (`concise`, `structured`, `terse`), same retrieval and
sources, each answer scored 1–5 on groundedness, relevance, completeness by a judge model.

```bash
uv run python -m pubmed_rag.evaluation.answer_eval --n 15
```

Results (15 questions, `hybrid_rerank`):

| Prompt | Groundedness | Relevance | Completeness | Overall |
|--------|:---:|:---:|:---:|:---:|
| concise | 4.93 | 5.0 | 4.73 | 4.889 |
| **structured** | **5.0** | **5.0** | **4.87** | **4.956** |
| terse | 4.93 | 5.0 | 4.73 | 4.889 |

**Decision:** ship the **`structured`** prompt (bottom-line + supporting bullets). It edges
out the others on completeness and groundedness. All variants score >4.8/5, indicating the
retrieved context reliably grounds the answers.

## Limitations / honesty notes

- Ground-truth questions are LLM-generated; spot-checked but not clinician-verified.
- One relevant doc per question understates hybrid/rerank value (see above).
- The judge is the same model family as the generator — a known optimism bias; scores are
  useful for *relative* prompt comparison, less so as absolute quality.
