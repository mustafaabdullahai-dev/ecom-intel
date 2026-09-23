import { Fragment, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Tag } from "@/components/Bits";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import type { HistoryItem } from "@/lib/types";

export default function HistoryPage() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [generating, setGenerating] = useState<string | null>(null);

  useEffect(() => {
    api.history().then(setItems).catch((e) => setError(String(e)));
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return items.filter(
      (it) =>
        !q ||
        [it.name, it.url, it.industry, it.region, it.platform]
          .join(" ")
          .toLowerCase()
          .includes(q),
    );
  }, [items, query]);

  async function downloadPdf(it: HistoryItem) {
    let url = it.pdf.url;
    if (!url) {
      setGenerating(it.id);
      try {
        const meta = await api.generatePdf(it.id);
        url = meta.url;
      } catch {
        setGenerating(null);
        setError("Could not generate PDF for this entry.");
        return;
      }
      setGenerating(null);
    }
    const a = document.createElement("a");
    a.href = url;
    a.target = "_blank";
    a.download = it.pdf.filename || "audit_report.pdf";
    a.click();
  }

  return (
    <>
      <div className="page-head">
        <h1>Analysis history</h1>
        <p className="caption">
          Every website ever audited — complete scorecards, per-score reasoning, and
          downloadable PDF reports that stay available even after the server restarts.
        </p>
      </div>

      <input
        className="input"
        placeholder="Search by name, URL, industry, region…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        style={{ maxWidth: 460, marginBottom: 16 }}
      />
      {error && <div className="notice" style={{ marginBottom: 12 }}>⚠ {error}</div>}

      {filtered.length === 0 ? (
        <div className="notice info">
          No analyses yet. Analyze a website from the{" "}
          <Link to="/analyze" style={{ color: "var(--accent)" }}>Analyze website</Link> page to build
          your history.
        </div>
      ) : (
        <div className="section">
          <div className="table-wrap" style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Business</th>
                  <th>Industry</th>
                  <th>Priority</th>
                  <th>Health</th>
                  <th>Oppty</th>
                  <th>Scans</th>
                  <th>Last scan</th>
                  <th>PDF report</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((it) => (
                  <Fragment key={it.id}>
                    <tr
                      className="clickable"
                      onClick={() => setOpen(open === it.id ? null : it.id)}
                    >
                      <td>
                        <b>{it.name}</b>
                        <div className="muted" style={{ fontSize: 11 }}>{it.url}</div>
                      </td>
                      <td className="muted">{it.industry || it.platform || "—"}</td>
                      <td><Tag priority={it.lead_priority} /></td>
                      <td className="mono">{it.scores?.business_health ?? "—"}</td>
                      <td className="mono">{it.scores?.ai_opportunity ?? "—"}</td>
                      <td className="mono">{it.scan_count ?? 1}</td>
                      <td className="mono muted">{(it.scanned_at || "—").slice(0, 19)}</td>
                      <td onClick={(e) => e.stopPropagation()}>
                        <button
                          className="btn ghost"
                          style={{ fontSize: 12, padding: "5px 10px", whiteSpace: "nowrap" }}
                          onClick={() => downloadPdf(it)}
                          disabled={generating === it.id}
                        >
                          {generating === it.id ? "Generating…" : it.pdf.url ? "⬇ PDF" : "⤓ Generate PDF"}
                        </button>
                      </td>
                    </tr>
                    {open === it.id && (
                      <tr key={`${it.id}-detail`}>
                        <td colSpan={8} style={{ padding: 0, border: "none" }}>
                          <div style={{ padding: 16, background: "var(--bg, #0f172a)" }}>
                            <div className="grid cols-2" style={{ gap: 20 }}>
                              <div>
                                <h3 style={{ marginBottom: 10 }}>Score breakdown &amp; reasoning</h3>
                                <ScoreBreakdown
                                  row={{ ...it.scores, score_explanations: it.score_explanations }}
                                />
                              </div>
                              <div>
                                <h3 style={{ marginBottom: 10 }}>Summary &amp; contacts</h3>
                                <div style={{ fontSize: 13, lineHeight: 1.6 }}>
                                  <div className="muted" style={{ maxHeight: 160, overflow: "auto", marginBottom: 10 }}>
                                    {it.ai_summary || "No AI summary stored."}
                                  </div>
                                  <div><span className="muted">URL:</span> {it.url || "—"}</div>
                                  <div><span className="muted">Region:</span> {it.region || "—"}</div>
                                  <div><span className="muted">Platform:</span> {it.platform || "—"}</div>
                                  <div><span className="muted">Email:</span> {it.contact_email || "—"}</div>
                                  <div><span className="muted">Phone:</span> {it.phone || "—"}</div>
                                  {it.change_since_previous && (
                                    <div><span className="muted">Change:</span> {it.change_since_previous}</div>
                                  )}
                                </div>
                                {it.pdfs.length > 1 && (
                                  <div style={{ marginTop: 12 }}>
                                    <span className="muted">All PDFs for this site:</span>
                                    <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 6 }}>
                                      {it.pdfs.map((f) => (
                                        <a key={f} href={`/backend/reports/pdf/${encodeURIComponent(f)}`} download style={{ fontSize: 12 }}>
                                          ⬇ {f}
                                        </a>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}