"""Record store — local JSON knowledge base.

Keeps append-only history for every business so the monitoring step can
compute "change since previous scan". This is the offline fallback; the
Google Sheets adapter mirrors these records to a spreadsheet when configured.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.config.settings import settings
from src.schemas import ChangeSummary, HistoryRecord, ScoreDelta

logger = logging.getLogger(__name__)


class Store:
    """Persist per-business history records to JSON under the data directory."""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = base_dir or Path(settings.DATA_DIR)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._history: dict[str, list[dict]] | None = None

    # -- history ------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._history is None:
            self._load()

    def record(self, record: HistoryRecord) -> ChangeSummary:
        """Store one record and diff it against the previous scan of the same business."""
        self._ensure_loaded()
        previous = self.latest(record.business_id)
        payload = record.model_dump(mode="json")
        self._history.setdefault(record.business_id, []).append(payload)
        self._flush()
        return self._diff(record, previous)

    def latest(self, business_id: str) -> HistoryRecord | None:
        self._ensure_loaded()
        rows = self._history.get(business_id, [])
        if not rows:
            return None
        return HistoryRecord.model_validate(rows[-1])

    def change_since(self, record: HistoryRecord) -> ChangeSummary:
        """Diff a freshly-built record against the last PERSISTED scan.

        Called before the new record is saved, so it always compares against
        the previous run, never against itself.
        """
        self._ensure_loaded()
        previous = self.latest(record.business_id)
        return self._diff(record, previous)

    def all_records(self) -> list[HistoryRecord]:
        self._ensure_loaded()
        out = []
        for rows in self._history.values():
            out.extend(HistoryRecord.model_validate(r) for r in rows)
        return out

    def save_pipeline(self, records: list[HistoryRecord]) -> list[ChangeSummary]:
        """Record a whole run, returning per-business change summaries."""
        summaries: list[ChangeSummary] = []
        for record in records:
            summaries.append(self.record(record))
        return summaries

    # -- internals -----------------------------------------------------------

    def _load(self) -> None:
        path = self.base_dir / "history.json"
        if path.exists():
            try:
                self._history = json.loads(path.read_text())
                return
            except (json.JSONDecodeError, OSError):
                logger.warning("Could not parse history.json, starting fresh.")
        self._history = {}

    def _flush(self) -> None:
        path = self.base_dir / "history.json"
        payload = {k: v for k, v in self._history.items() if v}
        path.write_text(json.dumps(payload, indent=2))
        logger.debug("Wrote %d business histories to %s", len(payload), path)

    @staticmethod
    def _diff(current: HistoryRecord, previous: HistoryRecord | None) -> ChangeSummary:
        if previous is None:
            return ChangeSummary(
                business_id=current.business_id,
                deltas=[],
                headline="First scan — no prior record.",
                is_first_scan=True,
            )
        names = [f for f in current.scores.model_fields
                 if f not in {"lead_qualification", "ai_opportunity", "business_health"}]
        deltas = []
        for name in names:
            prev = getattr(previous.scores, name)
            now = getattr(current.scores, name)
            if now - prev != 0:
                deltas.append(ScoreDelta(score_name=name, previous=prev, current=now, delta=now - prev))
        headline = (
            f"{len(deltas)} score(s) changed: "
            + ", ".join(f"{d.score_name} {d.delta:+d}" for d in deltas[:5])
        ) if deltas else "No score changes since last scan."
        return ChangeSummary(business_id=current.business_id,
                             deltas=deltas, headline=headline)


# Import triggers lazy load if using module-level instance.
store = Store()
store._load()