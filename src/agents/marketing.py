"""Agent 3 — Marketing Intelligence.

Evaluates the company's whole marketing operation: paid ads (Google/Facebook/
Instagram/TikTok/Pinterest), email/SMS, retargeting, affiliate, influencer,
referrals, promotions, retention, content marketing, brand positioning,
sales funnel, lead gen, landing pages, remarketing, and automation.

Outputs a maturity score (0-100) plus per-channel maturity so the scoring
engine can decline specific weaknesses.
"""

from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel

from src.agents.evidence import Evidence
from src.schemas import MarketingAnalysis
from src.utils.helpers import ask, as_str_list

logger = logging.getLogger(__name__)

CHANNELS = [
    "google_ads", "facebook_ads", "instagram_ads", "tiktok_ads", "pinterest",
    "email", "sms", "retargeting", "affiliate", "influencer", "referral",
    "promotions", "customer_retention", "content_marketing", "brand_positioning",
    "sales_funnel", "lead_generation", "landing_pages", "remarketing",
    "marketing_automation",
]


def _channel_json_shape() -> str:
    return "{" + ", ".join(f'"{c}": 0' for c in CHANNELS) + "}"


PROMPT = f"""You are a marketing strategist for ecommerce brands.

Assess this business's marketing maturity using ONLY the provided evidence.
Score 0 when there is no evidence (this is itself a signal — no ads, no
email, no funnel).

Score each channel 0-100 (100 = sophisticated, optimized):
{CHANNELS}

Return a SINGLE JSON object with this exact shape:
{{
  "maturity_score": 0,
  "channel_scores": {_channel_json_shape()},
  "active_channels": ["channels clearly in use"],
  "lifecycle_stage": "seed|growth|mature",
  "sales_funnel": "one line",
  "retention": "one line",
  "automation": "one line",
  "strengths": ["..."],
  "weaknesses": ["..."]
}}
JSON only, no markdown.
"""


class MarketingAgent:
    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def run(self, evidence: Evidence) -> MarketingAnalysis:
        user = evidence.context_block()
        parsed = ask(self.llm, PROMPT, user)

        if not isinstance(parsed, dict):
            logger.warning("Marketing LLM returned unusable output for %s", evidence.lead.name)
            return MarketingAnalysis(business_id=evidence.lead.id, maturity_score=0)

        channel_scores = {
            k: int(v or 0) for k, v in (parsed.get("channel_scores") or {}).items()
            if k in CHANNELS
        }
        return MarketingAnalysis(
            business_id=evidence.lead.id,
            maturity_score=int(parsed.get("maturity_score") or 0),
            channel_scores=channel_scores,
            active_channels=as_str_list(parsed.get("active_channels")),
            lifecycle_stage=parsed.get("lifecycle_stage", ""),
            sales_funnel=parsed.get("sales_funnel", ""),
            retention=parsed.get("retention", ""),
            automation=parsed.get("automation", ""),
            strengths=as_str_list(parsed.get("strengths")),
            weaknesses=as_str_list(parsed.get("weaknesses")),
        )