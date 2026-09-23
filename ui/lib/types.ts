export interface ProviderStatus {
  name: string;
  configured: boolean;
  model?: string;
}

export interface Health {
  status: string;
  database_url: boolean;
  postgres: boolean;
  sheets: boolean;
  celery: boolean;
  scheduler?: boolean;
  serp?: boolean;
  pagespeed?: boolean;
  providers?: ProviderStatus[];
  fetch_mode: string;
  proxy: boolean;
}

export interface Business {
  id: string;
  name: string;
  region: string;
  industry: string;
  platform: string;
  website: string;
  contact_email: string;
  phone: string;
  social_links: string;
  created_at?: string;
}

export interface ScoreContributor {
  name?: string;
  key?: string;
  label?: string;
  value: number;
  note?: string;
  band?: string;
  role?: string;
  delta?: number;
}

export interface ScoreReason {
  kind: "method" | "drag" | "support" | "context";
  text: string;
}

export interface ScoreExplanation {
  score: number;
  verdict?: string;
  formula: string;
  summary: string;
  /** New structured form (see src/services/explain.py). */
  label?: string;
  what?: string;
  basis?: string;
  band?: string;
  band_label?: string;
  method?: string;
  input_count?: number;
  inputs?: ScoreContributor[];
  reasons?: ScoreReason[];
  contributors?: ScoreContributor[];
}

export type ScoreBand = "weak" | "ok" | "strong";
export type ScoreRole = "drag" | "neutral" | "support";
export type ScoreMethod = "average" | "single" | "composed" | "derived";
export type ScoreSentiment = "positive" | "neutral" | "negative" | "critical";

/** LLM-authored reasoning for one dimension (src/services/rationale.py). */
export interface DimensionRationale {
  headline: string;
  sentiment: ScoreSentiment;
  rationale: string;
  drivers: string[];
  fix: string;
}

export interface OverallRationale {
  headline: string;
  sentiment: ScoreSentiment;
  rationale: string;
}

export interface RationalePayload {
  available: boolean;
  business_id?: string;
  scanned_at?: string;
  generated_at?: string;
  overall?: OverallRationale;
  dimensions?: Record<string, DimensionRationale>;
}

export interface ParsedInput {
  key: string;
  label: string;
  value: number;
  band: ScoreBand;
  role: ScoreRole;
  delta: number;
}

export interface ParsedDimension {
  key: string;
  label: string;
  what: string;
  basis: string;
  group: string;
  groupOrder: number;
  score: number;
  band: ScoreBand;
  bandLabel: string;
  method: ScoreMethod;
  formula: string;
  inputs: ParsedInput[];
  drags: ParsedInput[];
  supports: ParsedInput[];
  neutrals: ParsedInput[];
  reasons: ScoreReason[];
  summary: string;
  hasDetail: boolean;
}

export interface DimensionSummary {
  label: string;
  what: string;
  basis: string;
  avg: number;
  count: number;
  weak_count: number;
  strong_count: number;
  note: string;
}

export interface PdfMeta {
  filename: string;
  url: string;
}

export interface RankedRow {
  id: string;
  name: string;
  region: string;
  industry: string;
  platform?: string;
  website?: number;
  contact_email?: string;
  phone?: string;
  social_links?: string;
  lead_priority?: string;
  ai_summary?: string;
  change_since_previous?: string;
  scanned_at?: string;
  notes?: string;
  daily?: string;
  weekly?: string;
  monthly?: string;
  quarterly?: string;
  yearly?: string;
  seo?: number;
  marketing?: number;
  brand?: number;
  social?: number;
  content?: number;
  customer_experience?: number;
  trust?: number;
  technical?: number;
  product_trend?: number;
  growth_potential?: number;
  lead_qualification?: number;
  business_health?: number;
  ai_opportunity?: number;
  score_explanations?: Record<string, ScoreExplanation>;
  [k: string]: unknown;
}

export interface DashboardData {
  source: string;
  rows: RankedRow[];
}

export interface Stats {
  businesses: number;
  regions: Record<string, number>;
  industries: Record<string, number>;
  priorities: Record<string, number>;
  dimension_averages: Record<string, number>;
  dimension_summaries?: Record<string, DimensionSummary>;
  weakest_dimensions: [string, number][];
  strongest_dimensions: [string, number][];
}

export interface HistoryItem {
  id: string;
  name: string;
  url: string;
  region: string;
  industry: string;
  platform: string;
  contact_email: string;
  phone: string;
  lead_priority: string;
  ai_summary: string;
  scanned_at: string;
  scores: Record<string, number>;
  score_explanations: Record<string, ScoreExplanation>;
  change_since_previous: string;
  scan_count: number;
  pdfs: string[];
  pdf: PdfMeta;
}

export interface ScheduleJob {
  id: string;
  description: string;
  when: string;
}

export interface Schedules {
  enabled: boolean;
  jobs: ScheduleJob[];
}

export interface ExportData {
  filename: string;
  rows: number;
  csv: string;
}

export interface RecordRow {
  record_id?: number;
  business_id: string;
  business_name?: string;
  region?: string;
  industry?: string;
  contact_email?: string;
  phone?: string;
  social_links?: string;
  scanned_at: string;
  lead_priority?: string;
  ai_summary?: string;
  daily?: string;
  weekly?: string;
  monthly?: string;
  quarterly?: string;
  yearly?: string;
  change_since_previous?: string;
  notes?: string;
  sales_status?: string;
  outreach_status?: string;
  business_health?: number;
  ai_opportunity?: number;
  website?: number;
  seo?: number;
  marketing?: number;
  brand?: number;
  social?: number;
  content?: number;
  customer_experience?: number;
  trust?: number;
  technical?: number;
  product_trend?: number;
  growth_potential?: number;
  lead_qualification?: number;
  score_explanations?: Record<string, ScoreExplanation>;
  [k: string]: unknown;
}

export interface SimilarHit {
  business_id?: string;
  source?: string;
  content?: string;
  distance?: number;
  [k: string]: unknown;
}

export interface RunResult {
  run_id: string;
  analyzed: number;
  report: string;
  sheets_written: boolean;
}

export interface SecurityFinding {
  severity: string;
  category: string;
  title: string;
  detail: string;
  remediation: string;
}

export interface SecurityGap {
  topic: string;
  status: string;
  reason: string;
  recommendation: string;
}

export interface SecurityResult {
  overall_score: number;
  risk_level: string;
  https_enforced: boolean;
  https: number;
  ssl_tls: number;
  authentication: number;
  input_validation: number;
  file_permissions: number;
  security_headers: number;
  protocol: string;
  cipher: string;
  cert_issuer: string;
  cert_expires_days: number;
  security_headers_found: Record<string, boolean>;
  cookies_secure: boolean;
  cookies_httponly: boolean;
  exposed_paths: string[];
  findings: SecurityFinding[];
  gaps: SecurityGap[];
  checks_performed: string[];
  outreach_message: string;
  summary: string;
  url: string;
  business_id: string;
}

export interface AnalyzeResult {
  lead: {
    name: string;
    url: string;
    industry: string;
    region: string;
    platform: string;
  };
  scores: Record<string, number>;
  score_explanations?: Record<string, ScoreExplanation>;
  qualification: Record<string, unknown>;
  recommendation: Record<string, unknown>;
  evidence: Record<string, unknown>;
  security: SecurityResult;
  pdf?: PdfMeta;
}

export interface ReportContent {
  name: string;
  content: string;
}