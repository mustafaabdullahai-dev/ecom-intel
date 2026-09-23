"""LLM-authored score rationales.

The 14 scores themselves stay deterministic (src.scoring). This module adds a
qualitative layer on top: for every dimension the LLM reads the *exact inputs*
that produced the score and explains, in plain business language, why the score
came out that way — plus a sentiment, the ranked drivers, and a fix.

Output is forced through a structured parser so the UI always receives the
same shape regardless of which provider answered:

    {
      "overall": {"headline": str, "sentiment": str, "rationale": str},
      "dimensions": {
        "website": {"headline": str, "sentiment": str, "rationale": str,
                     "drivers": [str], "fix": str},
        ...
      }
    }

Results are cached to data/rationales.json keyed by business id.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config.settings import settings
from src.llm import REMOTE_PROVIDERS, _PROVIDER_PRIORITY
from src.services.explain import DIMENSION_META, SCORE_DIMENSIONS
from src.utils.helpers import as_str_list, ask, try_parse_json

logger = logging.getLogger(__name__)

_CACHE_FILE = Path(settings.DATA_DIR) / "rationales.json"
_LOCK = threading.Lock()

SENTIMENTS = ("positive", "neutral", "negative", "critical")


def _system_prompt() -> str:
    keys = ", ".join(SCORE_DIMENSIONS)
    return f"""You are a senior ecommerce growth consultant writing the reasoning behind a scored audit.

You receive a business profile and its 14 deterministic scores (0-100), each
with the exact inputs that produced it. For every dimension, explain WHY the
score is what it is, grounded in those inputs.

Rules:
- Use plain business language. Reference the real inputs by name and value.
- Be specific and analytical; never generic filler.
- Do NOT mention numeric thresholds, scoring bands, formulas, or the words
  "dragging"/"lifting" — explain causes, not arithmetic.
- sentiment: one of positive, neutral, negative, critical.
- headline: <= 10 words. rationale: 2-3 sentences. drivers: exactly 2 short
  cause phrases, most impactful first. fix: one short sentence.
- Keep every string brief so the JSON is never truncated.
- The "overall" entry summarises the business's digital position across all 14.

