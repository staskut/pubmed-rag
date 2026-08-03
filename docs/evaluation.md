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

Results (50 questions, k=10):

| Strategy | Hit Rate | MRR |
|----------|:--------:|:---:|
| keyword | 0.300 | 0.300 |
| **vector** | **0.920** | **0.867** |
| hybrid | 0.920 | 0.857 |
| hybrid_rerank | 0.920 | 0.853 |

**Reading it:**
- **Keyword is weak (0.30)** because the questions deliberately avoid abstract wording — lexical overlap is low. This is exactly the gap semantic search closes.
- **Vector, hybrid, and hybrid_rerank are effectively tied** (0.92 hit rate; MRR within 0.014, well inside noise at n=50).
- This benchmark has **one** relevant doc per question, so it rewards *finding the seed article* (vector's strength) but **cannot measure reranking's actual benefit — a diverse, non-duplicated set of relevant sources** (shown qualitatively: plain hybrid returned 6 unique articles across 8 slots vs 8/8 for hybrid_rerank).

**Decision:** keep **`hybrid_rerank`** as the default. It is statistically tied with vector
on this metric while adding lexical robustness (exact drug names, abbreviations) and source
diversity that the single-doc metric can't capture, and it produced the top answer scores
below. Keyword-only is rejected.

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
