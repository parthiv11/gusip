import { useEffect, useState } from "react";
import { api } from "../api/client";
import GujaratMap from "../components/GujaratMap";
import type { Alert, Camera } from "../types";

interface Gap {
  city: string;
  camera_count: number;
  uncovered_hint: string;
  recommended_cameras: number;
}

export default function MapPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [status, setStatus] = useState("");
  const [dept, setDept] = useState("");
  const [departments, setDepartments] = useState<{ id: number; name: string }[]>([]);

  useEffect(() => {
    api<{ id: number; name: string }[]>("/api/v1/cameras/departments").then(setDepartments);
    api<Gap[]>("/api/v1/gis/gaps").then(setGaps);
    api<Alert[]>("/api/v1/alerts?status=new&limit=80").then(setAlerts);
  }, []);

  useEffect(() => {
    const q = new URLSearchParams();
    if (status) q.set("status", status);
    if (dept) q.set("department_id", dept);
    api<Camera[]>(`/api/v1/cameras?${q.toString()}`).then(setCameras);
  }, [status, dept]);

  return (
    <div className="h-full grid grid-cols-1 lg:grid-cols-12 min-h-0 overflow-y-auto lg:overflow-hidden">
      <div className="lg:col-span-9 min-h-[50vh] lg:min-h-0">
        <GujaratMap cameras={cameras} showCoverage alerts={alerts} />
      </div>
      <div className="lg:col-span-3 border-t lg:border-t-0 lg:border-l border-white/10 p-3 overflow-auto bg-ink-900">
        <h2 className="text-sm font-semibold text-brass-400 mb-3">Filters</h2>
        <select className="w-full bg-ink-950 border border-white/10 rounded px-2 py-1 text-xs mb-2" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All status</option>
          <option value="online">Online</option>
          <option value="offline">Offline</option>
        </select>
        <select className="w-full bg-ink-950 border border-white/10 rounded px-2 py-1 text-xs mb-4" value={dept} onChange={(e) => setDept(e.target.value)}>
          <option value="">All departments</option>
          {departments.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
        <h3 className="text-xs uppercase tracking-widest text-slate-500 mb-2">Legend</h3>
        <ul className="text-[11px] text-slate-400 space-y-1 mb-4">
          <li><span className="inline-block w-2.5 h-2.5 rounded-full bg-emerald-400 mr-2" />Camera online</li>
          <li><span className="inline-block w-2.5 h-2.5 rounded-full bg-red-400 mr-2" />Camera offline</li>
          <li><span className="inline-block w-4 h-4 rounded-full bg-yellow-400 text-ink-950 text-[9px] font-bold text-center leading-4 mr-1.5">n</span> Open alert · number = hit count · click for screenshot</li>
        </ul>
        <h3 className="text-xs uppercase tracking-widest text-slate-500 mb-2">Coverage gaps</h3>
        <ul className="space-y-2">
          {gaps.map((g) => (
            <li key={g.city} className="border border-white/10 rounded p-2 text-xs">
              <div className="flex justify-between">
                <span className="font-medium">{g.city}</span>
                <span className="text-brass-400">+{g.recommended_cameras}</span>
              </div>
              <div className="text-slate-400 mt-1">{g.camera_count} cameras · {g.uncovered_hint}</div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
