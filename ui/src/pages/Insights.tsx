import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { ScoreBar, Tag } from "@/components/Bits";
import type { DashboardData, Stats } from "@/lib/types";

export default function InsightsPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardData | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.dashboard().then(setData).catch((e) => setError(String(e)));
    api.stats().then(setStats).catch(() => undefined);
  }, []);

  const rows = useMemo(() => data?.rows ?? [], [data]);

  const labels: Record<string, string> = {
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
  };

  return (
    <>
      <div className="page-head">
        <h1>Trends &amp; insights</h1>
        <p className="caption">Market-wide aggregation, industry benchmarks and opportunity hotspots</p>
      </div>

      {error && <div className="notice" style={{ marginBottom: 16 }}>⚠ {error}</div>}

      <div className="section grid" style={{ gridTemplateColumns: "1.4fr 1fr" }}>
        <div className="card">
          <h2>Weakest dimensions — where the market is leaving money on the table</h2>
          <div>
            {(stats?.weakest_dimensions ?? []).map(([dim, val], i) => {
              const ds = stats?.dimension_summaries?.[dim];
              return (
                <div key={dim} className="bench-row">
                  <span className="rank">{i + 1}</span>
                  <div style={{ flex: 1 }}>
                    <ScoreBar name={labels[dim] ?? dim} value={val} />
                    {ds?.note && (
                      <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
                        {ds.note} — {ds.what}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
            {!stats?.weakest_dimensions?.length && (
              <div className="muted" style={{ fontSize: 13 }}>
                No scored data yet — run an analysis to populate benchmarks.
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <h2>Strongest dimensions (saturation)</h2>
          <div>
            {(stats?.strongest_dimensions ?? []).map(([dim, val]) => (
              <div className="strong-row" key={dim}>
                <span>{labels[dim] ?? dim}</span>
                <span className="mono">{val} / 100</span>
              </div>
            ))}
            {!stats?.strongest_dimensions?.length && (
              <div className="muted" style={{ fontSize: 13 }}>—</div>
            )}
          </div>
        </div>
      </div>

      <div className="section grid cols-2">
        <div className="card">
          <h2>Industry distribution</h2>
          <div>
            {Object.entries(stats?.industries ?? {}).map(([ind, n]) => (
              <div className="distribution-row" key={ind}>
                <span>{ind}</span>
                <span className="mono">{n} bus.</span>
              </div>
            ))}
            {!Object.keys(stats?.industries ?? {}).length && (
              <div className="muted" style={{ fontSize: 13 }}>No businesses yet.</div>
            )}
          </div>
        </div>

        <div className="card">
          <h2>Priority mix</h2>
          <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
            <Tag priority="high" /> <b>{stats?.priorities?.high ?? 0}</b>
            <Tag priority="medium" /> <b>{stats?.priorities?.medium ?? 0}</b>
            <Tag priority="low" /> <b>{stats?.priorities?.low ?? 0}</b>
          </div>
          <div className="caption" style={{ marginTop: 10 }}>
            High = weak site, poor SEO, active business, strong sales potential.
          </div>
        </div>
      </div>

      <div className="section">
        <h2>Company benchmark table</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Business</th>
                <th>Region</th>
                <th>Priority</th>
                <th>Health</th>
                <th>Opportunity</th>
                <th>Product trend</th>
                <th>Growth potential</th>
              </tr>
            </thead>
            <tbody>
              {rows
                .sort((a, b) => (b.ai_opportunity ?? 0) - (a.ai_opportunity ?? 0))
                .map((r) => (
                  <tr key={r.id} className="clickable" onClick={() => navigate(`/leads/${r.id}`)}>
                    <td><b>{r.name}</b></td>
                    <td>{r.region}</td>
                    <td><Tag priority={r.lead_priority} /></td>
                    <td className="mono">{r.business_health ?? "—"}</td>
                    <td className="mono">{r.ai_opportunity ?? "—"}</td>
                    <td className="mono">{r.product_trend ?? "—"}</td>
                    <td className="mono">{r.growth_potential ?? "—"}</td>
                  </tr>
                ))}
            </tbody>
          </table>
          {!rows.length && (
            <div className="muted" style={{ padding: 14 }}>No data — run an analysis first.</div>
          )}
        </div>
      </div>
    </>
  );
}