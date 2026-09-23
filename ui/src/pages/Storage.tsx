import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Health } from "@/lib/types";

type StatusRow = { label: string; ok: boolean; detail?: string };

export default function StoragePage() {
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => undefined);
  }, []);

  const rows: StatusRow[] = [
    { label: "PostgreSQL + pgvector", ok: !!health?.postgres, detail: "structured leads, records, score snapshots, embeddings" },
    { label: "Google Sheets dataset", ok: !!health?.sheets, detail: health?.sheets ? "knowledge-base mirror configured" : "missing GOOGLE_SHEETS_ID / credentials" },
    { label: "Celery + Redis", ok: !!health?.celery, detail: "distributed deepdive scaling" },
    { label: "24/7 APScheduler", ok: !!health?.scheduler, detail: "daily → yearly automation loop" },
  ];

  return (
    <>
      <div className="page-head">
        <h1>Storage &amp; data sources</h1>
        <p className="caption">Where the AI consultant keeps its knowledge and how it gathers evidence</p>
      </div>

      <div className="section grid cols-2">
        <div className="card">
          <h2>Storage backends</h2>
          <div>
            {rows.map((r) => (
              <div className="source-row" key={r.label}>
                <span className={`dot ${r.ok ? "ok" : "bad"}`} />
                <div>
                  <div><b>{r.label}</b> {r.ok ? "· on" : "· off"}</div>
                  <div className="muted" style={{ fontSize: 12 }}>{r.detail}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <h2>Evidence-gathering sources</h2>
          <div>
            <div className="source-row">
              <span className={`dot ${health?.serp ? "ok" : "bad"}`} />
              <div>
                <div><b>SERP provider</b> — serper</div>
                <div className="muted" style={{ fontSize: 12 }}>
                  Google Search + Maps for Agent 1 discovery
                </div>
              </div>
            </div>
            <div className="source-row">
              <span className={`dot ${health?.pagespeed ? "ok" : "bad"}`} />
              <div>
                <div><b>PageSpeed Insights</b></div>
                <div className="muted" style={{ fontSize: 12 }}>
                  Core Web Vitals &amp; performance evidence for Agents 2/5
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="section">
        <div className="card">
          <h2>LLM routing &amp; failover providers</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Provider</th><th>Key</th><th>Default model</th><th>Role</th></tr>
              </thead>
              <tbody>
                {(health?.providers ?? []).map((p) => (
                  <tr key={p.name}>
                    <td><b>{p.name}</b></td>
                    <td>
                      <span className={`tag ${p.configured ? "low" : "bad"}`}>
                        {p.configured ? "configured" : "no key"}
                      </span>
                    </td>
                    <td className="mono">{p.model}</td>
                    <td className="muted">
                      {p.name === "groq" ? "primary (FALLBACK_PROVIDER)" :
                       p.name === "openrouter" ? "failover 1" :
                       p.name === "cerebras" ? "failover 2" :
                       p.name === "gemini" ? "failover 3 + embeddings" : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}