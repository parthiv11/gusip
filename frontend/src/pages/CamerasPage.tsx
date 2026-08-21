import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Camera } from "../types";

export default function CamerasPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [q, setQ] = useState("");
  useEffect(() => {
    api<Camera[]>("/api/v1/cameras").then(setCameras);
  }, []);
  const filtered = cameras.filter(
    (c) =>
      c.code.toLowerCase().includes(q.toLowerCase()) ||
      c.name.toLowerCase().includes(q.toLowerCase()) ||
      c.city.toLowerCase().includes(q.toLowerCase())
  );
  return (
    <div className="h-full p-4 overflow-auto">
      <div className="flex items-center gap-3 mb-4">
        <h1 className="text-lg font-semibold">Camera registry</h1>
        <input
          placeholder="Filter code, name, city"
          className="ml-auto bg-ink-900 border border-white/10 rounded px-3 py-1.5 text-sm w-72"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>
      <table className="w-full text-sm">
        <thead className="text-xs uppercase text-slate-500">
          <tr>
            <th className="text-left py-2">Code</th>
            <th className="text-left">Name</th>
            <th className="text-left">City</th>
            <th className="text-left">Source</th>
            <th className="text-left">Type</th>
            <th className="text-left">Status</th>
            <th className="text-left">AMC</th>
            <th className="text-left">Dept</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((c) => (
            <tr key={c.id} className="border-t border-white/5">
              <td className="py-2 font-mono text-brass-400">{c.code}</td>
              <td>{c.name}</td>
              <td>{c.city}</td>
              <td className="uppercase text-xs">{c.source_type}</td>
              <td>{c.camera_type}</td>
              <td className={c.status === "online" ? "text-emerald-400" : "text-red-400"}>{c.status}</td>
              <td>{c.amc_status}</td>
              <td className="text-slate-400">{c.department?.name}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
