"""PDF audit report generator.

Turns one completed website-analysis result into a formatted PDF:

  - header band with the website title + audit status
  - 14-dimension score table with per-dimension reasoning + a "how to fix" column
  - AI recommendation plans by horizon
  - live security audit section
  - AI-generated outreach message for the website owner

Built with reportlab (pure Python, no browser needed). Deterministic and
offline. ``generate_pdf(result, out_path)`` writes the file and returns the
path so the API can expose a download endpoint.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.services.explain import SCORE_DIMENSIONS, LABELS

# --------------------------------------------------------------------------- #
# Style palette
# --------------------------------------------------------------------------- #

_BRAND = colors.HexColor("#0f172a")
_ACCENT = colors.HexColor("#6366f1")
_GREEN = colors.HexColor("#16a34a")
_AMBER = colors.HexColor("#d97706")
_RED = colors.HexColor("#dc2626")
_INK = colors.HexColor("#0f172a")
_MUTED = colors.HexColor("#64748b")
_LINE = colors.HexColor("#e2e8f0")


def _styles() -> dict[str, ParagraphStyle]:
    ss = getSampleStyleSheet()
    s = {
        "h1": ParagraphStyle("h1", parent=ss["Title"], fontName="Helvetica-Bold",
                             fontSize=20, leading=24, textColor=colors.white),
        "sub": ParagraphStyle("sub", parent=ss["Normal"], fontSize=10, leading=14,
                              textColor=colors.HexColor("#c7d2fe")),
        "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold",
                             fontSize=13, leading=17, textColor=_BRAND,
                             spaceBefore=14, spaceAfter=6),
        "h3": ParagraphStyle("h3", parent=ss["Heading3"], fontName="Helvetica-Bold",
                             fontSize=10.5, leading=14, textColor=_INK,
                             spaceBefore=8, spaceAfter=3),
        "body": ParagraphStyle("body", parent=ss["BodyText"], fontSize=9.5,
                               leading=13.5, textColor=_INK),
        "muted": ParagraphStyle("muted", parent=ss["BodyText"], fontSize=8.5,
                                leading=11.5, textColor=_MUTED),
        "cell": ParagraphStyle("cell", parent=ss["BodyText"], fontSize=8.5,
                               leading=11, textColor=_INK),
        "cellb": ParagraphStyle("cellb", parent=ss["BodyText"], fontSize=8.5,
                                leading=11, textColor=_INK, fontName="Helvetica-Bold"),
        "kpi": ParagraphStyle("kpi", parent=ss["BodyText"], fontSize=8, leading=11,
                              textColor=_MUTED),
        "kv": ParagraphStyle("kv", parent=ss["BodyText"], fontSize=9, leading=12,
                             textColor=_BRAND, fontName="Helvetica-Bold"),
    }
    return s


def _band_color(score: int) -> colors.HexColor:
    return _GREEN if score >= 70 else _AMBER if score >= 40 else _RED


def _tf(styles, text: str) -> Paragraph:
    return Paragraph(str(text or "—").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
                     styles["body"])


def _cel(styles, text: str, bold: bool = False) -> Paragraph:
    safe = str(text or "—").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe, styles["cellb"] if bold else styles["cell"])


def _bullet(styles, text: str) -> Paragraph:
    safe = str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(f"•  {safe}", styles["body"])


# --------------------------------------------------------------------------- #
# Story builders
# --------------------------------------------------------------------------- #


def _header_story(styles, result: dict) -> list:
    lead = result.get("lead", {})
    scores = result.get("scores", {})
    qual = result.get("qualification", {})
    sec = result.get("security", {})
    title = lead.get("name") or "Website audit"
    url = lead.get("url") or ""
    priority = str(qual.get("priority") or "n/a").upper()

    flows: list = [Spacer(1, 2 * mm)]
    flows.append(Paragraph(title, styles["h1"]))
    flows.append(Paragraph(
        f"{url} &nbsp;·&nbsp; {lead.get('platform') or 'unknown'} &nbsp;·&nbsp; "
        f"{lead.get('industry') or 'website'}",
        styles["sub"],
    ))
    flows.append(Spacer(1, 3 * mm))

    cols = [
        [Paragraph("AUDIT STATUS", styles["kpi"]), Paragraph(priority, styles["kv"])],
        [Paragraph("BUSINESS HEALTH", styles["kpi"]), Paragraph(str(scores.get("business_health", "—")), styles["kv"])],
        [Paragraph("AI OPPORTUNITY", styles["kpi"]), Paragraph(str(scores.get("ai_opportunity", "—")), styles["kv"])],
        [Paragraph("LEAD QUALIFICATION", styles["kpi"]), Paragraph(str(scores.get("lead_qualification", "—")), styles["kv"])],
        [Paragraph("SECURITY RISK", styles["kpi"]), Paragraph(str(sec.get("risk_level") or "—").upper(), styles["kv"])],
        [Paragraph("REPORTED", styles["kpi"]), Paragraph(
            datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC"), styles["kv"])],
    ]
    t = Table(cols, colWidths=[33 * mm] * 6, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.6, _LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, _LINE),
    ]))
    flows.append(t)
    flows.append(Spacer(1, 2 * mm))
    if qual.get("reason"):
        flows.append(Paragraph(f"<b>Qualification note:</b> {qual['reason']}", styles["body"]))
    return flows


def _score_table_story(styles, result: dict) -> list:
    flows: list = [Paragraph("14-Point Score Breakdown — what scored, why, and how to fix", styles["h2"])]
    scores = result.get("scores", {})
    expl = result.get("score_explanations", {})
    rec = result.get("recommendation", {})
    sec = result.get("security", {})
    intro = Paragraph(
        "Each dimension is 0–100. The reasoning reflects the actual inputs the "
        "deterministic engine used; the fix column is sourced from the AI "
        "recommendation plans and the security audit where relevant.",
        styles["muted"],
    )
    flows.append(intro)
    flows.append(Spacer(1, 2 * mm))

    headers = ["Dim", "Score", "Band", "Reasoning — what &amp; why this score", "How to fix"]
    rows = []
    fixes = _fix_map(rec, sec)
    for i, dim in enumerate(SCORE_DIMENSIONS, start=1):
        label = LABELS.get(dim, dim)
        score = int(scores.get(dim) or 0)
        band = "strong" if score >= 70 else "ok" if score >= 40 else "weak"
        ex = expl.get(dim, {})
        reason = ex.get("summary") or f"{score}/100 — no breakdown stored for this scan."
        contrib = (ex.get("contributors") or [])[:6]
        if contrib:
            cs = ", ".join(f"{c.get('label') or c.get('name')} {c['value']}" for c in contrib)
            total = len(ex.get("contributors") or [])
            more = f"  (+{total - len(contrib)} more)" if total > len(contrib) else ""
            reason = f"{reason}<br/><font size='7' color='#64748b'>Components: {cs}{more}</font>"
        fix = fixes.get(dim, fixes.get("all", []))
        rows.append([
            Paragraph(str(i), styles["cell"]),
            Paragraph(str(score), styles["cellb"]),
            Paragraph(band, styles["cell"]),
            Paragraph(reason, styles["cell"]),
            Paragraph("<br/>".join(fix[:8]) or "—", styles["cell"]),
        ])

    t = Table([[Paragraph(h, styles["cellb"]) for h in headers]] + rows,
              colWidths=[10 * mm, 13 * mm, 14 * mm, 74 * mm, 63 * mm],
              repeatRows=1, splitByRow=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, _LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    flows.append(t)
    return flows


def _fix_map(rec: dict, sec: dict) -> dict[str, list[str]]:
    """Collect recommended actions per dimension (fallback bucket 'all')."""
    horizon_plans: list[str] = []
    for key in ("daily", "weekly", "monthly", "quarterly", "yearly"):
        plan = rec.get(key)
        if isinstance(plan, list):
            horizon_plans.extend(str(x) for x in plan if x)
        elif isinstance(plan, str) and plan.strip():
            horizon_plans.append(plan)

    sec_fixes: list[str] = []
    for f in sec.get("findings", []) or []:
        if f.get("remediation"):
            sec_fixes.append(f"[{f.get('severity', 'info')}] {f['remediation']}")

    website = horizon_plans[:] or ["Run the AI recommendation plans to build a prioritized action list."]
    technical = (sec_fixes[:] or []) + horizon_plans[:5]
    trust = sec_fixes[:5] + [
        r for r in horizon_plans if any(k in r.lower() for k in ("review", "ssl", "policy", "privacy", "trust"))
    ][:4]
    cx = horizon_plans[:5]
    all_fix = horizon_plans[:] or ["Build a prioritized roadmap from the AI recommendations."]

    return {
        "website": website,
        "marketing": all_fix,
        "seo": all_fix,
        "brand": all_fix,
        "social": all_fix,
        "content": all_fix,
        "customer_experience": cx,
        "trust": trust,
        "technical": technical,
        "product_trend": all_fix,
        "growth_potential": all_fix[:6],
        "lead_qualification": all_fix[:6],
        "business_health": all_fix,
        "ai_opportunity": all_fix,
        "all": all_fix,
    }


def _summary_story(styles, result: dict) -> list:
    flows: list = [Paragraph("Overall Verdict", styles["h2"])]
    scores = result.get("scores", {})
    expl = result.get("score_explanations", {})
    mean_cap = scores.get("business_health", 0)
    verdict = "Strongly positioned" if mean_cap >= 70 else "Developing" if mean_cap >= 40 else "Needs attention"
    flows.append(Paragraph(f"<b>{verdict}.</b> Business health {mean_cap}/100, "
                           f"AI opportunity {scores.get('ai_opportunity', 0)}/100, "
                           f"lead qualification {scores.get('lead_qualification', 0)}/100.",
                           styles["body"]))

    weak = [LABELS[d] for d in SCORE_DIMENSIONS if (scores.get(d) or 0) < 40]
    strong = [LABELS[d] for d in SCORE_DIMENSIONS if (scores.get(d) or 0) >= 70]
    lines = []
    if weak:
        lines.append(f"<b>Weakest dimensions:</b> {', '.join(weak)}.")
    if strong:
        lines.append(f"<b>Strongest dimensions:</b> {', '.join(strong)}.")
    if weak:
        for dim in SCORE_DIMENSIONS:
            if (scores.get(dim) or 0) < 40:
                ex = expl.get(dim, {})
                lines.append(f"<b>{LABELS[dim]}</b> — {ex.get('summary') or 'weak'}")
    flows.extend(Paragraph(l, styles["body"]) for l in lines)
    return flows


def _recommendations_story(styles, result: dict) -> list:
    rec = result.get("recommendation", {})
    flows: list = [Paragraph("AI Recommendations", styles["h2"])]
    any_plan = False
    for key, label in (
        ("daily", "Daily improvements"),
        ("weekly", "Weekly improvements"),
        ("monthly", "Monthly improvements"),
        ("quarterly", "Quarterly improvements"),
        ("yearly", "Yearly improvements"),
    ):
        plan = rec.get(key)
        items = plan if isinstance(plan, list) else ([plan] if plan else [])
        items = [i for i in items if i]
        if not items:
            continue
        any_plan = True
        flows.append(Paragraph(label, styles["h3"]))
        flows.append(ListFlowable(
            [ListItem(Paragraph(str(i), styles["body"]), leftIndent=4) for i in items],
            bulletType="bullet", start="•", leftIndent=12,
        ))
        flows.append(Spacer(1, 1 * mm))
    if not any_plan:
        flows.append(Paragraph("No recommendation plan was generated.", styles["muted"]))
    return flows


def _security_story(styles, result: dict) -> list:
    sec = result.get("security") or {}
    if not sec:
        return []
    flows: list = [Paragraph("Live Security Audit", styles["h2"])]
    risk = str(sec.get("risk_level") or "unknown").upper()
    flows.append(Paragraph(
        f"Overall security <b>{sec.get('overall_score', 0)}/100</b> — risk level <b>{risk}</b>. "
        f"HTTPS enforced: {'yes' if sec.get('https_enforced') else 'no'}; TLS "
        f"{sec.get('protocol') or '?'} / {sec.get('cipher') or '?'}; cert issuer "
        f"<b>{sec.get('cert_issuer') or '?'}</b> (expires in {sec.get('cert_expires_days', 0)} days).",
        styles["body"],
    ))
    flows.append(Spacer(1, 2 * mm))

    cats = [
        ("HTTPS enforcement", sec.get("https")),
        ("SSL / TLS configuration", sec.get("ssl_tls")),
        ("Authentication & access control", sec.get("authentication")),
        ("Input validation", sec.get("input_validation")),
        ("File permissions / config exposure", sec.get("file_permissions")),
        ("Security headers", sec.get("security_headers")),
    ]
    rows = [[Paragraph("Category", styles["cellb"]), Paragraph("Score", styles["cellb"]),
             Paragraph("Status", styles["cellb"])]]
    for name, val in cats:
        v = int(val or 0)
        rows.append([Paragraph(name, styles["cell"]), Paragraph(str(v), styles["cell"]),
                     Paragraph("hardened", styles["cell"]) if v >= 70 else
                     Paragraph("partial", styles["cell"]) if v >= 40 else Paragraph("weak", styles["cell"])])
    t = Table(rows, colWidths=[70 * mm, 16 * mm, 16 * mm], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, _LINE),
        ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    flows.append(t)

    findings = sec.get("findings") or []
    if findings:
        flows.append(Paragraph("Findings", styles["h3"]))
        for f in findings[:10]:
            line = f"<b>[{f.get('severity', 'info')}] {f.get('title')}</b>"
            if f.get("detail"):
                line += f" — {f['detail']}"
            if f.get("remediation"):
                line += f" <font color='#16a34a'><b>Fix:</b> {f['remediation']}</font>"
            flows.append(_bullet(styles, line))

    gaps = sec.get("gaps") or []
    if gaps:
        flows.append(Paragraph("What This Site Lacks", styles["h3"]))
        for g in gaps[:8]:
            line = f"<b>{g.get('topic')}</b> ({g.get('status') or 'lacking'})"
            if g.get("reason"):
                line += f" — {g['reason']}"
            if g.get("recommendation"):
                line += f" <font color='#16a34a'><b>Recommendation:</b> {g['recommendation']}</font>"
            flows.append(_bullet(styles, line))

    exposed = sec.get("exposed_paths") or []
    if exposed:
        flows.append(Paragraph(f"<b>Exposed endpoints probed:</b> {', '.join(exposed)}", styles["body"]))
    return flows


def _outreach_story(styles, result: dict) -> list:
    sec = result.get("security") or {}
    msg = sec.get("outreach_message") or ""
    flows: list = [Paragraph("Outreach Message for the Website Owner", styles["h2"])]
    if msg:
        box = Table([[Paragraph(msg, styles["body"])]], colWidths=[160 * mm])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eef2ff")),
            ("BOX", (0, 0), (-1, -1), 0.6, _ACCENT),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ]))
        flows.append(box)
    else:
        flows.append(Paragraph(
            "Run a fresh analysis of this website to generate the live security "
            "audit and an AI outreach message for the owner.",
            styles["muted"],
        ))
    return flows


def _evidence_story(styles, result: dict) -> list:
    ev = result.get("evidence") or {}
    if not ev:
        return []
    flows: list = [Paragraph("Evidence Collected", styles["h2"])]
    for k, v in list(ev.items())[:10]:
        flows.append(Paragraph(f"<b>{k}:</b> <font color='#64748b'>{str(v)[:240]}</font>", styles["body"]))
    return flows


# --------------------------------------------------------------------------- #
# Doc + on-page header/footer
# --------------------------------------------------------------------------- #


def _on_page(canvas, doc, title: str, status: str, band: colors.HexColor):
    """Draw the colored header band (title + audit status) on every page."""
    canvas.saveState()
    canvas.setFillColor(_BRAND)
    canvas.rect(0, doc.pagesize[1] - 24 * mm, doc.pagesize[0], 24 * mm, stroke=0, fill=1)
    canvas.setFillColor(_ACCENT)
    canvas.rect(0, doc.pagesize[1] - 25.2 * mm, doc.pagesize[0], 1.2 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawString(16 * mm, doc.pagesize[1] - 9 * mm, title[:90])
    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(colors.HexColor("#c7d2fe"))
    canvas.drawString(16 * mm, doc.pagesize[1] - 13 * mm, "AI Ecommerce Consultant · Automated Website Audit")
    canvas.setFillColor(band)
    canvas.rect(150 * mm, doc.pagesize[1] - 13.5 * mm, 44 * mm, 8 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 8.5)
    canvas.drawCentredString(172 * mm, doc.pagesize[1] - 10.5 * mm, f"STATUS: {status}")
    # footer
    canvas.setFillColor(_MUTED)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(16 * mm, 9 * mm, f"Generated {datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')}")
    canvas.drawRightString(doc.pagesize[0] - 16 * mm, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


def generate_pdf(result: dict, out_path: str | os.PathLike) -> str:
    """Render ``result`` into a formatted PDF at ``out_path``; returns the path."""
    styles = _styles()
    lead = result.get("lead", {})
    scores = result.get("scores", {})
    title = (lead.get("name") or "Website audit")[:90]
    status = str((result.get("qualification") or {}).get("priority") or "n/a").upper()
    band = _band_color(int(scores.get("business_health") or 0))

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=30 * mm, bottomMargin=16 * mm,
        title=f"{title} — Website Audit",
        author="ecom-intel",
    )

    story: list = []
    story.extend(_header_story(styles, result))
    story.extend(_summary_story(styles, result))
    story.extend(_score_table_story(styles, result))
    story.extend(_recommendations_story(styles, result))
    story.extend(_security_story(styles, result))
    story.extend(_outreach_story(styles, result))
    story.extend(_evidence_story(styles, result))

    doc.build(story, onFirstPage=lambda c, d: _on_page(c, d, title, status, band),
              onLaterPages=lambda c, d: _on_page(c, d, title, status, band))
    return str(out_path)


def generate_findings_pdf(
    findings: list[dict],
    out_path: str | os.PathLike,
    title: str = "Business findings",
) -> str:
    """Render a compact findings table PDF (used by the finder tab)."""
    styles = _styles()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_file = out_path.name
    header = Paragraph(f"H1 · {title}", styles["h1"])
    muted = Paragraph(f"{len(findings)} businesses · generated {datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')} · ecom-intel", styles["muted"])
    data = [[Paragraph(f"<b>{c}</b>", styles["hdr"]) for c in ("Business", "Website", "Platform", "Industry", "Region", "City", "Email", "Phone", "Social", "Outreach")]]
    for i, b in enumerate(findings, 1):
        data.append([
            Paragraph(f"<b>{esc(str(b.get('name') or b.get('title') or ''))}</b>", styles["cel"]),
            Paragraph(esc(str(b.get('url') or '')) if isinstance(b.get('url'), str) else Paragraph(f"<b>{str(i)}</b>", styles["cel"]), styles["cel"]),
            Paragraph(esc(str(b.get('platform') or 'unknown')).lower(), styles["cel"]),
            Paragraph(esc(str(b.get('industry') or '')), styles["cel"]),
            Paragraph(esc(str(b.get('region') or '')), styles["cel"]),
            Paragraph(esc(str(b.get('city') or '')), styles["cel"]),
            Paragraph(esc(str(b.get('email') or b.get('contact_email') or '')), styles["cel"]),
            Paragraph(esc(str(b.get('phone') or '')), styles["cel"]),
            Paragraph(esc(", ".join(dict(b.get('social_handles') or {}).values()) or ""), styles["cel"]),
            Paragraph(esc(str(b.get('outreach') or '')), styles["cel"]),
        ])
    story: list = [header, muted, Spacer(1, 16)]
    tb = Table(data, repeatRows=1, colWidths=[56*mm, 76*mm, 40*mm, 42*mm, 38*mm, 32*mm, 60*mm, 34*mm, 52*mm, 44*mm], rowHeights=16)
    tb.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d5d9e2")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tb)
    doc = SimpleDocTemplate(str(out_path), pagesize=A4, leftMargin=16*mm, rightMargin=16*mm, topMargin=22*mm, bottomMargin=16*mm, title=title, author="ecom-intel")
    doc.build(story)
    return str(out_path)
