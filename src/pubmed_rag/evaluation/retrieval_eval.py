"""Evaluate retrieval strategies against the ground-truth set.

Metrics (relevance is the single source PMID per question):
  * Hit Rate@k — fraction of questions where the relevant PMID appears in top-k.
  * MRR       — mean reciprocal rank of the relevant PMID.

Runs every strategy so the best can be chosen (rubric: multiple approaches).

Run: uv run python -m pubmed_rag.evaluation.retrieval_eval --k 10
"""
from __future__ import annotations

import argparse
import json

import json
import os

from ..db import connect
from ..rag import STRATEGIES, rewrite_query  # includes keyword/vector/hybrid/hybrid_rerank
from .ground_truth import load

STRATEGY_ORDER = ["keyword", "vector", "hybrid", "hybrid_rerank"]
OUT = "data/eval/retrieval_results.json"
REWRITE_CACHE = "data/eval/rewrites.json"


def _rewrites(gt: list[dict]) -> dict[str, str]:
    """Rewritten form of each question (cached, since it costs LLM calls)."""
    cache = json.load(open(REWRITE_CACHE)) if os.path.exists(REWRITE_CACHE) else {}
    changed = False
    for item in gt:
        q = item["question"]
        if q not in cache:
            cache[q] = rewrite_query(q)[0]
            changed = True
    if changed:
        json.dump(cache, open(REWRITE_CACHE, "w"), indent=2)
    return cache


def _rank_of(pmid: str, hits) -> int | None:
    """1-based rank of the first hit whose article == pmid (dedup by pmid)."""
    seen, rank = set(), 0
    for h in hits:
        if h.pmid in seen:
            continue
        seen.add(h.pmid)
        rank += 1
        if h.pmid == pmid:
            return rank
    return None


def evaluate(k: int = 10, gt_path: str | None = None, rewrite: bool = False) -> dict:
    gt = load(gt_path) if gt_path else load()
    rewrites = _rewrites(gt) if rewrite else {}
    conn = connect()
    results: dict[str, dict] = {}
    try:
        for strat in STRATEGY_ORDER:
            search = STRATEGIES[strat]
            hits_sum = rr_sum = 0.0
            for item in gt:
                query = rewrites[item["question"]] if rewrite else item["question"]
                hits = search(query, k=k, conn=conn)
                rank = _rank_of(item["pmid"], hits)
                if rank:
                    hits_sum += 1
                    rr_sum += 1.0 / rank
            n = len(gt)
            results[strat] = {"hit_rate": hits_sum / n, "mrr": rr_sum / n, "n": n}
    finally:
        conn.close()

    best = max(results, key=lambda s: results[s]["mrr"])
    out_path = OUT.replace(".json", "_rewrite.json") if rewrite else OUT
    payload = {"k": k, "query_rewriting": rewrite, "results": results, "best_strategy": best}
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    label = "rewritten queries" if rewrite else "raw questions"
    print(f"\nRetrieval evaluation on {len(gt)} {label} (k={k}):\n")
    print(f"  {'strategy':<16}{'Hit Rate':>10}{'MRR':>10}")
    print("  " + "-" * 36)
    for strat in STRATEGY_ORDER:
        r = results[strat]
        star = "  <- best" if strat == best else ""
        print(f"  {strat:<16}{r['hit_rate']:>10.3f}{r['mrr']:>10.3f}{star}")
    print(f"\nBest strategy by MRR: {best}. Saved to {out_path}")
    return payload


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--gt", dest="gt_path", default=None)
    ap.add_argument("--rewrite", action="store_true",
                    help="rewrite each question first (mirrors the production RAG path)")
    evaluate(**vars(ap.parse_args()))
