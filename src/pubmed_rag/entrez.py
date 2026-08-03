"""Fetch and normalize anesthesiology literature from NCBI.

Two data sources, per the PRD:
  * PubMed (Entrez E-utilities) -> title, abstract, metadata for breadth.
  * PubMed Central Open Access (BioC API) -> full text for depth, where available.

The public entry point is :func:`iter_articles`, a generator of normalized
article dicts. It is deliberately independent of dlt/Postgres so it can be
tested on its own.
"""
from __future__ import annotations

import time
from typing import Iterator

import requests
from lxml import etree
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import config

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
BIOC = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json"

EFETCH_BATCH = 200  # PubMed efetch handles ~200 ids per request comfortably

_session = requests.Session()
_session.headers.update({"User-Agent": f"{config.tool} (mailto:{config.email})"})


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=20))
def _get(url: str, params: dict | None = None, timeout: int = 60) -> requests.Response:
    resp = _session.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    time.sleep(config.rate_delay)  # respect NCBI rate limits
    return resp


# --------------------------------------------------------------------------- #
# Step 1: search -> post the result set to the history server
# --------------------------------------------------------------------------- #
def search(query: str) -> tuple[int, str, str]:
    """Run esearch with history. Returns (count, webenv, query_key)."""
    params = {
        "db": "pubmed",
        "term": query,
        "usehistory": "y",
        "retmode": "json",
        **config.eutils_params,
    }
    data = _get(f"{EUTILS}/esearch.fcgi", params).json()["esearchresult"]
    return int(data["count"]), data["webenv"], data["querykey"]


# --------------------------------------------------------------------------- #
# Step 2: fetch PubMed records in batches and parse the XML
# --------------------------------------------------------------------------- #
def _text(node, path: str) -> str:
    el = node.find(path)
    return el.text.strip() if el is not None and el.text else ""


def _abstract(article) -> str:
    """Concatenate (possibly structured) AbstractText nodes, keeping labels."""
    parts: list[str] = []
    for at in article.findall(".//Abstract/AbstractText"):
        text = "".join(at.itertext()).strip()
        if not text:
            continue
        label = at.get("Label")
        parts.append(f"{label}: {text}" if label else text)
    return "\n\n".join(parts)


def _authors(article) -> list[str]:
    out = []
    for a in article.findall(".//AuthorList/Author"):
        last = _text(a, "LastName")
        initials = _text(a, "Initials")
        collective = _text(a, "CollectiveName")
        if last:
            out.append(f"{last} {initials}".strip())
        elif collective:
            out.append(collective)
    return out


def _pub_year(article) -> str:
    for path in (".//JournalIssue/PubDate/Year", ".//JournalIssue/PubDate/MedlineDate"):
        val = _text(article, path)
        if val:
            return val[:4]
    return ""


def _article_ids(pubmed_article) -> dict[str, str]:
    ids = {}
    for aid in pubmed_article.findall(".//PubmedData/ArticleIdList/ArticleId"):
        if aid.text:
            ids[aid.get("IdType", "")] = aid.text.strip()
    return ids


def parse_pubmed_xml(xml_bytes: bytes) -> list[dict]:
    """Parse an efetch PubmedArticleSet into normalized records."""
    root = etree.fromstring(xml_bytes)
    records = []
    for pa in root.findall("PubmedArticle"):
        article = pa.find(".//Article")
        if article is None:
            continue
        ids = _article_ids(pa)
        pmid = _text(pa, ".//MedlineCitation/PMID")
        mesh = [
            _text(mh, "DescriptorName")
            for mh in pa.findall(".//MeshHeadingList/MeshHeading")
        ]
        records.append(
            {
                "pmid": pmid,
                "pmcid": ids.get("pmc", ""),
                "doi": ids.get("doi", ""),
                "title": "".join(article.find("ArticleTitle").itertext()).strip()
                if article.find("ArticleTitle") is not None
                else "",
                "abstract": _abstract(article),
                "authors": _authors(article),
                "journal": _text(article, ".//Journal/Title"),
                "pub_year": _pub_year(article),
                "mesh_terms": [m for m in mesh if m],
                "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            }
        )
    return records


def fetch_pubmed_batch(webenv: str, query_key: str, retstart: int, retmax: int) -> list[dict]:
    params = {
        "db": "pubmed",
        "query_key": query_key,
        "WebEnv": webenv,
        "retstart": retstart,
        "retmax": retmax,
        "retmode": "xml",
        **config.eutils_params,
    }
    resp = _get(f"{EUTILS}/efetch.fcgi", params)
    return parse_pubmed_xml(resp.content)


# --------------------------------------------------------------------------- #
# Step 3: enrich with PMC Open Access full text
# --------------------------------------------------------------------------- #
# Passage sections we drop: they add noise, not answerable content.
_SKIP_SECTIONS = {"REF", "TABLE", "FIG", "COMP_INT", "ABBR", "ACK_FUND", "AUTH_CONT"}


def fetch_full_text(pmcid: str) -> str:
    """Return concatenated body full text for a PMC id, or '' if unavailable."""
    if not pmcid:
        return ""
    num = pmcid.replace("PMC", "")
    try:
        resp = _get(f"{BIOC}/PMC{num}/unicode", timeout=90)
        docs = resp.json()
    except Exception:
        return ""  # not in OA set / transient issue -> abstract-only fallback
    parts: list[str] = []
    for doc in docs if isinstance(docs, list) else [docs]:
        for passage in doc.get("documents", [{}])[0].get("passages", []) \
                if "documents" in doc else doc.get("passages", []):
            section = (passage.get("infons", {}) or {}).get("section_type", "").upper()
            if section in _SKIP_SECTIONS:
                continue
            text = (passage.get("text") or "").strip()
            if text:
                parts.append(text)
    return "\n\n".join(parts)


# --------------------------------------------------------------------------- #
# Public generator
# --------------------------------------------------------------------------- #
def iter_articles(
    query: str | None = None,
    max_articles: int | None = None,
    with_full_text: bool = True,
    seen: set[str] | None = None,
) -> Iterator[dict]:
    """Yield normalized article records for a single PubMed query.

    ``seen`` is an optional set of PMIDs already emitted; matching records are
    skipped and new ones are added to it (used to dedup across passes).
    """
    query = query or config.full_query
    cap = config.max_articles if max_articles is None else max_articles
    seen = seen if seen is not None else set()

    count, webenv, query_key = search(query)
    # We may skip duplicates, so scan more than `cap` records to still reach it.
    scan_limit = count if cap in (0, None) else count

    emitted = 0
    for start in range(0, scan_limit, EFETCH_BATCH):
        for rec in fetch_pubmed_batch(webenv, query_key, start, EFETCH_BATCH):
            if rec["pmid"] in seen:
                continue
            seen.add(rec["pmid"])
            if with_full_text and rec["pmcid"]:
                rec["full_text"] = fetch_full_text(rec["pmcid"])
            else:
                rec["full_text"] = ""
            rec["has_full_text"] = bool(rec["full_text"])
            yield rec
            emitted += 1
            if cap and emitted >= cap:
                return


def iter_corpus(specs: list[tuple[str, int]], with_full_text: bool = True) -> Iterator[dict]:
    """Yield a deduped corpus across several (query, max) passes.

    A shared ``seen`` set guarantees each PMID (and its full-text fetch) is
    emitted at most once, even when passes overlap.
    """
    seen: set[str] = set()
    for query, cap in specs:
        yield from iter_articles(
            query=query, max_articles=cap, with_full_text=with_full_text, seen=seen
        )
