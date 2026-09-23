import { useEffect, useState } from "react";
import { applyTheme, getPref, setPref, watchSystem, type ThemePref } from "@/lib/theme";

const OPTIONS: { key: ThemePref; label: string; title: string }[] = [
  { key: "light", label: "☀", title: "Light" },
  { key: "dark", label: "☾", title: "Dark" },
  { key: "system", label: "Auto", title: "System default" },
];

export function ThemeToggle() {
  const [pref, setPrefState] = useState<ThemePref>("dark");

  useEffect(() => {
    setPrefState(getPref());
  }, []);

  useEffect(() => {
    return watchSystem(() => {
      if (getPref() === "system") applyTheme("system");
    });
  }, []);

  function choose(next: ThemePref) {
    setPref(next);
    setPrefState(next);
  }

  return (
    <div className="theme-toggle" role="group" aria-label="Theme">
      {OPTIONS.map((o) => (
        <button
          key={o.key}
          type="button"
          title={o.title}
          aria-pressed={pref === o.key}
          className={pref === o.key ? "active" : ""}
          onClick={() => choose(o.key)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
