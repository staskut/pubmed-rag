"""Generate a labeled evaluation set: (question -> relevant PMID).

For a sample of articles we ask the LLM to write one natural clinical question
that the article answers. The article's PMID is the ground-truth relevant
document, so retrieval can be scored with Hit Rate / MRR.

Sampling is deterministic (`ORDER BY md5(pmid)`) so the set is reproducible.

Run: uv run python -m pubmed_rag.evaluation.ground_truth --n 50
"""
from __future__ import annotations

import argparse
import json
import os

from tqdm import tqdm

from ..db import connect
from ..llm import chat

OUT = "data/eval/ground_truth.jsonl"

GEN_SYSTEM = (
    "You write benchmark questions to evaluate a medical literature search engine. "
    "Given a paper's title and abstract, write ONE specific, natural clinical question "
    "that this paper answers — the kind an anesthesiologist would type. Focus on the main "
    "finding (drug, dose, comparison, or outcome). Do NOT copy phrases verbatim from the "
    "abstract, and do not mention the study itself. Return only the question."
)


def sample_articles(n: int) -> list[tuple[str, str, str]]:
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pmid, title, abstract FROM articles "
                "WHERE length(abstract) > 400 ORDER BY md5(pmid) LIMIT %s",
                (n,),
            )
            return cur.fetchall()
    finally:
        conn.close()


def generate(n: int = 50, out: str = OUT) -> None:
    os.makedirs(os.path.dirname(out), exist_ok=True)
    rows = sample_articles(n)
    written = 0
    with open(out, "w") as f:
        for pmid, title, abstract in tqdm(rows, desc="generating questions"):
            q, _ = chat(
                [{"role": "system", "content": GEN_SYSTEM},
                 {"role": "user", "content": f"Title: {title}\n\nAbstract: {abstract}"}],
                max_tokens=60,
            )
            q = q.strip().strip('"')
            if q:
                f.write(json.dumps({"question": q, "pmid": pmid, "title": title}) + "\n")
                written += 1
    print(f"Wrote {written} question/PMID pairs to {out}")


def load(path: str = OUT) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--out", default=OUT)
    generate(**vars(ap.parse_args()))
