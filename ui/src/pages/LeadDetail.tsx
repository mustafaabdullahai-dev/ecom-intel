import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { Spinner, Tag } from "@/components/Bits";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import type { RationalePayload, RecordRow, SimilarHit } from "@/lib/types";

const HORIZONS = [
  ["daily", "Daily improvements"],
  ["weekly", "Weekly improvements"],
  ["monthly", "Monthly improvements"],
  ["quarterly", "Quarterly improvements"],
  ["yearly", "Yearly improvements"],
] as const;

export default function BusinessDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id ?? "";

  const [records, setRecords] = useState<RecordRow[]>([]);
  const [error, setError] = useState("");
  const [rationales, setRationales] = useState<RationalePayload | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState("");

  useEffect(() => {
    api.businessRecords(id).then(setRecords).catch((e) => setError(String(e)));
  }, [id]);

  useEffect(() => {
    setRationales(null);
    setGenError("");
    api
      .rationale(id)
      .then((r) => {
        if (r.available) setRationales(r);
      })
      .catch(() => {});
  }, [id]);

  async function generateRationale() {
    setGenerating(true);
    setGenError("");
    try {
      setRationales(await api.generateRationale(id));
    } catch (e) {
      setGenError(String(e));
    } finally {
      setGenerating(false);
    }
  }

  const latest = records[0];

  if (error) {
    return <div className="notice" style={{ marginTop: 40 }}>⚠ {error}</div>;
  }

  if (!latest) {
    return (
      <div className="notice info" style={{ marginTop: 40 }}>
        Loading business <code>{id}</code>…
      </div>
    );
  }

  const horizons = HORIZONS.filter(([k]) => latest[k]);

  return (
    <>
      <div className="page-head">
        <h1>
          {latest.business_name || id} <small>{latest.business_id}</small>
        </h1>
        <p className="caption">
          {latest.region || ""} · {latest.industry || ""} · monitored knowledge base
          {latest.scanned_at ? ` · last scan ${String(latest.scanned_at).slice(0, 19)}` : ""}
        </p>
      </div>

      <div className="grid cols-4">
        <div className="card kpi">
          <div className="label">Business health</div>
          <div className={`value ${(latest.business_health ?? 0) >= 60 ? "good" : (latest.business_health ?? 0) >= 40 ? "amber" : ""}`}>
            {latest.business_health ?? "—"}
          </div>
        </div>
        <div className="card kpi">
          <div className="label">AI opportunity</div>
          <div className={`value ${(latest.ai_opportunity ?? 0) >= 60 ? "good" : (latest.ai_opportunity ?? 0) >= 40 ? "amber" : ""}`}>
            {latest.ai_opportunity ?? "—"}
          </div>
        </div>
        <div className="card kpi">
          <div className="label">Lead qualification</div>
          <div className="value">{latest.lead_qualification ?? "—"}</div>
        </div>
        <div className="card kpi">
          <div className="label">Priority</div>
          <div style={{ marginTop: 10 }}>
            <Tag priority={latest.lead_priority} />
          </div>
        </div>
      </div>

      <div className="section">
        <h2>Contact</h2>
        <div className="grid cols-2">
          <div className="card">
            <div className="label">Email</div>
            <div className="mono" style={{ fontSize: 15, wordBreak: "break-all" }}>
              {latest.contact_email || "—"}
            </div>
          </div>
          <div className="card">
            <div className="label">Phone / WhatsApp</div>
            <div className="mono" style={{ fontSize: 15 }}>
              {latest.phone || "—"}
            </div>
            {(() => {
              const digits = (latest.phone || "").replace(/\D/g, "");
              if (digits.length < 7 || digits.length > 15) return null;
              return (
                <a
                  className="btn"
                  href={`https://wa.me/${digits}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ marginTop: 10 }}
                >
                  Chat on WhatsApp
                </a>
              );
            })()}
          </div>
        </div>
      </div>

      {latest.change_since_previous && (
        <div className="notice" style={{ marginTop: 16 }}>
          <b>Change since previous scan:</b> {latest.change_since_previous}
        </div>
      )}

      <div className="section grid" style={{ gridTemplateColumns: "1.4fr 1fr" }}>
        <div className="card">
          <div className="bd-head-row">
            <div>
              <h2>14-point score breakdown</h2>
              <p className="caption" style={{ marginBottom: 12 }}>
                {rationales
                  ? "AI reads each dimension's inputs and explains why the score came out that way."
                  : "Every dimension with its score, band, the inputs that drove it, and why."}
              </p>
            </div>
            <button className="btn" onClick={generateRationale} disabled={generating}>
              {generating
                ? "Analysing inputs…"
                : rationales
                  ? "Regenerate AI rationale"
                  : "Generate AI rationale"}
            </button>
          </div>
          {generating && (
            <Spinner label="The model is reviewing every input — this takes a few seconds." />
          )}
          {genError && (
            <div className="notice" style={{ marginBottom: 12 }}>
              ⚠ {genError}
            </div>
          )}
          {rationales?.generated_at && (
            <p className="caption" style={{ marginTop: -4 }}>
              AI rationale generated {String(rationales.generated_at).slice(0, 19)} UTC
            </p>
          )}
          <ScoreBreakdown row={latest} rationales={rationales} />
        </div>

        <div className="card">
          <h2>AI summary</h2>
          <div className="cluster muted" style={{ maxHeight: 240 }}>
            {latest.ai_summary || "No AI summary stored for this scan."}
          </div>
          {(latest.notes || latest.lead_priority) && (
            <div className="meta-block">
              <div>
                <span className="muted">Sales status:</span>{" "}
                <b>{latest.sales_status || "—"}</b>
              </div>
              <div>
                <span className="muted">Outreach status:</span>{" "}
                <b>{latest.outreach_status || "—"}</b>
              </div>
              <div>
                <span className="muted">Notes:</span>{" "}
                <span className="muted">{latest.notes || "—"}</span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="section">
        <h2>Historical performance tracking</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Scanned</th>
                <th>Health</th>
                <th>Opportunity</th>
                <th>Priority</th>
                <th>Change</th>
                <th>AI summary</th>
              </tr>
            </thead>
            <tbody>
              {records.slice(0, 50).map((r, i) => (
                <tr key={i}>
                  <td className="mono muted">{(r.scanned_at || "—").slice(0, 19)}</td>
                  <td className="mono">{r.business_health ?? "—"}</td>
                  <td className="mono">{r.ai_opportunity ?? "—"}</td>
                  <td><Tag priority={r.lead_priority} /></td>
                  <td className="muted" style={{ maxWidth: 260, whiteSpace: "normal" }}>
                    {r.change_since_previous || "—"}
                  </td>
                  <td style={{ maxWidth: 320, whiteSpace: "normal" }} className="muted">
                    {(r.ai_summary || "").slice(0, 140)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {horizons.length > 0 && (
        <div className="section grid cols-2">
          {horizons.map(([k, label]) => (
            <div className="card" key={k}>
              <h2>{label}</h2>
              <div className="cluster muted">{(latest[k] as string) || ""}</div>
            </div>
          ))}
        </div>
      )}

      <div className="section">
        <h2>Semantic memory (Agent 6/7 chunks)</h2>
        <div className="card">
          <SemanticRelated business={id} />
        </div>
      </div>
    </>
  );
}

function SemanticRelated({ business }: { business: string }) {
  const [hits, setHits] = useState<SimilarHit[]>([]);

  useEffect(() => {
    api.similar(business, 6).then(setHits).catch(() => setHits([]));
  }, [business]);

  if (!hits.length)
    return (
      <div className="muted" style={{ fontSize: 13 }}>
        No embedding chunks stored yet (Agent 6/7 + embeddings provider). Run a full scan to populate.
      </div>
    );
  return (
    <div>
      {hits.map((h, i) => (
        <div key={i} style={{ padding: "10px 0", borderBottom: "1px solid var(--border)" }}>
          <span className="muted mono">{h.business_id} · {h.source ?? "site"}</span>
          <div style={{ marginTop: 4 }}>{(h.content as string)?.slice(0, 220)}</div>
        </div>
      ))}
    </div>
  );
}