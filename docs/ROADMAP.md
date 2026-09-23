# ecom-intel — Infrastructure Roadmap

Production hardening for the 8-agent pipeline. Everything below is **optional**:
the shipped defaults (no keys, local Ollama, JSON + Google Sheets, sequential
deepdive) run the full system today. Each layer here unblocks scale, data
volume, or resistance to anti-bot walls.

---

## 1. Anti-bot & scraping (implemented — needs keys/hardware)

**Code:** `src/services/fetcher.py`, consumer `src/services/scraper.py`

| Option | Cost | Use |
|---|---|---|
| `FETCH_MODE=playwright` + `playwright install chromium` | free | JS-rendered Shopify/Woo pages, checkout flows, dynamic catalogs |
| `PROXY_URL=http://user:pass@host:port` | paid | residential exit for Cloudflare/CAPTCHA-facing sites |

Providers for residential bandwidth (monthly typical):

- **Bright Data** — ~$3–6/GB residential; mature ecommerce/IG datasets; SOCKS proxies.
- **Oxylabs** — ~$3–10/GB; Web Unlocker bundle handles captchas/Cloudflare out-of-the-box.
- **Scrape-It.Cloud / Scrape-it.home** — cheap rotate-as-you-go packages; fine for low volume.
- **Smartproxy / IPRoyal** — budget residential; slower on aggressive sites.

Combine: proxy + Playwright for the product/site scrape (Agent 2) and the link
probe; keep plain HTTP for search snippets (fast, low proxy cost).

## 2. Data-source API adapters (implemented — API keys required)

**Code:** `src/services/sources/` (serp, pagespeed, seo, social)

- **PageSpeed Insights** — free; supply `PAGESPEED_API_KEY`. Gives Core Web
  Vitals, performance/SEO/accessibility categories for Agent 2 with **real
  field data** (CrUX) instead of LLM estimates.
- **SERP / Maps** — `SERP_PROVIDER=value_serp` (one token, clean JSON, includes
  Google Maps places). `data_for_seo` alternative (login+password REST).
  Supersedes DuckDuckGo for discovery and adds **Google Maps local businesses**.
- **SEO datasets** — `SEO_PROVIDER=ahrefs|semrush|moz`: backlinks, organic
  keyword counts, domain authority → seed Agent 2/3 instead of guessing.
  Typical pricing: Ahrefs Lite ~$129/mo; SEMrush Pro ~$129/mo; Moz Standard
  ~$99/mo. Free tiers: Moz has a 10-query free tier; SEMrush trials.
- **Social listening** — `SOCIAL_PROVIDER=apify` (pay-per-use actors: Instagram,
  TikTok, Facebook). Brandwatch client ships as a documented stub (enterprise
  contracts only).

Adapters degrade gracefully: agent prompts only see evidence if the API
responds; otherwise they score from scraped site + search snippets.

## 3. PostgreSQL + pgvector (implemented — needs a Postgres 14+ instance)

**Code:** `src/services/db.py`, schema in `deploy/schema.sql`,
embeddings in `src/services/embeddings.py`.

- Structured lead tables: `businesses`, `records`, `score_snapshots` (1 business
  → many scans → 14 scores, and 1 business → N competitors in agent output).
- Embeddings (`embeddings` table, `vector(1024)`, HNSW index) store review and
  site-copy chunks; **Agent 6/7 semantic memory** recalls similar observations
  across scans (`/similar`).
- Embedding model runs **locally via Ollama** (`mxbai-embed-large`) — no cloud
  embedding spend. Swap to OpenAI/Cohere embed by replacing `embed_text()`.
- Enable: set `DATABASE_URL`, run `psql "$DATABASE_URL" -f deploy/schema.sql`.
  When unset, every call no-ops and JSON + Sheets remain the store.

Managed options: Neon (free tier), Supabase (free tier + pgvector built-in),
RDS/Aurora. Self-host: docker `pgvector/pgvector:pg16`.

## 4. Celery + Redis (implemented — needs Redis)

**Code:** `src/services/tasks.py`, consumer `src/workflows/orchestrator.py`

- Sequential deepdive is the bottleneck above ~50 leads/run. `USE_CELERY=true`
  dispatches one `deepdive_lead` task per business; each worker renders its
  evidence, runs Website→Competitor with its routed model, and returns
  `BusinessIntelligence` for the score/recommend/store nodes.
- Hard scale ceiling is Ollama throughput — shard Ollama across workers or use
  a GPU host (vLLM/TGI behind an OpenAI-compatible endpoint) and point
  `OLLAMA_BASE_URL` at it.
- Deploy: `docker run -d -p 6379:6379 redis` + `celery -A src.services.tasks worker --concurrency=4`.

## 5. API + dashboard (implemented — needs ports)

**Code:** `src/api.py` (FastAPI), `src/dashboard.py` (Streamlit)

```bash
python main.py --serve          # FastAPI on :8000
python main.py --dashboard      # Streamlit on :8501
```

- `/run` webhook lets the scheduler or a cron POST a new scan; `/businesses`,
  `/businesses/{id}/records`, `/reports`, `/similar` feed the dashboard.
- Streamlit renders the priority funnel + per-business scorecards from the
  latest records (Postgres preferred; JSON fallback).
- Client-facing variant (shadcn/ui + Next.js) can consume the same FastAPI
  endpoints; nothing server-side needs to change.

## 6. Recommendation matrix

| Layer | When to adopt | First action |
|---|---|---|
| Playwright + proxy | Sites get blocked / JS content missed | `playwright install chromium`, ask proxy provider for a trial GB |
| PageSpeed key | Want real CWV, not estimates | free key at pagespeed.web.dev |
| Value Serp | Need Maps discovery + stable SERP | ~$10 trial credit |
| Postgres+pgvector | Growing history / semantic memory | Neon free tier + `deploy/schema.sql` |
| Celery+Redis | >50 leads per run | `docker run redis`, start workers |
| Dashboard/API | Sales team wants self-serve access | `python main.py --serve --dashboard` |

## Cost snapshot (monthly, baseline)

| Item | Low | Medium | Heavy |
|---|---|---|---|
| Proxies | $0 (HTTP only) | $30 (5GB residential) | $300+ |
| SERP/Maps | $0 (DuckDuckGo) | $30 (Value Serp) | $300 (DataForSEO) |
| SEO API | $0 | $99 | $199+ |
| PageSpeed | $0 | $0 | $0 |
| Postgres | $0 (self-host) | $0–25 (Neon/Supabase) | $50+ |
| Redis | $0 (self-host) | $0 | managed $0–30 |
| Embeds | $0 (Ollama) | $0 | GPU $100+ |
| Ollama GPUs | 1×consumer GPU | 1×A10/4090 | A100 cluster |

**Zero-key baseline stays free**: DuckDuckGo + HTTP scrape + JSON/Sheets + local
Ollama embeddings. Every paid layer is additive.