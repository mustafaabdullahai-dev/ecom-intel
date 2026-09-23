"""APScheduler automation — the 24/7 loop.

Registers the frequency jobs the spec requires:

  daily      monitor website/product/feedback changes (quick rescore pass)
  weekly     full rescore + competitor analysis + refreshed recommendations
  monthly    comprehensive audits + long-term trends + executive report
  quarterly  strategic growth reports + competitor benchmarking
  yearly     complete digital-transformation roadmap

Each job runs the pipeline and persists records + sheets; deeper reporting is
added per interval. Jobs are no-ops if ``SCHEDULER_ENABLED`` is false.
"""

from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config.settings import settings
from src.schemas import BusinessIntelligence
from src.services.reporting import (
    write_monthly_report,
    write_quarterly_report,
    write_yearly_report,
)
from src.workflows.orchestrator import Pipeline

logger = logging.getLogger(__name__)

_LAST_RUN: dict[str, datetime] = {}


# ---------------------------------------------------------------------------
# Periodic runners
# ---------------------------------------------------------------------------


class SchedulerBot:
    """Holds the pipeline once and exposes frequency-limited jobs."""

    def __init__(self):
        self.pipeline = None
        self.last_intel: list[BusinessIntelligence] = []

    def _ensure_pipeline(self) -> Pipeline:
        if self.pipeline is None:
            self.pipeline = Pipeline()
        return self.pipeline

    def run_full(self, regions: list[str] | None = None) -> None:
        """Full intelligence pass (uses discovery target; regions default EG)."""
        pipeline = self._ensure_pipeline()
        regions = regions or ["Egypt"]
        logger.info("[scheduler] full run for %s", regions)
        state = pipeline.graph.invoke({"regions": regions})
        self.last_intel = state.get("intelligence", [])
        logger.info("[scheduler] run complete: %d business(es) analyzed.",
                    len(self.last_intel))

    # -- interval jobs -----------------------------------------------------

    def daily_job(self) -> None:
        logger.info("[daily] monitoring pass")
        self.run_full()

    def weekly_job(self) -> None:
        logger.info("[weekly] rescore + competitor refresh")
        self.run_full()

    def monthly_job(self) -> None:
        logger.info("[monthly] comprehensive audit")
        self.run_full()
        if self.last_intel:
            write_monthly_report(self.last_intel, settings.OUTPUT_DIR)

    def quarterly_job(self) -> None:
        logger.info("[quarterly] strategic growth report")
        self.run_full()
        if self.last_intel:
            write_quarterly_report(self.last_intel, settings.OUTPUT_DIR)

    def yearly_job(self) -> None:
        logger.info("[yearly] digital transformation roadmap")
        self.run_full()
        if self.last_intel:
            write_yearly_report(self.last_intel, settings.OUTPUT_DIR)


# ---------------------------------------------------------------------------
# Scheduler wiring
# ---------------------------------------------------------------------------


def build_scheduler(bot: SchedulerBot) -> BlockingScheduler:
    sched = BlockingScheduler()
    timezone = "UTC"

    sched.add_job(
        bot.daily_job,
        CronTrigger(day_of_week="*", hour=settings.DAILY_HOUR,
                    minute=settings.DAILY_MINUTE, timezone=timezone),
        id="daily",
    )
    sched.add_job(
        bot.weekly_job,
        CronTrigger(day_of_week=settings.WEEKLY_DAY, hour=settings.WEEKLY_HOUR,
                    minute=settings.DAILY_MINUTE, timezone=timezone),
        id="weekly",
    )
    sched.add_job(
        bot.monthly_job,
        CronTrigger(day=settings.MONTHLY_DAY, hour=settings.DAILY_HOUR,
                    minute=settings.DAILY_MINUTE, timezone=timezone),
        id="monthly",
    )
    months = [int(m) for m in settings.QUARTERLY_MONTHS.split(",")]
    sched.add_job(
        bot.quarterly_job,
        CronTrigger(month=",".join(str(m) for m in months), day=1,
                    hour=settings.DAILY_HOUR, minute=settings.DAILY_MINUTE,
                    timezone=timezone),
        id="quarterly",
    )
    sched.add_job(
        bot.yearly_job,
        CronTrigger(month=settings.YEARLY_MONTH, day=1, hour=settings.DAILY_HOUR,
                    minute=settings.DAILY_MINUTE, timezone=timezone),
        id="yearly",
    )
    return sched


def start_scheduler() -> None:
    """Start the blocking scheduler (intended for a dedicated process)."""
    if not settings.SCHEDULER_ENABLED:
        logger.warning("Scheduler disabled (set SCHEDULER_ENABLED=true to run it).")
        return
    bot = SchedulerBot()
    sched = build_scheduler(bot)
    logger.info("Starting 24/7 scheduler: daily/weekly/monthly/quarterly/yearly jobs.")
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")