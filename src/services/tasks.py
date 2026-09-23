"""Celery + Redis task layer.

Scale-out path for the deepdive stage: when ``USE_CELERY=true`` the pipeline
dispatches one ``deepdive_lead`` task per business to a Celery worker instead
of looping sequentially in the graph node. Each worker runs the six analysts
for its business and returns a finished ``BusinessIntelligence`` payload.

Run a worker with::

    celery -A src.services.tasks worker --loglevel=info

Requires Redis and the model images pulled (routing handled on the worker).
"""

from __future__ import annotations

import logging

from celery import Celery

from src.config.settings import settings

logger = logging.getLogger(__name__)

app = Celery(
    "ecom_intel",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_max_tasks_per_child=10,
)


@app.task(name="ping")
def ping() -> dict:
    """Ops healthcheck: verifies broker + worker round-trip."""
    return {"pong": True, "worker": True}


@app.task(name="deepdive_lead")
def deepdive_lead(lead_payload: dict) -> dict:
    """One full deepdive pass for a single business (Website..Competitor)."""
    from src.agents.competitor import CompetitorAgent
    from src.agents.evidence import gather_evidence
    from src.agents.marketing import MarketingAgent
    from src.agents.product_trend import ProductTrendAgent
    from src.agents.sentiment import SentimentAgent
    from src.agents.social import SocialMediaAgent
    from src.agents.website import WebsiteAgent
    from src.llm import get_llm
    from src.schemas import BusinessIntelligence, BusinessLead

    lead = BusinessLead.model_validate(lead_payload)
    evidence = gather_evidence(lead)

    intel = BusinessIntelligence(
        lead=lead,
        website=WebsiteAgent(get_llm("website")).run(evidence),
        marketing=MarketingAgent(get_llm("marketing")).run(evidence),
        social=SocialMediaAgent(get_llm("social")).run(evidence),
        product_trend=ProductTrendAgent(get_llm("product_trend")).run(evidence),
        sentiment=SentimentAgent(get_llm("sentiment")).run(evidence),
        competitor=CompetitorAgent(get_llm("competitor")).run(evidence),
    )
    return intel.model_dump(mode="json")


def dispatch_deepdive(leads: list, timeout: int = 600) -> list[dict]:
    """Queue one task per lead, then fan-in the finished intel payloads."""
    from src.schemas import BusinessLead
    from celery.result import allow_join_result

    async_results = []
    for lead in leads:
        if isinstance(lead, BusinessLead):
            async_results.append(deepdive_lead.delay(lead.model_dump(mode="json")))
    with allow_join_result():
        return [r.get(timeout=timeout) for r in async_results]