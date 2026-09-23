"""Google Sheets knowledge-base adapter.

Mirrors the JSON record store to a Google Spreadsheet (one row per business
per scan). Configure via .env:

  GOOGLE_SHEETS_CREDENTIALS=path/to/service-account.json
  GOOGLE_SHEETS_ID=<spreadsheet-id-from-the-url>

When credentials are missing the adapter is a no-op and the local JSON store
remains the source of truth.
"""

from __future__ import annotations

import logging

from src.config.settings import settings
from src.schemas import HistoryRecord

logger = logging.getLogger(__name__)

FIELDS = [
    "business_id", "business_name", "region", "website", "industry",
    "contact_email", "phone", "social_links", "platform",
    "lead_qualification", "lead_priority", "ai_summary",
    "daily", "weekly", "monthly", "quarterly", "yearly",
    "last_analysis_date", "next_scheduled_analysis", "change_since_previous",
    "overall_business_health", "overall_ai_opportunity",
    "sales_status", "outreach_status", "notes",
]


def _score_columns() -> list[str]:
    return [
        "website_score", "seo_score", "marketing_score", "brand_score",
        "social_score", "content_score", "customer_experience_score",
        "trust_score", "technical_score", "product_trend_score",
        "growth_potential_score",
    ]


HEADERS = [
    "Business ID", "Business Name", "Region", "Website", "Industry",
    "Contact Email", "Phone", "Social Media Links", "Platform",
    "Lead Qualification", "Lead Priority", "AI Summary",
    "Daily Recommendations", "Weekly Recommendations", "Monthly Recommendations",
    "Quarterly Recommendations", "Yearly Recommendations",
    "Last Analysis Date", "Next Scheduled Analysis", "Change Since Previous Scan",
    "Overall Business Health", "Overall AI Opportunity",
    "Sales Status", "Outreach Status", "Notes",
] + [c.replace("_", " ").title() for c in _score_columns()]


class SheetsExporter:
    """Optionally mirrors records to a Google Sheet."""

    def __init__(self):
        self._client = None
        self._sheet = None
        self.enabled = bool(
            settings.GOOGLE_SHEETS_CREDENTIALS and settings.GOOGLE_SHEETS_ID
        )

    def _connect(self):
        if self._client is not None:
            return
        import gspread
        from google.oauth2.service_account import Credentials

        creds = Credentials.from_service_account_file(
            settings.GOOGLE_SHEETS_CREDENTIALS,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        self._client = gspread.authorize(creds)
        self._sheet = self._client.open_by_key(settings.GOOGLE_SHEETS_ID).sheet1
        self._ensure_headers()

    def _ensure_headers(self):
        existing = self._sheet.row_values(1)
        if existing != HEADERS:
            self._sheet.clear()
            self._sheet.append_row(HEADERS)

    def write_records(self, records: list[HistoryRecord]) -> bool:
        """Append one row per record. Returns True when written to Sheets."""
        if not self.enabled:
            logger.info("Google Sheets not configured; skipping export.")
            return False
        try:
            self._connect()
            for record in records:
                self._sheet.append_row(_to_row(record), value_input_option="USER_ENTERED")
            logger.info("Exported %d row(s) to Google Sheets.", len(records))
            return True
        except Exception:  # pragma: no cover - external service
            logger.exception("Google Sheets export failed; local JSON store remains.")
            return False


def _to_row(record: HistoryRecord) -> list:
    s = record.scores
    return [
        record.business_id,
        record.business_name,
        record.region,
        record.website,
        record.industry,
        record.contact_email,
        record.phone,
        record.social_links,
        record.platform,
        s.lead_qualification,
        record.lead_priority,
        record.ai_summary,
        record.daily, record.weekly, record.monthly, record.quarterly, record.yearly,
        record.last_analysis_date,
        record.next_scheduled_analysis,
        record.change_since_previous,
        record.overall_business_health,
        record.overall_ai_opportunity,
        record.sales_status,
        record.outreach_status,
        record.notes,
        s.website, s.seo, s.marketing, s.brand, s.social, s.content,
        s.customer_experience, s.trust, s.technical, s.product_trend,
        s.growth_potential,
    ]