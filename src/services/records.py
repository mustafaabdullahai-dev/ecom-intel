"""Record builder — converts BusinessIntelligence into HistoryRecord rows.

Each record is one row in the Google Sheets knowledge base / JSON history.
This is where recommendation plans get flattened into the per-horizon columns,
scores are spread across columns, and the "next scheduled analysis" date is
computed from the automation schedule.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.config.settings import settings
from src.schemas import BusinessIntelligence, HistoryRecord
from src.services.storage import store


def build_records(intelligence: list[BusinessIntelligence], run_id: str) -> list[HistoryRecord]:
    """Build the full-row records for a run, including change-since-previous.

    Diffing happens against the previous PERSISTED scan (before this run's
    records are saved), which keeps change-since-previous meaningful.
    """
    records: list[HistoryRecord] = [(_to_record(intel, run_id)) for intel in intelligence]
    for record in records:
        record.change_since_previous = store.change_since(record).headline
    return records


def _to_record(intel: BusinessIntelligence, run_id: str) -> HistoryRecord:
    from src.services.explain import explain_scores

    lead = intel.lead
    scores = intel.scores
    qual = intel.qualification
    plan = intel.recommendation_plan

    social_links = ", ".join(
        f"{k}:{v}" for k, v in lead.social_handles.items()
    )

    return HistoryRecord(
        business_id=lead.id,
        business_name=lead.name,
        region=lead.region,
        website=lead.url or "",
        industry=lead.industry,
        contact_email=lead.email,
        phone=lead.phone,
        social_links=social_links,
        platform=lead.platform.value,
        scores=scores,
        lead_priority=qual.priority.value if qual else "low",
        ai_summary=plan.ai_summary if plan else "",
        daily=_join(plan.daily if plan else []),
        weekly=_join(plan.weekly if plan else []),
        monthly=_join(plan.monthly if plan else []),
        quarterly=_join(plan.quarterly if plan else []),
        yearly=_join(plan.yearly if plan else []),
        last_analysis_date=_now(),
        next_scheduled_analysis=_next_scheduled(),
        change_since_previous="",
        overall_business_health=scores.business_health,
        overall_ai_opportunity=scores.ai_opportunity,
        sales_status="new",
        outreach_status="not_contacted",
        notes=qual.reason if qual else "_no qualification_",
        score_explanations=explain_scores(intel, scores),
    )


def _join(items: list[str]) -> str:
    """Flatten a list to a compact comma string for a spreadsheet cell."""
    return ", ".join(str(i).strip() for i in items if i)


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _next_scheduled() -> str:
    """Next daily run time, a rough proxy for 'next full scan'."""
    next_daily = datetime.utcnow().replace(
        hour=settings.DAILY_HOUR, minute=settings.DAILY_MINUTE, second=0
    ) + timedelta(days=1)
    return next_daily.isoformat(timespec="minutes")