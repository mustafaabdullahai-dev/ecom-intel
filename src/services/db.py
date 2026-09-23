"""PostgreSQL + pgvector knowledge base.

Complements (and can replace) the JSON record store for:

  - structured lead tables + per-scan records,
  - embedding storage + semantic search for Agent 6 (sentiment) and
    Agent 7 (competitor) over review / website copy chunks.

Everything is optional: when ``DATABASE_URL`` is unset the singleton returns a
no-op object and the pipeline stays fully local (JSON + Google Sheets).

Schema lives in ``deploy/schema.sql`` (create extension vector; tables below).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import Engine, create_engine, text

from src.config.settings import settings

logger = logging.getLogger(__name__)

_MIGRATIONS = [
    "ALTER TABLE records ADD COLUMN IF NOT EXISTS score_explanations TEXT",
]


class PostgresMemory:
    """Thin SQLAlchemy wrapper: records + pgvector semantic search."""

    def __init__(self, database_url: str | None = None):
        self.url = database_url or settings.DATABASE_URL
        self._engine: Engine | None = None
        self.enabled = bool(self.url)
        if self.enabled:
            try:
                self._engine = create_engine(
                    self.url, pool_size=settings.DB_POOL_SIZE, pool_pre_ping=True
                )
                self._migrate()
                logger.info("Postgres memory connected: %s", self.url.split("@")[-1])
            except Exception as exc:  # noqa: BLE001
                logger.warning("Postgres unavailable (%s) — running local-only.", exc)
                self._engine = None
                self.enabled = False

    def _migrate(self) -> None:
        """Idempotent schema additions so old databases keep working."""
        with self._engine.begin() as conn:
            for stmt in _MIGRATIONS:
                conn.execute(text(stmt))
        logger.info("Postgres schema up to date (%d migration(s))", len(_MIGRATIONS))

    # -- records -----------------------------------------------------------

    def save_record(self, record) -> None:
        """Upsert a HistoryRecord row plus its scores into Postgres."""
        if not self.enabled:
            return
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO businesses
                      (id, name, region, industry, platform, website, contact_email,
                       phone, social_links, created_at)
                    VALUES
                      (:id, :name, :region, :industry, :platform, :website,
                       :email, :phone, :social_links, now())
                    ON CONFLICT (id) DO UPDATE SET
                      region = EXCLUDED.region, industry = EXCLUDED.industry,
                      website = EXCLUDED.website, contact_email = EXCLUDED.contact_email,
                      phone = EXCLUDED.phone, social_links = EXCLUDED.social_links
                """),
                {
                    "id": record.business_id, "name": record.business_name,
                    "region": record.region, "industry": record.industry,
                    "platform": record.platform, "website": record.website,
                    "email": record.contact_email, "phone": record.phone,
                    "social_links": record.social_links,
                },
            )
            record_id = conn.execute(
                text("""
                    INSERT INTO records (
                      business_id, scanned_at, lead_priority, ai_summary,
                      daily, weekly, monthly, quarterly, yearly,
                      change_since_previous, notes, score_explanations
                    ) VALUES (
                      :business_id, :scanned_at, :priority, :ai_summary,
                      :daily, :weekly, :monthly, :quarterly, :yearly,
                      :change_since_previous, :notes, :score_explanations
                    )
                    RETURNING id
                """),
                {
                    "business_id": record.business_id, "scanned_at": record.last_analysis_date,
                    "priority": record.lead_priority, "ai_summary": record.ai_summary,
                    "daily": record.daily, "weekly": record.weekly,
                    "monthly": record.monthly, "quarterly": record.quarterly,
                    "yearly": record.yearly,
                    "change_since_previous": record.change_since_previous,
                    "notes": record.notes,
                    "score_explanations": json.dumps(record.score_explanations or {}),
                },
            ).scalar_one()
            s = record.scores
            conn.execute(
                text("""
                    INSERT INTO score_snapshots (
                      record_id, website, seo, marketing, brand, social, content,
                      customer_experience, trust, technical, product_trend,
                      growth_potential, lead_qualification, business_health, ai_opportunity
                    ) VALUES (
                      :record_id, :website, :seo, :marketing, :brand, :social, :content,
                      :customer_experience, :trust, :technical, :product_trend,
                      :growth_potential, :lead_qualification, :business_health, :ai_opportunity
                    )
                    ON CONFLICT (record_id) DO UPDATE SET
                      website = EXCLUDED.website, seo = EXCLUDED.seo,
                      marketing = EXCLUDED.marketing, brand = EXCLUDED.brand,
                      business_health = EXCLUDED.business_health,
                      ai_opportunity = EXCLUDED.ai_opportunity
                """),
                {
                    "record_id": record_id,
                    "website": s.website, "seo": s.seo, "marketing": s.marketing,
                    "brand": s.brand, "social": s.social, "content": s.content,
                    "customer_experience": s.customer_experience, "trust": s.trust,
                    "technical": s.technical, "product_trend": s.product_trend,
                    "growth_potential": s.growth_potential,
                    "lead_qualification": s.lead_qualification,
                    "business_health": s.business_health, "ai_opportunity": s.ai_opportunity,
                },
            )

    def list_businesses(self, limit: int = 200) -> list[dict]:
        if not self.enabled:
            return []
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("SELECT * FROM businesses ORDER BY created_at DESC LIMIT :limit"),
                {"limit": limit},
            ).mappings().all()
            return [dict(r) for r in rows]

    def latest_records(self, limit: int = 500) -> list[dict]:
        if not self.enabled:
            return []
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT r.*, b.name AS business_name,
                           s.website, s.seo, s.marketing, s.brand, s.social,
                           s.content, s.customer_experience, s.trust, s.technical,
                           s.product_trend, s.growth_potential,
                           s.lead_qualification, s.business_health, s.ai_opportunity
                    FROM records r
                    JOIN businesses b ON b.id = r.business_id
                    LEFT JOIN score_snapshots s ON s.record_id = r.id
                    ORDER BY r.scanned_at DESC
                    LIMIT :limit
                """),
                {"limit": limit},
            ).mappings().all()
            return [self._parse_row(dict(r)) for r in rows]

    def records_for(self, business_id: str, limit: int = 200) -> list[dict]:
        """Every historical record (plus scores) for one business, newest first."""
        if not self.enabled:
            return []
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT r.*, b.name AS business_name, b.region, b.industry,
                           b.platform, b.website AS website_url,
                           b.contact_email, b.phone,
                           s.website, s.seo, s.marketing, s.brand, s.social,
                           s.content, s.customer_experience, s.trust, s.technical,
                           s.product_trend, s.growth_potential,
                           s.lead_qualification, s.business_health, s.ai_opportunity
                    FROM records r
                    JOIN businesses b ON b.id = r.business_id
                    LEFT JOIN score_snapshots s ON s.record_id = r.id
                    WHERE r.business_id = :business_id
                    ORDER BY r.scanned_at DESC
                    LIMIT :limit
                """),
                {"business_id": business_id, "limit": limit},
            ).mappings().all()
            return [self._parse_row(dict(r)) for r in rows]

    @staticmethod
    def _parse_row(row: dict) -> dict:
        """Decode the score_explanations TEXT column into a dict when present."""
        raw = row.get("score_explanations")
        if isinstance(raw, str):
            try:
                row["score_explanations"] = json.loads(raw or "{}")
            except (json.JSONDecodeError, TypeError):
                row["score_explanations"] = {}
        return row

    # -- embeddings (pgvector) ---------------------------------------------

    def remember(self, business_id: str, chunks: list[str], source: str) -> int:
        """Store embedding rows (chunk text -> vector) for a business."""
        if not self.enabled or not chunks:
            return 0
        from src.services.embeddings import embed_text

        count = 0
        with self._engine.begin() as conn:
            for chunk in chunks:
                vector = embed_text(chunk)
                if not vector:
                    continue
                conn.execute(
                    text("""
                        INSERT INTO embeddings (business_id, source, content, embedding)
                        VALUES (:business_id, :source, :content, :embedding)
                    """),
                    {
                        "business_id": business_id, "source": source,
                        "content": chunk[:4000], "embedding": vector,
                    },
                )
                count += 1
        return count

    def similar(self, query: str, limit: int = 5) -> list[dict]:
        """Return the most semantically similar stored chunks."""
        if not self.enabled:
            return []
        from src.services.embeddings import embed_text

        vector = embed_text(query)
        if not vector:
            return []
        # pgvector accepts a Python list for the :vector param (psycopg2? no).
        # Format the vector as a literal to stay dialect-agnostic:
        vector_lit = f"[{','.join(f'{v:.6f}' for v in vector[: settings.EMBEDDING_DIM])}]"
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT business_id, source, content,
                           (embedding <=> CAST(:vector AS vector)) AS distance
                    FROM embeddings
                    WHERE embedding IS NOT NULL
                    ORDER BY distance
                    LIMIT :limit
                """),
                {"vector": vector_lit, "limit": limit},
            ).mappings().all()
            return [dict(r) for r in rows]

    # -- dashboard convenience ---------------------------------------------

    def rank_businesses(self) -> list[dict]:
        """Latest knowledge-base rows with scores, for dashboard tables."""
        if not self.enabled:
            return []
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("""
                    WITH latest AS (
                      SELECT DISTINCT ON (business_id) *
                      FROM records
                      ORDER BY business_id, scanned_at DESC
                    )
                    SELECT b.id, b.name, b.region, b.industry, b.platform,
                           b.contact_email, b.phone, b.social_links,
                           b.website AS website_url,
                           l.lead_priority, l.ai_summary, l.change_since_previous,
                           l.scanned_at, l.score_explanations,
                           s.website, s.seo, s.marketing, s.brand, s.social,
                           s.content, s.customer_experience, s.trust, s.technical,
                           s.product_trend, s.growth_potential, s.lead_qualification,
                           s.business_health, s.ai_opportunity
                    FROM businesses b
                    JOIN latest l ON l.business_id = b.id
                    LEFT JOIN score_snapshots s ON s.record_id = l.id
                    ORDER BY l.scanned_at DESC
                """),
            ).mappings().all()
            return [self._parse_row(dict(r)) for r in rows]


class _NoopMemory:
    """Stand-in when DATABASE_URL is unset — every method is a safe no-op."""

    enabled = False

    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            return [] if name in ("list_businesses", "latest_records", "similar", "rank_businesses") else None
        return _noop


_memory: Optional[PostgresMemory] = None


def memory() -> PostgresMemory:
    """Lazy singleton. Returns an enabled PostgresMemory or a no-op."""

    global _memory
    if _memory is None:
        pg = PostgresMemory()
        _memory = pg if pg.enabled else _NoopMemory()
    return _memory  # type: ignore[return-value]