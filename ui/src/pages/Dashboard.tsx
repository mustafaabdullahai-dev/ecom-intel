import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { ScoreBar, Tag } from "@/components/Bits";
import type { DashboardData, Health, RankedRow, Stats } from "@/lib/types";

export default function DashboardPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardData | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.dashboard().then(setData).catch((e) => setError(String(e)));
    api.stats().then(setStats).catch(() => undefined);
    api.health().then(setHealth).catch(() => undefined);
  }, []);

  const rows = useMemo(() => data?.rows ?? [], [data]);
  const top = useMemo(
    () => [...rows].sort((a, b) => (b.ai_opportunity ?? 0) - (a.ai_opportunity ?? 0)),
    [rows],
  );

  const dimensionLabels: Record<string, string> = {
    website: "Website quality",
    seo: "SEO readiness",
    marketing: "Marketing maturity",
    brand: "Brand strength",
    social: "Social presence",
    content: "Content quality",
    customer_experience: "Customer experience",
    trust: "Trust signals",
    technical: "Technical health",
    product_trend: "Product trend",
    growth_potential: "Growth potential",
    lead_qualification: "Lead qualification",
    business_health: "Business health",
    ai_opportunity: "AI opportunity",
  };

  const priorities = stats?.priorities ?? {};
  const regions = stats?.regions ?? {};
  const totalBusinesses = stats?.businesses ?? rows.length;
  const dimensionOrder = [
    "website", "seo", "marketing", "brand", "social", "content",
    "customer_experience", "trust", "technical", "product_trend",
    "growth_potential", "lead_qualification", "business_health", "ai_opportunity",
  ];

  return (
    <>
      <div className="page-head">
        <h1>Executive dashboard</h1>
        <p className="caption">
          8-agent pipeline · 14-point AI scoring model · continuous monitoring
        </p>
      </div>

      {error && <div className="notice" style={{ marginBottom: 18 }}>⚠ {error}</div>}

      <div className="health-strip">
        <span className={`pill ${health?.status === "ok" ? "good" : "bad"}`}>API {health?.status ?? "…"}</span>
        <span className={`pill ${health?.postgres ? "good" : "bad"}`}>Postgres {health?.postgres ? "connected" : "off"}</span>
        <span className={`pill ${health?.sheets ? "good" : "bad"}`}>Sheets {health?.sheets ? "on" : "off"}</span>
        <span className={`pill ${health?.scheduler ? "good" : "bad"}`}>Scheduler {health?.scheduler ? "on" : "off"}</span>
        <span className={`pill ${health?.celery ? "good" : "bad"}`}>Celery {health?.celery ? "on" : "off"}</span>
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
          <div className="value">{totalBusinesses}</div>
          <div className="sub">{Object.keys(regions).length} region(s) covered</div>
        </div>
        <div className="card kpi">
          <div className="label">Avg AI opportunity</div>
          <div className="value">{stats?.dimension_averages?.ai_opportunity ?? "—"}</div>
          <div className="sub">headroom across all leads /100</div>
        </div>
        <div className="card kpi">
          <div className="label">Avg business health</div>
          <div className="value">{stats?.dimension_averages?.business_health ?? "—"}</div>
          <div className="sub">overall digital maturity /100</div>
        </div>
        <div className="card kpi">
          <div className="label">Lead priority mix</div>
          <div className="value" style={{ fontSize: 15, marginTop: 10, lineHeight: 2 }}>
            <Tag priority="high" /> <b>{priorities.high ?? 0}</b>{"   "}
            <Tag priority="medium" /> <b>{priorities.medium ?? 0}</b>{"   "}
            <Tag priority="low" /> <b>{priorities.low ?? 0}</b>
          </div>
        </div>
      </div>

      <div className="section grid" style={{ gridTemplateColumns: "1.4fr 1fr" }}>
        <div className="card">
          <h2>Classifier confidence — 14-point score model (company averages)</h2>
          <p className="caption" style={{ marginBottom: 10 }}>
            Averages across {totalBusinesses} business(es). Each dimension explains what
            it measures and why the average sits where it does.
          </p>
          <div style={{ columnCount: 2, columnGap: 40 }}>
            {dimensionOrder.map((dim) => {
              const ds = stats?.dimension_summaries?.[dim];
              return (
                <div key={dim} style={{ marginBottom: 8, breakInside: "avoid" }}>
                  <ScoreBar
                    name={dimensionLabels[dim]}
                    value={stats?.dimension_averages?.[dim]}
                  />
                  {ds && (
                    <details style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>
                      <summary style={{ cursor: "pointer" }}>
                        {ds.note || `${ds.count} scored business(es)`}
                      </summary>
                      <div style={{ marginTop: 4, lineHeight: 1.5 }}>
                        <b>{ds.what}</b>
                        <div style={{ marginTop: 2 }}>{ds.basis}</div>
                      </div>
                    </details>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <h2>Weakest dimensions (opportunity)</h2>
            <div>
              {(stats?.weakest_dimensions ?? []).map(([name, val]) => (
                <div className="weak-row" key={name}>
                  <span>{dimensionLabels[name] ?? name}</span>
                  <span className="mono">{val}</span>
                </div>
              ))}
              {!stats?.weakest_dimensions?.length && (
                <div className="muted" style={{ fontSize: 13 }}>No scored leads yet.</div>
              )}
            </div>
          </div>
          <div className="card">
            <h2>Geographic coverage</h2>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {Object.entries(regions).map(([reg, n]) => (
                <span className="chip" key={reg}>{reg} · {n}</span>
              ))}
              {!Object.keys(regions).length && (
                <div className="muted" style={{ fontSize: 13 }}>No leads yet.</div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="section">
        <h2>Highest opportunity leads</h2>
        {top.length === 0 ? (
          <div className="notice info">
            No businesses yet. Start a run from the{" "}
            <Link to="/run" style={{ color: "var(--accent)" }}>Run analysis</Link> page.
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Business</th>
                  <th>Region</th>
                  <th>Industry</th>
                  <th>Priority</th>
                  <th>Health</th>
                  <th>Opportunity</th>
                  <th>AI summary</th>
                </tr>
              </thead>
              <tbody>
                {top.slice(0, 12).map((r: RankedRow) => (
                  <tr key={r.id} className="clickable" onClick={() => navigate(`/leads/${r.id}`)}>
                    <td><b>{r.name}</b></td>
                    <td>{r.region}</td>
                    <td className="muted">{r.industry}</td>
                    <td><Tag priority={r.lead_priority} /></td>
                    <td className="mono">{r.business_health ?? "—"}</td>
                    <td className="mono">{r.ai_opportunity ?? "—"}</td>
                    <td style={{ maxWidth: 400, whiteSpace: "normal" }}>
                      <span className="muted">{(r.ai_summary || "").slice(0, 110)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}