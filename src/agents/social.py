"""Agent 4 — Social Media Intelligence.

Analyses the business's presence across Facebook, Instagram, TikTok, Pinterest,
LinkedIn, YouTube, Threads, and X: posting frequency, follower growth,
engagement rate, content quality, brand consistency, customer interaction,
response time, hashtags, virality, and social-commerce readiness.

Only platforms present in the lead's handles are scored; everything else is
marked absent (0) — a useful gap signal.
"""

from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel

from src.agents.evidence import Evidence
from src.schemas import PlatformSocial, SocialMediaAnalysis
from src.utils.helpers import ask, as_str_list

logger = logging.getLogger(__name__)

PLATFORMS = ["facebook", "instagram", "tiktok", "pinterest", "linkedin", "youtube", "threads", "x"]


def _metric_shape() -> str:
    return (
        '{"posting_frequency": 0, "follower_growth": 0, "engagement_rate": 0, '
        '"content_quality": 0, "customer_interaction": 0, "response_time": 0, "notes": ""}'
    )


def _platform_shape() -> str:
    return "{" + ", ".join(f'"{p}": {_metric_shape()}' for p in PLATFORMS) + "}"


PROMPT = f"""You are a social media analyst for ecommerce brands.

Assess the business's social presence using ONLY the provided evidence.
For each platform, score 0 when there is no evidence. Score the platforms
found in the lead's social handles; leave others at 0.

Metrics per platform (0-100; response_time higher = faster replies):
{_metric_shape()}

Return a SINGLE JSON object with this exact shape:
{{
  "platforms": {_platform_shape()},
  "brand_consistency": 0,
  "community_management": 0,
  "social_commerce_ready": true,
  "overall_score": 0,
  "strengths": ["..."],
  "weaknesses": ["..."]
}}
JSON only, no markdown.
"""


class SocialMediaAgent:
    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def run(self, evidence: Evidence) -> SocialMediaAnalysis:
        user = evidence.context_block()
        parsed = ask(self.llm, PROMPT, user)

        if not isinstance(parsed, dict):
            logger.warning("Social LLM returned unusable output for %s", evidence.lead.name)
            return SocialMediaAnalysis(business_id=evidence.lead.id)

        platforms: dict[str, PlatformSocial] = {}
        for name, raw in (parsed.get("platforms") or {}).items():
            if name not in PLATFORMS or not isinstance(raw, dict):
                continue
            fields = {
                k: (str(v) if k == "notes" else int(v or 0))
                for k, v in raw.items() if k in PlatformSocial.model_fields
            }
            platforms[name] = PlatformSocial(**fields)
        return SocialMediaAnalysis(
            business_id=evidence.lead.id,
            platforms=platforms,
            brand_consistency=int(parsed.get("brand_consistency") or 0),
            community_management=int(parsed.get("community_management") or 0),
            social_commerce_ready=bool(parsed.get("social_commerce_ready", False)),
            overall_score=int(parsed.get("overall_score") or 0),
            strengths=as_str_list(parsed.get("strengths")),
            weaknesses=as_str_list(parsed.get("weaknesses")),
        )