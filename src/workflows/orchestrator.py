"""LangGraph orchestration for the AI Ecommerce Consultant.

Spec agents wired into one state machine:

    discovery -> qualify -> deepdive* -> score -> recommend -> store -> report

The deepdive node runs the six analysts for each qualified business in one
pass (a single fan-out worker). LangGraph 1.2's conditional Send fan-outs
double-fire, so we deliberately keep ONE worker node that loops over leads;
true per-lead parallelism moves to a task queue (Celery/Redis) at scale.

Deepdive for each business runs, in sequence:
  Website -> Marketing -> Social -> Product Trend -> Sentiment -> Competitor
then the scoring engine computes the 14 standardized scores deterministically,
qualifies the lead, and the Recommendation Engine writes the time-horizon plan.

Models are routed per agent role (see src/llm.py): Discovery/Website on
Llama/Qwen, Marketing/Social/Sentiment on 128K-context models, and
Competitor/Recommendation on DeepSeek-R1.
"""

from __future__ import annotations

import logging
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from src.agents.competitor import CompetitorAgent
from src.agents.discovery import DiscoveryAgent
from src.agents.evidence import gather_evidence
from src.agents.marketing import MarketingAgent
from src.agents.product_trend import ProductTrendAgent
from src.agents.recommendation import RecommendationEngine
from src.agents.security import SecurityAgent
from src.agents.sentiment import SentimentAgent
from src.agents.social import SocialMediaAgent
from src.agents.website import WebsiteAgent
from src.config.settings import settings
from src.llm import get_llm
from src.schemas import (
    BusinessIntelligence,
    BusinessLead,
    DiscoveryResult,
    HistoryRecord,
    PipelineResult,
)
from src.scoring import qualify, score_business
from src.services.records import build_records
from src.services.reporting import write_report
from src.services.sheets import SheetsExporter
from src.services.storage import store

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


def _merge(left, right):
    return (left or []) + (right or [])


class WorkflowState(TypedDict, total=False):
    regions: list[str]
    discovery: DiscoveryResult
    leads: list[BusinessLead]
    qualified_leads: list[BusinessLead]
    intelligence: Annotated[list[BusinessIntelligence], _merge]
    records: list[HistoryRecord]
    run_id: str
    report_path: str
    records_written: bool


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class Pipeline:
    """Wires the eight agents into a LangGraph state machine."""

    def __init__(self):
        # One model per agent role (per the routing table in src/llm.py).
        self.discovery = DiscoveryAgent(get_llm("discovery"))
        self.website = WebsiteAgent(get_llm("website"))
        self.marketing = MarketingAgent(get_llm("marketing"))
        self.social = SocialMediaAgent(get_llm("social"))
        self.product_trend = ProductTrendAgent(get_llm("product_trend"))
        self.sentiment = SentimentAgent(get_llm("sentiment"))
        self.competitor = CompetitorAgent(get_llm("competitor"))
        self.recommendation = RecommendationEngine(get_llm("recommendation"))
        self.security = SecurityAgent(get_llm("security"))
        self.sheets = SheetsExporter()

        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(WorkflowState)
        builder.add_node("discovery", self._discovery_node)
        builder.add_node("qualify", self._qualify_node)
        builder.add_node("deepdive", self._deepdive_node)
        builder.add_node("score", self._score_node)
        builder.add_node("recommend", self._recommend_node)
        builder.add_node("store", self._store_node)
        builder.add_node("report", self._report_node)

        builder.add_edge(START, "discovery")
        builder.add_edge("discovery", "qualify")
        # Single fan-out worker: deepdive loops over every qualified lead.
        builder.add_edge("qualify", "deepdive")
        builder.add_edge("deepdive", "score")
        builder.add_edge("score", "recommend")
        builder.add_edge("recommend", "store")
        builder.add_edge("store", "report")
        builder.add_edge("report", END)
        return builder.compile()

    # -- node implementations ---------------------------------------------

    def _discovery_node(self, state: WorkflowState) -> dict:
        discovery = self.discovery.run(state.get("regions", []))
        return {
            "discovery": discovery,
            "leads": discovery.leads,
            "run_id": discovery.leads[0].id if discovery.leads else "run",
        }

    def _qualify_node(self, state: WorkflowState) -> dict:
        """Quick pre-filter: keep leads that look like an operating business.

        Detailed priority (high/medium/low) is computed later by the scoring
        engine in the Score node — this node only drops obvious dead ends so
        the deepdive workers don't waste time on them.
        """
        qualified: list[BusinessLead] = []
        for lead in state.get("leads", []):
            signal = bool(lead.url or lead.social_handles or lead.email)
            score = 80 if signal else 40
            if score >= settings.MIN_CONFIDENCE:
                qualified.append(lead)
        return {"qualified_leads": qualified}

    def _deepdive_node(self, state: WorkflowState) -> dict:
        """Six analysts per lead. Sequential, or via Celery when USE_CELERY."""
        leads = state.get("qualified_leads", [])
        if settings.USE_CELERY:
            from src.services.tasks import dispatch_deepdive

            intelligence = [
                BusinessIntelligence.model_validate(payload)
                for payload in dispatch_deepdive(leads)
            ]
        else:
            intelligence = []
            for lead in leads:
                evidence = gather_evidence(lead)

                website = self.website.run(evidence)
                marketing = self.marketing.run(evidence)
                social = self.social.run(evidence)
                product = self.product_trend.run(evidence)
                sentiment = self.sentiment.run(evidence)
                competitor = self.competitor.run(evidence)
                security = self.security.run(lead.url or "", business_id=lead.id)

                intelligence.append(BusinessIntelligence(
                    lead=lead,
                    website=website,
                    marketing=marketing,
                    social=social,
                    product_trend=product,
                    sentiment=sentiment,
                    competitor=competitor,
                    security=security,
                ))
        return {"intelligence": intelligence}

    def _score_node(self, state: WorkflowState) -> dict:
        # Scores/qualification are set IN PLACE on the shared BusinessIntelligence
        # objects. `intelligence` is a reducer-merged channel, so re-emitting the
        # full list here would double its contents — return no state writes.
        for intel in state.get("intelligence", []):
            intel.scores = score_business(intel)
            intel.qualification = qualify(intel, intel.scores)
        return {}

    def _recommend_node(self, state: WorkflowState) -> dict:
        # Same in-place pattern: plans are attached to the existing objects.
        for intel in state.get("intelligence", []):
            if intel.recommendation_plan is None:
                intel.recommendation_plan = self.recommendation.run(intel)
        return {}

    def _store_node(self, state: WorkflowState) -> dict:
        records = build_records(state.get("intelligence", []), state.get("run_id", "run"))
        store.save_pipeline(records)
        # Optional Postgres + pgvector mirror (no-op when DATABASE_URL unset).
        from src.services.db import memory

        pg = memory()
        if pg.enabled:
            for record in records:
                pg.save_record(record)
        sheets_written = self.sheets.write_records(records)
        return {"records": records, "records_written": sheets_written}

    def _report_node(self, state: WorkflowState) -> dict:
        result = PipelineResult(
            run_id=state.get("run_id", "run"),
            discovery=state["discovery"],
            intelligence=state.get("intelligence", []),
            records=state.get("records", []),
            sheets_written=state.get("records_written", False),
        )
        path = write_report(result, settings.OUTPUT_DIR)
        return {"report_path": path}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_pipeline() -> Pipeline:
    return Pipeline()