import type {
  ParsedDimension,
  ParsedInput,
  ScoreBand,
  ScoreExplanation,
  ScoreMethod,
  ScoreReason,
  ScoreRole,
} from "./types";

const STRONG = 70;
const OK = 40;

export function bandOf(value: number): ScoreBand {
  if (value >= STRONG) return "strong";
  if (value >= OK) return "ok";
  return "weak";
}

function roleOf(value: number): ScoreRole {
  if (value < OK) return "drag";
  if (value >= STRONG) return "support";
  return "neutral";
}

export const BAND_LABELS: Record<ScoreBand, string> = {
  strong: "Strong (70-100)",
  ok: "Developing (40-69)",
  weak: "Weak (0-39)",
};

const INPUT_LABELS: Record<string, string> = {
  homepage_quality: "Homepage quality",
  navigation: "Navigation",
  user_experience: "User experience",
  mobile_responsiveness: "Mobile responsiveness",
  website_speed: "Website speed",
  performance: "Performance",
  product_pages: "Product pages",
  image_quality: "Image quality",
  content_quality: "Content quality",
  conversion_optimization: "Conversion optimization",
  call_to_actions: "Calls to action",
  landing_pages: "Landing pages",
  seo: "SEO basics",
  technical_seo: "Technical SEO",
  schema_markup: "Schema markup",
  metadata: "Metadata",
  internal_linking: "Internal linking",
  page_structure: "Page structure",
  indexability: "Indexability",
  core_web_vitals: "Core Web Vitals",
  broken_links: "Broken links",
  trust_signals: "Trust signals",
  return_policy: "Return policy",
  privacy_policy: "Privacy policy",
  security: "Security",
  ssl: "SSL / HTTPS",
  reviews: "Reviews",
  blog_activity: "Blog activity",
  checkout_experience: "Checkout experience",
  payment_options: "Payment options",
  search_functionality: "Search functionality",
  filtering: "Filtering",
  faq: "FAQ",
  live_chat: "Live chat",
  contact_information: "Contact information",
  brand_positioning: "Brand positioning",
  brand_consistency: "Brand consistency",
  content_marketing: "Content marketing",
  reputation_score: "Reputation (sentiment)",
  demand: "Product demand",
  "product demand": "Product demand",
  search_interest: "Search interest",
  popularity: "Popularity",
  competition: "Competition",
  inventory_risk: "Inventory risk",
  active: "Active-seller signal",
  "active signal": "Active-seller signal",
  product_trend: "Product trend",
  social: "Social audience",
  "100 − website": "Untapped website headroom",
  "100 − seo": "Untapped SEO headroom",
  "100 − marketing": "Untapped marketing headroom",
  "100 − business_health": "Untapped health headroom",
  "100 − competitor": "Competitive headroom",
};

