"""Agent 1 — Business Discovery.

Finds ecommerce businesses in the requested regions across many sources
(web search, directories, social/marketplace signals) and extracts a rich
contact profile: name, website, industry, products, country, city, email,
phone, social profiles, and ecommerce platform.

Because current web sources don't require API keys (DuckDuckGo), the agent
combines search snippets with a quick site fingerprint to fill the profile.
Swap/add sources inside ``search_businesses`` without touching the agent.
"""

from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel

from src.config.settings import settings
from src.schemas import (
    BusinessLead,
    DiscoveryResult,
    Platform,
)
from src.services.search import search_businesses
from src.services.scraper import scrape_website
from src.llm import get_llm_rotation
from src.utils.helpers import ask, slugify

logger = logging.getLogger(__name__)

PROMPT = """You are a business discovery scout finding ecommerce businesses in
{region}.

Raw search results are provided. Keep entries that look like operating
ecommerce businesses and extract their profile.

Return a SINGLE JSON object with this exact shape:
{{
  "leads": [
    {{
      "name": "business name",
      "country": "{region}",
      "city": "city if known, else empty string",
      "industry": "product/service vertical",
      "products": ["top product lines"],
      "url": "website url or empty string",
      "email": "contact email if visible, else empty string",
      "phone": "phone if visible, else empty string",
      "platform": "unknown|shopify|woocommerce|magento|bigcommerce|etsy|amazon|wix|squarespace|facebook_shop|instagram_shop|custom|no_website",
      "social_handles": {{"instagram": "@... or empty", "facebook": "... or empty", "tiktok": "... or empty"}},
      "description": "one line about what they sell"
    }}
  ]
}}
JSON only, no markdown.
"""


class DiscoveryAgent:
    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def run(self, regions: list[str], target: int | None = None) -> DiscoveryResult:
        """Discover leads across regions."""
        target = target or settings.DISCOVERY_TARGET
        per_region = max(1, target // max(len(regions), 1))

        leads: list[BusinessLead] = []
        for region in regions:
            logger.info("Discovering ecommerce businesses in %s", region)
            leads.extend(self._scan_region(region, per_region))

        unique = self._dedupe(leads)[:target]

        summary = (
            f"Discovered {len(unique)} unique ecommerce leads across "
            f"{len(regions)} region(s): {', '.join(regions)}. "
            f"Sources: web search + site fingerprinting."
        )
        logger.info(summary)
        return DiscoveryResult(leads=unique, summary=summary)

    # -- internal -----------------------------------------------------------

    def _scan_region(self, region: str, limit: int) -> list[BusinessLead]:
        queries = [
            f"top online ecommerce stores in {region}",
            f"popular online shops {region}",
            f"ecommerce brand home decor fashion {region}",
        ]
        collected: list[dict] = []
        for query in queries:
            collected.extend(search_businesses(query, region=region))

        # Google Maps listings (Value Serp) add real, local businesses.
        from src.services.search import maps_search

        collected.extend(maps_search("online shop", region=region, max_results=20))

        if not collected:
            logger.warning("No search results for %s", region)
            return []

        user = "Raw search results (title | url | snippet):\n" + "\n".join(
            f"- {r.get('title', '')} | {r.get('url', '')} | {r.get('snippet', '')[:200]}"
            for r in collected[:20]
        )
        parsed = ask(
            _discovery_rotation(),
            PROMPT.format(region=region),
            user,
            retries=1,
        )
        if not isinstance(parsed, dict) or "leads" not in parsed:
            logger.warning("Discovery LLM returned unusable output for %s", region)
            return []

        leads = []
        for raw in parsed["leads"][:limit]:
            name = str(raw.get("name", "")).strip()
            if not name:
                continue
            lead = BusinessLead(
                id=slugify(name),
                name=name,
                country=raw.get("country", region),
                region=region,
                city=raw.get("city", ""),
                industry=raw.get("industry", ""),
                products=[p for p in raw.get("products", []) if p],
                url=raw.get("url") or None,
                email=raw.get("email", ""),
                phone=raw.get("phone", ""),
                platform=_platform(raw.get("platform", "")),
                social_handles={k: v for k, v in (raw.get("social_handles") or {}).items() if v},
                description=raw.get("description", ""),
            )
            self._enrich(lead)
            leads.append(lead)
        return leads

    @staticmethod
    def _enrich(lead: BusinessLead) -> None:
        """Fill gaps with real site fingerprint data (cheap, one fetch)."""
        if not lead.url:
            return
        page = _scrape_with_budget(lead.url)
        if page is None:
            return
        if lead.platform is Platform.UNKNOWN and page.platform is not Platform.CUSTOM:
            lead.platform = page.platform
        if not lead.email and page.emails:
            lead.email = page.emails[0]
        if not lead.phone and page.phones:
            lead.phone = page.phones[0]
        if not lead.industry and page.title:
            # Fall back to homepage title as industry hint.
            lead.description = lead.description or page.title

    @staticmethod
    def _dedupe(leads: list[BusinessLead]) -> list[BusinessLead]:
        seen: set[str] = set()
        out = []
        for lead in leads:
            key = lead.name.lower()
            if key not in seen:
                seen.add(key)
                out.append(lead)
        return out


def _discovery_rotation():
    """Ordered providers for discovery, OpenRouter first.

    Groq (the global primary) routinely trips its tiny free-tier TPM budget on
    the big discovery prompt, so we rotate OpenRouter → groq → rest.
    """
    rotation = get_llm_rotation(role="discovery", temperature=settings.OLLAMA_TEMPERATURE)
    ordered = sorted(
        rotation,
        key=lambda c: 0 if "nemotron" in str(getattr(c, "model", "")) else 1,
    )
    return ordered


def _platform(value: str) -> Platform:
    try:
        return Platform(value.strip().lower())
    except ValueError:
        return Platform.UNKNOWN


def _scrape_with_budget(url: str, budget_s: float = 12.0):
    """Run a fingerprint scrape, aborting after ``budget_s`` so a slow or
    zombie site can't stall a whole discovery pass."""
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(scrape_website, url, 0)
        try:
            return future.result(timeout=budget_s)
        except concurrent.futures.TimeoutError:
            return None