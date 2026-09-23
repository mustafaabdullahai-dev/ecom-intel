import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Health, Schedules } from "@/lib/types";

const ICONS = ["☀", "▦", "◨", "▣", "◎"];

export default function AutomationPage() {
  const [sched, setSched] = useState<Schedules | null>(null);
  const [health, setHealth] = useState<Health | null>(null);

  useEffect(() => {
    api.schedules().then(setSched).catch(() => undefined);
    api.health().then(setHealth).catch(() => undefined);
  }, []);

  return (
    <>
      <div className="page-head">
        <h1>24/7 automation</h1>
        <p className="caption">Continuous monitoring loop — the platform works while you sleep</p>
      </div>

      <div className={`notice ${health?.scheduler ? "info" : "bad"}`} style={{ marginBottom: 18 }}>
        <b>Status:</b>{" "}
        {health?.scheduler
          ? "Scheduler enabled — jobs run on the configured cadence."
          : "Scheduler is currently off. Set SCHEDULER_ENABLED=true and launch `python main.py --schedule`."}
      </div>

      <div className="grid cols-3">
        {(sched?.jobs ?? []).map((j, i) => (
          <div className="card job-card" key={j.id}>
            <div className="job-icon">{ICONS[i]}</div>
            <h2 style={{ textTransform: "capitalize" }}>{j.id}</h2>
            <div className="caption">{j.description}</div>
            <div className="job-when">{j.when}</div>
          </div>
        ))}
      </div>

      <div className="section">
        <div className="card">
          <h2>Automation schedule (from spec)</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Cadence</th><th>Monitored activity</th></tr>
              </thead>
              <tbody>
                <tr><td><b>Daily</b></td><td>Website changes · new products · pricing updates · customer feedback · social activity</td></tr>
                <tr><td><b>Weekly</b></td><td>Recalculate AI scores · analyze competitors · refresh recommendations</td></tr>
                <tr><td><b>Monthly</b></td><td>Comprehensive business audits · long-term trends · executive reports</td></tr>
                <tr><td><b>Quarterly</b></td><td>Strategic growth reports · competitor benchmarking</td></tr>
                <tr><td><b>Yearly</b></td><td>Digital transformation roadmap · year-over-year performance comparison</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}