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

from ..db import connect
from ..rag import STRATEGIES  # includes keyword/vector/hybrid/hybrid_rerank
from .ground_truth import load

STRATEGY_ORDER = ["keyword", "vector", "hybrid", "hybrid_rerank"]
OUT = "data/eval/retrieval_results.json"


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


def evaluate(k: int = 10, gt_path: str | None = None) -> dict:
    gt = load(gt_path) if gt_path else load()
    conn = connect()
    results: dict[str, dict] = {}
    try:
        for strat in STRATEGY_ORDER:
            search = STRATEGIES[strat]
            hits_sum = rr_sum = 0.0
            for item in gt:
                hits = search(item["question"], k=k, conn=conn)
                rank = _rank_of(item["pmid"], hits)
                if rank:
                    hits_sum += 1
                    rr_sum += 1.0 / rank
            n = len(gt)
            results[strat] = {"hit_rate": hits_sum / n, "mrr": rr_sum / n, "n": n}
    finally:
        conn.close()

    best = max(results, key=lambda s: results[s]["mrr"])
    payload = {"k": k, "results": results, "best_strategy": best}
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"\nRetrieval evaluation on {len(gt)} questions (k={k}):\n")
    print(f"  {'strategy':<16}{'Hit Rate':>10}{'MRR':>10}")
    print("  " + "-" * 36)
    for strat in STRATEGY_ORDER:
        r = results[strat]
        star = "  <- best" if strat == best else ""
        print(f"  {strat:<16}{r['hit_rate']:>10.3f}{r['mrr']:>10.3f}{star}")
    print(f"\nBest strategy by MRR: {best}. Saved to {OUT}")
    return payload


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--gt", dest="gt_path", default=None)
    evaluate(**vars(ap.parse_args()))
