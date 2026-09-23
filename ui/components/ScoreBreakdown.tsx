import { useMemo } from "react";
import { buildBreakdown, groupBreakdown } from "@/lib/breakdown";
import type {
  DimensionRationale,
  ParsedDimension,
  ParsedInput,
  RationalePayload,
  ScoreReason,
  ScoreSentiment,
} from "@/lib/types";

const ROLE_LABEL: Record<ParsedInput["role"], string> = {
  drag: "drag",
  neutral: "ok",
  support: "lift",
};

const KIND_LABEL: Record<ScoreReason["kind"], string> = {
  method: "METHOD",
  drag: "DRAG",
  support: "LIFT",
  context: "NOTE",
};

const SENTIMENT_LABEL: Record<ScoreSentiment, string> = {
  positive: "Healthy",
  neutral: "Mixed",
  negative: "Weak",
  critical: "Critical",
};

function oneLiner(d: ParsedDimension): string {
  if (d.drags.length) {
    const top = d.drags
      .slice(0, 2)
      .map((i) => `${i.label} ${i.value}`)
      .join(", ");
    const more = d.drags.length > 2 ? ` +${d.drags.length - 2} more` : "";
    return `Dragged down by ${top}${more}`;
  }
  if (d.supports.length) {
    const top = d.supports
      .slice(0, 2)
      .map((i) => `${i.label} ${i.value}`)
      .join(", ");
    const more = d.supports.length > 2 ? ` +${d.supports.length - 2} more` : "";
    return `Lifted by ${top}${more}`;
  }
  if (d.inputs.length) return `All ${d.inputs.length} inputs sit in the 40-69 developing band`;
  return d.bandLabel;
}

function AiBlock({ rationale }: { rationale: DimensionRationale }) {
  return (
    <div className={`bd-ai sent-${rationale.sentiment}`}>
      <div className="bd-ai-top">
        <span className={`bd-ai-badge sent-${rationale.sentiment}`}>
          {SENTIMENT_LABEL[rationale.sentiment] ?? rationale.sentiment}
        </span>
        {rationale.headline && <span className="bd-ai-headline">{rationale.headline}</span>}
      </div>
      {rationale.rationale && <p className="bd-ai-text">{rationale.rationale}</p>}
      {rationale.drivers.length > 0 && (
        <div className="bd-ai-drivers">
          {rationale.drivers.map((t, i) => (
            <span key={i} className="bd-chip">
              {t}
            </span>
          ))}
        </div>
      )}
      {rationale.fix && (
        <div className="bd-ai-fix">
          <span className="bd-ai-fix-label">Recommended</span>
          <span>{rationale.fix}</span>
        </div>
      )}
    </div>
  );
}

function InputRow({ i }: { i: ParsedInput }) {
  const delta = Math.round(i.delta);
  return (
    <div className={`bd-input ${i.role}`}>
      <span className="bd-input-name" title={i.key}>
        {i.label}
      </span>
      <span className="bd-input-bar">
        <i className={i.band} style={{ width: `${i.value}%` }} />
      </span>
      <span className={`bd-input-val ${i.band}`}>{i.value}</span>
      <span className={`bd-input-delta ${delta >= 0 ? "up" : "down"}`}>
        {delta >= 0 ? `+${delta}` : delta}
      </span>
    </div>
  );
}

function DimensionCard({
  d,
  rationale,
}: {
  d: ParsedDimension;
  rationale?: DimensionRationale;
}) {
  const inputs = useMemo(
    () => [...d.inputs].sort((a, b) => a.value - b.value),
    [d.inputs],
  );

  const hasAi = Boolean(rationale && (rationale.rationale || rationale.headline));

  return (
    <details className={`bd-item band-${d.band}`}>
      <summary className="bd-head">
        <span className="bd-head-main">
          <span className="bd-name">{d.label}</span>
          <span className="bd-what">{hasAi ? rationale!.headline || d.what : d.what}</span>
        </span>
        <span className="bd-bar">
          <i className={d.band} style={{ width: `${d.score}%` }} />
        </span>
        <span className={`bd-score ${d.band}`}>{d.score}</span>
        <span className={`bd-band ${d.band}`}>{d.bandLabel}</span>
        <span className="bd-caret" aria-hidden>
          ▾
        </span>
      </summary>

      <div className="bd-body">
        {hasAi ? (
          <AiBlock rationale={rationale!} />
        ) : (
          <>
            <div className="bd-line muted">{oneLiner(d)}</div>

            <div className="bd-sub">Why this score</div>
            <ul className="bd-reasons">
              {d.reasons.map((r, idx) => (
                <li key={idx} className={`bd-reason ${r.kind}`}>
                  <span className={`bd-kind ${r.kind}`}>{KIND_LABEL[r.kind]}</span>
                  <span>{r.text}</span>
                </li>
              ))}
            </ul>
          </>
        )}

        {inputs.length > 0 && (
          <>
            <div className="bd-sub">
              Inputs <span className="muted">— sorted worst first, Δ = value vs this score</span>
            </div>
            <div className="bd-inputs">
              {inputs.map((i, idx) => (
                <InputRow key={`${i.key}-${idx}`} i={i} />
              ))}
            </div>
            <div className="bd-legend">
              <span className="bd-swatch drag" /> below 40 (drag)
              <span className="bd-swatch neutral" /> 40-69 (developing)
              <span className="bd-swatch support" /> 70+ (lift)
            </div>
          </>
        )}

        <div className="bd-basis">
          <span className="muted">Method:</span> {d.method} · {d.formula}
        </div>
      </div>
    </details>
  );
}

export function ScoreBreakdown({
  row,
  rationales,
}: {
  row: Record<string, unknown>;
  rationales?: RationalePayload | null;
}) {
  const groups = useMemo(() => groupBreakdown(buildBreakdown(row)), [row]);
  const overall = rationales?.overall;

  return (
    <div className="bd">
      {overall && (overall.rationale || overall.headline) && (
        <div className={`bd-overall sent-${overall.sentiment}`}>
          <div className="bd-ai-top">
            <span className={`bd-ai-badge sent-${overall.sentiment}`}>
              {SENTIMENT_LABEL[overall.sentiment] ?? overall.sentiment}
            </span>
            <span className="bd-overall-title">{overall.headline || "AI assessment"}</span>
          </div>
          {overall.rationale && <p className="bd-ai-text">{overall.rationale}</p>}
        </div>
      )}
      {groups.map((g) => (
        <div className="bd-group" key={g.group}>
          <div className="bd-group-title">{g.group}</div>
          {g.items.map((d) => (
            <DimensionCard key={d.key} d={d} rationale={rationales?.dimensions?.[d.key]} />
          ))}
        </div>
      ))}
    </div>
  );
}
