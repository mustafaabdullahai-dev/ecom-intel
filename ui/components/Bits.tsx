import type { ScoreExplanation } from "@/lib/types";

export function ScoreBar({ name, value, compact }: { name: string; value?: number; compact?: boolean }) {
  const v = Math.max(0, Math.min(100, Math.round((value ?? 0) || 0)));
  const cls = v >= 70 ? "good" : v >= 45 ? "amber" : "bad";
  return (
    <div className="score-row" style={compact ? { gap: 6 } : undefined}>
      <span className="name" style={compact ? { fontSize: 12 } : undefined}>{name}</span>
      <div className="bar">
        <i className={cls} style={{ width: `${v}%` }} />
      </div>
      <span className="val">{v}</span>
    </div>
  );
}

export function ScoreExplain({ label, value, expl }: { label: string; value?: number; expl?: ScoreExplanation }) {
  const v = Math.max(0, Math.min(100, Math.round((value ?? 0) || 0)));
  const has = expl && expl.summary;
  return (
    <div style={{ margin: "2px 0 10px" }}>
      <ScoreBar name={label} value={v} />
      {has ? (
        <div style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.5, marginTop: 4 }}>
          <span className="why">{expl?.summary}</span>
          {(expl?.contributors?.length ?? 0) > 0 && (
            <details style={{ marginTop: 4 }} aria-label="Score basis">
              <summary style={{ cursor: "pointer", fontSize: 11, opacity: 0.85 }}>
                Basis — what this score is built from
              </summary>
              <div style={{ marginTop: 4, display: "flex", flexWrap: "wrap", gap: 6 }}>
                {expl!.contributors!.map((c) => (
                  <span
                    key={c.name}
                    className="chip"
                    style={{ opacity: c.note === "weak" ? 0.85 : undefined }}
                    title={c.note === "weak" ? "weak input (<40)" : c.note === "strong" ? "strong input (>=70)" : c.name}
                  >
                    {c.name} · {c.value}
                  </span>
                ))}
              </div>
            </details>
          )}
          {!((expl?.contributors?.length ?? 0) > 0) && expl?.formula && (
            <details style={{ marginTop: 4 }}>
              <summary style={{ cursor: "pointer", fontSize: 11, opacity: 0.85 }}>Basis — formula</summary>
              <div style={{ marginTop: 4 }}>{expl?.formula}</div>
            </details>
          )}
        </div>
      ) : (
        <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
          No per-scan breakdown stored for this dimension.
        </div>
      )}
    </div>
  );
}

export function Tag({ priority }: { priority?: string }) {
  const p = (priority || "").toLowerCase() ?? "";
  const cls = p === "high" || p === "priority" || p === "critical"
    ? "high" : p === "medium" ? "medium" : p === "low" ? "low" : "sut";
  return <span className={`tag ${cls}`}>{(priority || "n/a").toUpperCase()}</span>;
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, color: "var(--muted)" }}>
      <span style={{ display: "inline-block" }} className="dot ok" />
      {label || "Working…"}
    </div>
  );
}