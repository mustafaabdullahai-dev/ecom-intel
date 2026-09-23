import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Tag } from "@/components/Bits";
import type { Health, Stats } from "@/lib/types";

interface Stage {
  order: number;
  node: string;
  agents: string[];
  output: string;
}

interface AgentRole {
  stage: string;
  agent: string;
  local_model: string;
  remote_model: string;
  job: string;
}

interface NavTab {
  group: string;
  tab: string;
  route: string;
  purpose: string;
  data: string;
}

const PIPELINE: Stage[] = [
  { order: 1, node: "Discovery", agents: ["Discovery Agent"], output: "Lead candidates per region (name, url, socials, email)" },
  { order: 2, node: "Qualify", agents: ["Qualifier (deterministic)"], output: "Qualified leads that pass the minimum-confidence pre-filter" },
  { order: 3, node: "Deepdive", agents: ["Website", "Marketing", "Social", "Product Trend", "Sentiment", "Competitor", "Security"], output: "Raw structured evidence per dimension for each business" },
  { order: 4, node: "Score", agents: ["AI Scoring Engine (deterministic)"], output: "14 standardized /100 scores + per-score reasoning" },
  { order: 5, node: "Recommend", agents: ["Recommendation Engine"], output: "Priority (high/medium/low) + time-horizon growth plan" },
  { order: 6, node: "Store", agents: ["Storage + Sheets Exporter"], output: "History records in JSON + Postgres/pgvector + Google Sheets" },
  { order: 7, node: "Report", agents: ["Report Writer"], output: "Markdown audit report + optional PDF" },
];

const AGENT_ROLES: AgentRole[] = [
  { stage: "Discovery", agent: "Discovery Agent", local_model: "llama3.3:70b", remote_model: "gpt-oss-20b / nemotron-120b", job: "SERP + directory mining, structured lead extraction" },
  { stage: "Deepdive", agent: "Website Agent", local_model: "qwen2.5:72b", remote_model: "gpt-oss-20b / nemotron-120b", job: "Site audit: stack, UX, perf, content quality (strict JSON schema)" },
  { stage: "Deepdive", agent: "Marketing Agent", local_model: "llama3.3:70b", remote_model: "gpt-oss-120b / nemotron-120b", job: "Marketing maturity, channels, funnel analysis" },
  { stage: "Deepdive", agent: "Social Media Agent", local_model: "qwen2.5:72b", remote_model: "gpt-oss-20b / nemotron-120b", job: "Social presence, engagement, follower signals" },
  { stage: "Deepdive", agent: "Product Trend Agent", local_model: "deepseek-r1:70b", remote_model: "gpt-oss-120b / nemotron-550b", job: "Market/product trend analysis, category momentum" },
  { stage: "Deepdive", agent: "Sentiment Agent", local_model: "qwen2.5:72b", remote_model: "gpt-oss-120b / nemotron-120b", job: "Review/customer sentiment across the brand footprint" },
  { stage: "Deepdive", agent: "Competitor Agent", local_model: "deepseek-r1:70b", remote_model: "gpt-oss-120b / nemotron-550b", job: "Competitor benchmarking and positioning gaps" },
  { stage: "Deepdive", agent: "Security Agent", local_model: "deepseek-r1:70b", remote_model: "gpt-oss-120b / nemotron-550b", job: "Website security audit: HTTPS, headers, findings, remediation" },
  { stage: "Recommend", agent: "Recommendation Engine", local_model: "deepseek-r1:70b", remote_model: "gpt-oss-120b / nemotron-550b", job: "Strategic roadmap synthesis across all evidence" },
];

const SCORE_DIMENSIONS: { code: string; label: string }[] = [
  { code: "website", label: "Website quality" },
  { code: "seo", label: "SEO readiness" },
  { code: "marketing", label: "Marketing maturity" },
  { code: "brand", label: "Brand strength" },
  { code: "social", label: "Social presence" },
  { code: "content", label: "Content quality" },
  { code: "customer_experience", label: "Customer experience" },
  { code: "trust", label: "Trust signals" },
  { code: "technical", label: "Technical health" },
  { code: "product_trend", label: "Product trend" },
  { code: "growth_potential", label: "Growth potential" },
  { code: "lead_qualification", label: "Lead qualification" },
  { code: "business_health", label: "Business health" },
  { code: "ai_opportunity", label: "AI opportunity" },
];

