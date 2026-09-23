"""Google PageSpeed Insights adapter (Agent 2 website metrics).

Free API: https://developers.google.com/speed/docs/insights/v5/get-started
Returns Core Web Vitals + mobile/desktop performance from real CrUX field data
where available. Used to fill the objectively-measurable website categories.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


class PageSpeedAdapter:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.available = bool(api_key)

    def analyze(self, url: str, strategy: str = "mobile") -> dict[str, Any]:
        """Fetch PSI for ``url``; returns a compact metrics dict ({} on failure)."""
        try:
            resp = requests.get(
                ENDPOINT,
                params={
                    "url": url,
                    "key": self.api_key,
                    "strategy": strategy,
                },
                timeout=60,
            )
            resp.raise_for_status()
            return self._flatten(resp.json())
        except Exception as exc:  # noqa: BLE001 - API/billing/network variability
            logger.warning("PageSpeed failed for %s: %s", url, exc)
            return {}

    @staticmethod
    def _flatten(data: dict) -> dict[str, Any]:
        lh = data.get("lighthouseResult") or {}
        cats = {name: (item.get("score") or 0) * 100
                for name, item in (lh.get("categories") or {}).items()}
        audits = lh.get("audits") or {}
        text_metrics = ("largest-contentful-paint", "first-contentful-paint",
                        "interactive", "cumulative-layout-shift", "speed-index")
        metrics: dict[str, Any] = {
            m: (audits.get(m) or {}).get("numericValue")
            for m in text_metrics
        }
        return {
            "lighthouse_categories": cats,
            "metrics": metrics,
            "cls": audits.get("cumulative-layout-shift", {}).get("displayValue", ""),
            "lcp": audits.get("largest-contentful-paint", {}).get("displayValue", ""),
            "mobile_friendly": data.get("mobile-friendliness") or True,
        }