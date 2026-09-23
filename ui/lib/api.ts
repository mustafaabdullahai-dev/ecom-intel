import type {
  Business,
  DashboardData,
  ExportData,
  Health,
  HistoryItem,
  RecordRow,
  ReportContent,
  RunResult,
  Schedules,
  SimilarHit,
  Stats,
  AnalyzeResult,
  PdfMeta,
  RationalePayload,
} from "./types";

// All calls go through `/backend/*` which the Vite dev/preview server proxies
// to FastAPI (see vite.config.ts -> server.proxy).
const BASE = "/backend";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export const api = {
  health: () => get<Health>("/health"),
  businesses: (limit = 200) => get<Business[]>(`/businesses?limit=${limit}`),
  dashboard: () => get<DashboardData>("/dashboard-data"),
  stats: () => get<Stats>("/stats"),
  schedules: () => get<Schedules>("/schedules"),
  exportCsv: () => get<ExportData>("/export.csv"),
  businessRecords: (id: string) => get<RecordRow[]>(`/businesses/${encodeURIComponent(id)}/records`),
  rationale: (id: string) =>
    get<RationalePayload>(`/businesses/${encodeURIComponent(id)}/rationale`),
  generateRationale: (id: string) =>
    post<RationalePayload>(`/businesses/${encodeURIComponent(id)}/rationale`, {}),
  reports: () => get<string[]>("/reports"),
  report: (name: string) => get<ReportContent>(`/reports/${encodeURIComponent(name)}`),
  similar: (q: string, limit = 8) =>
    get<SimilarHit[]>(`/similar?q=${encodeURIComponent(q)}&limit=${limit}`),
  history: () => get<HistoryItem[]>("/history"),
  generatePdf: (businessId: string) =>
    post<PdfMeta>(`/reports/pdf/generate/${encodeURIComponent(businessId)}`, {}),
  run: (regions: string[], target: number) =>
    post<RunResult>("/run", { regions, target }),
  analyze: async (url: string, deepdive = true, industry = ""): Promise<AnalyzeResult> => {
    // POST returns { job_id }; poll GET /analyze/{id} until done.
    const created = await post<{ job_id: string }>("/analyze", { url, deepdive, industry });
    const id = created.job_id;
    const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
    for (;;) {
      await sleep(4000);
      const job = await get<{
        status: "running" | "done" | "error";
        result: AnalyzeResult | null;
        error: string | null;
      }>(`/analyze/${id}`);
      if (job.status === "done" && job.result) return job.result;
      if (job.status === "error") throw new Error(job.error || "Analysis failed");
    }
  },
};