const NAV_TABS: NavTab[] = [
  { group: "Consultant", tab: "Overview", route: "/overview", purpose: "Agent dashboard — pipeline, model routing, health, and this navigation spec.", data: "Pipeline spec + live /health + /stats" },
  { group: "Consultant", tab: "Executive dashboard", route: "/", purpose: "Top-level KPIs across the whole knowledge base.", data: "/dashboard-data + /stats" },
  { group: "Consultant", tab: "Qualified leads", route: "/leads", purpose: "Ranked, AI-scored business list with full scorecards.", data: "/businesses + /dashboard-data" },
  { group: "Consultant", tab: "Trends & insights", route: "/insights", purpose: "Cross-business benchmarks, distributions, weakest dimensions.", data: "/dashboard-data + /stats" },
  { group: "Operations", tab: "Run analysis", route: "/run", purpose: "Trigger the full 8-agent pipeline for chosen regions/industries.", data: "POST /run" },
  { group: "Operations", tab: "Analyze website", route: "/analyze", purpose: "Single-URL deepdive with security audit + PDF report.", data: "POST /analyze (poll job)" },
  { group: "Operations", tab: "Analysis history", route: "/history", purpose: "Every analyzed website with scorecard, security risk, PDFs.", data: "/history" },
  { group: "Operations", tab: "24/7 automation", route: "/automation", purpose: "Scheduled daily/weekly/monthly/quarterly/yearly runs.", data: "/schedules + POST /schedule" },
  { group: "Operations", tab: "Audit reports", route: "/reports", purpose: "Generated markdown audit reports.", data: "/reports + /reports/{name}" },
  { group: "Knowledge", tab: "Semantic search", route: "/search", purpose: "pgvector semantic search over agent memory (Agent 6/7 evidence).", data: "/similar?q=" },
  { group: "Knowledge", tab: "Storage & sources", route: "/storage", purpose: "Backend stores and data sources status.", data: "/health" },
];

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="meta-block" style={{ margin: 0, display: "flex", justifyContent: "space-between", gap: 16, borderTop: "none", borderBottom: "1px solid var(--border)", padding: "9px 0" }}>
      <span style={{ color: "var(--muted)" }}>{k}</span>
      <span style={{ textAlign: "right" }}>{v}</span>
    </div>
  );
}

