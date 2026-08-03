"""Seed synthetic monitoring data so the Grafana dashboard is meaningful in a demo.

Inserts realistic query_logs + feedback spread over the last 7 days. This is
DEMO data — use --clear to wipe existing logs first. Real usage from the app
accumulates in the same tables.

Run: uv run python -m pubmed_rag.seed_monitoring --n 150 --clear
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta, timezone

from .db import connect

STRATEGIES = (["hybrid_rerank"] * 6) + (["hybrid"] * 2) + ["vector", "keyword"]

FALLBACK_QUESTIONS = [
    "What is the most effective prophylaxis for postoperative nausea and vomiting?",
    "Does sugammadex reduce residual neuromuscular blockade versus neostigmine?",
    "What dexmedetomidine dose is used for pediatric procedural sedation?",
    "How does a lumbar wedge affect hypotension during cesarean under spinal anesthesia?",
    "Is opioid-free anesthesia associated with less postoperative nausea?",
    "What is the analgesic efficacy of the erector spinae plane block?",
    "Does intraoperative ketamine reduce chronic postsurgical pain?",
    "What are the risks of high epidural sufentanil doses in labor analgesia?",
]


def _questions() -> list[str]:
    try:
        with open("data/eval/ground_truth.jsonl") as f:
            qs = [json.loads(line)["question"] for line in f if line.strip()]
        return qs or FALLBACK_QUESTIONS
    except FileNotFoundError:
        return FALLBACK_QUESTIONS


def seed(n: int = 150, clear: bool = False, seed_value: int = 42) -> None:
    rng = random.Random(seed_value)
    questions = _questions()
    now = datetime.now(timezone.utc)

    conn = connect()
    try:
        with conn, conn.cursor() as cur:
            if clear:
                cur.execute("TRUNCATE feedback, query_logs RESTART IDENTITY CASCADE")

            for _ in range(n):
                # bias timestamps toward business hours over the last 7 days
                day = rng.randint(0, 6)
                hour = int(rng.triangular(8, 20, 14))
                ts = (now - timedelta(days=day)).replace(
                    hour=hour, minute=rng.randint(0, 59), second=rng.randint(0, 59)
                )
                strat = rng.choice(STRATEGIES)
                q = rng.choice(questions)
                # keyword path is cheaper/faster; generative paths cost tokens
                if strat == "keyword":
                    latency, pt, ct = rng.randint(150, 500), 0, 0
                else:
                    latency = int(rng.gauss(7000, 1500))
                    pt, ct = rng.randint(2800, 5200), rng.randint(120, 320)
                cost = round(pt / 1e6 * 0.15 + ct / 1e6 * 0.60, 6)

                cur.execute(
                    "INSERT INTO query_logs (question, rewritten_question, strategy, top_k, "
                    "retrieved_pmids, answer, latency_ms, prompt_tokens, completion_tokens, "
                    "cost_usd, ts) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                    (q, q, strat, 8, json.dumps([]), "(demo answer)",
                     max(latency, 80), pt, ct, cost, ts),
                )
                qid = cur.fetchone()[0]

                # ~60% of queries get feedback; ~80% of that is positive
                if rng.random() < 0.60:
                    rating = 1 if rng.random() < 0.80 else -1
                    cur.execute(
                        "INSERT INTO feedback (query_log_id, rating, comment, ts) "
                        "VALUES (%s,%s,%s,%s)",
                        (qid, rating, None, ts + timedelta(seconds=rng.randint(5, 90))),
                    )

            cur.execute("SELECT count(*) FROM query_logs")
            total = cur.fetchone()[0]
    finally:
        conn.close()
    print(f"Seeded {n} queries. query_logs now has {total} rows.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--clear", action="store_true")
    seed(n=ap.parse_args().n, clear=ap.parse_args().clear)