Return JSON only (no markdown) with exactly this shape:
{{
  "overall": {{"headline": "", "sentiment": "", "rationale": ""}},
  "dimensions": {{
    "<dimension_key>": {{"headline": "", "sentiment": "", "rationale": "", "drivers": ["", ""], "fix": ""}}
  }}
}}
Include every one of these dimension keys: {keys}.
JSON only.
"""


def _str_field(record: dict, *names: str) -> str:
    for n in names:
        v = record.get(n)
        if v:
            return str(v)
    return ""


def build_evidence(record: dict) -> str:
    """Render a compact, input-level evidence bundle for the LLM."""
    name = _str_field(record, "business_name", "name") or "Unknown business"
    bid = _str_field(record, "business_id", "id")
    lines = [
        f"BUSINESS: {name} ({bid})",
        "Industry: {i} | Region: {r} | Platform: {p} | URL: {u}".format(
            i=_str_field(record, "industry") or "—",
            r=_str_field(record, "region") or "—",
            p=_str_field(record, "platform") or "—",
            u=_str_field(record, "website_url", "url") or "—",
        ),
    ]
    summary = _str_field(record, "ai_summary")
    if summary:
        lines.append(f"AI summary: {summary[:600]}")
    notes = _str_field(record, "notes")
    if notes:
        lines.append(f"Sales/qualification notes: {notes[:400]}")

    lines.append("")
    lines.append("SCORES (0-100) with the exact inputs behind each:")

    expl = record.get("score_explanations") or {}
    for i, dim in enumerate(SCORE_DIMENSIONS, start=1):
        meta = DIMENSION_META.get(dim, {})
        score = int(record.get(dim) or 0)
        lines.append("")
        lines.append(f"{i}. {meta.get('label', dim)} — score {score}/100")
        what = meta.get("what")
        if what:
            lines.append(f"   measures: {what}")
        entry = expl.get(dim) if isinstance(expl, dict) else None
        inputs = []
        if isinstance(entry, dict):
            raw = entry.get("inputs") or entry.get("contributors") or []
            for c in raw:
                if not isinstance(c, dict):
                    continue
                label = c.get("label") or c.get("name") or c.get("key")
                if label is None:
                    continue
                inputs.append(f"{label} {int(c.get('value') or 0)}")
        if inputs:
            lines.append("   inputs: " + "; ".join(inputs[:14]))
        else:
            lines.append("   inputs: (no sub-score detail stored for this scan)")
    return "\n".join(lines)


def _rationale_clients() -> list[Any]:
    """Provider clients with a real output budget (the shared factory caps low).

    Ordered primary-first so a healthy provider answers on the first pass.
    """
    from langchain_openai import ChatOpenAI

    primary = settings.FALLBACK_PROVIDER
    order = [primary, *[p for p in _PROVIDER_PRIORITY if p != primary]]
    clients = []
    for provider in order:
        cfg = REMOTE_PROVIDERS.get(provider)
        if not cfg:
            continue
        api_key = getattr(settings, str(cfg["api_key"]), None) or settings.OPENAI_API_KEY
        if not api_key:
            continue
        roles = cfg.get("roles") or {}
        clients.append(
            ChatOpenAI(
                model=roles.get("recommendation", cfg["default"]),
                api_key=api_key,
                base_url=settings.GEMINI_BASE_URL if provider == "gemini" else cfg["base_url"],
                temperature=0.2,
                timeout=45,
                max_retries=0,
                max_tokens=6000,
            )
        )
    return clients


def _balance_json(text: str) -> Any:
    """Best-effort recovery for JSON that was cut off by a token limit."""
    start = text.find("{")
    if start < 0:
        return None
    s = text[start:]
    stack: list[str] = []
    in_str = False
    esc = False
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]" and stack:
            stack.pop()
    out = s + ('"' if in_str else "")
    for opener in reversed(stack):
        out += "}" if opener == "{" else "]"
    try:
        return json.loads(out)
    except (json.JSONDecodeError, ValueError):
        return None


def _norm_sentiment(value: Any) -> str:
    s = str(value or "").strip().lower()
    if not s:
        return "neutral"
    if any(k in s for k in ("critical", "severe", "at risk", "failing", "alarming")):
        return "critical"
    if any(k in s for k in ("negative", "poor", "weak", "bad", "concerning", "inadequate")):
        return "negative"
    if any(k in s for k in ("positive", "strong", "excellent", "healthy", "good", "solid")):
        return "positive"
    return "neutral"


def _norm_dim(entry: Any) -> dict[str, Any]:
    if not isinstance(entry, dict):
        return {
            "headline": "",
            "sentiment": "neutral",
            "rationale": str(entry or "").strip(),
            "drivers": [],
            "fix": "",
        }
    return {
        "headline": str(entry.get("headline") or entry.get("title") or entry.get("verdict") or "").strip(),
        "sentiment": _norm_sentiment(entry.get("sentiment")),
        "rationale": str(
            entry.get("rationale")
            or entry.get("reason")
            or entry.get("why")
            or entry.get("explanation")
            or ""
        ).strip(),
        "drivers": as_str_list(entry.get("drivers") or entry.get("key_drivers") or entry.get("causes"))[:5],
        "fix": str(
            entry.get("fix")
            or entry.get("recommendation")
            or entry.get("action")
            or entry.get("next_step")
            or ""
        ).strip(),
    }


def parse_rationale(raw: Any, keys: list[str] | None = None) -> dict[str, Any]:
    """Structured-output parser — normalise any provider response into shape.

    Accepts a dict, a JSON string, or fenced markdown; tolerates dimension keys
    at the top level or nested under "dimensions"; coerces sentiments, driver
    lists and missing fields.
    """
    keys = keys or SCORE_DIMENSIONS
    data: Any = raw
    if not isinstance(data, dict):
        text = str(raw or "")
        data = try_parse_json(text)
        if not isinstance(data, dict):
            data = _balance_json(text)
    if not isinstance(data, dict):
        data = {}

    dims_raw = data.get("dimensions") if isinstance(data.get("dimensions"), dict) else None
    if dims_raw is None:
        dims_raw = {k: data.get(k) for k in keys if k in data}
    if not isinstance(dims_raw, dict):
        dims_raw = {}

    dimensions: dict[str, Any] = {}
    for k in keys:
        if k in dims_raw and dims_raw[k] is not None:
            dimensions[k] = _norm_dim(dims_raw[k])

    overall_raw = data.get("overall") if isinstance(data.get("overall"), dict) else {}
    overall = _norm_dim(overall_raw)
    if not overall["rationale"] and isinstance(data.get("summary"), str):
        overall["rationale"] = data["summary"].strip()

    return {"overall": {k: overall[k] for k in ("headline", "sentiment", "rationale")}, "dimensions": dimensions}


def generate_rationales(record: dict) -> dict[str, Any]:
    """Ask the LLM to explain every dimension from its inputs."""
    evidence = build_evidence(record)
    raw = ask(_rationale_clients(), _system_prompt(), evidence, retries=1)
    parsed = parse_rationale(raw)
    parsed["business_id"] = _str_field(record, "business_id", "id")
    parsed["scanned_at"] = _str_field(record, "scanned_at")
    parsed["generated_at"] = datetime.now(timezone.utc).isoformat()
    return parsed


# --------------------------------------------------------------------------- #
# Cache
# --------------------------------------------------------------------------- #


def _read_cache() -> dict[str, Any]:
    if not _CACHE_FILE.exists():
        return {}
    try:
        return json.loads(_CACHE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def load_cached(business_id: str) -> dict[str, Any] | None:
    return _read_cache().get(business_id)


def save_cached(business_id: str, payload: dict[str, Any]) -> None:
    with _LOCK:
        cache = _read_cache()
        cache[business_id] = payload
        try:
            _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = _CACHE_FILE.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(cache, indent=2))
            tmp.replace(_CACHE_FILE)
        except OSError as exc:  # noqa: BLE001 - cache is best-effort
            logger.warning("Could not persist rationale cache: %s", exc)
