import { useState } from "react";
import { api } from "@/lib/api";
import { Spinner } from "@/components/Bits";
import type { SimilarHit } from "@/lib/types";

const SUGGESTIONS = [
  "shipping complaints",
  "instagram engagement ideas",
  "competitor pricing strategy",
  "product trend 2026",
];

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SimilarHit[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function search(text?: string) {
    const query = (text ?? q).trim();
    if (!query) return;
    setQ(query);
    setBusy(true);
    setError("");
    try {
      const r = await api.similar(query, 10);
      setHits(r);
    } catch (e) {
      setError(String(e));
      setHits([]);
    } finally {
      setBusy(false);
    }
  }

  const rank = (d?: number) => (d === undefined ? "?" : Math.round((1 - d) * 100));

  return (
    <>
      <h1>
        Semantic search <small>pgvector memory from Agent 6 reviews + Agent 7 competitor copy</small>
      </h1>

      <div className="similar-box" style={{ marginTop: 18 }}>
        <input
          className="input"
          placeholder="Ask the knowledge base… e.g. customers complain about checkout"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
        />
        <button className="btn" onClick={() => search()}>Search</button>
      </div>

      <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
        {SUGGESTIONS.map((s) => (
          <button key={s} className="chip" style={{ cursor: "pointer" }} onClick={() => search(s)}>
            {s}
          </button>
        ))}
      </div>

      <div className="section">
        {busy && <Spinner label="Embedding your query and searching…" />}
        {error && <div className="notice">⚠ {error}</div>}

        {!busy && hits !== null && hits.length === 0 && (
          <div className="notice info">No semantic chunks found. Run a scan so Agent 6/7 can write embeddings.</div>
        )}

        {!busy &&
          hits &&
          hits.map((h, i) => (
            <div className="card" key={i} style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <span className="chip">{h.business_id || "global"}</span>
                <span className="chip">{h.source || "site"}</span>
                <span className="chip" style={{ marginLeft: "auto" }}>
                  relevance {rank(h.distance)}%
                </span>
              </div>
              <div className="cluster muted" style={{ marginTop: 10, maxHeight: 160, whiteSpace: "pre-wrap" }}>
                {h.content}
              </div>
            </div>
          ))}
      </div>
    </>
  );
}