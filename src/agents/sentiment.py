"""Agent 6 — Customer Sentiment.

Collects and interprets public review evidence (Google, Facebook, Trustpilot,
on-site reviews) found via web snippets — the key public signals available
without paid review APIs — and turns it into reputation, satisfaction, and
response-quality scores plus complaint themes.
"""

from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel

from src.agents.evidence import Evidence
from src.schemas import ReviewSource, SentimentAnalysis
from src.utils.helpers import ask, as_str_list

logger = logging.getLogger(__name__)

PROMPT = """You are a reputation analyst for ecommerce brands.

Extract customer-sentiment signals from the provided evidence (web snippets
of reviews, ratings, complaints, forum posts, social comments). Be honest
about how much evidence exists — if snippets show no reviews, score low and
say so.

Return a SINGLE JSON object with this exact shape:
{{
  "sources": [
    {{"source": "google|facebook|trustpilot|site_reviews|other",
      "review_count": 0, "average_rating": 0.0,
      "positive_themes": ["..."], "negative_themes": ["..."]}}
  ],
  "complaints": ["..."],
  "common_issues": ["..."],
  "satisfaction_score": 0,
  "response_quality": 0,
  "reputation_score": 0,
  "evidence_note": "one line on where evidence came from and confidence"
}}
JSON only, no markdown.
"""


class SentimentAgent:
    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def run(self, evidence: Evidence) -> SentimentAnalysis:
        user = evidence.context_block()
        parsed = ask(self.llm, PROMPT, user)

        if not isinstance(parsed, dict):
            logger.warning("Sentiment LLM returned unusable output for %s", evidence.lead.name)
            return SentimentAnalysis(business_id=evidence.lead.id)

        sources = [
            ReviewSource(
                source=src.get("source", "other"),
                review_count=int(src.get("review_count") or 0),
                average_rating=float(src.get("average_rating") or 0.0),
                positive_themes=as_str_list(src.get("positive_themes")),
                negative_themes=as_str_list(src.get("negative_themes")),
            )
            for src in (parsed.get("sources") or [])
            if isinstance(src, dict)
        ]
        return SentimentAnalysis(
            business_id=evidence.lead.id,
            sources=sources,
            complaints=as_str_list(parsed.get("complaints")),
            common_issues=as_str_list(parsed.get("common_issues")),
            satisfaction_score=int(parsed.get("satisfaction_score") or 0),
            response_quality=int(parsed.get("response_quality") or 0),
            reputation_score=int(parsed.get("reputation_score") or 0),
            evidence_note=parsed.get("evidence_note", ""),
        )