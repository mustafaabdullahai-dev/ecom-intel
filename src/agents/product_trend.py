"""Agent 5 — Product Trend Intelligence.

Evaluates the business's product mix against market demand: current demand,
trend direction, seasonality, competition, price positioning, search
interest, popularity, lifecycle stage, and generates up/cross-sell +
replacement + new-product ideas and inventory-risk flags.
"""

from __future__ import annotations

import logging

from langchain_core.language_models.chat_models import BaseChatModel

from src.agents.evidence import Evidence
from src.schemas import ProductTrendAnalysis
from src.utils.helpers import ask, as_str_list

logger = logging.getLogger(__name__)

PROMPT = """You are a product & market trend analyst for ecommerce.

Assess the demand and trend for THIS business's products using only the
provided evidence. All metrics 0-100 except explicit strings.

Return a SINGLE JSON object with this exact shape:
{{
  "demand": 0,
  "trend_direction": "rising|stable|falling",
  "seasonality": "low|moderate|high",
  "competition": 0,
  "price_positioning": "premium|mid|budget",
  "search_interest": 0,
  "popularity": 0,
  "lifecycle_stage": "intro|growth|maturity|decline",
  "new_product_ideas": ["..."],
  "upsell_opportunities": ["..."],
  "cross_sell_opportunities": ["..."],
  "replacement_opportunities": ["product lines worth replacing"],
  "inventory_risk": 0,
  "overall_score": 0,
  "reasoning": "one sentence"
}}
JSON only, no markdown.
"""


class ProductTrendAgent:
    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    def run(self, evidence: Evidence) -> ProductTrendAnalysis:
        user = evidence.context_block()
        parsed = ask(self.llm, PROMPT, user)

        if not isinstance(parsed, dict):
            logger.warning("Product LLM returned unusable output for %s", evidence.lead.name)
            return ProductTrendAnalysis(business_id=evidence.lead.id)

        return ProductTrendAnalysis(
            business_id=evidence.lead.id,
            demand=int(parsed.get("demand") or 0),
            trend_direction=parsed.get("trend_direction", ""),
            seasonality=parsed.get("seasonality", ""),
            competition=int(parsed.get("competition") or 0),
            price_positioning=parsed.get("price_positioning", ""),
            search_interest=int(parsed.get("search_interest") or 0),
            popularity=int(parsed.get("popularity") or 0),
            lifecycle_stage=parsed.get("lifecycle_stage", ""),
            new_product_ideas=as_str_list(parsed.get("new_product_ideas")),
            upsell_opportunities=as_str_list(parsed.get("upsell_opportunities")),
            cross_sell_opportunities=as_str_list(parsed.get("cross_sell_opportunities")),
            replacement_opportunities=as_str_list(parsed.get("replacement_opportunities")),
            inventory_risk=int(parsed.get("inventory_risk") or 0),
            overall_score=int(parsed.get("overall_score") or 0),
            reasoning=parsed.get("reasoning", ""),
        )