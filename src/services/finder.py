"""On-demand business discovery used by the "Find businesses" tab.

Purpose-built alternative to the nightly DiscoveryAgent: the user picks a
keyword, optionally constrains the region (or searches the whole world), an
industry, a hosting platform (e.g. Shopify) and a result limit, then we run
one self-contained discovery pass: web search + maps search, dedupe, a light
scrape to fingerprint the platform and pull contacts, then ship structured
rows straight to the UI and a branded findings PDF.
"""

from __future__ import annotations

import logging
import re as _re
from urllib.parse import urlparse
from src.schemas import BusinessLead, Platform
from src.services.search import maps_search, search_businesses
from src.services.scraper import scrape_website

logger = logging.getLogger(__name__)


# Normalised (lower) → canonical platform, used to honour the platform filter
# even when the scraper reports a close variant (e.g. woo -> woocommerce).
PLATFORM_ALIASES: dict[str, str] = {
    "shopify": "shopify",
    "woocommerce": "woocommerce",
    "woo": "woocommerce",
    "wordpress": "woocommerce",
    "magento": "magento",
    "wix": "wix",
    "squarespace": "squarespace",
    "bigcommerce": "bigcommerce",
    "opencart": "opencart",
    "prestashop": "prestashop",
    "shopifyplus": "shopify",
    "amazon": "amazon",
    "etsy": "etsy",
    "webflow": "webflow",
}


def _to_platform(raw: str) -> str:
    return PLATFORM_ALIASES.get(str(raw or "").strip().lower(), str(raw or "unknown").lower())


def _dedupe(rows: list[dict]) -> list[dict]:
    """Drop repeated origins while preserving order and best source."""
    seen: set[str] = set()
    out: list[dict] = []
    for r in rows:
        host = (urlparse(str(r.get("url") or "")).netloc or r.get("url") or "").lower().replace("www.", "")
        key = host or str(r.get("title") or "").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def find_businesses(
    keyword: str,
    region: str = "",
    industry: str = "",
    platform: str = "",
    limit: int = 20,
) -> list[BusinessLead]:
    """Discover ecommerce businesses matching ``keyword`` (+optional filters).

    Returns up to ``limit`` :class:`BusinessLead` rows, enriched with a
    fingerprint platform and (when the scrape succeeds) contact data.
    """
    keyword = (keyword or "").strip()
    if not keyword:
        raise ValueError("keyword is required")

    # Keep a generous pool so the platform/industry filters can cut it down
    # and still land on the requested limit.
    pool_limit = max(limit * 8, 30)
    queries = [keyword]
    if industry and industry.lower() not in ("all", "any"):
        queries.append(f"{keyword} {industry}")
    if platform and platform.lower() not in ("all", "any"):
        queries.append(f"{keyword} {platform} online store ltd")

    results: list[dict] = []
    for q in queries:
        try:
            results += search_businesses(q, region, pool_limit)
        except Exception as exc:  # pragma: no cover - network error path
            logger.warning("web search failed for %r: %s", q, exc)
        try:
            results += maps_search(q, region, min(pool_limit, 12))
        except Exception as exc:  # pragma: no cover
            logger.warning("maps search failed for %r: %s", q, exc)

    results = _dedupe(results)

    leads: list[BusinessLead] = []
    for row in results[: min(len(results), limit * 2)]:
        url = str(row.get("url") or "").strip()
        title = str(row.get("title") or "").strip() or (urlparse(url).netloc if url else "") or ""
        name = title or url
        try:
            page = scrape_website(url)
        except Exception as exc:  # pragma: no cover - scrape is best-effort
            logger.warning("scrape failed for %s: %s", url, exc)
            page = None

        detected = _to_platform(page.platform.name if (page and page.platform) else "unknown")
        if platform and platform.lower() not in ("all", "any"):
            if detected not in ("unknown", platform.lower()) and not PLATFORM_ALIASES.get(platform.lower()) == detected:
                detected_lk = platform.lower()
                if detected not in (detected_lk, PLATFORM_ALIASES.get(detected_lk, "")):
                    continue

        try:
            host = urlparse(url).netloc
        except Exception:  # pragma: no cover
            host = url
        region_field = region
        lead = BusinessLead(
            id=_re.sub(r"[^a-z0-9]+", "-", name.lower())[:60].strip("-") or host,
            name=name[:160],
            country="",
            region=region_field,
            industry=industry,
            platform=Platform(detected.lower()) if detected.lower() in Platform._value2member_map_ else Platform.UNKNOWN,
            url=url,
            email=(page.emails[0] if page and page.emails else ""),
            phone=(page.phones[0] if page and page.phones else ""),
            description=str(row.get("snippet") or "")[:400],
            source=str(row.get("source") or "web_search"),
        )
        leads.append(lead)
        if len(leads) >= limit:
            break

    return leads


def outreach_message(lead: BusinessLead) -> str:
    """A short, friendly outreach line for a freshly found lead."""
    who = lead.name.strip() or lead.url or "the business"
    return (
        f"Hi {who} team — I came across your online store while researching "
        f"{lead.industry or 'ecommerce businesses'} in {lead.region or 'your area'}. "
        "I run a free AI-based website audit focused on conversion, SEO and trust "
        "signals for stores like yours; would you like a quick summary and a PDF "
        "report? Happy to send it over — no strings attached."
    )
