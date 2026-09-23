"""Agent 8 — AI Recommendation Engine.

Turns a business's full intelligence + scores into an ordered improvement
plan split by execution horizon: daily (quick wins), weekly, monthly,
quarterly, and yearly (strategy). Also writes the "AI consultant" summary
line used in the knowledge base.

Lead qualification itself is computed deterministically by the scoring engine
(no LLM call) so scores and tiers stay consistent across runs.
"""

from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel

from src.schemas import BusinessIntelligence, RecommendationPlan
from src.utils.helpers import ask, as_str_list

logger = logging.getLogger(__name__)

PROMPT = """You are an AI ecommerce consultant. For the business below you have
its audit (website, marketing, social, product, sentiment, competitors) and
standardized scores.

Write a concrete improvement plan divided by time horizon. Each item must be
actionable and specific to THIS business (name real problems, not generic
advice).

Return a SINGLE JSON object with this exact shape:
{{
  "ai_summary": "one-sentence consultant summary of the business",
  "daily": ["quick wins: fix broken links, improve CTAs, respond to reviews, publish social posts, update product images"],
  "weekly": ["blog articles, promo campaigns, email sequences, homepage banners, product description optimization"],
  "monthly": ["technical SEO audit, competitor benchmarking, UX improvements, campaign analysis, conversion optimization"],
  "quarterly": ["landing page redesigns, catalog expansion, branding improvements, marketing automation, loyalty program"],
  "yearly": ["website redesign, business expansion strategy, technology upgrades, international market expansion, AI adoption roadmap"]
}}
JSON only, no markdown.
"""


class RecommendationEngine:
    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def run(self, intel: BusinessIntelligence) -> RecommendationPlan:
        user = self._serialize(intel)
        parsed = ask(self.llm, PROMPT, user)

        if not isinstance(parsed, dict):
            logger.warning("Recommendation LLM returned unusable output for %s", intel.lead.name)
            return RecommendationPlan(business_id=intel.lead.id)

        return RecommendationPlan(
            business_id=intel.lead.id,
            ai_summary=parsed.get("ai_summary", ""),
            daily=as_str_list(parsed.get("daily")),
            weekly=as_str_list(parsed.get("weekly")),
            monthly=as_str_list(parsed.get("monthly")),
            quarterly=as_str_list(parsed.get("quarterly")),
            yearly=as_str_list(parsed.get("yearly")),
        )

    # -- internal -----------------------------------------------------------

    @staticmethod
    def _serialize(intel: BusinessIntelligence) -> str:
        lead = intel.lead
        lines = [
            f"Business: {lead.name} | {lead.industry} | {lead.region}, {lead.country}",
            f"Platform: {lead.platform.value} | URL: {lead.url or 'none'}",
            f"Scores: {intel.scores.model_dump()}",
        ]
        if intel.website:
            lines.append(f"Website weaknesses: {', '.join(intel.website.weaknesses[:5])}")
        if intel.marketing:
            lines.append(
                f"Marketing maturity: {intel.marketing.maturity_score} "
                f"active={intel.marketing.active_channels[:5]} "
                f"weak={', '.join(k for k, v in intel.marketing.channel_scores.items() if v < 30)}"
            )
        if intel.social:
            lines.append(f"Social: {intel.social.overall_score} platforms={list(intel.social.platforms)}")
        if intel.product_trend:
            lines.append(
                f"Products: trend={intel.product_trend.trend_direction} "
                f"stage={intel.product_trend.lifecycle_stage}"
            )
        if intel.sentiment:
            lines.append(
                f"Sentiment: rep={intel.sentiment.reputation_score} "
                f"issues={intel.sentiment.common_issues[:4]}"
            )
        if intel.competitor:
            lines.append(f"Competitive gaps: {', '.join(intel.competitor.competitive_gaps[:5])}")
        return "\n".join(lines)