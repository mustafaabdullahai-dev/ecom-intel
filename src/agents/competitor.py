"""Agent 7 — Competitor Intelligence.

Compares the focal business against its competitors across dimensions:
pricing, products, website, branding, marketing, SEO, social media, customer
reviews, promotions, technology stack, and USP. Outputs a position, a list of
competitive gaps, and per-competitor profiles.
"""

from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel

from src.agents.evidence import Evidence
from src.schemas import Competitor, CompetitorAnalysis
from src.utils.helpers import ask, as_str_list

logger = logging.getLogger(__name__)

PROMPT = """You are a competitive-intelligence analyst for ecommerce.

Compare the focal business with its competitors using only the provided
evidence (focal business context + web snippets may mention rivals).

Return a SINGLE JSON object with this exact shape:
{{
  "competitors": [
    {{"name": "competitor name", "url": "url or empty",
      "strengths": ["..."], "weaknesses": ["..."]}}
  ],
  "comparisons": {{"pricing": "note", "products": "note", "website": "note",
    "branding": "note", "marketing": "note", "seo": "note", "social": "note",
    "reviews": "note", "promotions": "note", "tech_stack": "note", "usp": "note"}},
  "competitive_gaps": ["dimensions where the focal business clearly trails"],
  "position": "strong|moderate|weak|unknown",
  "tech_stack": ["detected technologies of the focal business"],
  "overall_score": 0,
  "summary": "one sentence"
}}
overall_score 0-100 where HIGHER = bigger competitive gap (worse for focal).
JSON only, no markdown.
"""


class CompetitorAgent:
    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def run(self, evidence: Evidence) -> CompetitorAnalysis:
        user = evidence.context_block()
        parsed = ask(self.llm, PROMPT, user)

        if not isinstance(parsed, dict):
            logger.warning("Competitor LLM returned unusable output for %s", evidence.lead.name)
            return CompetitorAnalysis(business_id=evidence.lead.id)

        competitors = [
            Competitor(
                name=c.get("name", "") if isinstance(c, dict) else str(c),
                url=c.get("url", "") if isinstance(c, dict) else "",
                strengths=as_str_list(c.get("strengths")) if isinstance(c, dict) else [],
                weaknesses=as_str_list(c.get("weaknesses")) if isinstance(c, dict) else [],
            )
            for c in (parsed.get("competitors") or [])
            if (c.get("name") if isinstance(c, dict) else str(c))
        ]
        return CompetitorAnalysis(
            business_id=evidence.lead.id,
            competitors=competitors,
            comparisons=parsed.get("comparisons", {}),
            competitive_gaps=as_str_list(parsed.get("competitive_gaps")),
            position=parsed.get("position", "unknown"),
            tech_stack=as_str_list(parsed.get("tech_stack")),
            overall_score=int(parsed.get("overall_score") or 0),
            summary=parsed.get("summary", ""),
        )