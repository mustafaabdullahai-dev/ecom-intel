import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Spinner } from "@/components/Bits";
import type { ReportContent } from "@/lib/types";

export default function ReportsPage() {
  const [files, setFiles] = useState<string[]>([]);
  const [active, setActive] = useState<ReportContent | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    api.reports().then(setFiles).catch(() => setFiles([]));
  }, []);

  async function open(name: string) {
    setBusy(true);
    try {
      setActive(await api.report(name));
    } catch {
      setActive(null);
      setNotice(`Could not open ${name} — the backend may be starting. Try again in a moment.`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>
        Reports <small>generated audit files in {`output/`}</small>
      </h1>

      <div className="grid cols-2" style={{ marginTop: 18, alignItems: "start" }}>
        <div>
          {files.length === 0 ? (
            <div className="notice info">No reports yet — run an analysis to produce audit files.</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>File</th><th></th></tr>
                </thead>
                <tbody>
                  {files.map((f) => (
                    <tr key={f}>
                      <td className="mono">{f}</td>
                      <td>
                        <button className="btn ghost" style={{ padding: "6px 14px" }} onClick={() => open(f)}>
                          Open
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div>
          {busy && <Spinner label="Loading report…" />}
          {active && (
            <div className="card">
              <h2 style={{ marginTop: 0, wordBreak: "break-all" }}>{active.name}</h2>
              <pre className="cluster">{active.content}</pre>
            </div>
          )}
          {!active && !busy && (
            <div className="notice info">Select a report to preview its markdown.</div>
          )}
          {notice && <div className="notice warn">{notice}</div>}
        </div>
      </div>
    </>
  );
}