export default function OverviewPage() {
  const [health, setHealth] = useState<Health | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setError(String(e)));
    api.stats().then(setStats).catch(() => undefined);
  }, []);

  const priorities = stats?.priorities ?? {};

  return (
    <>
      <div className="page-head">
        <h1>Overview</h1>
        <p className="caption">
          Agent dashboard — the AI Ecommerce Consultant system, its pipeline, model routing,
          and the specification of every tab in this UI.
        </p>
      </div>

      {error && <div className="notice" style={{ marginBottom: 18 }}>⚠ {error}</div>}

      <div className="health-strip">
        <span className={`pill ${health?.status === "ok" ? "good" : "bad"}`}>API {health?.status ?? "…"}</span>
        <span className={`pill ${health?.postgres ? "good" : "bad"}`}>Postgres {health?.postgres ? "connected" : "off"}</span>
        <span className={`pill ${health?.sheets ? "good" : "bad"}`}>Sheets {health?.sheets ? "on" : "off"}</span>
        <span className={`pill ${health?.scheduler ? "good" : "bad"}`}>Scheduler {health?.scheduler ? "on" : "off"}</span>
        <span className={`pill ${health?.celery ? "good" : "bad"}`}>Celery {health?.celery ? "on" : "off"}</span>
        <span className={`pill ${health?.serp ? "good" : "bad"}`}>SERP {health?.serp ? "on" : "off"}</span>
        <span className="pill">fetch: {health?.fetch_mode}</span>
        {health?.providers?.map((p) => (
          <span className={`pill ${p.configured ? "good" : "bad"}`} key={p.name}>
            {p.name} {p.configured ? `· ${p.model}` : "no key"}
          </span>
        ))}
      </div>

      <div className="grid cols-4">
        <div className="card kpi">
          <div className="label">Businesses tracked</div>
          <div className="value">{stats?.businesses ?? 0}</div>
          <div className="sub">{Object.keys(stats?.regions ?? {}).length} region(s) covered</div>
        </div>
        <div className="card kpi">
          <div className="label">Avg AI opportunity</div>
          <div className="value amber">{stats?.dimension_averages?.ai_opportunity ?? "—"}</div>
          <div className="sub">headroom across leads /100</div>
        </div>
        <div className="card kpi">
          <div className="label">Avg business health</div>
          <div className="value">{stats?.dimension_averages?.business_health ?? "—"}</div>
          <div className="sub">overall digital maturity /100</div>
        </div>
        <div className="card kpi">
          <div className="label">Priority mix</div>
          <div className="value" style={{ fontSize: 15, marginTop: 10, lineHeight: 2 }}>
            <Tag priority="high" /> <b>{priorities.high ?? 0}</b>{"   "}
            <Tag priority="medium" /> <b>{priorities.medium ?? 0}</b>{"   "}
            <Tag priority="low" /> <b>{priorities.low ?? 0}</b>
          </div>
        </div>
      </div>

      <div className="section grid" style={{ gridTemplateColumns: "1.6fr 1fr" }}>
        <div className="card">
          <h2>Agent pipeline — 8-agent state machine</h2>
          <p className="caption" style={{ marginBottom: 12 }}>
            discovery → qualify → deepdive (6 analysts + security) → score → recommend → store → report.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Node</th>
                  <th>Agents</th>
                  <th>Structured output</th>
                </tr>
              </thead>
              <tbody>
                {PIPELINE.map((s) => (
                  <tr key={s.node}>
                    <td className="mono muted">{s.order}</td>
                    <td><b>{s.node}</b></td>
                    <td style={{ whiteSpace: "normal" }}>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                        {s.agents.map((a) => (
                          <span className="chip" key={a}>{a}</span>
                        ))}
                      </div>
                    </td>
                    <td className="muted" style={{ whiteSpace: "normal", maxWidth: 320 }}>{s.output}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <h2>Agent identity</h2>
            <Row k="System" v={<b>AI Ecommerce Consultant</b>} />
            <Row k="Sub-agents" v={PIPELINE.reduce((n, s) => n + s.agents.length, 0)} />
            <Row k="Runtime" v="LangGraph state machine" />
            <Row k="Scoring" v="Deterministic, reproducible (no LLM)" />
            <Row k="Status" v={
              <span className={`pill ${health?.status === "ok" ? "good" : "bad"}`}>
                {health?.status ?? "…"}
              </span>
            } />
            <Row k="Data source" v={health?.postgres ? "Postgres + pgvector" : "Local JSON store"} />
          </div>

          <div className="card">
            <h2>Scoring engine — 14 dimensions</h2>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {SCORE_DIMENSIONS.map((d) => (
                <span className="chip" key={d.code} title={d.code}>{d.label}</span>
              ))}
            </div>
            <div className="caption" style={{ marginTop: 10 }}>
              Evidence feeds from the Qwen/Llama agents; scores are plain arithmetic so results stay
              reproducible across runs and providers.
            </div>
          </div>
        </div>
      </div>

      <div className="section">
        <h2>Model routing per agent role</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Stage</th>
                <th>Agent</th>
                <th>Local (Ollama) model</th>
                <th>Remote fallback models</th>
                <th>Job</th>
              </tr>
            </thead>
            <tbody>
              {AGENT_ROLES.map((r) => (
                <tr key={r.agent}>
                  <td className="muted">{r.stage}</td>
                  <td><b>{r.agent}</b></td>
                  <td className="mono">{r.local_model}</td>
                  <td className="mono muted">{r.remote_model}</td>
                  <td className="muted" style={{ whiteSpace: "normal", maxWidth: 340 }}>{r.job}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="section">
        <h2>Navigation — tab specifications</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Group</th>
                <th>Tab</th>
                <th>Route</th>
                <th>Purpose</th>
                <th>Data (structured)</th>
              </tr>
            </thead>
            <tbody>
              {NAV_TABS.map((t) => (
                <tr key={t.route + t.tab}>
                  <td><span className="chip">{t.group}</span></td>
                  <td>
                    <Link to={t.route} style={{ fontWeight: 700, color: "var(--accent-2)" }}>{t.tab}</Link>
                  </td>
                  <td className="mono muted">{t.route}</td>
                  <td className="muted" style={{ whiteSpace: "normal", maxWidth: 340 }}>{t.purpose}</td>
                  <td className="mono muted">{t.data}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="section">
        <h2>Q&A — scoring concepts, explained (README)</h2>
        <p className="caption" style={{ marginBottom: 14 }}>
          A reference for the four questions everyone asks: what counts as a qualified lead,
          what a number like 87 for AI opportunity really means, how business health is derived,
          and why a business gets tagged high / medium / low priority.
        </p>

        {[
          {
            q: "What is a “qualified lead”?",
            dimension: "lead_qualification",
            oneLine:
              "How good a sales prospect a business is — a deterministic blend of its weaknesses (room to improve) and its demonstrated potential (demand + audience).",
            what: (
              <>
                The qualification step has two layers. A fast <b>pre-filter</b> at the start of the
                pipeline drops dead ends: a lead only survives if it has a real signal — a working
                website, social handles, or an email. The detailed <b>lead_qualification score (0–100)</b>
                is then computed by the scoring engine from how badly the business underperforms on
                things we can fix, combined with how much latent demand and audience it already has.
              </>
            ),
            how: (
              <>
                <div className="mono" style={{ color: "var(--accent-2)", margin: "8px 0" }}>
                  lead_qualification = avg[<br />
                  &nbsp;&nbsp;(100 − website), &nbsp;&nbsp;→ capability gap (90 if no website)<br />
                  &nbsp;&nbsp;(100 − seo), &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;→ organic gap (90 if no website)<br />
                  &nbsp;&nbsp;(100 − marketing), &nbsp;&nbsp;→ marketing gap (80 if no data)<br />
                  &nbsp;&nbsp;product demand, &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;→ is the market buying?<br />
                  &nbsp;&nbsp;social score, &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;→ does an audience exist?<br />
                  &nbsp;&nbsp;active (100 with evidence, else 40) &nbsp;→ is it an operating business?<br />
                  ]
                </div>
                A high score therefore means: <i>a real, operating business with demand and an
                audience that is under-delivering on the digital capabilities we can improve.</i>
              </>
            ),
            read: "High = ideal consulting/client prospect. Mid = ambivalent, needs evidence before pitching. Low = weak signals, cold outreach unlikely to convert.",
            used: ["Qualified leads tab", "Executive dashboard table", "Overview KPIs", "Export CSV"],
          },
          {
            q: "What does “AI opportunity” measure?",
            dimension: "ai_opportunity",
            oneLine:
              "The overall AI-driven service opportunity for us — an aggregate of how much the business needs help, can benefit, and is worth pursuing competitively.",
            what: (
              <>
                AI opportunity is the headline number for the whole funnel. It combines four signals:
                the lead’s qualification, how much headroom its business health leaves on the table,
                how weak its competitive position is, and whether its product has market momentum.
              </>
            ),
            how: (
              <>
                <div className="mono" style={{ color: "var(--accent-2)", margin: "8px 0" }}>
                  ai_opportunity = avg[<br />
                  &nbsp;&nbsp;lead_qualification, &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;→ how good a prospect it is<br />
                  &nbsp;&nbsp;100 − business_health, &nbsp;→ “how sick” — the fixable upside<br />
                  &nbsp;&nbsp;100 − competitor_score, → how beatable the competition is (50 if n/a)<br />
                  &nbsp;&nbsp;product_trend &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;→ market momentum<br />
                  ]
                </div>
                A business with a mediocre site but strong demand and weak rivals scores far higher
                than a business that is already digitally mature.
              </>
            ),
            read: "Higher = pitch priority. This is the number the executive dashboard averages and the leads table sorts on.",
            used: ["Executive dashboard “Avg AI opportunity”", "Qualified leads — ranked view", "Audit reports / PDF summaries"],
          },
          {
            q: "What is “business health”?",
            dimension: "business_health",
            oneLine:
              "A business’s overall digital maturity — the simple average of its nine capability scores.",
            what: (
              <>
                Health is a plain composite of the operational dimensions, not an estimate. If your
                website is broken, SEO is absent and your social is sparse, health drops — no matter
                how strong the product is. It answers: <i>“how well is this business actually run
                online today?”</i>
              </>
            ),
            how: (
              <>
                <div className="mono" style={{ color: "var(--accent-2)", margin: "8px 0" }}>
                  business_health = avg[<br />
                  &nbsp;&nbsp;website, seo, marketing, brand, social, content,<br />
                  &nbsp;&nbsp;customer_experience, trust, technical<br />
                  ]
                </div>
                Because opportunity = 100 − health, a low health score is <b>not</b> bad news for us —
                it is literally the headroom where an engagement creates value.
              </>
            ),
            read: "0–40 = high headroom (prime consulting target). 40–70 = moderate. 70+ = already healthy, limited upsell.",
            used: ["Executive dashboard “Avg business health”", "Score bars per dimension", "Export CSV"],
          },
          {
            q: "What does “priority context” (high / medium / low) mean?",
            dimension: "lead_qualification",
            oneLine:
              "The deterministic tier each business is bucketed into from its lead-qualification score, with an auto-generated reason.",
            what: (
              <>
                Every business gets one of three tags. The tier is pure arithmetic, so two scans of
                the same business always produce the same tier (values are reproducible). The tag
                comes with a <b>reason string</b> generated from the score line, e.g.
                “high-priority because of weak website, poor SEO, low marketing maturity, healthy
                product demand, existing audience.”
              </>
            ),
            how: (
              <table style={{ marginBottom: 8 }}>
                <thead>
                  <tr>
                    <th>lead_qualification</th>
                    <th>Priority</th>
                    <th>Profile</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="mono">≥ 72</td>
                    <td><Tag priority="high" /></td>
                    <td className="muted" style={{ whiteSpace: "normal" }}>Active business, real demand/audience, big measurable gaps to fix.</td>
                  </tr>
                  <tr>
                    <td className="mono">45 – 71</td>
                    <td><Tag priority="medium" /></td>
                    <td className="muted" style={{ whiteSpace: "normal" }}>Some signals; worth a targeted pitch, may need validation.</td>
                  </tr>
                  <tr>
                    <td className="mono">&lt; 45</td>
                    <td><Tag priority="low" /></td>
                    <td className="muted" style={{ whiteSpace: "normal" }}>Weak signals; low conversion probability, deprioritized.</td>
                  </tr>
                </tbody>
              </table>
            ),
            read: "The tag drives the priority mix KPI, lead filtering, the CSV export, and PDF audit reports.",
            used: ["Overview “Priority mix” KPI", "Qualified leads — priority column", "Audit reports", "Export CSV"],
          },
        ].map((item) => {
          const live = stats?.dimension_averages?.[item.dimension];
          return (
            <details key={item.q} className="card faq" style={{ marginBottom: 12, padding: "16px 20px" }}>
              <summary style={{ cursor: "pointer", fontSize: 15, fontWeight: 700, display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ color: "var(--accent-2)" }}>Q.</span> {item.q}
                <span className="pill" style={{ marginLeft: "auto" }}>
                  avg {live ?? "—"}/100
                </span>
              </summary>
              <div style={{ marginTop: 14, lineHeight: 1.7, fontSize: 13.5 }}>
                <div className="card" style={{ background: "var(--panel-2)", padding: "12px 14px", marginBottom: 12 }}>
                  <b style={{ color: "var(--accent-2)" }}>In one line —</b>
                  <span style={{ color: "var(--text)" }}> {item.oneLine}</span>
                </div>

                <div style={{ marginBottom: 10 }}>
                  <b>What it measures</b>
                  <div className="muted">{item.what}</div>
                </div>

                <div style={{ marginBottom: 10 }}>
                  <b>How it is computed</b>
                  {item.how}
                </div>

                <div style={{ marginBottom: 10 }}>
                  <b>How to read it</b>
                  <div className="muted">{item.read}</div>
                </div>

                <div>
                  <b>Where it shows up</b>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
                    {item.used.map((u) => (
                      <span className="chip" key={u}>{u}</span>
                    ))}
                  </div>
                </div>
              </div>
            </details>
          );
        })}
      </div>
    </>
  );
}