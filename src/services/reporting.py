"""Report generators.

Produces the human-readable deliverables:
  - full audit report (per run, every agent section)
  - monthly comprehensive audit brief
  - quarterly strategic growth report
  - yearly digital transformation roadmap
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from src.schemas import BusinessIntelligence, PipelineResult

logger = logging.getLogger(__name__)


def write_report(result: PipelineResult, output_dir: str) -> str:
    """Write the full audit report and return its path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"audit_{result.run_id}.md"
    path.write_text("\n".join(_full_report(result)))
    logger.info("Audit report written to %s", path)
    return str(path)


# ---------------------------------------------------------------------------
# Full audit report
# ---------------------------------------------------------------------------


def _full_report(result: PipelineResult) -> list[str]:
    lines = [
        "# AI Ecommerce Consultant — Business Audit Report",
        "",
        f"Run: `{result.run_id}` — {result.finished_at.isoformat()}",
        "",
        "## Discovery",
        "",
        result.discovery.summary,
        "",
        f"Leads found: {len(result.discovery.leads)} | Analyzed: {len(result.intelligence)}",
        "",
    ]
    for intel in sorted(result.intelligence, key=_opportunity_key, reverse=True):
        lines += _business_section(intel)
    if result.records:
        lines += ["## Knowledge Base (change since previous scan)", ""]
        for r in result.records:
            lines.append(f"- **{r.business_name}**: {r.change_since_previous}")
        lines.append("")
    if result.sheets_written:
        lines += ["Google Sheets knowledge base updated.", ""]
    return lines


def _business_section(intel: BusinessIntelligence) -> list[str]:
    lead = intel.lead
    s = intel.scores
    qual = intel.qualification
    plan = intel.recommendation_plan
    lines = [
        "---",
        "",
        f"## {lead.name}",
        "",
        f"- Industry: {lead.industry or 'unknown'} | Region: {lead.region} | Platform: {lead.platform.value}",
        f"- Contact: {lead.email or '-'} / {lead.phone or '-'} | {lead.url or 'no website'}",
        f"- **Priority: {qual.priority.value.upper()}** (lead qualification {s.lead_qualification}/100) — {qual.reason if qual else ''}",
        "",
        "### Scores (0-100)",
        "",
        "| Score | Value | Score | Value |",
        "|---|---|---|---|",
        f"| Website | {s.website} | SEO | {s.seo} |",
        f"| Marketing | {s.marketing} | Social | {s.social} |",
        f"| Brand | {s.brand} | Content | {s.content} |",
        f"| Customer Experience | {s.customer_experience} | Trust | {s.trust} |",
        f"| Technical | {s.technical} | Product Trend | {s.product_trend} |",
        f"| Growth Potential | {s.growth_potential} | Business Health | {s.business_health} |",
        f"| AI Opportunity | {s.ai_opportunity} | Lead Qualification | {s.lead_qualification} |",
        "",
    ]

    if intel.website:
        w = intel.website
        lines += [
            "### Website Intelligence",
            "",
            f"- Weaknesses: {_join(w.weaknesses)}",
            f"- Broken links: {w.broken_links_found} | SSL: {w.has_ssl} | Load: {w.page_load_ms}ms",
            f"- {w.summary}",
            "",
        ]
    if intel.marketing:
        m = intel.marketing
        lines += [
            "### Marketing Intelligence",
            "",
            f"- Maturity: {m.maturity_score}/100 | Active channels: {_join(m.active_channels)}",
            f"- Weak channels: {_join([k for k, v in m.channel_scores.items() if v < 30]) or 'none below 30'}",
            f"- Funnel: {m.sales_funnel} | Retention: {m.retention}",
            "",
        ]
    if intel.social:
        so = intel.social
        lines += [
            "### Social Media Intelligence",
            "",
            f"- Overall: {so.overall_score}/100 | Platforms: {_join(list(so.platforms)) or 'none found'}",
            f"- Social-commerce ready: {so.social_commerce_ready}",
            f"- Weaknesses: {_join(so.weaknesses)}",
            "",
        ]
    if intel.product_trend:
        p = intel.product_trend
        lines += [
            "### Product Trend Intelligence",
            "",
            f"- Demand {p.demand}/100 | Trend: {p.trend_direction} | Lifecycle: {p.lifecycle_stage}",
            f"- New product ideas: {_join(p.new_product_ideas)}",
            f"- Upsell: {_join(p.upsell_opportunities)} | Cross-sell: {_join(p.cross_sell_opportunities)}",
            "",
        ]
    if intel.sentiment:
        se = intel.sentiment
        lines += [
            "### Customer Sentiment",
            "",
            f"- Reputation {se.reputation_score}/100 | Satisfaction {se.satisfaction_score}/100 | Responses {se.response_quality}/100",
            f"- Complaints: {_join(se.complaints)}",
            f"- Evidence: {se.evidence_note}",
            "",
        ]
    if intel.competitor:
        c = intel.competitor
        lines += [
            "### Competitor Intelligence",
            "",
            f"- Position: {c.position} | Competitors: {_join([x.name for x in c.competitors]) or 'none named'}",
            f"- Competitive gaps: {_join(c.competitive_gaps)}",
            "",
        ]
    if plan:
        lines += [
            "### AI Recommendation Engine",
            "",
            f"**Summary:** {plan.ai_summary}",
            "",
            f"- **Daily:** {_join(plan.daily)}",
            f"- **Weekly:** {_join(plan.weekly)}",
            f"- **Monthly:** {_join(plan.monthly)}",
            f"- **Quarterly:** {_join(plan.quarterly)}",
            f"- **Yearly:** {_join(plan.yearly)}",
            "",
        ]
    return lines


