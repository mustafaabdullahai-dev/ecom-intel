# ecom-intel

Autonomous **ecommerce business intelligence** — a multi-agent AI Consultant
built with LangChain + LangGraph that continuously discovers, analyzes,
monitors, and evaluates ecommerce businesses across any region, scores each one
on a standardized 14-score model, and produces a ranked, prioritized prospect
knowledge base with time-horizon action plans for your sales team.

Runs **fully locally** (Ollama) — no cloud LLM required.

```
discovery -> qualify -> deepdive -> score -> recommend -> store -> report

deepdive (per business, one worker):
  Website -> Marketing -> Social -> Product Trend -> Sentiment -> Competitor
```

## Agents (per the spec)

| # | Agent | File | Route (model) | Role |
|---|---|---|---|---|
| 1 | Business Discovery | `src/agents/discovery.py` | `llama3.3:70b` | Web search per region, shortlist leads, extract contacts. |
| 2 | Website Intelligence | `src/agents/website.py` | `qwen2.5:72b` | Full audit: 36 category scores, SEO, UX, CWV, SSL, load time. |
| 3 | Marketing Intelligence | `src/agents/marketing.py` | `llama3.3:70b` | 20 channel scores, funnel, retention, automation maturity. |
| 4 | Social Media Intelligence | `src/agents/social.py` | `qwen2.5:72b` | Per-platform metrics (IG, TikTok, FB...), community, social-commerce readiness. |
| 5 | Product Trend Intelligence | `src/agents/product_trend.py` | `deepseek-r1:70b` | Demand, trend direction, lifecycle, new/upsell/cross-sell product ideas. |
| 6 | Customer Sentiment | `src/agents/sentiment.py` | `qwen2.5:72b` | Review mining, complaints, satisfaction & reputation scores. |
| 7 | Competitor Intelligence | `src/agents/competitor.py` | `deepseek-r1:70b` | Named competitors, benchmarks, competitive gaps, position. |
| 8 | AI Recommendation Engine | `src/agents/recommendation.py` | `deepseek-r1:70b` | Daily/weekly/monthly/quarterly/yearly plans + AI summary. |

The **14-score system** (`src/scoring.py`) is deterministic arithmetic — no LLM —
so scores and lead-priority tiers (high/medium/low) stay reproducible. The
per-role model routing lives in `src/llm.py` (`MODEL_ASSIGNMENTS`) and can be
overridden via `OLLAMA_ROLE_MODELS` in `.env`.

## Project layout

```
ecom-intel/
├── main.py                        # CLI: single run | --schedule | --serve | --dashboard
├── requirements.txt
├── .env.example                   # copy to .env
├── deploy/schema.sql              # PostgreSQL + pgvector schema
├── docs/ROADMAP.md                # infrastructure & cost roadmap
├── src/
│   ├── llm.py                     # per-agent model factory (Ollama)
│   ├── scheduler.py               # APScheduler daily/weekly/monthly/quarterly/yearly
│   ├── scoring.py                 # deterministic 14-score engine + priority tiers
│   ├── schemas/                   # pydantic models (agents, scores, records)
│   ├── agents/                    # the 8 agents + evidence gatherer (+ semantic memory)
│   ├── workflows/orchestrator.py  # LangGraph state machine
│   ├── services/
│   │   ├── fetcher.py             # anti-bot fetch: HTTP | Playwright + proxy
│   │   ├── sources/               # SERP, PageSpeed, SEO, social API adapters
│   │   ├── db.py                  # Postgres + pgvector memory (optional)
│   │   ├── embeddings.py          # local Ollama embeddings
│   │   ├── tasks.py               # Celery deepdive workers (optional)
│   │   ├── search.py, scraper.py, records.py, storage.py, sheets.py, reporting.py
│   ├── api.py                     # FastAPI layer (--serve)
│   ├── dashboard.py               # Streamlit dashboard (--dashboard)
│   ├── config/settings.py         # env-driven settings
│   └── utils/helpers.py           # prompt helpers, JSON parsing, slugs
├── data/                          # JSON knowledge base (per-business history)
└── output/                        # audit + monthly/quarterly/yearly reports
```

## Requirements

- **Python 3.10+** (tested on 3.14)
- **Ollama** running with the routed models pulled:

```bash
ollama pull llama3.3:70b
ollama pull qwen2.5:72b
ollama pull deepseek-r1:70b
```

Smaller machines: edit `src/llm.py` `MODEL_ASSIGNMENTS` to e.g. `qwen2.5:7b`,
`llama3.1:8b`, `deepseek-r1:8b`.

## Setup

```bash
cd ecom-intel
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Usage

```bash
python main.py --regions "Egypt" "Dubai"         # one full run
python main.py --regions "USA" --target 15 --yes
SCHEDULER_ENABLED=true python main.py --schedule # 24/7 automation loop
```

Output:

- `output/audit_<run>.md` — full per-business audit (all agents + 14 scores)
- `data/history.json` — append-only knowledge base (drives "change since last scan")
- Google Sheets — when `GOOGLE_SHEETS_CREDENTIALS` + `GOOGLE_SHEETS_ID` are set
- `output/monthly_*.md`, `quarterly_*.md`, `yearly_*.md` — from the scheduler

## Configuration (.env)

| Variable | Default | Meaning |
|---|---|---|
| `OLLAMA_MODEL` | `llama3.1` | Fallback model |
| `OLLAMA_ROLE_MODELS` | (routing table) | Per-agent model JSON override |
| `DISCOVERY_TARGET` | `10` | Max leads per run |
| `MIN_CONFIDENCE` | `50` | Qualification cutoff |
| `GOOGLE_SHEETS_CREDENTIALS` | | Service-account JSON path |
| `GOOGLE_SHEETS_ID` | | Spreadsheet id |
| `FETCH_MODE` | `http` | `playwright` for headless Chromium (JS-heavy sites) |
| `PROXY_URL` | | Residential proxy exit for anti-bot walls |
| `PAGESPEED_API_KEY` / `SERP_PROVIDER` / `SEO_PROVIDER` / `SOCIAL_PROVIDER` | `none` | Free/paid data-source adapters |
| `DATABASE_URL` | | Postgres + pgvector (see `deploy/schema.sql`) |
| `USE_CELERY` / `CELERY_BROKER_URL` | `false` / redis://:6379 | Distributed deepdive |
| `SCHEDULER_ENABLED` | `false` | Run the APScheduler loop |
| `DAILY_HOUR` / `WEEKLY_DAY` / `MONTHLY_DAY` / `QUARTERLY_MONTHS` / `YEARLY_MONTH` | | Job timing |
| `FALLBACK_PROVIDER` | `none` | `openai-compatible` to use a remote model |

## Notes / limitations

- LangGraph 1.2's `Send` fan-outs double-fire on this version, so deepdive is a
  single sequential worker by default; `USE_CELERY=true` moves it to a
  distributed queue (see `docs/ROADMAP.md`).
- Businesses blocking scrapers are scored from search snippets only; enable
  Playwright + a proxy (`FETCH_MODE=playwright`, `PROXY_URL=...`) for JS-heavy
  and challenge-gated stores.
- DuckDuckGo (`src/services/search.py`) is the no-key default; richer discovery
  (Google Maps, social listening) needs paid APIs.
- Postgres, Celery, FastAPI and the Streamlit dashboard are optional plug-ins —
  the full pipeline runs with zero keys and no external services.