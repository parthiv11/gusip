import { FormEvent, useEffect, useState } from "react";
import { api, can } from "../api/client";

interface CaseRow {
  id: number;
  title: string;
  description?: string | null;
  status: string;
  created_by: string;
  created_at: string;
}

export default function CasesPage() {
  const [rows, setRows] = useState<CaseRow[]>([]);
  const [title, setTitle] = useState("Stolen Fortuner — Satellite FIR 112/2026");
  const [description, setDescription] = useState("Multi-camera hops SG Highway to Gandhinagar.");

  async function load() {
    setRows(await api<CaseRow[]>("/api/v1/cases"));
  }
  useEffect(() => {
    load();
  }, []);

  async function create(e: FormEvent) {
    e.preventDefault();
    const c = await api<CaseRow>("/api/v1/cases", { method: "POST", body: JSON.stringify({ title, description }) });
    const alerts = await api<{ id: number }[]>("/api/v1/alerts?limit=1");
    if (alerts[0]) {
      await api(`/api/v1/cases/${c.id}/evidence?alert_id=${alerts[0].id}&notes=auto-attached%20latest%20alert`, { method: "POST" });
    }
    load();
  }

  async function exp(id: number) {
    const data = await api(`/api/v1/cases/${id}/export`);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `gusip-case-${id}.json`;
    a.click();
  }

  return (
    <div className="h-full p-4 overflow-auto">
      <h1 className="text-lg font-semibold mb-4">Case folders</h1>
      <form onSubmit={create} className="flex gap-2 mb-6">
        <input className="flex-1 bg-ink-900 border border-white/10 rounded px-3 py-2 text-sm" value={title} onChange={(e) => setTitle(e.target.value)} />
        <button className="bg-brass-500 text-ink-950 px-4 rounded text-sm font-semibold">Create</button>
      </form>
      <ul className="space-y-2">
        {rows.map((r) => (
          <li key={r.id} className="border border-white/10 rounded p-3 flex justify-between">
            <div>
              <div className="font-medium">{r.title}</div>
              <div className="text-xs text-slate-400">
                {r.status} · {r.created_by} · {r.created_at}
              </div>
            </div>
            {can("export") && (
              <button onClick={() => exp(r.id)} className="text-xs text-brass-400">
                Export JSON
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
