"""Social listening adapters (Agent 4 backfill).

Apify exposes thousands of public actors (Instagram/TikTok/Facebook scrapers)
behind a single token: you start an actor run and poll for a dataset.
Brandwatch is a paid enterprise listening API; this ships the adapter contract
with a documented stub so keys can be dropped in later.

All providers return the same per-platform snapshot shape consumed by
``SocialMediaAgent``.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from src.config.settings import settings

logger = logging.getLogger(__name__)

APIFY_API = "https://api.apify.com/v2"


class SocialAdapter:
    def __init__(self, provider: str):
        self.provider = provider
        creds = {
            "apify": settings.APIFY_API_KEY,
            "brandwatch": settings.BRANDWATCH_API_TOKEN,
        }
        self.available = bool(creds.get(provider))

    def platform_report(self, handle: str, platform: str) -> dict[str, Any]:
        """Return a platform snapshot for one handle ({} when unsupported)."""
        if self.provider == "apify":
            return self._apify_report(handle, platform)
        if self.provider == "brandwatch":
            return self._brandwatch_report(handle)
        return {}

    # -- Apify -------------------------------------------------------------

    def _apify_report(self, handle: str, platform: str) -> dict[str, Any]:
        actors = {
            "instagram": "apify/instagram-profile-scraper",
            "tiktok": "clockworks/tiktok-scraper",
            "facebook": "gpu/facebook-page-scraper",
        }
        actor = actors.get(platform)
        if actor is None:
            return {}
        # Kick off an actor run and poll the default dataset.
        run = requests.post(
            f"{APIFY_API}/acts/{actor}/runs",
            params={"token": settings.APIFY_API_KEY},
            json={"username": handle.lstrip("@")},
            timeout=30,
        ).json()
        run_id = run.get("data", {}).get("id")
        if not run_id:
            return {}
        dataset = self._wait_for_dataset(run_id)
        return self._normalize_apify(dataset, platform)

    def _wait_for_dataset(self, run_id: str, max_wait: int = 90) -> list[dict]:
        import time

        waited = 0
        while waited < max_wait:
            status = requests.get(
                f"{APIFY_API}/actor-runs/{run_id}",
                params={"token": settings.APIFY_API_KEY},
                timeout=30,
            ).json().get("data", {}).get("status")
            if status == "SUCCEEDED":
                items = requests.get(
                    f"{APIFY_API}/actor-runs/{run_id}/dataset/items",
                    params={"token": settings.APIFY_API_KEY},
                    timeout=30,
                ).json()
                return items if isinstance(items, list) else []
            time.sleep(10)
            waited += 10
        return []

    @staticmethod
    def _normalize_apify(items: list[dict], platform: str) -> dict[str, Any]:
        if not items:
            return {}
        profile = items[0]
        return {
            "platform": platform,
            "handle": profile.get("username") or profile.get("fullName") or "",
            "followers": profile.get("followersCount") or profile.get("followers"),
            "posts": profile.get("postsCount") or profile.get("videoCount") or 0,
            "likes": profile.get("likesCount") or profile.get("total_likes") or 0,
            "engagement_estimate": profile.get("engagementRate") or 0,
            "biography": profile.get("description") or profile.get("biography") or "",
            "source": "apify",
        }

    # -- Brandwatch -----------------------------------------------------------

    def _brandwatch_report(self, handle: str) -> dict[str, Any]:
        # Documented placeholder: Brandwatch v2 requires query + dataset setup.
        logger.warning("Brandwatch report not yet wired; add query building to this method.")
        return {"platform": "brandwatch", "handle": handle, "source": "brandwatch"}