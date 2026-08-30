import { FormEvent, useEffect, useState } from "react";
import { api, can } from "../api/client";
import type { Alert } from "../types";

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

  const [error, setError] = useState("");

  async function load() {
    setRows(await api<CaseRow[]>("/api/v1/cases"));
  }
  useEffect(() => {
    load();
  }, []);

  async function create(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const c = await api<CaseRow>("/api/v1/cases", { method: "POST", body: JSON.stringify({ title, description }) });
      const alerts = await api<Alert[]>("/api/v1/alerts?status=new&limit=80");
      const compact = (s: string) => s.toUpperCase().replaceAll(" ", "");
      const match =
        alerts.find((a) => a.watchlist?.category === "stolen_vehicle") ||
        alerts.find((a) => {
          const plate = a.watchlist?.plate_number;
          return Boolean(plate && compact(title).includes(compact(plate)));
        }) ||
        alerts[0];
      if (match) {
        await api(`/api/v1/cases/${c.id}/evidence?alert_id=${match.id}&notes=auto-attached%20watchlist%20alert`, {
          method: "POST",
        });
      }
      await load();
    } catch (err) {
      setError(String(err));
    }
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
    <div className="h-full p-4 overflow-auto bg-[#0B0D10]">
      <h1 className="text-lg font-semibold mb-4 text-[#F2F4F7]">Case folders</h1>
      {error && <div className="text-red-400 text-xs mb-2">{error}</div>}
      <form onSubmit={create} className="flex flex-col sm:flex-row gap-2 mb-6">
        <input
          className="flex-1 bg-[#11151C] border border-white/10 rounded px-3 py-2 text-sm text-[#F2F4F7]"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <button className="bg-[#D9A441] text-[#0B0D10] px-4 py-2 rounded text-sm font-semibold">Create</button>
      </form>
      <ul className="space-y-2">
        {rows.map((r) => (
          <li
            key={r.id}
            className="border border-white/10 rounded-[4px] p-3 flex flex-col sm:flex-row sm:justify-between gap-2 bg-[#11151C]"
          >
            <div>
              <div className="font-medium text-[#F2F4F7]">{r.title}</div>
              <div className="text-xs text-[#9AA4B2]">
                {r.status} · {r.created_by} · {r.created_at}
              </div>
            </div>
            {can("export") && (
              <button onClick={() => exp(r.id)} className="text-xs text-[#D9A441]">
                Export JSON
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
