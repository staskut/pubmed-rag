"""End-to-end RAG flow: rewrite -> retrieve -> assemble -> generate -> log.

    from pubmed_rag.rag import answer
    result = answer("What antiemetic is most effective for PONV?")
    print(result.text)

Also runnable as a CLI:  uv run python -m pubmed_rag.rag "your question"
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field

from .db import connect
from .llm import Usage, chat
from .retrieval import STRATEGIES as _BASE_STRATEGIES, Hit
from .rerank import hybrid_rerank_search

# hybrid + cross-encoder rerank is the best-quality strategy and the default
STRATEGIES = {**_BASE_STRATEGIES, "hybrid_rerank": hybrid_rerank_search}

# Production prompt = the "structured" variant, which won the LLM-judge answer
# evaluation (see docs/evaluation.md). Keeps strong grounding/safety language.
SYSTEM = (
    "You are an anesthesiology literature assistant. Answer using ONLY the provided "
    "PubMed sources; do not rely on outside knowledge. Structure the answer as: a "
    "one-sentence bottom-line, then 2-4 bullet points of supporting evidence. Cite each "
    "claim inline with bracketed source numbers like [1], [2]. If the sources do not "
    "contain enough information, or the evidence is weak or conflicting, say so plainly "
    "instead of guessing. End with: 'This is a summary of published literature, not "
    "medical advice.'"
)

REWRITE_SYSTEM = (
    "Rewrite the user's question into a concise PubMed-style search query: keep key "
    "clinical terms, drugs, and outcomes; drop filler words. Return only the query text."
)


@dataclass
class RagResult:
    question: str
    rewritten: str
    strategy: str
    text: str
    hits: list[Hit]
    usage: Usage = field(default_factory=Usage)
    latency_ms: int = 0
    query_log_id: int | None = None


def rewrite_query(question: str) -> tuple[str, Usage]:
    text, usage = chat(
        [{"role": "system", "content": REWRITE_SYSTEM},
         {"role": "user", "content": question}],
        max_tokens=60,
    )
    return text.strip() or question, usage


def build_messages(question: str, hits: list[Hit]) -> list[dict]:
    blocks = []
    for i, h in enumerate(hits, 1):
        blocks.append(f"[{i}] {h.citation()}\n{h.content}")
    context = "\n\n".join(blocks) if blocks else "(no sources retrieved)"
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Question: {question}\n\nSources:\n{context}"},
    ]


def log_query(result: RagResult, conn) -> int:
    with conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO query_logs (question, rewritten_question, strategy, top_k, "
            "retrieved_pmids, answer, latency_ms, prompt_tokens, completion_tokens, cost_usd) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (
                result.question, result.rewritten, result.strategy, len(result.hits),
                json.dumps([h.pmid for h in result.hits]), result.text,
                result.latency_ms, result.usage.prompt_tokens,
                result.usage.completion_tokens, round(result.usage.cost_usd, 6),
            ),
        )
        return cur.fetchone()[0]


def save_feedback(query_log_id: int, rating: int, comment: str = "") -> None:
    """Persist a thumbs up/down (+1/-1) for a logged query."""
    conn = connect()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO feedback (query_log_id, rating, comment) VALUES (%s,%s,%s)",
                (query_log_id, rating, comment or None),
            )
    finally:
        conn.close()


def answer(
    question: str,
    strategy: str = "hybrid_rerank",
    k: int = 8,
    rewrite: bool = True,
    log: bool = True,
) -> RagResult:
    """Run the full RAG flow and (optionally) persist it to query_logs."""
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy {strategy!r}; choose from {list(STRATEGIES)}")
    t0 = time.perf_counter()
    usage = Usage()
    conn = connect()
    try:
        rewritten = question
        if rewrite:
            rewritten, u = rewrite_query(question)
            usage.add(u)

        search = STRATEGIES[strategy]
        hits = search(rewritten, k=k, conn=conn)

        text, u = chat(build_messages(question, hits))
        usage.add(u)

        result = RagResult(
            question=question, rewritten=rewritten, strategy=strategy,
            text=text, hits=hits, usage=usage,
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
        if log:
            result.query_log_id = log_query(result, conn)
        return result
    finally:
        conn.close()


def _main() -> None:
    q = " ".join(sys.argv[1:]) or "What is the most effective prophylaxis for PONV?"
    res = answer(q)
    print(f"\nQ: {res.question}\n(rewritten: {res.rewritten} | strategy: {res.strategy} "
          f"| {res.latency_ms} ms | ${res.usage.cost_usd:.4f})\n")
    print(res.text)
    print("\nSources:")
    for i, h in enumerate(res.hits, 1):
        print(f"  [{i}] {h.citation()}  {h.source_url}")


if __name__ == "__main__":
    _main()
