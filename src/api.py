"""FastAPI application — webhooks + API layer over the pipeline.

Endpoints:
  GET  /health                    liveness + backend status
  POST /run                       trigger a full pipeline run (optional regions)
  GET  /businesses                local JSON knowledge base
  GET  /businesses/{id}/records   history for one business
  GET  /businesses/{id}/rationale cached LLM score rationale
  POST /businesses/{id}/rationale generate LLM score rationale from inputs
  GET  /reports                   list generated report files
  POST /schedule                  toggle/start the scheduler in this process
  GET  /similar?q=...             pgvector semantic search (Agent 6/7 memory)
  POST /analyze                   analyze a specific website URL

Run with:  uvicorn src.api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import glob
import json
import logging
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from src.config.settings import settings
from src.schemas import BusinessIntelligence
from src.services.db import memory
from src.services.explain import dimension_summary, explain_from_record
from src.services.pdfreport import generate_pdf
from src.services.rationale import generate_rationales, load_cached, save_cached
from src.services.storage import store
from src.workflows.orchestrator import build_pipeline
from src.services.finder import find_businesses  # noqa: E402

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.DASHBOARD_TITLE or "ecom-intel", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Background analysis jobs — kept in memory but mirrored to disk so completed
# reports survive a server restart and are always viewable afterwards.
# ---------------------------------------------------------------------------

_JOBS: dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()
_JOBS_FILE = Path(settings.DATA_DIR) / "analyze_jobs.json"


def _jobs_load() -> None:
    try:
        if _JOBS_FILE.exists():
            with _JOBS_FILE.open() as f:
                _JOBS.update(json.load(f))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not load saved jobs: %s", exc)


def _jobs_save() -> None:
    try:
        _JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _JOBS_FILE.open("w") as f:
            json.dump(_JOBS, f, indent=2)
    except OSError as exc:
        logger.warning("Could not persist jobs: %s", exc)


def _pdf_dir() -> Path:
    path = Path(settings.OUTPUT_DIR) / "pdf"
    path.mkdir(parents=True, exist_ok=True)
    return path


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """Browser hits — redirect straight to the interactive API docs."""
    return RedirectResponse(url="/docs")


class RunRequest(BaseModel):
    regions: list[str] = ["Egypt"]
    target: Optional[int] = None
    industry: Optional[str] = None


class AnalyzeWebsiteRequest(BaseModel):
    url: str
    deepdive: bool = True
    industry: Optional[str] = None


@app.get("/health")
def health() -> dict:
    pg = memory()
    from src.llm import REMOTE_PROVIDERS

    providers = [
        {
            "name": name,
            "configured": bool(
                getattr(settings, str(cfg["api_key"])) or settings.OPENAI_API_KEY
            ),
            "model": cfg.get("default"),
        }
        for name, cfg in REMOTE_PROVIDERS.items()
    ]
    return {
        "status": "ok",
        "database_url": bool(settings.DATABASE_URL),
        "postgres": bool(pg.enabled),
        "sheets": bool(settings.GOOGLE_SHEETS_ID),
        "celery": settings.USE_CELERY,
        "scheduler": settings.SCHEDULER_ENABLED,
        "serp": bool(settings.SERPER_API_KEY),
        "pagespeed": bool(settings.PAGESPEED_API_KEY),
        "providers": providers,
        "fetch_mode": settings.FETCH_MODE,
        "proxy": bool(settings.PROXY_URL),
    }


@app.post("/run", status_code=201)
def run(req: RunRequest) -> dict:
    """Synchronous pipeline run. For long runs prefer the scheduler/CLI."""
    pipeline = build_pipeline()
    state = pipeline.graph.invoke({"regions": req.regions})
    return {
        "run_id": state.get("run_id", ""),
        "analyzed": len(state.get("intelligence", [])),
        "report": state.get("report_path", ""),
        "sheets_written": state.get("records_written", False),
    }


@app.post("/analyze", status_code=202)
def analyze_website(req: AnalyzeWebsiteRequest) -> dict:
    """Kick off a background analysis job; poll GET /analyze/{job_id}.

    The full agent run takes minutes, so we return a job handle immediately
    instead of holding the proxy/browser connection open. The job runs
    server-side (independent of any browser tab) and its completed result —
    including the generated PDF audit report — is persisted to disk so it can
    be viewed again at any time.
    """
    job_id = uuid.uuid4().hex[:10]
    with _JOBS_LOCK:
        _JOBS[job_id] = {"status": "running", "result": None, "error": None}
    _jobs_save()

    thread = threading.Thread(
        target=_analyze_worker,
        args=(job_id, req), daemon=True,
    )
    thread.start()
    return {"job_id": job_id}


_jobs_load()


@app.get("/analyze/{job_id}")
def analyze_status(job_id: str) -> dict:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job id")
    return job


def _analyze_worker(job_id: str, req: AnalyzeWebsiteRequest) -> None:
    """Run the analysis pipeline off the request thread and stash the result."""
    try:
        result = _run_analysis(req)
        result = _attach_pdf(result)
        with _JOBS_LOCK:
            _JOBS[job_id] = {"status": "done", "result": result, "error": None}
    except HTTPException as exc:
        with _JOBS_LOCK:
            _JOBS[job_id] = {"status": "error", "result": None, "error": exc.detail}
    except Exception as exc:  # noqa: BLE001 - surfaced via the job
        logger.exception("analyze job %s failed", job_id)
        with _JOBS_LOCK:
            _JOBS[job_id] = {"status": "error", "result": None, "error": str(exc)}
    _jobs_save()


def _attach_pdf(result: dict) -> dict:
    """Generate the formatted PDF audit report and attach a download link."""
    try:
        business_id = (result.get("lead") or {}).get("url", "")
        business_id = business_id.replace("https://", "").replace("http://", "").split("/")[0]
        stem = f"{business_id}_{datetime.now().strftime('%Y%m%d_%H%M')}"
        path = _pdf_dir() / f"{stem}.pdf"
        generate_pdf(result, path)
        result["pdf"] = {"filename": path.name, "url": f"/backend/reports/pdf/{path.name}"}
    except Exception as exc:  # noqa: BLE001 - a missing PDF must never fail the job
        logger.exception("PDF report generation failed")
        result["pdf"] = {"filename": "", "url": "", "error": str(exc)}
    return result


def _run_analysis(req: AnalyzeWebsiteRequest) -> dict:
    """The actual 8-agent analyze pipeline for one URL."""
    from src.schemas import BusinessLead
    from src.services.scraper import scrape_website
    from src.workflows.orchestrator import build_pipeline
    from src.agents.evidence import gather_evidence
    from src.config.settings import settings

    page = scrape_website(req.url)
    if not page:
        raise HTTPException(status_code=400, detail="Could not fetch the website")

    lead = BusinessLead(
        id=req.url.replace("https://", "").replace("http://", "").split("/")[0],
        name=page.title or req.url,
        country="",
        region="",
        city="",
        industry=req.industry or "website",
        products=[],
        url=req.url,
        email="",
        phone="",
        platform=page.platform,
        social_handles={},
        description=page.text[:200] if page.text else "",
    )

    pipeline = build_pipeline()

    # Skip discovery: run qualify directly
    signal = bool(lead.url or lead.social_handles or lead.email)
    score = 80 if signal else 40
    if score < settings.MIN_CONFIDENCE:
        raise HTTPException(status_code=400, detail="Lead did not pass qualification")

    # Deepdive (same as _deepdive_node)
    from src.agents.security import SecurityAgent
    from src.llm import get_llm_rotation
    from src.schemas import BusinessIntelligence

    security = SecurityAgent(get_llm_rotation("security")[0])
    intelligence = []
    for ld in [lead]:
        evidence = gather_evidence(ld)
        website = pipeline.website.run(evidence)
        marketing = pipeline.marketing.run(evidence)
        social = pipeline.social.run(evidence)
        product = pipeline.product_trend.run(evidence)
        sentiment = pipeline.sentiment.run(evidence)
        competitor = pipeline.competitor.run(evidence)
        security_audit = security.run(ld.url or "", business_id=ld.id)

        intelligence.append(BusinessIntelligence(
            lead=ld,
            website=website,
            marketing=marketing,
            social=social,
            product_trend=product,
            sentiment=sentiment,
            competitor=competitor,
            security=security_audit,
        ))

    # Score + qualify
    from src.scoring import qualify as qualify_fn, score_business
    for intel in intelligence:
        intel.scores = score_business(intel)
        intel.qualification = qualify_fn(intel, intel.scores)

    # Recommend
    for intel in intelligence:
        if intel.recommendation_plan is None:
            intel.recommendation_plan = pipeline.recommendation.run(intel)

    # Store (optional Postgres + sheets)
    from src.services.records import build_records
    from src.services.db import memory
    from src.services.sheets import SheetsExporter

    records = build_records(intelligence, "analyze")
    store.save_pipeline(records)
    pg = memory()
    if pg.enabled:
        for record in records:
            pg.save_record(record)
    sheets = SheetsExporter()
    sheets.write_records(records)

    i = intelligence[0]
    from src.services.explain import explain_scores
    return {
        "lead": {
            "name": i.lead.name,
            "url": i.lead.url,
            "industry": i.lead.industry,
            "region": i.lead.region,
            "platform": i.lead.platform.value,
        },
        "scores": i.scores.model_dump() if i.scores else {},
        "score_explanations": explain_scores(i, i.scores) if i.scores else {},
        "qualification": i.qualification.model_dump() if i.qualification else {},
        "recommendation": i.recommendation_plan.model_dump() if i.recommendation_plan else {},
        "evidence": i.evidence.model_dump() if hasattr(i, "evidence") and i.evidence else {},
        "security": i.security.model_dump() if i.security else {},
    }


SCORE_DIMENSIONS = [
    "website", "seo", "marketing", "brand", "social", "content",
    "customer_experience", "trust", "technical", "product_trend",
    "growth_potential", "lead_qualification", "business_health", "ai_opportunity",
]


@app.get("/businesses")
def businesses(limit: int = 200) -> list[dict]:
    pg = memory()
    if pg.enabled:
        return pg.list_businesses(limit)
    rows = store.all_records()
    seen: dict[str, dict] = {}
    for r in rows:
        seen.setdefault(
            r.business_id,
            {
                "id": r.business_id,
                "name": r.business_name,
                "region": r.region,
                "industry": r.industry,
                "platform": r.platform,
                "website": r.website,
                "contact_email": r.contact_email,
                "phone": r.phone,
            },
        )
    return list(seen.values())[:limit]


from collections import Counter

_RANK_COLUMNS = [
    "id", "name", "region", "industry", "platform", "website", "contact_email",
    "phone", "social_links", "lead_priority", "ai_summary", "change_since_previous",
    "scanned_at", "business_health", "ai_opportunity",
] + SCORE_DIMENSIONS + ["notes", "daily", "weekly", "monthly", "quarterly", "yearly"]


def _range_rows() -> list[dict]:
    """Latest per-business rows with the full score set (postgres or JSON).

    Postgres rows already carry flat score columns; JSON rows store the scores
    in a nested dict, so we promote them to a single consistent shape.
    """
    pg = memory()
    if pg.enabled:
        return pg.rank_businesses()
    records = store.all_records()
    latest: dict[str, dict] = {}
    for r in records:
        d = r.model_dump(mode="json")
        prev = latest.get(r.business_id)
        if prev is None or d.get("last_analysis_date", "") > (prev.get("last_analysis_date") or ""):
            latest[r.business_id] = d
    rows = list(latest.values())
    for d in rows:
        if isinstance(d.get("scores"), dict):
            for k, v in d["scores"].items():
                d.setdefault(k, v)
        d.setdefault("id", d.get("business_id"))
        d.setdefault("name", d.get("business_name"))
        d.setdefault("website_url", d.get("website", ""))
    return rows


@app.get("/dashboard-data")
def dashboard_data() -> dict:
    """Latest per-business rows for the dashboard, leads and insights pages."""
    rows = _range_rows()
    return {"source": "postgres" if memory().enabled else "json", "rows": rows}


@app.get("/stats")
def stats() -> dict:
    """Executive-dashboard aggregates across the whole knowledge base."""
    rows = _range_rows()
    totals = Counter(r.get("region", "n/a") or "n/a" for r in rows)
    industries = Counter((r.get("industry") or "n/a") for r in rows)
    priorities = Counter((r.get("lead_priority") or "n/a").lower() for r in rows)
    avg: dict[str, int] = {}
    for dim in SCORE_DIMENSIONS:
        vals = [int(r.get(dim) or 0) for r in rows if (r.get(dim) or 0)]
        avg[dim] = round(sum(vals) / len(vals)) if vals else 0
    dimension_summaries = {}
    for dim in SCORE_DIMENSIONS:
        dimension_summaries[dim] = dimension_summary(dim, avg[dim], len(rows), rows)
    return {
        "businesses": len(rows),
        "records": len(store.all_records()) if not memory().enabled else 0,
        "regions": dict(totals.most_common()),
        "industries": dict(industries.most_common(10)),
        "priorities": dict(priorities),
        "dimension_averages": avg,
        "dimension_summaries": dimension_summaries,
        "weakest_dimensions": sorted(
            ((k, v) for k, v in avg.items() if k not in ("business_health", "ai_opportunity", "lead_qualification")),
            key=lambda kv: kv[1],
        )[:6],
        "strongest_dimensions": sorted(
            ((k, v) for k, v in avg.items() if k not in ("business_health", "ai_opportunity", "lead_qualification")),
            key=lambda kv: -kv[1],
        )[:4],
    }


@app.get("/export.csv")
def export_csv() -> dict:
    """Structured dataset for the sales team (spec column set)."""
    pg = memory()
    rows: list[dict]
    if pg.enabled:
        latest = pg.latest_records()
        rows, seen = [], set()
        for r in latest:
            if r.get("business_id") in seen:
                continue
            seen.add(r["business_id"])
            rows.append(r)
    else:
        rows = _range_rows()

    import csv
    import io

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_RANK_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k, "") for k in _RANK_COLUMNS})
    return {
        "filename": "ecom_intel_leads.csv",
        "rows": len(rows),
        "csv": buf.getvalue(),
    }


@app.get("/schedules")
def schedules() -> dict:
    """24/7 automation schedule configuration + runtime status."""
    return {
        "enabled": settings.SCHEDULER_ENABLED,
        "jobs": [
            {
                "id": "daily",
                "description": "Monitor website/product/feedback changes",
                "when": "every day at 06:00 UTC",
            },
            {
                "id": "weekly",
                "description": "Recalculate AI scores, analyze competitors",
                "when": "every Mon at 06:00 UTC",
            },
            {
                "id": "monthly",
                "description": "Comprehensive business audits + executive report",
                "when": "on day 1 at 06:00 UTC",
            },
            {
                "id": "quarterly",
                "description": "Strategic growth reports + competitor benchmarking",
                "when": "on 1, 4, 7, 10-01 at 00 UTC",
            },
            {
                "id": "yearly",
                "description": "Digital transformation roadmap, YoY comparison",
                "when": "on 1-01 at 00 UTC",
            },
        ],
    }


@app.get("/similar")
def similar(q: str, k: int = 10) -> list[dict]:
    """Semantic search over Agent 6/7 memory (pgvector)."""
    pg = memory()
    if not pg.enabled:
        return []
    hits = pg.similar(q, k)
    return [dict(h) for h in hits]


@app.get("/businesses/{business_id}/records")
def business_records(business_id: str) -> list[dict]:
    """All historical records for a single business."""
    pg = memory()
    if pg.enabled:
        rows = pg.records_for(business_id)
    else:
        records = store.all_records()
        rows = [
            r.model_dump(mode="json")
            for r in records
            if r.business_id == business_id
        ]
    # Backfill per-score reasoning for rows stored before it was captured.
    for row in rows:
        if not row.get("score_explanations"):
            row["score_explanations"] = explain_from_record(row)
    return rows


@app.get("/businesses/{business_id}/rationale")
def business_rationale(business_id: str) -> dict:
    """Return the cached LLM score rationale for one business (if generated)."""
    cached = load_cached(business_id)
    if not cached:
        return {"available": False, "business_id": business_id}
    return {"available": True, **cached}


@app.post("/businesses/{business_id}/rationale")
def generate_business_rationale(business_id: str) -> dict:
    """Generate (and cache) an LLM rationale for every score from its inputs.

    Long-running (one LLM round trip) but synchronous: FastAPI runs this in a
    worker thread so the event loop stays free.
    """
    rows = business_records(business_id)
    if not rows:
        raise HTTPException(404, "No records found for this business")
    try:
        payload = generate_rationales(rows[0])
    except Exception as exc:  # noqa: BLE001 - surface provider failure to UI
        logger.exception("Rationale generation failed for %s", business_id)
        raise HTTPException(502, f"Rationale generation failed: {exc}") from exc
    save_cached(business_id, payload)
    return {"available": True, **payload}


@app.get("/reports")
def reports() -> list[dict]:
    out = []
    for path in sorted(glob.glob("output/*.md"), reverse=True):
        name = os.path.basename(path)
        out.append({"name": name, "path": path})
    return out


@app.get("/reports/{name}")
def report(name: str) -> dict:
    path = f"output/{name}"
    if not os.path.exists(path):
        raise HTTPException(404, "Report not found")
    with open(path) as f:
        return {"name": name, "content": f.read()}


@app.get("/reports/pdf/{filename}")
def report_pdf(filename: str) -> FileResponse:
    """Download a generated PDF audit report for one analyzed website."""
    safe = Path(filename).name
    path = _pdf_dir() / safe
    if not path.exists():
        raise HTTPException(404, "PDF report not found")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=safe,
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


@app.post("/reports/pdf/generate/{business_id}")
def generate_report_pdf(business_id: str) -> dict:
    """Generate a PDF audit report for a previously analyzed website.

    Uses the full saved record (scores, explanations, recommendations) so
    archived analyses can still produce a downloadable report. New analyses
    generate the PDF automatically while the background job finishes.
    """
    rows = _range_rows()
    row = next((r for r in rows if r.get("id") == business_id), None)
    if row is None:
        raise HTTPException(404, "Website not found in history")
    safe = Path(business_id).name
    stem = f"{safe}_{str(row.get('scanned_at') or 'record')[:10]}"
    path = _pdf_dir() / f"{stem}.pdf"
    generate_pdf(_record_to_pdf_result(row), path)
    filename = path.name
    return {"filename": filename, "url": f"/backend/reports/pdf/{filename}"}


def _record_to_pdf_result(row: dict) -> dict:
    """Shape a stored knowledge-base row into the dict the PDF renderer expects."""
    expl = row.get("score_explanations") or explain_from_record(row)
    rec: dict[str, list[str]] = {}
    for k in ("daily", "weekly", "monthly", "quarterly", "yearly"):
        v = row.get(k) or ""
        rec[k] = [p.strip() for p in str(v).split(",") if p.strip()] if isinstance(v, str) else []
    return {
        "lead": {
            "name": row.get("name") or "Website audit",
            "url": row.get("website_url") or row.get("url") or "",
            "industry": row.get("industry") or "",
            "region": row.get("region") or "",
            "platform": row.get("platform") or "",
        },
        "scores": {d: row.get(d) for d in SCORE_DIMENSIONS},
        "score_explanations": expl,
        "qualification": {
            "priority": row.get("lead_priority") or "n/a",
            "reason": row.get("notes") or "",
        },
        "recommendation": rec,
        "evidence": {},
        "security": {},
    }


@app.get("/history")
def history() -> list[dict]:
    """Every previously analyzed website with its full data + PDF reports.

    Each entry carries the latest scorecard, qualification, security risk,
    a complete per-scan history, and every generated PDF for that website.
    """
    rows = _range_rows()
    pdfs: dict[str, list[str]] = {}
    if _pdf_dir().exists():
        for p in sorted(_pdf_dir().glob("*.pdf"), reverse=True):
            base = p.stem.split("_")[0]
            pdfs.setdefault(base, []).append(p.name)

    by_id: dict[str, list[dict]] = {}
    for r in rows:
        by_id.setdefault(r.get("id"), []).append(r)

    out: list[dict] = []
    for r in rows:
        bid = r.get("id")
        files = pdfs.get(bid, [])
        latest_pdf = files[0] if files else ""
        out.append({
            "id": bid,
            "name": r.get("name"),
            "url": r.get("website_url") or r.get("url") or "",
            "region": r.get("region"),
            "industry": r.get("industry"),
            "platform": r.get("platform") or "",
            "contact_email": r.get("contact_email", ""),
            "phone": r.get("phone", ""),
            "lead_priority": r.get("lead_priority"),
            "ai_summary": r.get("ai_summary", ""),
            "scanned_at": r.get("scanned_at"),
            "scores": {d: r.get(d) for d in SCORE_DIMENSIONS},
            "score_explanations": r.get("score_explanations") or explain_from_record(r),
            "change_since_previous": r.get("change_since_previous", ""),
            "scan_count": len(by_id.get(bid, [])),
            "pdfs": files,
            "pdf": {"filename": latest_pdf, "url": f"/backend/reports/pdf/{latest_pdf}" if latest_pdf else ""},
        })
    return out



# ---------------------------------------------------------------------------
# Manual business finder (Find tab)
# ---------------------------------------------------------------------------
_FIND_FILE = Path(settings.DATA_DIR) / "find_jobs.json"
_FIND_JOBS: dict[str, dict] = {}
_FIND_LOCK = threading.Lock()


def _find_load() -> None:
    try:
        if _FIND_FILE.exists():
            with _FIND_FILE.open() as fh:
                _FIND_JOBS.update(json.load(fh))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not load find jobs: %s", exc)


def _find_save() -> None:
    try:
        _FIND_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _FIND_FILE.open("w") as fh:
            json.dump(_FIND_JOBS, fh, indent=2)
    except OSError as exc:
        logger.warning("Could not persist find jobs: %s", exc)


class FinderQueryRequest(BaseModel):
    keyword: str = ""
    region: str = ""
    industry: str = ""
    platform: str = ""
    limit: int = 20


@app.post("/find-businesses", status_code=202)
def start_find(req: FinderQueryRequest) -> dict:
    """Kick off a background discovery job."""
    if not req.keyword.strip():
        raise HTTPException(status_code=422, detail="keyword is required")
    job_id = uuid.uuid4().hex[:10]
    with _FIND_LOCK:
        _FIND_JOBS[job_id] = {"status": "running", "result": None, "error": None}
    _find_save()
    threading.Thread(target=_find_worker, args=(job_id, req), daemon=True).start()
    return {"job_id": job_id}


@app.get("/find-businesses/{job_id}")
def find_status(job_id: str):
    with _FIND_LOCK:
        job = _FIND_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown find job id")
    return job


@app.get("/findings")
def findings_history() -> list[dict]:
    """Completed finder runs (persisted, survives restart), newest first."""
    out: list[dict] = []
    for jid, job in sorted(
        _FIND_JOBS.items(),
        key=lambda kv: kv[1].get("created_at") or "",
        reverse=True,
    ):
        res = job.get("result")
        if not res:
            continue
        out.append({
            "job_id": jid,
            "keyword": res.get("keyword"),
            "region": res.get("region"),
            "industry": res.get("industry"),
            "platform": res.get("platform"),
            "limit": res.get("limit"),
            "count": res.get("count", 0),
            "summary": res.get("summary"),
            "pdf": res.get("pdf") or {},
        })
    return out


def _find_worker(job_id: str, req: FinderQueryRequest) -> None:
    """Run discovery off the request thread; render a findings PDF; persist."""
    try:
        leads = find_businesses(
            req.keyword, region=req.region, industry=req.industry,
            platform=req.platform, limit=req.limit,
        )
        findings = []
        for lead in leads:
            findings.append({
                "name": lead.name, "url": lead.url,
                "platform": lead.platform.value if lead.platform else "unknown",
                "industry": lead.industry or "", "region": lead.region or "",
                "city": lead.city or "", "email": lead.email or "",
                "phone": lead.phone or "",
                "social": dict(lead.social_handles or {}),
                "outreach": getattr(lead, "outreach", ""),
            })
        pdf_url = ""
        pdf_name = ""
        if findings:
            try:
                from src.services.pdfreport import generate_findings_pdf
                pdf_name = f"find_{job_id}.pdf"
                import os
                pdf_dir = Path(settings.OUTPUT_DIR) / "pdf"
                pdf_dir.mkdir(parents=True, exist_ok=True)
                generate_findings_pdf(findings, pdf_dir / pdf_name,
                                      title=f"Business findings — {req.keyword} ({req.region or 'world'})")
                pdf_url = f"/backend/reports/pdf/{pdf_name}"
            except Exception as exc:
                logger.warning("findings PDF failed for %s: %s", job_id, exc)
        result = {
            "keyword": req.keyword, "region": req.region,
            "industry": req.industry, "platform": req.platform,
            "limit": req.limit, "count": len(findings),
            "findings": findings,
            "summary": f"{len(findings)} business(es) found for “{req.keyword}” in {req.region or 'the whole world'}.",
            "pdf": {"filename": pdf_name, "url": pdf_url} if pdf_name else None,
        }
        with _FIND_LOCK:
            _FIND_JOBS[job_id] = {
                "status": "done", "result": result, "error": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as exc:
        logger.exception("find job %s failed", job_id)
        with _FIND_LOCK:
            _FIND_JOBS[job_id] = {"status": "error", "result": None, "error": str(exc),
                                  "created_at": datetime.now(timezone.utc).isoformat()}
    _find_save()


_find_load()

@app.post("/schedule")
def schedule(enable: bool = True) -> dict:
    settings.SCHEDULER_ENABLED = enable
    return {"enabled": settings.SCHEDULER_ENABLED}