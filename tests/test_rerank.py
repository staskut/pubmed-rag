from pubmed_rag import rerank
from pubmed_rag.retrieval import Hit


def _hit(pmid, content, cid):
    return Hit(chunk_id=cid, pmid=pmid, section="body", content=content,
               title=f"t{pmid}", journal="j", pub_year=2025, source_url="u", score=0.0)


class _FakeEncoder:
    """Returns a score per document equal to its length (deterministic)."""
    def __init__(self, scores):
        self._scores = scores

    def rerank(self, query, docs):
        return self._scores


def test_rerank_dedupes_by_pmid_and_orders_by_score(monkeypatch):
    hits = [
        _hit("A", "a1", 1),
        _hit("A", "a2", 2),   # duplicate article, lower score -> dropped
        _hit("B", "b1", 3),
        _hit("C", "c1", 4),
    ]
    # scores align to hits order: A=0.9, A=0.5, B=0.8, C=0.1
    monkeypatch.setattr(rerank, "_model", lambda: _FakeEncoder([0.9, 0.5, 0.8, 0.1]))
    out = rerank.rerank_hits("q", hits, top_n=3)
    assert [h.pmid for h in out] == ["A", "B", "C"]      # deduped, score-ordered
    assert out[0].score == 0.9 and out[1].score == 0.8   # scores applied
    assert len({h.pmid for h in out}) == len(out)         # all unique


def test_rerank_respects_top_n(monkeypatch):
    hits = [_hit(p, p, i) for i, p in enumerate("ABCDE")]
    monkeypatch.setattr(rerank, "_model", lambda: _FakeEncoder([0.5, 0.4, 0.3, 0.2, 0.1]))
    assert len(rerank.rerank_hits("q", hits, top_n=2)) == 2


def test_rerank_empty():
    assert rerank.rerank_hits("q", [], top_n=5) == []
