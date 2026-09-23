import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ScoreBar } from "@/components/Bits";
import { ScoreBreakdown } from "@/components/ScoreBreakdown";
import type { AnalyzeResult, SecurityGap, SecurityResult } from "@/lib/types";

function Tag({ label, priority }: { label: string; priority?: string }) {
  const p = (priority || "").toLowerCase() ?? "";
  const cls = p === "high" || p === "priority" || p === "critical"
    ? "high" : p === "medium" ? "medium" : p === "low" ? "low" : "sut";
  return <span className={`tag ${cls}`}>{label}</span>;
}

function SeverityBadge({ level }: { level: string }) {
  const l = (level || "").toLowerCase();
  const cls = l === "critical" || l === "high"
    ? "bad" : l === "medium" ? "warn" : l === "low" ? "ok" : "neutral";
  return <span className={`tag ${cls}`}>{l || "info"}</span>;
}

export default function AnalyzePage() {
  const [url, setUrl] = useState("");
  const [industry, setIndustry] = useState("");
  const [result, setResult] = useState<AnalyzeResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const poll = useCallback(async (id: string) => {
    const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
    for (;;) {
      await sleep(4000);
      try {
        const job = await fetch(`/backend/analyze/${id}`, { cache: "no-store" }).then((r) => r.json());
        if (job.status === "done" && job.result) {
          setResult(job.result);
          setLoading(false);
          break;
        }
        if (job.status === "error") {
          setError(job.error || "Analysis failed");
          setLoading(false);
          localStorage.removeItem("ecom_latest_job");
          break;
        }
      } catch {
        setLoading(false);
        setError("Lost connection to the analysis job — check back in History.");
        break;
      }
    }
  }, []);

  // Resume a job that was still running when the user left the page (e.g.
  // switched tabs). The job itself runs on the server, so it keeps going and
  // the completed report reappears here on return.
  useEffect(() => {
    const saved = localStorage.getItem("ecom_latest_job");
    if (saved && !result) {
      setResult(null);
      setLoading(true);
      fetch(`/backend/analyze/${saved}`, { cache: "no-store" })
        .then((r) => r.json())
        .then((job) => {
          if (job.status === "done" && job.result) {
            setResult(job.result);
            setLoading(false);
          } else if (job.status === "running") {
            setLoading(true);
            poll(saved);
          } else {
            localStorage.removeItem("ecom_latest_job");
          }
        })
        .catch(() => undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const created = await fetch("/backend/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim(), deepdive: true, industry: industry.trim() }),
      }).then((r) => r.json());
      localStorage.setItem("ecom_latest_job", created.job_id);
      poll(created.job_id);
    } catch (e) {
      setError(String(e));
      setLoading(false);
    }
  };

  const securityDimensions: [string, keyof SecurityResult][] = [
    ["HTTPS", "https"],
    ["SSL / TLS", "ssl_tls"],
    ["Authentication", "authentication"],
    ["Input Validation", "input_validation"],
    ["File Permissions", "file_permissions"],
    ["Security Headers", "security_headers"],
  ];

  return (
    <>
      <div className="page-head">
        <h1>Analyze a Website</h1>
        <p className="caption">
          Paste any URL to run a full AI audit: business intelligence, live security scan,
          what it lacks, and fixes to recommend.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="card" style={{ maxWidth: 640 }}>
        <div className="grid cols-2" style={{ gap: 12, marginBottom: 12 }}>
          <input
            className="input"
            type="url"
            placeholder="https://example.com"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
          />
          <input
            className="input"
            placeholder="Category / industry (optional)"
            value={industry}
            onChange={(e) => setIndustry(e.target.value)}
          />
        </div>
        <button className="btn" type="submit" disabled={loading} style={{ width: "100%" }}>
          {loading ? "Auditing… 9 agents running (2-6 min)" : "Analyze Website"}
        </button>
      </form>

      {error && <div className="notice bad" style={{ marginTop: 16 }}>⚠ {error}</div>}

      {result && (
        <div className="section">
          <div className="card">
            <h2 style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 16 }}>
              {result.lead.name}
              <span className="muted">{result.lead.url}</span>
            </h2>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
              <Tag label={result.lead.platform} priority={result.lead.platform === "shopify" ? "high" : "medium"} />
              <Tag label={result.lead.industry} priority="medium" />
              <Tag label={result.lead.region || "—"} priority="low" />
            </div>
          </div>

          <div className="section grid cols-2">
            <div className="card">
              <h2 style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
                <span>14-Point Score Breakdown</span>
                {result.pdf?.url && (
                  <a className="btn" style={{ fontSize: 12, padding: "6px 10px" }} href={result.pdf.url} download>
                    ⭳ Download audit PDF
                  </a>
                )}
              </h2>
              <p className="caption" style={{ marginBottom: 12 }}>
                Each score explains what it measures, why it scored what it did, and what to fix.
              </p>
              <ScoreBreakdown
                row={{ ...result.scores, score_explanations: result.score_explanations }}
              />
            </div>

            <div className="card">
              <h2>Qualification</h2>
              {result.qualification && Object.entries(result.qualification).map(([k, v]) => (
                <div key={k} style={{ marginBottom: 8 }}>
                  <span className="muted">{k}:</span> <span className="mono">{String(v)}</span>
                </div>
              ))}
            </div>
          </div>

          {result.recommendation && Object.keys(result.recommendation).length > 0 && (
            <div className="section grid cols-2">
              {Object.entries(result.recommendation).map(([horizon, plan]) => (
                <div className="card" key={horizon}>
                  <h2 style={{ textTransform: "capitalize" }}>{horizon} Plan</h2>
                  <div className="cluster muted">{String(plan)}</div>
                </div>
              ))}
            </div>
          )}

          {result.evidence && Object.keys(result.evidence).length > 0 && (
            <div className="section">
              <h2>Evidence Collected</h2>
              <div className="card cluster" style={{ maxHeight: 300, overflow: "auto" }}>
                {Object.entries(result.evidence).map(([k, v]) => (
                  <div key={k} style={{ marginBottom: 12 }}>
                    <b>{k}:</b> <span className="muted">{String(v).slice(0, 300)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {result.security && result.security.overall_score >= 0 && (
            <div className="section">
              <div className="card">
                <h2 style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 16 }}>
                  Live Security Audit
                  <SeverityBadge level={result.security.risk_level} />
                  <ScoreBar name="Overall Security" value={result.security.overall_score} compact />
                </h2>
                <p className="muted" style={{ marginBottom: 12 }}>
                  Scanned the real site over the network: HTTPS, TLS handshake, headers, cookies,
                  forms, and sensitive endpoints.
                </p>
                <div className="grid cols-2" style={{ gap: 16 }}>
                  {securityDimensions.map(([label, key]) => (
                    <ScoreBar
                      key={key}
                      name={label}
                      value={result.security[key] as number}
                      compact
                    />
                  ))}
                </div>
                <div className="cluster" style={{ marginTop: 12, gap: 16 }}>
                  <span className="muted">TLS: {result.security.protocol || "?"}</span>
                  <span className="muted">Cipher: {result.security.cipher || "?"}</span>
                  <span className="muted">Cert: {result.security.cert_issuer || "?"}</span>
                  {result.security.cert_expires_days >= 0 && (
                    <span className="muted">
                      Expires in {result.security.cert_expires_days} day(s)
                    </span>
                  )}
                  <span className="muted">
                    Cookies: {result.security.cookies_secure ? "Secure ✓" : "no Secure"} /{" "}
                    {result.security.cookies_httponly ? "HttpOnly ✓" : "no HttpOnly"}
                  </span>
                </div>
                {result.security.exposed_paths.length > 0 && (
                  <div className="notice bad" style={{ marginTop: 12 }}>
                    ⚠ Exposed paths: {result.security.exposed_paths.join(", ")}
                  </div>
                )}
              </div>

              {result.security.findings.length > 0 && (
                <div className="card">
                  <h2 style={{ marginBottom: 12 }}>Findings</h2>
                  {result.security.findings.map((f, idx) => (
                    <div key={idx} style={{ marginBottom: 14, borderBottom: "1px solid var(--line,#ffffff22)", paddingBottom: 10 }}>
                      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                        <SeverityBadge level={f.severity} />
                        <b>{f.title}</b>
                      </div>
                      {f.detail && <p className="muted" style={{ margin: "6px 0" }}>{f.detail}</p>}
                      {f.remediation && (
                        <p style={{ margin: 0 }}>
                          <span className="muted">Fix: </span>{f.remediation}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {result.security.gaps.length > 0 && (
                <div className="card">
                  <h2 style={{ marginBottom: 12 }}>What This Site Lacks</h2>
                  {result.security.gaps.map((g, idx) => (
                    <div key={idx} style={{ marginBottom: 14, borderBottom: "1px solid var(--line,#ffffff22)", paddingBottom: 10 }}>
                      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                        <Tag label={g.status || "lacking"} priority={g.status === "present" ? "low" : "medium"} />
                        <b>{g.topic}</b>
                      </div>
                      {g.reason && <p className="muted" style={{ margin: "6px 0" }}>{g.reason}</p>}
                      {g.recommendation && (
                        <p style={{ margin: 0 }}>
                          <span className="muted">Recommendation: </span>{g.recommendation}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {result.security.outreach_message && (
                <div className="card">
                  <h2 style={{ marginBottom: 12 }}>Outreach Message for the Owner</h2>
                  <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>
                    {result.security.outreach_message}
                  </p>
                  <button
                    className="btn"
                    style={{ marginTop: 10 }}
                    onClick={() => navigator.clipboard.writeText(result.security.outreach_message)}
                  >
                    Copy message
                  </button>
                </div>
              )}
            </div>
          )}

          {result.security.summary && (
            <div className="card">
              <h2 style={{ marginBottom: 8 }}>Summary</h2>
              <p className="muted">{result.security.summary}</p>
            </div>
          )}
        </div>
      )}
    </>
  );
}