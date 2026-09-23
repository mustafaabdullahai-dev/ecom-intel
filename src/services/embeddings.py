"""Embedding provider for the semantic memory (Agents 6/7 + /similar).

Provider is selected by ``EMBEDDING_PROVIDER``:
  - "gemini"             -> Google Gemini text-embedding-004 (free tier) [default]
  - "openai-compatible"  -> any OpenAI /embeddings endpoint (set own key/base)
  - "ollama"             -> local Ollama (requires ollama serve running)

Returns an empty list on any failure so callers degrade gracefully.
"""

from __future__ import annotations

import logging

import requests

from src.config.settings import settings

logger = logging.getLogger(__name__)

_EMBEDDING_MODEL = settings.EMBEDDING_MODEL
_EMBEDDING_DIM = settings.EMBEDDING_DIM


def embed_text(text: str) -> list[float]:
    """Return the embedding vector for ``text`` (empty on failure)."""
    if not text or not text.strip():
        return []
    provider = settings.EMBEDDING_PROVIDER
    try:
        if provider == "gemini":
            return _gemini_embed(text)
        if provider == "openai-compatible":
            return _openai_embed(text)
        return _ollama_embed(text)
    except Exception as exc:  # noqa: BLE001 - any provider may be down/misconfigured
        logger.warning("Embedding failed (%s): %s", provider, exc)
        return []


def _gemini_embed(text: str) -> list[float]:
    if not settings.GEMINI_API_KEY:
        logger.warning("EMBEDDING_PROVIDER=gemini but GEMINI_API_KEY is empty.")
        return []
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{_EMBEDDING_MODEL}:embedContent"
    )
    resp = requests.post(
        url,
        params={"key": settings.GEMINI_API_KEY},
        json={
            "model": f"models/{_EMBEDDING_MODEL}",
            "content": {"parts": [{"text": text[:24000]}]},
            "outputDimensionality": _EMBEDDING_DIM,
        },
        timeout=30,
    )
    resp.raise_for_status()
    values = (resp.json().get("embedding") or {}).get("values") or []
    return [float(v) for v in values][:_EMBEDDING_DIM]


def _openai_embed(text: str) -> list[float]:
    api_key = settings.OPENAI_API_KEY or settings.GEMINI_API_KEY
    base = settings.OPENAI_BASE_URL or settings.GEMINI_BASE_URL
    if not api_key:
        logger.warning("OpenAI-compatible embeddings configured but no API key set.")
        return []
    resp = requests.post(
        f"{base.rstrip('/')}/embeddings",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": _EMBEDDING_MODEL, "input": text[:24000]},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json().get("data") or []
    return [float(v) for v in (data[0].get("embedding") or [])][:_EMBEDDING_DIM]


def _ollama_embed(text: str) -> list[float]:
    import ollama

    resp = ollama.embeddings(model=_EMBEDDING_MODEL, prompt=text[:6000])
    return resp.get("embedding", [])[:_EMBEDDING_DIM]


def build_index(text: str, chunk_size: int = 900, overlap: int = 100) -> list[list[float]]:
    """Embed a long text in overlapping chunks (one vector per chunk)."""
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        chunks.append(embed_text(text[start:start + chunk_size]))
        start += chunk_size - overlap
    return [v for v in chunks if v]