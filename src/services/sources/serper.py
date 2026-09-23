"""Serper.dev adapter — SERP + Google Maps for lead discovery.

Serper (https://serper.dev) returns Google results as JSON with one API key.
Same normalized dict contract as the other SERP providers.

Endpoints:
  POST https://google.serper.dev/search   -> organic/web results
  POST https://google.serper.dev/maps     -> local business listings
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from src.config.settings import settings

logger = logging.getLogger(__name__)

SEARCH_ENDPOINT = "https://google.serper.dev/search"
MAPS_ENDPOINT = "https://google.serper.dev/maps"


class SerperAdapter:
    """Structured web + maps search via Serper.dev."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or settings.SERPER_API_KEY
        self.available = bool(self.api_key)

    def _post(self, url: str, body: dict) -> dict[str, Any]:
        resp = requests.post(
            url,
            json=body,
            headers={
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json",
            },
            timeout=settings.FETCH_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    # -- web search --------------------------------------------------------

    def web_search(self, query: str, region: str = "", max_results: int = 8) -> list[dict]:
        gl = _country_code(region)
        body = {"q": f"ecommerce online store {query} {region}".strip(), "num": max_results}
        if gl:
            body["gl"] = gl
        payload = self._post(SEARCH_ENDPOINT, body)
        results: list[dict] = []
        for item in payload.get("organic") or []:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": "serper",
            })
        return results[:max_results]

    # -- google maps --------------------------------------------------------

    def maps_search(self, query: str, region: str = "", max_results: int = 8) -> list[dict]:
        body = {"q": f"{query} {region}".strip()}
        gl = _country_code(region)
        if gl:
            body["gl"] = gl
        payload = self._post(MAPS_ENDPOINT, body)
        results: list[dict] = []
        for place in payload.get("places") or []:
            results.append({
                "title": place.get("title", ""),
                "url": place.get("website") or "",
                "snippet": place.get("category", place.get("description", "")),
                "phone": place.get("phoneNumber", place.get("phone", "")),
                "address": place.get("address", ""),
                "rating": place.get("rating", 0),
                "review_count": place.get("reviewsCount", place.get("reviews", 0)),
                "source": "serper_maps",
            })
        return results[:max_results]


def _country_code(region: str) -> str:
    """Crude region -> country code for Serper's ``gl`` param (best effort)."""
    if not region:
        return ""
    region_l = region.lower()
    for name, code in (
        ("egypt", "eg"), ("dubai", "ae"), ("uae", "ae"), ("saudi", "sa"),
        ("usa", "us"), ("united states", "us"), ("uk", "uk"),
        ("germany", "de"), ("france", "fr"), ("turkey", "tr"),
        ("china", "cn"), ("india", "in"), ("pakistan", "pk"),
        ("qatar", "qa"), ("kuwait", "kw"), ("morocco", "ma"),
    ):
        if name in region_l:
            return code
    return ""