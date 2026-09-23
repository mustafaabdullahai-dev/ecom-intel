import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { Tag } from "@/components/Bits";
import type { DashboardData, ExportData, RankedRow } from "@/lib/types";

const SCORE_COLS: [string, keyof RankedRow][] = [
  ["Website", "website"],
  ["SEO", "seo"],
  ["Marketing", "marketing"],
  ["Social", "social"],
  ["Product trend", "product_trend"],
  ["CX", "customer_experience"],
  ["Trust", "trust"],
  ["Technical", "technical"],
  ["Health", "business_health"],
  ["Oppty", "ai_opportunity"],
];

export default function LeadsPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardData | null>(null);
  const [query, setQuery] = useState("");
  const [region, setRegion] = useState("all");
  const [priority, setPriority] = useState("all");
  const [error, setError] = useState("");
  const [exportInfo, setExportInfo] = useState<ExportData | null>(null);

  useEffect(() => {
    api.dashboard().then(setData).catch((e) => setError(String(e)));
  }, []);

  const rows = useMemo(() => data?.rows ?? [], [data]);

  const regions = useMemo(
    () => Array.from(new Set(rows.map((r) => r.region).filter(Boolean))).sort(),
    [rows],
  );

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter(
      (r) =>
        (region === "all" || r.region === region) &&
        (priority === "all" || (r.lead_priority || "").toLowerCase() === priority) &&
        (!q ||
          [r.name, r.industry, r.platform, r.website, r.contact_email]
            .join(" ")
            .toLowerCase()
            .includes(q)),
    );
  }, [rows, query, region, priority]);

  async function exportCsv() {
    try {
      const e = await api.exportCsv();
      setExportInfo(e);
      // Build a download from the payload in a new blob.
      const blob = new Blob([e.csv], { type: "text/csv" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = e.filename;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch {
      setError("CSV export failed");
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>Qualified leads</h1>
        <p className="caption">
          Structured dataset for the sales team — scoreboard per spec column set
        </p>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", gap: 14, flexWrap: "wrap" }}>
        <div className="grid cols-4" style={{ flex: 1, marginBottom: 0 }}>
          <input
            className="input"
            placeholder="Search name, industry, website, email…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <select className="select" value={region} onChange={(e) => setRegion(e.target.value)}>
            <option value="all">All regions</option>
            {regions.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <select className="select" value={priority} onChange={(e) => setPriority(e.target.value)}>
            <option value="all">All priorities</option>
            <option value="high">High priority</option>
            <option value="medium">Medium priority</option>
            <option value="low">Low priority</option>
          </select>
          <button className="btn ghost" onClick={exportCsv}>⭳ Export CSV</button>
        </div>
      </div>

      {exportInfo && (
        <div className="notice" style={{ marginTop: 12 }}>
          Exported <b>{exportInfo.rows}</b> row(s) to <code>{exportInfo.filename}</code>.
        </div>
      )}
      {error && <div className="notice" style={{ marginTop: 12 }}>⚠ {error}</div>}

      <div className="section">
        {filtered.length === 0 ? (
          <div className="notice info">
            No leads match. Run a discovery pass from the <b>Run analysis</b> page to find ecommerce businesses.
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Business</th>
                  <th>Region</th>
                  <th>Industry</th>
                  {SCORE_COLS.map(([l, k]) => (
                    <th key={k as string} className="mono">{l}</th>
                  ))}
                  <th>Priority</th>
                  <th>Last scan</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <tr key={r.id} className="clickable" onClick={() => navigate(`/leads/${r.id}`)}>
                    <td>
                      <b>{r.name}</b>
                      <div className="muted" style={{ fontSize: 11 }}>{r.platform || r.phone || r.contact_email}</div>
                    </td>
                    <td>{r.region}</td>
                    <td className="muted">{r.industry}</td>
                    {SCORE_COLS.map(([l, k]) => (
                      <td className="mono" key={k as string}>{r[k] != null ? (r[k] as number) : "—"}</td>
                    ))}
                    <td><Tag priority={r.lead_priority} /></td>
                    <td className="mono muted">{(r.scanned_at || "—").slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!rows.length && (
              <div className="muted" style={{ padding: 14, fontSize: 13 }}>
                Knowledge base is empty — run a full analysis to populate it.
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}