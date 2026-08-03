"""Evaluate answer quality with an LLM-as-a-judge across prompt variants.

Generates answers for a sample of questions under several system-prompt variants
(same retrieval), then a judge model scores each 1-5 on groundedness, relevance,
and completeness. The best-scoring prompt is the one we ship (rubric: multiple
approaches evaluated).

Run: uv run python -m pubmed_rag.evaluation.answer_eval --n 15
"""
from __future__ import annotations

import argparse
import json

from tqdm import tqdm

from ..db import connect
from ..llm import chat
from ..rag import STRATEGIES, build_messages
from .ground_truth import load

OUT = "data/eval/answer_results.json"

# --- prompt variants under test (kept explicit so re-runs stay comparable) --
VARIANT_CONCISE = (
    "You are a careful assistant that answers anesthesiology questions using ONLY the "
    "provided PubMed sources. Use only the sources; cite every claim inline like [1], [2]. "
    "If the sources are insufficient, say so plainly. Be concise and clinical. "
    "End with: 'This is a summary of published literature, not medical advice.'"
)

VARIANT_STRUCTURED = (
    "You are an anesthesiology literature assistant. Answer using ONLY the provided "
    "sources. Structure the answer as: a one-sentence bottom-line, then 2-4 bullet points "
    "of supporting evidence. Cite each claim inline as [1], [2]. If evidence is weak or "
    "conflicting, state that explicitly. End with: 'This is a summary of published "
    "literature, not medical advice.'"
)

VARIANT_TERSE = (
    "Answer the anesthesiology question using ONLY the sources, in at most three sentences, "
    "with inline citations [1], [2]. If the sources are insufficient, say so. "
    "End with: 'This is a summary of published literature, not medical advice.'"
)

VARIANTS = {
    "concise": VARIANT_CONCISE,
    "structured": VARIANT_STRUCTURED,
    "terse": VARIANT_TERSE,
}

# --- judge ------------------------------------------------------------------
JUDGE_SYSTEM = (
    "You are a strict expert anesthesiologist grading an AI answer. Given the QUESTION, "
    "the SOURCES the AI was given, and its ANSWER, score three dimensions as integers 1-5:\n"
    "- groundedness: are all claims supported by the sources (no hallucination)?\n"
    "- relevance: does it directly answer the question?\n"
    "- completeness: does it capture the key evidence available in the sources?\n"
    'Return strict JSON: {"groundedness": int, "relevance": int, "completeness": int}.'
)


def judge(question: str, context: str, answer: str) -> dict:
    text, _ = chat(
        [{"role": "system", "content": JUDGE_SYSTEM},
         {"role": "user", "content": f"QUESTION:\n{question}\n\nSOURCES:\n{context}\n\nANSWER:\n{answer}"}],
        response_format={"type": "json_object"},
        max_tokens=60,
    )
    try:
        d = json.loads(text)
        return {k: int(d.get(k, 0)) for k in ("groundedness", "relevance", "completeness")}
    except (json.JSONDecodeError, ValueError, TypeError):
        return {"groundedness": 0, "relevance": 0, "completeness": 0}


def evaluate(n: int = 15, strategy: str = "hybrid_rerank", k: int = 6) -> dict:
    questions = [item["question"] for item in load()[:n]]
    search = STRATEGIES[strategy]
    conn = connect()
    # accumulate per-variant dimension sums
    agg = {v: {"groundedness": 0.0, "relevance": 0.0, "completeness": 0.0} for v in VARIANTS}
    try:
        for q in tqdm(questions, desc="judging answers"):
            hits = search(q, k=k, conn=conn)
            base = build_messages(q, hits)          # [system, user]
            context = base[1]["content"]
            for vname, vsystem in VARIANTS.items():
                ans, _ = chat([{"role": "system", "content": vsystem}, base[1]])
                scores = judge(q, context, ans)
                for dim, val in scores.items():
                    agg[vname][dim] += val
    finally:
        conn.close()

    n_q = len(questions)
    results = {}
    for v, sums in agg.items():
        means = {d: round(s / n_q, 3) for d, s in sums.items()}
        means["overall"] = round(sum(means.values()) / 3, 3)
        results[v] = means
    best = max(results, key=lambda v: results[v]["overall"])

    payload = {"n": n_q, "strategy": strategy, "results": results, "best_variant": best}
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"\nAnswer evaluation on {n_q} questions (strategy={strategy}), 1-5 scale:\n")
    print(f"  {'variant':<14}{'ground':>9}{'relev':>9}{'complete':>10}{'overall':>9}")
    print("  " + "-" * 51)
    for v, m in results.items():
        star = "  <- best" if v == best else ""
        print(f"  {v:<14}{m['groundedness']:>9}{m['relevance']:>9}"
              f"{m['completeness']:>10}{m['overall']:>9}{star}")
    print(f"\nBest prompt variant: {best}. Saved to {OUT}")
    return payload


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=15)
    ap.add_argument("--strategy", default="hybrid_rerank")
    ap.add_argument("--k", type=int, default=6)
    evaluate(**vars(ap.parse_args()))
