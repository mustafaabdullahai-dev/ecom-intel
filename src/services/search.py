"""Web search service.

DuckDuckGo is the default (free, no key). When a SERP provider is configured
(Value Serp / DataForSEO) it is used for cleaner, more reliable JSON results,
plus native Google Maps business discovery.

Each result is normalized into a plain dict so downstream agents can consume
it without caring about the source.
"""

from __future__ import annotations

import logging
import traceback

from langchain_core.tools import tool
from langchain_core.tools.structured import StructuredTool

logger = logging.getLogger(__name__)


def search_businesses(query: str, region: str = "", max_results: int = 8) -> list[dict]:
    """Search the web for ecommerce businesses matching ``query``.

    Returns a list of dicts with keys: title, url, snippet, source.
    """
    adapter = _serp()
    if adapter is not None:
        return adapter.web_search(query, region, max_results) or _ddg(query, region, max_results)
    return _ddg(query, region, max_results)


def maps_search(query: str, region: str = "", max_results: int = 8) -> list[dict]:
    """Google Maps business listings (requires a Value Serp API key)."""
    adapter = _serp()
    if adapter is None:
        return []
    try:
        return adapter.maps_search(query, region, max_results)
    except Exception:  # pragma: no cover - API dependent
        logger.warning("Maps search failed; returning empty list.")
        return []


def fetch_site_text(url: str) -> str:
    """Readable text for a URL via the anti-bot fetch layer (used by agents)."""
    from src.services.fetcher import get_fetcher, readable_text

    try:
        result = get_fetcher().fetch(url)
        return readable_text(result.html) if result else ""
    except Exception:  # pragma: no cover - network dependent
        return ""


def _serp():
    from src.services.sources import serp_adapter

    try:
        return serp_adapter()
    except Exception:  # pragma: no cover - defensive
        return None


def _ddg(query: str, region: str, max_results: int) -> list[dict]:
    try:
        from ddgs import DDGS

        results: list[dict] = []
        with DDGS() as ddgs:
            for r in ddgs.text(
                f"ecommerce online store {query} {region}".strip(),
                max_results=max_results,
            ):
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", ""),
                        "source": "duckduckgo",
                    }
                )
        return results
    except Exception:  # pragma: no cover - network dependent
        logger.warning("Search failed: %s", traceback.format_exc())
        return []


# Exposed as a LangChain tool so it can be injected into agent toolkits.
search_tool = StructuredTool.from_function(search_businesses)