import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function AdminPage() {
  const [audit, setAudit] = useState<Record<string, unknown>[]>([]);
  const [stats, setStats] = useState<Record<string, unknown>>({});
  const [error, setError] = useState("");

  useEffect(() => {
    api<Record<string, unknown>>("/api/v1/admin/stats").then(setStats);
    api<Record<string, unknown>[]>("/api/v1/admin/audit")
      .then(setAudit)
      .catch(() => setError("Audit log requires coordinator or admin role."));
  }, []);

  return (
    <div className="h-full p-4 overflow-auto">
      <h1 className="text-lg font-semibold mb-4">Administration</h1>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        {["cameras", "online", "events", "open_alerts"].map((k) => (
          <div key={k} className="border border-white/10 rounded p-3 bg-ink-900">
            <div className="text-[10px] uppercase tracking-widest text-slate-500">{k.replaceAll("_", " ")}</div>
            <div className="text-2xl font-semibold text-brass-400">{String(stats[k] ?? "—")}</div>
          </div>
        ))}
      </div>
      {error && <div className="text-amber-400 text-sm mb-3">{error}</div>}
      <h2 className="text-sm font-semibold mb-2">Audit trail</h2>
      <div className="overflow-x-auto">
      <table className="w-full text-xs min-w-[640px]">
        <thead className="text-slate-500 uppercase">
          <tr>
            <th className="text-left py-2">Time</th>
            <th className="text-left">User</th>
            <th className="text-left">Action</th>
            <th className="text-left">Resource</th>
            <th className="text-left">IP</th>
          </tr>
        </thead>
        <tbody>
          {audit.map((r) => (
            <tr key={String(r.id)} className="border-t border-white/5">
              <td className="py-1.5 font-mono">{String(r.created_at)}</td>
              <td>{String(r.username)}</td>
              <td>{String(r.action)}</td>
              <td className="text-slate-400">{String(r.resource)}</td>
              <td>{String(r.ip_address)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  );
}
