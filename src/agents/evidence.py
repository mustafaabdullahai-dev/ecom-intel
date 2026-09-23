"""Shared per-business evidence pack.

The deepdive worker scrapes AND searches ONCE per business, then hands the
resulting ``Evidence`` to every intelligence agent. This avoids hammering the
site with one request per agent and gives agents a consistent picture.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.schemas import BusinessLead
from src.services.scraper import ScrapedPage, scrape_website
from src.services.search import search_businesses

logger = logging.getLogger(__name__)

EVIDENCE_QUERIES = (
    "reviews complaints",
    "pricing discount promo",
    "social media followers news",
    "competitors similar brands",
)


@dataclass
class Evidence:
    lead: BusinessLead
    page: ScrapedPage | None
    snippets: list[dict] = field(default_factory=list)
    memory: list[dict] = field(default_factory=list)  # semantic neighbors from pgvector

    # -- formatting ----------------------------------------------------------

    def website_block(self) -> str:
        """Site-derived signals (scraper output), safe for prompts."""
        if self.page is None:
            return "No scraped website (offline, blocked, or no URL)."
        p = self.page
        lines = [
            f"URL: {p.url}",
            f"Platform fingerprint: {p.platform.value} ({', '.join(p.html_hits) or 'none'})",
            f"SSL/HTTPS: {p.has_ssl}",
            f"Load time: {p.load_time_ms} ms",
            f"Broken links: {p.broken_links}/{p.checked_links} checked",
            f"Has shop signals: {p.has_shop} | Checkout: {p.has_checkout}",
            f"Trust words seen: {p.has_trust_signals} | Contact pages: {p.has_contact_pages}",
            f"Emails found: {', '.join(p.emails) or 'none'}",
            f"Phones found: {', '.join(p.phones) or 'none'}",
        ]
        if p.title:
            lines.append(f"Title: {p.title}")
        if p.text:
            lines.append(f"Content preview: {p.text[:1800]}")
        return "\n".join(lines)

    def context_block(self) -> str:
        """Business identity + web snippets for market-level agents."""
        lead = self.lead
        lines = [
            f"Business: {lead.name} | {lead.industry or 'unknown industry'} | "
            f"{lead.city}, {lead.region}, {lead.country}",
            f"Products: {', '.join(lead.products) or 'unknown'}",
            f"Website: {lead.url or 'none'} | Platform: {lead.platform.value}",
            f"Email: {lead.email or 'unknown'} | Phone: {lead.phone or 'unknown'}",
            f"Socials: {', '.join(f'{k}={v}' for k, v in lead.social_handles.items()) or 'unknown'}",
            f"Description: {lead.description or 'n/a'}",
        ]
        if self.snippets:
            lines.append("Web snippets:")
            for r in self.snippets[:12]:
                lines.append(
                    f"- {r.get('title', '')} | {r.get('url', '')} | "
                    f"{r.get('snippet', '')[:220]}"
                )
        if self.memory:
            lines.append("Similar prior observations (semantic memory):")
            for m in self.memory[:5]:
                lines.append(f"- [{m.get('source','')}] {m.get('content','')[:220]}")
        return "\n".join(lines)


def gather_evidence(lead: BusinessLead) -> Evidence:
    """One scrape + one set of search snippets per business."""
    page = scrape_website(lead.url) if lead.url else None

    snippets: list[dict] = []
    for suffix in EVIDENCE_QUERIES:
        try:
            snippets.extend(
                search_businesses(f"{lead.name} {lead.industry} {suffix}".strip(),
                                  region=lead.region, max_results=4)
            )
        except Exception:  # pragma: no cover - network dependent
            logger.debug("Evidence search failed for %s", lead.name)

    evidence = Evidence(lead=lead, page=page, snippets=snippets)
    _recall_semantic_memory(evidence)
    return evidence


def _recall_semantic_memory(evidence: Evidence) -> None:
    """Optional pgvector memory: persist this scan's text, recall similar items.

    No-op when DATABASE_URL is unset — the pipeline is fully local.
    """
    try:
        from src.services.db import memory

        mem = memory()
        if not mem.enabled:
            return
        chunks = []
        if evidence.page and evidence.page.text:
            chunks.append(evidence.page.text[:3000])
        for r in evidence.snippets[:10]:
            body = r.get("snippet") or r.get("title") or ""
            if body:
                chunks.append(f"{evidence.lead.name}: {body[:800]}")
        mem.remember(evidence.lead.id, chunks, source="evidence")
        lookups = [
            f"{evidence.lead.name} customer complaints and reviews",
            f"{evidence.lead.name} competitors",
        ]
        for q in lookups:
            evidence.memory.extend(mem.similar(q, limit=4))
    except Exception:  # pragma: no cover - DB/embedding variability
        logger.debug("Semantic memory skipped for %s.", evidence.lead.name)