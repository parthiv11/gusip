import { FormEvent, useState } from "react";
import { api, can, getSession } from "../api/client";
import GujaratMap from "../components/GujaratMap";
import type { EventItem, TrackPoint } from "../types";

const PURPOSES = [
  ["evaluation", "Evaluation / demo"],
  ["stolen_vehicle", "Stolen vehicle"],
  ["blacklisted_vehicle", "Blacklisted vehicle"],
  ["wanted_person", "Wanted person"],
  ["missing_person", "Missing person"],
  ["traffic_incident", "Traffic incident"],
  ["law_and_order", "Law and order"],
] as const;

export default function SearchPage() {
  const [plate, setPlate] = useState("GJ 01 ST 0001");
  const [purpose, setPurpose] = useState("evaluation");
  const [events, setEvents] = useState<EventItem[]>([]);
  const [track, setTrack] = useState<TrackPoint[]>([]);
  const [error, setError] = useState("");
  const canExport = can("export");

  async function onSearch(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const ev = await api<EventItem[]>("/api/v1/search/events", {
        method: "POST",
        body: JSON.stringify({ plate, limit: 50, purpose }),
      });
      setEvents(ev);
      const pts = await api<TrackPoint[]>(
        `/api/v1/search/plate/${encodeURIComponent(plate)}?purpose=${encodeURIComponent(purpose)}`
      );
      setTrack(pts);
    } catch (err) {
      setError(String(err));
    }
  }

  const cameras = track.map((p, i) => ({
    id: p.camera_id,
    code: p.camera_code ?? String(i),
    name: p.camera_name ?? "",
    department_id: 0,
    camera_type: "ip",
    ownership: "",
    source_type: "rtsp",
    status: "online",
    connectivity: "",
    amc_status: "",
    coverage_radius_m: 80,
    latitude: p.latitude,
    longitude: p.longitude,
    city: p.city ?? "",
  }));

  return (
    <div className="h-full grid grid-cols-12">
      <div className="col-span-5 p-4 overflow-auto border-r border-white/10">
        <h1 className="text-lg font-semibold mb-3">Investigation search</h1>
        <form onSubmit={onSearch} className="flex flex-col gap-2 mb-4">
          <input className="bg-ink-900 border border-white/10 rounded px-3 py-2 text-sm font-mono" value={plate} onChange={(e) => setPlate(e.target.value)} />
          <div className="flex gap-2">
            <select
              className="flex-1 bg-ink-900 border border-white/10 rounded px-3 py-2 text-sm"
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
            >
              {PURPOSES.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
            <button className="bg-brass-500 text-ink-950 px-4 rounded text-sm font-semibold">Search</button>
          </div>
        </form>
        <p className="text-[11px] text-slate-500 mb-3">
          Purpose is mandatory and audited (ABAC). Evaluation plate: add it on Watchlist, then wait for ANPR on government feeds.
          {canExport ? (
            <>
              {" "}
              <button
                type="button"
                className="text-orange-300 underline"
                onClick={async () => {
                  const r = await fetch("/api/v1/feeds/anpr-report?fmt=csv", {
                    headers: { Authorization: `Bearer ${getSession()?.token ?? ""}` },
                  });
                  if (!r.ok) {
                    setError(await r.text());
                    return;
                  }
                  const blob = await r.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = "gusip-anpr-report.csv";
                  a.click();
                }}
              >
                Download ANPR report (CSV)
              </button>
            </>
          ) : (
            <span className="block mt-1 text-slate-600">CSV export is limited to investigation / coordinator / admin.</span>
          )}
        </p>
        {error && <div className="text-red-400 text-xs mb-2">{error}</div>}
        <div className="text-xs text-slate-500 mb-2">{events.length} events · {track.length} hops</div>
        <ol className="space-y-2">
          {track.map((p, i) => (
            <li key={i} className="text-sm border border-white/10 rounded p-2">
              <span className="font-mono text-brass-400">{p.camera_code}</span> {p.camera_name}
              <div className="text-xs text-slate-400">
                {p.city} · {new Date(p.timestamp).toLocaleString("en-IN")}
              </div>
            </li>
          ))}
        </ol>
      </div>
      <div className="col-span-7">
        <GujaratMap cameras={cameras} track={track} />
      </div>
    </div>
  );
}
