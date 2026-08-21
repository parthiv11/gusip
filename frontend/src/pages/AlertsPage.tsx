import { useEffect, useState } from "react";
import { api } from "../api/client";
import { snapSrc } from "../api/media";
import type { Alert } from "../types";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [status, setStatus] = useState("");
  async function load() {
    const q = status ? `?status=${status}` : "";
    setAlerts(await api<Alert[]>(`/api/v1/alerts${q}`));
  }
  useEffect(() => {
    load();
  }, [status]);
  return (
    <div className="h-full p-4 overflow-auto">
      <div className="flex items-center gap-3 mb-4">
        <h1 className="text-lg font-semibold">Alerts</h1>
        <select className="ml-auto bg-ink-900 border border-white/10 rounded px-2 py-1 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All</option>
          <option value="new">New</option>
          <option value="acknowledged">Acknowledged</option>
        </select>
      </div>
      <div className="grid gap-3">
        {alerts.map((a) => (
          <div key={a.id} className="border border-white/10 rounded p-3 grid grid-cols-12 gap-3 bg-ink-900">
            <div className="col-span-2">
              {a.snapshot_url && <img src={snapSrc(a.snapshot_url)} className="w-full h-24 object-cover rounded" alt="" />}
            </div>
            <div className="col-span-10 text-sm">
              <div className="flex justify-between">
                <span className="text-brass-400 font-medium">{a.watchlist?.category?.replaceAll("_", " ")}</span>
                <span className="font-mono text-xs text-slate-500">{a.timestamp}</span>
              </div>
              <div>
                {a.watchlist?.name} · {a.watchlist?.plate_number} · {Math.round(a.confidence * 100)}%
              </div>
              <div className="text-slate-400 text-xs mt-1">
                {a.camera?.code} {a.camera?.name} · {a.camera?.city} · {a.status}
              </div>
              <p className="text-xs text-slate-500 mt-1">{a.watchlist?.description}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
