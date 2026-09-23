import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "@/components/Sidebar";
import { ThemeToggle } from "@/components/ThemeToggle";
import { api } from "@/lib/api";
import type { Health } from "@/lib/types";

export function AppShell() {
  const [health, setHealth] = useState<Health | undefined>();

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(undefined));
  }, []);

  return (
    <div className="shell">
      <Sidebar health={health} />
      <div className="main-col">
        <header className="topbar">
          <ThemeToggle />
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
