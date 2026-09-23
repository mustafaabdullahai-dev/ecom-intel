"""SEO dataset adapters (Agent 2/3 backfill).

Plug in one of:

  - Ahrefs   v2 API     (apiv2.ahrefs.com)   — backlinks, organic keywords
  - SEMrush   v3 API     (SEMRush)           — organic + paid traffic
  - Moz       URL Metric API (linkscape)     — domain authority, backlinks

Each provider exposes the same compact ``site_report(url)`` dict so the agents
can consume backlinks / organic keywords / domain authority uniformly. When no
provider is configured the agents simply score from the scraped page.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from src.config.settings import settings

logger = logging.getLogger(__name__)


class SeoAdapter:
    def __init__(self, provider: str):
        self.provider = provider
        creds = {
            "ahrefs": settings.AHREFS_API_KEY,
            "semrush": settings.SEMRUSH_API_KEY,
            "moz": settings.MOZ_ACCESS_ID and settings.MOZ_SECRET_KEY,
        }
        self.available = bool(creds.get(provider))

    def site_report(self, url: str) -> dict[str, Any]:
        """Return uniform SEO signals for ``url`` ({} on failure/missing)."""
        fn = getattr(self, f"_report_{self.provider}", None)
        if fn is None:
            return {}
        try:
            return fn(url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("SEO %s failed for %s: %s", self.provider, url, exc)
            return {}

    # -- Ahrefs --------------------------------------------------------------

    def _report_ahrefs(self, url: str) -> dict[str, Any]:
        # DOC_REFS: we query the "backlinks overview" + "organic keywords".
        domain = _domain(url)
        headers = {"Authorization": f"Bearer {settings.AHREFS_API_KEY}"}
        backlinks = requests.get(
            f"{settings.AHREFS_API_LINK}/site_metrics",
            params={"target": domain, "metrics": "domain_rating,backlinks"},
            headers=headers, timeout=30,
        ).json().get("result", {})
        keywords = requests.get(
            f"{settings.AHREFS_API_LINK}/organic_keywords",
            params={"target": domain, "limit": 5, "order_by": "position:asc"},
            headers=headers, timeout=30,
        ).json().get("result", {})
        return {
            "backlinks": backlinks.get("backlinks") or 0,
            "domain_rating": backlinks.get("domain_rating") or 0,
            "organic_keywords": len(keywords.get("organic_keywords") or []),
        }

    # -- SEMrush -------------------------------------------------------------

    def _report_semrush(self, url: str) -> dict[str, Any]:
        domain = _domain(url)
        resp = requests.get(
            "https://api.semrush.com/",
            params={
                "type": "domain_organic",
                "key": settings.SEMRUSH_API_KEY,
                "domain": domain,
                "display_limit": 5,
                "export_columns": "Ph,Po,Nq,Nr,Ad",
            },
            timeout=30,
        )
        resp.raise_for_status()
        rows = resp.text.strip().splitlines()
        return {
            "organic_keywords": len(rows[1:]) if len(rows) > 1 else 0,
            "raw_sample": rows[1:4],
        }

    # -- Moz ---------------------------------------------------------------

    def _report_moz(self, url: str) -> dict[str, Any]:
        # Moz URL Metrics v2 free tier: one field per call, batched here.
        domain = _domain(url)
        cols = "url,domain_authority,page_authority,external_links"
        resp = requests.post(
            "https://lsapi.seomoz.com/v2/url_metrics",
            json={"collections": ["top_pages", "root_domain", "url"], "target": domain},
            headers=self._moz_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        top = (data.get("results") or [{}])[0]
        return {
            "domain_authority": top.get("domain_authority") or 0,
            "page_authority": top.get("page_authority") or 0,
            "external_links": top.get("external_links") or 0,
        }

    def _moz_headers(self) -> dict[str, str]:
        # Moz HMAC-SHA1 signature (expires in 5 minutes).
        import base64
        import hashlib
        import hmac

        expires = str(int(time.time()) + 300)
        sig = hmac.new(
            settings.MOZ_SECRET_KEY.encode(),
            encode(f"{settings.MOZ_ACCESS_ID}\n{expires}"),
            hashlib.sha1,
        ).digest()
        return {
            "Authorization": "Basic " + base64.b64encode(
                encode(f"{settings.MOZ_ACCESS_ID}:{sig.decode('latin1')}")
            ).decode(),
        }


def _domain(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url if "://" in url else f"https://{url}")
    return (parsed.netloc or parsed.path).lower().lstrip("www.")


def encode(s: str) -> bytes:
    return s.encode("utf-8")