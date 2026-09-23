import { Link, useLocation } from "react-router-dom";
import type { Health } from "@/lib/types";

const GROUPS: { title: string; links: { href: string; label: string; icon: string }[] }[] = [
  {
    title: "Consultant",
    links: [
      { href: "/overview", label: "Overview", icon: "◉" },
      { href: "/", label: "Executive dashboard", icon: "◈" },
      { href: "/leads", label: "Qualified leads", icon: "▦" },
      { href: "/insights", label: "Trends & insights", icon: "≋" },
    ],
  },
  {
    title: "Operations",
    links: [
      { href: "/run", label: "Run analysis", icon: "▶" },
      { href: "/analyze", label: "Analyze website", icon: "⌕" },
      { href: "/history", label: "Analysis history", icon: "🗎" },
      { href: "/automation", label: "24/7 automation", icon: "⟳" },
      { href: "/reports", label: "Audit reports", icon: "⎙" },
    ],
  },
  {
    title: "Knowledge",
    links: [
      { href: "/search", label: "Semantic search", icon: "⌕" },
      { href: "/storage", label: "Storage & sources", icon: "▤" },
    ],
  },
];

function Dot({ ok }: { ok?: boolean }) {
  return <span className={`dot ${ok ? "ok" : "bad"}`} />;
}

export function Sidebar({ health }: { health?: Health }) {
  const { pathname } = useLocation();

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">◈</div>
        <div>
          <b>ecom</b>-intel
          <div className="brand-sub">AI Ecommerce Consultant</div>
        </div>
      </div>

      {GROUPS.map((g) => (
        <nav className="nav-group" key={g.title}>
          <div className="nav-title">{g.title}</div>
          {g.links.map((l) => {
            const active =
              l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                to={l.href}
                className={`navlink ${active ? "active" : ""}`}
              >
                <span className="nav-icon">{l.icon}</span>
                <span className="label">{l.label}</span>
              </Link>
            );
          })}
        </nav>
      ))}

      <div className="spacer" />
      {health && (
        <div className="status">
          <div>
            <Dot ok={health.status === "ok"} /> API {health.status}
          </div>
          <div>
            <Dot ok={health.postgres} /> Postgres + pgvector
          </div>
          <div>
            <Dot ok={health.sheets} /> Google Sheets
          </div>
          <div>
            <Dot ok={health.scheduler} /> 24/7 scheduler
          </div>
          <div>
            <Dot ok={health.celery} /> Celery workers
          </div>
          <div style={{ marginTop: 8, opacity: 0.65 }}>
            fetch: {health.fetch_mode}
          </div>
        </div>
      )}
    </aside>
  );
}