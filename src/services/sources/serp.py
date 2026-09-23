"""SERP + Google Maps adapter for structured lead discovery.

Value Serp (https://www.valueserp.com) exposes Google Web + Maps search as
clean JSON with one API key. DataForSEO is accepted as an alternative provider
with a documented (but untested) payload shape — switch the env var, drop in
the credentials, and the same adapter contract holds.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from src.config.settings import settings

logger = logging.getLogger(__name__)

WEB_QUERY_ENDPOINT = "https://api.valueserp.com/search"
MAPS_QUERY_ENDPOINT = "https://api.valueserp.com/search"


class SerpAdapter:
    """Structured web + maps search returning normalized lead dicts."""

    def __init__(self, provider: str = "value_serp"):
        self.provider = provider
        self.available = (
            bool(settings.VALUE_SERP_API_KEY) if provider == "value_serp"
            else bool(settings.DATA_FOR_SEO_USER and settings.DATA_FOR_SEO_PASSWORD)
        )

    # -- web search --------------------------------------------------------

    def web_search(self, query: str, region: str = "", max_results: int = 8) -> list[dict]:
        if self.provider == "value_serp":
            payload = self._value_serp_web(query, region, max_results)
        else:
            payload = self._data_for_seo_web(query, region, max_results)
        results: list[dict] = []
        for item in payload or []:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", item.get("url", "")),
                "snippet": item.get("snippet", ""),
                "source": f"{self.provider}_serp",
            })
        return results

    # -- google maps --------------------------------------------------------

    def maps_search(self, query: str, region: str = "", max_results: int = 8) -> list[dict]:
        """Google Maps business listings for the target locality."""
        if self.provider != "value_serp":
            logger.warning("Maps search only implemented for Value Serp.")
            return []
        resp = requests.get(
            MAPS_QUERY_ENDPOINT,
            params={
                "api_key": settings.VALUE_SERP_API_KEY,
                "engine": "google_maps",
                "search_type": "places",
                "q": f"{query} {region}".strip(),
                "num": max_results,
            },
            timeout=settings.FETCH_TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json()
        places = (body.get("local_results") or {})
        results: list[dict] = []
        for place in places if isinstance(places, list) else (places.get("places") or []):
            results.append({
                "title": place.get("title", ""),
                "url": place.get("link", place.get("website", "")),
                "snippet": place.get("category", ""),
                "phone": place.get("phone", place.get("phone_number", "")),
                "address": place.get("address", ""),
                "rating": place.get("rating", 0),
                "review_count": place.get("reviews", 0),
                "source": "value_serp_maps",
            })
        return results[:max_results]

    # -- providers ----------------------------------------------------------

    def _value_serp_web(self, query: str, region: str, max_results: int) -> list[dict]:
        resp = requests.get(
            WEB_QUERY_ENDPOINT,
            params={
                "api_key": settings.VALUE_SERP_API_KEY,
                "q": f"ecommerce online store {query} {region}".strip(),
                "num": max_results,
            },
            timeout=settings.FETCH_TIMEOUT,
        )
        resp.raise_for_status()
        return (resp.json().get("organic_results") or [])[:max_results]

    def _data_for_seo_web(self, query: str, region: str, max_results: int) -> list[dict]:
        # DataForSEO REST v3: /v3/dataforseo_labs/google/organic/list is the
        # best-fit endpoint; this ships an explicit (documented) placeholder.
        url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
        headers = {
            "Authorization": "Basic " + _basic_auth(settings.DATA_FOR_SEO_USER,
                                                    settings.DATA_FOR_SEO_PASSWORD),
            "Content-Type": "application/json",
        }
        payload = [{
            "keyword": f"ecommerce online store {query} {region}".strip(),
            "location_name": region or "United States",
            "language_name": "English",
            "limit": max_results,
        }]
        resp = requests.post(url, headers=headers, json=payload, timeout=settings.FETCH_TIMEOUT)
        resp.raise_for_status()
        tasks = (resp.json().get("tasks") or [])
        items: list[Any] = []
        for task in tasks:
            for res in task.get("result") or []:
                items.extend(res.get("items") or [])
        return [i for i in items if i.get("type") == "organic"]


def _basic_auth(user: str, password: str) -> str:
    import base64
    return base64.b64encode(f"{user}:{password}".encode()).decode()