# ---------------------------------------------------------------------------
# Periodic reports (monthly / quarterly / yearly)
# ---------------------------------------------------------------------------


def write_monthly_report(intelligence: list[BusinessIntelligence], output_dir: str) -> str:
    """Comprehensive monthly audit: per-business scorecards + long-term trends."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"monthly_{datetime.utcnow().strftime('%Y%m')}.md"
    lines = ["# Monthly Business Audit", "", f"Generated: {_now()}", ""]
    for intel in sorted(intelligence, key=_opportunity_key, reverse=True):
        s = intel.scores
        lines += [
            f"### {intel.lead.name} — health {s.business_health}/100, opportunity {s.ai_opportunity}/100",
            f"- Priority: {intel.qualification.priority.value if intel.qualification else 'n/a'}",
            f"- Top monthly actions: {_join(intel.recommendation_plan.monthly if intel.recommendation_plan else [])}",
            "",
        ]
    path.write_text("\n".join(lines))
    return str(path)


def write_quarterly_report(intelligence: list[BusinessIntelligence], output_dir: str) -> str:
    """Quarterly strategic growth report benchmarking businesses."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"quarterly_{datetime.utcnow().strftime('%Y_q%q')}.md"
    lines = ["# Quarterly Strategic Growth Report", "", f"Generated: {_now()}", ""]
    for intel in sorted(intelligence, key=_opportunity_key, reverse=True):
        s = intel.scores
        c = intel.competitor
        lines += [
            f"### {intel.lead.name}",
            f"- Opportunity: {s.ai_opportunity}/100 | Competitors: {c.position if c else 'unknown'}",
            f"- Competitive gaps: {_join(c.competitive_gaps if c else [])}",
            f"- Quarterly strategy: {_join(intel.recommendation_plan.quarterly if intel.recommendation_plan else [])}",
            "",
        ]
    path.write_text("\n".join(lines))
    return str(path)


def write_yearly_report(intelligence: list[BusinessIntelligence], output_dir: str) -> str:
    """Yearly digital-transformation roadmap."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"yearly_{datetime.utcnow().strftime('%Y')}.md"
    lines = [
        "# Yearly Digital Transformation Roadmap",
        "",
        f"Generated: {_now()}",
        "",
        "Per-business 12-month plans: an AI adoption roadmap, technology upgrades,"
        " expansion strategy, and international-market options.",
        "",
    ]
    for intel in sorted(intelligence, key=_opportunity_key, reverse=True):
        plan = intel.recommendation_plan
        lines += [
            f"### {intel.lead.name}",
            f"- Yearly roadmap: {_join(plan.yearly if plan else [])}",
            "",
        ]
    path.write_text("\n".join(lines))
    return str(path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _opportunity_key(intel: BusinessIntelligence) -> int:
    return intel.scores.ai_opportunity if intel else 0


def _join(items) -> str:
    return ", ".join(str(i).strip() for i in items if i)


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")