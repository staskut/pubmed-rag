"""Central configuration, loaded from environment / .env."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    return int(raw) if raw else default


@dataclass(frozen=True)
class Config:
    # NCBI Entrez
    email: str = os.getenv("NCBI_EMAIL", "").strip()
    api_key: str = os.getenv("NCBI_API_KEY", "").strip()
    tool: str = os.getenv("NCBI_TOOL", "pubmed-rag").strip()

    # Corpus definition
    query: str = os.getenv(
        "PUBMED_QUERY", "(Anesthesia[MeSH] OR Anesthetics[MeSH] OR Analgesia[MeSH])"
    ).strip()
    date_from: str = os.getenv("PUBMED_DATE_FROM", "2015").strip()
    date_to: str = os.getenv("PUBMED_DATE_TO", "2025").strip()
    max_articles: int = _int("PUBMED_MAX_ARTICLES", 200)

    # OpenAI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    embed_model: str = os.getenv("EMBED_MODEL", "text-embedding-3-small").strip()
    chat_model: str = os.getenv("CHAT_MODEL", "gpt-4o-mini").strip()
    embed_dim: int = _int("EMBED_DIM", 1536)

    @property
    def full_query(self) -> str:
        """PubMed query with the publication-date window applied."""
        return f"({self.query}) AND {self.date_from}:{self.date_to}[dp]"

    @property
    def eutils_params(self) -> dict[str, str]:
        """Shared params NCBI asks every request to carry."""
        p = {"tool": self.tool}
        if self.email:
            p["email"] = self.email
        if self.api_key:
            p["api_key"] = self.api_key
        return p

    @property
    def rate_delay(self) -> float:
        """Seconds to wait between requests (10/s with key, 3/s without)."""
        return 0.11 if self.api_key else 0.34


config = Config()
