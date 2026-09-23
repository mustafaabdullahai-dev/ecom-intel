"""Small shared helpers used across agents."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)


def compose(messages: list[str]) -> list[dict]:
    """Turn a list of prompt strings into a LangChain chat-tail-friendly list."""
    return [{"role": r, "content": c} for r, c in messages]


def strip_json_fences(text: str) -> str:
    """Remove ```json ... ``` fences that local models often add."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def try_parse_json(text: str) -> dict | None:
    """Best-effort JSON parse. Returns None on failure."""
    cleaned = strip_json_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Some models wrap with extra prose; try the first balanced block.
        try:
            return json.loads(cleaned[cleaned.find("{") : cleaned.rfind("}") + 1])
        except (json.JSONDecodeError, ValueError):
            return None


def ask(
    llm,
    system: str,
    user: str,
    *,
    return_text: bool = False,
    max_tokens: int = 0,
    retries: int = 2,
) -> str | dict[str, Any] | None:
    """Single prompt/response round trip.

    Returns parsed JSON when the system prompt asks for JSON, otherwise the
    raw text unless ``return_text`` is set.

    ``llm`` may be a single chat model or a list of providers to rotate
    through when one returns empty/unparseable output.
    """
    providers = list(llm) if isinstance(llm, (list, tuple)) else [llm]
    messages = [
        SystemMessage(content=system) if hasattr(providers[0], "bind") else collapse(system),
        HumanMessage(content=user),
    ]
    wants_json = not return_text and _looks_like_json_request(system)

    last_raw: str | None = None
    for pi, provider in enumerate(providers):
        chain = provider | StrOutputParser()
        for attempt in range(retries + 1):
            raw: str | None = None
            try:
                raw = _to_str(chain.invoke(messages))
            except Exception as exc:  # provider hiccup handled by fallbacks too
                logger.warning(
                    "ask() invoke %s/%s attempt %d failed: %s",
                    pi + 1, len(providers), attempt + 1, exc,
                )
            if not raw or not raw.strip():
                last_raw = raw or ""
                if attempt < retries:
                    logger.warning(
                        "ask() %s/%s got empty output, retrying (%d/%d)",
                        pi + 1, len(providers), attempt + 1, retries,
                    )
                    continue
                break

            last_raw = raw
            if not wants_json or return_text:
                return raw
            parsed = try_parse_json(raw)
            if parsed is not None:
                return parsed
            if attempt < retries:
                logger.warning(
                    "ask() %s/%s failed to parse JSON, retrying (%d/%d)",
                    pi + 1, len(providers), attempt + 1, retries,
                )
        if pi + 1 < len(providers):
            logger.warning(
                "ask() %s/%s exhausted retries; rotating to next provider",
                pi + 1, len(providers),
            )

    return last_raw


def as_str_list(value: Any, default: list[str] | None = None) -> list[str]:
    """Coerce an LLM field into a list of strings.

    Models sometimes return a string where a list is expected. If the value
    is already a list, each item is stringified. If it's a string, it's split
    on common delimiters and kept as a single-element list on failure.
    """
    if value is None:
        return list(default) if default else []
    if isinstance(value, list):
        return [_to_str(item) for item in value if _to_str(item).strip()]
    if isinstance(value, (tuple, set)):
        return [_to_str(item) for item in value if _to_str(item).strip()]
    if isinstance(value, dict):
        return [_to_str(item) for item in value.values() if _to_str(item).strip()]
    text = _to_str(value)
    if re.search(r"[,;\n]", text):
        return [part.strip() for part in re.split(r"[,;\n]+", text) if part.strip()]
    return [text.strip()] if text.strip() else (list(default) if default else [])


def _to_str(value: Any) -> str:
    """Safely stringify model output (str vs list content parts vs accessors)."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return "".join(_to_str(part) for part in value)
    if isinstance(value, dict):
        content = value.get("content", value.get("text", ""))
        return _to_str(content if content else list(value.values()))
    try:
        return str(value)
    except Exception:
        return ""


def collapse(text: str) -> SystemMessage:
    return SystemMessage(content=text)


def _looks_like_json_request(system: str) -> bool:
    return "json" in system.lower()


def slugify(name: str) -> str:
    """Turn a business name into a stable id-friendly slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "unknown"


def top_n(items: list[Any], key: str, n: int) -> list[Any]:
    """Return the top ``n`` items sorted by a numeric attribute."""
    return sorted(items, key=lambda x: x.model_dump().get(key, 0), reverse=True)[:n]