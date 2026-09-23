import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Spinner } from "@/components/Bits";
import type { RunResult } from "@/lib/types";

const COMMON_INDUSTRIES = [
  "electronics",
  "fashion & apparel",
  "home & garden",
  "beauty & personal care",
  "health & wellness",
  "sports & outdoors",
  "toys & games",
  "automotive",
  "books & media",
  "food & grocery",
  "pet supplies",
  "jewelry & accessories",
];

export default function RunPage() {
  const [regions, setRegions] = useState("Egypt, Dubai, Saudi Arabia");
  const [industry, setIndustry] = useState("");
  const [target, setTarget] = useState(5);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RunResult | null>(null);
  const [error, setError] = useState("");

  async function run() {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const r = await api.run(
        regions.split(",").map((s) => s.trim()).filter(Boolean),
        target,
      );
      setResult(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>Run Analysis</h1>
        <p className="caption">
          Trigger the full 8-agent pipeline with custom region and industry filters
        </p>
      </div>

      <div className="grid cols-2" style={{ gap: 16 }}>
        <div className="card">
          <h2 style={{ marginBottom: 16 }}>Configuration</h2>

          <label className="field">Regions (comma-separated)</label>
          <input
            className="input"
            value={regions}
            onChange={(e) => setRegions(e.target.value)}
            placeholder="Egypt, Dubai, Saudi Arabia, USA"
            disabled={busy}
          />

          <label className="field">Industry Filter (optional)</label>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 4 }}>
            <input
              className="input"
              style={{ flex: 1, minWidth: 200 }}
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              placeholder="e.g. electronics, fashion, home & garden"
              disabled={busy}
            />
            <button
              type="button"
              className="btn ghost"
              disabled={busy}
              onClick={() => setIndustry(COMMON_INDUSTRIES[0])}
            >
              Quick pick
            </button>
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
            {COMMON_INDUSTRIES.map((ind) => (
              <button
                key={ind}
                type="button"
                className={`pill ${industry === ind ? "good" : ""}`}
                onClick={() => setIndustry(ind)}
                disabled={busy}
              >
                {ind}
              </button>
            ))}
          </div>

          <label className="field">Discovery target (max leads per region)</label>
          <input
            className="input"
            type="number"
            min={1}
            max={50}
            value={target}
            onChange={(e) => setTarget(Number(e.target.value))}
            disabled={busy}
          />

          <div style={{ marginTop: 18 }}>
            <button className="btn" onClick={run} disabled={busy} style={{ width: "100%" }}>
              {busy ? "Running…" : "▶ Start Full Run"}
            </button>
          </div>

          <div className="caption" style={{ marginTop: 14 }}>
            Agent flow: discovery → qualify → deepdive (website / marketing / social / product /
            sentiment / competitor) → score → recommend → store → report.
          </div>
        </div>

        <div className="card">
          {busy && <Spinner label="Agents working… this can take several minutes on live data." />}

          {error && <div className="notice bad" style={{ marginBottom: 12 }}>⚠ {error}</div>}

          {!busy && !result && (
            <div className="caption">
              The run is synchronous via the FastAPI backend — watch this panel for the audit
              summary, then open the report in the Reports tab.
            </div>
          )}

          {result && (
            <>
              <h2 style={{ marginTop: 0 }}>Run Complete</h2>
              <div className="grid cols-3">
                <div className="kpi">
                  <div className="label">Run ID</div>
                  <div className="mono muted" style={{ fontSize: 13, wordBreak: "break-all" }}>
                    {result.run_id}
                  </div>
                </div>
                <div className="kpi">
                  <div className="label">Businesses Analyzed</div>
                  <div className="value">{result.analyzed}</div>
                </div>
                <div className="kpi">
                  <div className="label">Sheets Export</div>
                  <div className="value small">{result.sheets_written ? "written" : "off"}</div>
                </div>
              </div>
              <div style={{ marginTop: 18 }}>
                <Link className="btn ghost" to="/reports">
                  View Report → {result.report}
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}