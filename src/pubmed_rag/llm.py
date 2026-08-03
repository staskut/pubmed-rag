"""Thin OpenAI wrapper: embeddings + chat, with token/cost bookkeeping.

Kept small on purpose so the rest of the code depends on a stable surface
(`embed_texts`, `chat`) rather than the OpenAI SDK directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import config

# USD per 1M tokens (as of 2025); used for rough cost logging, not billing.
_PRICING = {
    "text-embedding-3-small": {"input": 0.02},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}

_client: OpenAI | None = None


def client() -> OpenAI:
    global _client
    if _client is None:
        if not config.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set — add it to .env to use embeddings/generation."
            )
        _client = OpenAI(api_key=config.openai_api_key)
    return _client


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0

    def add(self, other: "Usage") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.cost_usd += other.cost_usd


def _cost(model: str, prompt: int, completion: int) -> float:
    p = _PRICING.get(model, {})
    return prompt / 1e6 * p.get("input", 0.0) + completion / 1e6 * p.get("output", 0.0)


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=20))
def embed_texts(texts: list[str]) -> tuple[list[list[float]], Usage]:
    """Embed a batch of texts; returns vectors and usage."""
    resp = client().embeddings.create(model=config.embed_model, input=texts)
    vectors = [d.embedding for d in resp.data]
    used = resp.usage.prompt_tokens
    return vectors, Usage(prompt_tokens=used, cost_usd=_cost(config.embed_model, used, 0))


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0][0]


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=20))
def chat(messages: list[dict], temperature: float = 0.0, **kwargs) -> tuple[str, Usage]:
    """Chat completion; returns text and usage."""
    resp = client().chat.completions.create(
        model=config.chat_model, messages=messages, temperature=temperature, **kwargs
    )
    u = resp.usage
    usage = Usage(
        prompt_tokens=u.prompt_tokens,
        completion_tokens=u.completion_tokens,
        cost_usd=_cost(config.chat_model, u.prompt_tokens, u.completion_tokens),
    )
    return resp.choices[0].message.content or "", usage