function humanize(key: string): string {
  if (INPUT_LABELS[key]) return INPUT_LABELS[key];
  return key
    .replace(/_/g, " ")
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Static catalog mirroring src/services/explain.py DIMENSION_META. */
interface DimensionMeta {
  label: string;
  what: string;
  basis: string;
  group: string;
  groupOrder: number;
}

const CAPABILITY = "Capability";
const MARKET = "Market";
const PROSPECT = "Prospect";
const ROLLUP = "Roll-up";

export const DIMENSION_CATALOG: Record<string, DimensionMeta> = {
  website: {
    label: "Website quality",
    what: "Quality of the online storefront itself.",
    basis: "Average of 12 website-audit categories (homepage, navigation, UX, mobile, speed, performance, product pages, imagery, content, CRO, CTAs, landing pages).",
    group: CAPABILITY,
    groupOrder: 1,
  },
  seo: {
    label: "SEO readiness",
    what: "Organic search readiness.",
    basis: "Average of 9 SEO categories (SEO basics, technical SEO, schema, metadata, internal links, structure, indexability, Core Web Vitals, broken links).",
    group: CAPABILITY,
    groupOrder: 1,
  },
  marketing: {
    label: "Marketing maturity",
    what: "Marketing rollout, channels, funnel and retention.",
    basis: "Direct Agent 3 maturity_score roll-up (channels, lifecycle, funnel, retention, automation).",
    group: CAPABILITY,
    groupOrder: 1,
  },
  brand: {
    label: "Brand strength",
    what: "Brand consistency and positioning strength.",
    basis: "Average of Agent 3 brand_positioning, Agent 4 brand_consistency and website trust_signals.",
    group: CAPABILITY,
    groupOrder: 1,
  },
  social: {
    label: "Social presence",
    what: "Social media presence across platforms.",
    basis: "Agent 4 overall_score from posting frequency, follower growth, engagement, content and response time.",
    group: CAPABILITY,
    groupOrder: 1,
  },
  content: {
    label: "Content quality",
    what: "Content quality and blog / creative strength.",
    basis: "Average of website content_quality, blog_activity and Agent 3 content_marketing.",
    group: CAPABILITY,
    groupOrder: 1,
  },
  customer_experience: {
    label: "Customer experience",
    what: "Usability, checkout and support experience.",
    basis: "Average of 10 CX categories (UX, checkout, payments, search, filtering, FAQ, chat, contact, reviews, mobile).",
    group: CAPABILITY,
    groupOrder: 1,
  },
  trust: {
    label: "Trust signals",
    what: "Trust signals, policies, security and reputation.",
    basis: "Average of trust_signals, return_policy, privacy_policy, security, ssl, reviews plus Agent 6 reputation_score.",
    group: CAPABILITY,
    groupOrder: 1,
  },
  technical: {
    label: "Technical health",
    what: "Performance, Core Web Vitals, indexability, security.",
    basis: "Average of performance, website_speed, core_web_vitals, technical_seo, indexability, security, ssl.",
    group: CAPABILITY,
    groupOrder: 1,
  },
  product_trend: {
    label: "Product trend",
    what: "Product-line market opportunity.",
    basis: "Agent 5 overall_score (demand, search interest, popularity, competition, seasonality, price, lifecycle).",
    group: MARKET,
    groupOrder: 2,
  },
  growth_potential: {
    label: "Growth potential",
    what: "Headroom / upside for the business.",
    basis: "product_trend + (100 − website) + (100 − marketing) + social + (100 − competitor).",
    group: PROSPECT,
    groupOrder: 3,
  },
  lead_qualification: {
    label: "Lead qualification",
    what: "How good a sales prospect this is.",
    basis: "(100 − website) + (100 − seo) + (100 − marketing) + product demand + social + active signal.",
    group: PROSPECT,
    groupOrder: 3,
  },
  business_health: {
    label: "Business health",
    what: "Overall digital maturity.",
    basis: "Average of the 9 capability scores (website, seo, marketing, brand, social, content, CX, trust, technical).",
    group: ROLLUP,
    groupOrder: 4,
  },
  ai_opportunity: {
    label: "AI opportunity",
    what: "Overall AI-driven service opportunity.",
    basis: "lead_qualification + (100 − business_health) + (100 − competitor) + product_trend.",
    group: ROLLUP,
    groupOrder: 4,
  },
};

export const DIMENSION_ORDER: string[] = Object.keys(DIMENSION_CATALOG);

export const GROUP_ORDER: [string, number][] = [
  [CAPABILITY, 1],
  [MARKET, 2],
  [PROSPECT, 3],
  [ROLLUP, 4],
];

/** Ordered (overriding) list used across the UI. */
export const DISPLAY_ORDER: string[] = [
  "website", "seo", "technical", "marketing", "brand", "social", "content",
  "customer_experience", "trust", "product_trend", "growth_potential",
  "lead_qualification", "business_health", "ai_opportunity",
];

function detectMethod(formula: string, inputs: ParsedInput[], provided?: string): ScoreMethod {
  if (provided && ["average", "single", "composed", "derived"].includes(provided)) {
    return provided as ScoreMethod;
  }
  const f = (formula || "").toLowerCase();
  if (f.includes("+") && f.includes("100")) return "composed";
  if (f.includes("average")) return "average";
  if (f.includes("roll-up") || f.includes("overall_score")) return "single";
  if (inputs.length) return "average";
  return "derived";
}

function toInputs(expl: ScoreExplanation | undefined, score: number): ParsedInput[] {
  const raw = expl?.inputs?.length ? expl.inputs : expl?.contributors ?? [];
  return raw
    .map((c) => {
      const key = String(c.key ?? c.name ?? c.label ?? "");
      const label = humanize(c.label ?? c.name ?? key);
      const value = Math.max(0, Math.min(100, Math.round(Number(c.value) || 0)));
      return {
        key,
        label,
        value,
        band: bandOf(value),
        role: roleOf(value),
        delta: typeof c.delta === "number" ? c.delta : value - score,
      } satisfies ParsedInput;
    })
    .filter((c) => c.key || c.label);
}

function buildReasons(
  method: ScoreMethod,
  formula: string,
  drags: ParsedInput[],
  supports: ParsedInput[],
  inputs: ParsedInput[],
  provided?: ScoreReason[],
): ScoreReason[] {
  if (provided?.length) return provided;

  const methodText: Record<ScoreMethod, string> = {
    average: `Equal-weight average of ${inputs.length} inputs.`,
    single: "Direct AI-agent roll-up (not an average of sub-scores).",
    composed: formula
      ? `Built from combined component scores: ${formula}.`
      : `Built from ${inputs.length} component scores.`,
    derived: "Reconstructed from the saved scan record.",
  };

  const reasons: ScoreReason[] = [{ kind: "method", text: methodText[method] }];
  for (const c of drags) {
    reasons.push({
      kind: "drag",
      text: `${c.label} scored ${c.value}/100 — under the 40 threshold, dragging the score down by ${Math.abs(c.delta)} pts vs the average.`,
    });
  }
  for (const c of supports) {
    reasons.push({
      kind: "support",
      text: `${c.label} scored ${c.value}/100 — a strong input lifting the score by ${c.delta} pts vs the average.`,
    });
  }
  if (inputs.length && !drags.length && !supports.length) {
    reasons.push({
      kind: "context",
      text: "Every input sits in the 40-69 developing band — no single dominant weak or strong factor.",
    });
  }
  return reasons;
}

/**
 * Normalise one raw explanation into a fully structured dimension.
 * Handles both the new structured payload (src/services/explain.py) and
 * legacy rows that only carry a prose `summary` + `contributors`.
 */
export function parseDimension(
  key: string,
  score: number,
  expl?: ScoreExplanation,
): ParsedDimension {
  const meta = DIMENSION_CATALOG[key] ?? {
    label: key,
    what: "",
    basis: expl?.basis || expl?.formula || "",
    group: CAPABILITY,
    groupOrder: 1,
  };

  const safeScore = Math.max(0, Math.min(100, Math.round(Number(score) || 0)));
  const inputs = toInputs(expl, safeScore);
  const drags = inputs.filter((i) => i.role === "drag").sort((a, b) => a.value - b.value);
  const supports = inputs.filter((i) => i.role === "support").sort((a, b) => b.value - a.value);
  const neutrals = inputs.filter((i) => i.role === "neutral").sort((a, b) => b.value - a.value);

  const band = (expl?.band as ScoreBand) || bandOf(safeScore);
  const method = detectMethod(expl?.formula || meta.basis, inputs, expl?.method);
  const reasons = buildReasons(method, expl?.formula || meta.basis, drags, supports, inputs, expl?.reasons);

  return {
    key,
    label: expl?.label || meta.label,
    what: expl?.what || meta.what,
    basis: expl?.basis || meta.basis,
    group: meta.group,
    groupOrder: meta.groupOrder,
    score: safeScore,
    band,
    bandLabel: expl?.band_label || BAND_LABELS[band],
    method,
    formula: expl?.formula || meta.basis,
    inputs,
    drags,
    supports,
    neutrals,
    reasons,
    summary: expl?.summary || `${safeScore}/100 — ${BAND_LABELS[band]}.`,
    hasDetail: inputs.length > 0 || reasons.length > 1,
  };
}

/**
 * Parse an entire record (all 14 dimensions) into ordered, grouped
 * structured breakdowns. This is the single entry point the UI renders from.
 */
export function buildBreakdown(
  row: Record<string, unknown> | undefined | null,
): ParsedDimension[] {
  if (!row) return [];
  const expl = (row.score_explanations ?? {}) as Record<string, ScoreExplanation>;
  return DISPLAY_ORDER.map((key) =>
    parseDimension(key, Number(row[key]) || 0, expl[key]),
  );
}

export function groupBreakdown(
  dims: ParsedDimension[],
): { group: string; order: number; items: ParsedDimension[] }[] {
  return GROUP_ORDER.map(([group, order]) => ({
    group,
    order,
    items: dims.filter((d) => d.group === group),
  })).filter((g) => g.items.length > 0);
}
