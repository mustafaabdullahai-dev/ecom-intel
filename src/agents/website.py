"""Agent 2 — Website Intelligence.

Audits every business website against the full dimension list from the spec
(homepage, navigation, UX, mobile, speed, SEO, accessibility, links, security,
SSL, checkout, payments, search/filter, product pages, content, trust signals,
conversion, blog, technical SEO, schema, metadata, CWV...). Grounds each score
in the scraped evidence.
"""

from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel

from src.agents.evidence import Evidence
from src.schemas import WebsiteAnalysis, WebsiteCategoryScores
from src.utils.helpers import ask, as_str_list

logger = logging.getLogger(__name__)

CATEGORIES = ",".join(
    [
        "homepage_quality", "navigation", "user_experience", "mobile_responsiveness",
        "website_speed", "performance", "seo", "accessibility", "broken_links",
        "security", "ssl", "checkout_experience", "payment_options",
        "search_functionality", "filtering", "product_pages", "image_quality",
        "content_quality", "trust_signals", "return_policy", "privacy_policy",
        "faq", "live_chat", "contact_information", "reviews",
        "conversion_optimization", "call_to_actions", "landing_pages",
        "blog_activity", "technical_seo", "schema_markup", "metadata",
        "internal_linking", "page_structure", "indexability", "core_web_vitals",
    ]
)


def _category_json_shape() -> str:
    """Sample JSON the model must fill: {"name": 0, ...}."""
    return "{" + ", ".join(f'"{c}": 0' for c in CATEGORIES.split(",")) + "}"


PROMPT = f"""You are an ecommerce website auditor.

Score every website dimension 0-100 based ONLY on the provided evidence.
Score 0 when there is no evidence for a dimension (honest "cannot tell").

Dimensions:
{CATEGORIES}

Return a SINGLE JSON object with this exact shape:
{{
  "categories": {_category_json_shape()},
  "strengths": ["..."],
  "weaknesses": ["..."],
  "summary": "one paragraph website verdict"
}}
For broken_links, higher = fewer broken links (100 = none). JSON only, no markdown.
"""


class WebsiteAgent:
    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def run(self, evidence: Evidence) -> WebsiteAnalysis:
        user = evidence.website_block()
        parsed = ask(self.llm, PROMPT, user)

        if not isinstance(parsed, dict) or "categories" not in parsed:
            logger.warning("Website LLM returned unusable output for %s", evidence.lead.name)
            return WebsiteAnalysis(business_id=evidence.lead.id, categories=WebsiteCategoryScores())

        page = evidence.page
        categories = WebsiteCategoryScores(**{
            k: int(v or 0) for k, v in parsed["categories"].items()
            if k in WebsiteCategoryScores.model_fields
        })
        return WebsiteAnalysis(
            business_id=evidence.lead.id,
            categories=categories,
            strengths=as_str_list(parsed.get("strengths")),
            weaknesses=as_str_list(parsed.get("weaknesses")),
            broken_links_found=page.broken_links if page else 0,
            has_ssl=page.has_ssl if page else False,
            page_load_ms=page.load_time_ms if page else None,
            contact_email=(page.emails[0] if page and page.emails else evidence.lead.email),
            contact_phone=(page.phones[0] if page and page.phones else evidence.lead.phone),
            summary=parsed.get("summary", ""),
        )