import { FormEvent, useMemo, useState } from "react";
import { api, can } from "../api/client";
import { snapSrc } from "../api/media";
import InvestigationMap, { InvestigationPoint } from "../components/InvestigationMap";
import type { EventItem, TrackPoint } from "../types";

interface FaceHit {
  id: number;
  name?: string | null;
  category: string;
  score: number;
  photo_url?: string | null;
  priority?: string;
}

interface FaceSearchOut {
  engine: string;
  query_has_face: boolean;
  threshold: number;
  watchlist: FaceHit[];
  events: EventItem[];
  track: TrackPoint[];
  global_track_id?: string | null;
}

const PURPOSES = [
  ["evaluation", "Evaluation / demo"],
  ["stolen_vehicle", "Stolen vehicle"],
  ["blacklisted_vehicle", "Blacklisted vehicle"],
  ["wanted_person", "Wanted person"],
  ["missing_person", "Missing person"],
  ["traffic_incident", "Traffic incident"],
  ["law_and_order", "Law and order"],
] as const;

function compass(from: TrackPoint, to: TrackPoint): string {
  const dLon = ((to.longitude - from.longitude) * Math.PI) / 180;
  const lat1 = (from.latitude * Math.PI) / 180;
  const lat2 = (to.latitude * Math.PI) / 180;
  const y = Math.sin(dLon) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);
  const brng = (Math.atan2(y, x) * 180) / Math.PI;
  const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  return dirs[Math.round((((brng + 360) % 360) / 45) % 8)];
}

function attr(events: EventItem[], key: string): string | null {
  for (const ev of events) {
    const value = ev.attributes?.[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return null;
}

function eventForHop(events: EventItem[], hop: TrackPoint): EventItem | undefined {
  const sameCam = events.filter((ev) => ev.camera_id === hop.camera_id);
  if (!sameCam.length) return undefined;
  const t = new Date(hop.timestamp).getTime();
  return sameCam.slice().sort((a, b) => Math.abs(new Date(a.timestamp).getTime() - t) - Math.abs(new Date(b.timestamp).getTime() - t))[0];
}

export default function SearchPage() {
  const [mode, setMode] = useState<"plate" | "face">("plate");
  const [plate, setPlate] = useState("GJ 01 ST 0001");
  const [faceFile, setFaceFile] = useState<File | null>(null);
  const [purpose, setPurpose] = useState("evaluation");
  const [events, setEvents] = useState<EventItem[]>([]);
  const [track, setTrack] = useState<TrackPoint[]>([]);
  const [faceHits, setFaceHits] = useState<FaceHit[]>([]);
  const [faceEngine, setFaceEngine] = useState("");
  const [error, setError] = useState("");
  const [selectedCam, setSelectedCam] = useState<number | null>(null);
  const canExport = can("export");

  async function onSearch(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      if (mode === "face") {
        if (!faceFile) {
          setError("Choose a still of an enrolled adult.");
          return;
        }
        const body = new FormData();
        body.append("file", faceFile);
        body.append("purpose", purpose);
        body.append("limit", "50");
        const out = await api<FaceSearchOut>("/api/v1/search/face", { method: "POST", body });
        setEvents(out.events);
        setTrack(out.track);
        setFaceHits(out.watchlist);
        setFaceEngine(out.engine);
        setSelectedCam(out.track[0]?.camera_id ?? out.events[0]?.camera_id ?? null);
        return;
      }
      setFaceHits([]);
      setFaceEngine("");
      const ev = await api<EventItem[]>("/api/v1/search/events", {
        method: "POST",
        body: JSON.stringify({ plate, limit: 50, purpose }),
      });
      setEvents(ev);
      const pts = await api<TrackPoint[]>(
        `/api/v1/search/plate/${encodeURIComponent(plate)}?purpose=${encodeURIComponent(purpose)}`
      );
      setTrack(pts);
      setSelectedCam(pts[0]?.camera_id ?? ev[0]?.camera_id ?? null);
    } catch (err) {
      setError(String(err));
    }
  }

  const uniqueCams = new Set(track.map((p) => p.camera_id)).size;
  const last = track[track.length - 1];
  const first = track[0];
  const heading = track.length >= 2 ? compass(track[0], track[track.length - 1]) : null;
  const color = attr(events, "color");
  const klass = attr(events, "vehicle_class") || attr(events, "object_type");
  const meanConf =
    events.length > 0 ? Math.round((events.reduce((s, ev) => s + (ev.confidence || 0), 0) / events.length) * 100) : null;
  const selectedHop = track.find((p) => p.camera_id === selectedCam) ?? last;
  const selectedEvent = selectedHop ? eventForHop(events, selectedHop) : events[0];
  const still = snapSrc(selectedEvent?.snapshot_url);
  const searched = track.length > 0 || events.length > 0 || faceHits.length > 0;

  const hopTimes = useMemo(
    () =>
      track.map((p) =>
        new Date(p.timestamp).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false })
      ),
    [track]
  );

  const invPoints: InvestigationPoint[] = useMemo(
    () =>
      track.map((p, i) => ({
        id: i + 1,
        camCode: p.camera_code ?? String(p.camera_id),
        name: p.camera_name ?? "",
        city: p.city ?? "",
        lat: p.latitude,
        lng: p.longitude,
        time: new Date(p.timestamp).toLocaleTimeString("en-IN", { hour12: false }),
        date: new Date(p.timestamp).toLocaleDateString("en-IN"),
        confidence: "",
        thumbnail: "",
        isLatest: i === track.length - 1,
      })),
    [track]
  );
  const selectedHopIndex = track.findIndex((p) => p.camera_id === selectedCam);

  return (
    <div className="h-full grid grid-cols-1 lg:grid-cols-12 min-h-0 overflow-y-auto lg:overflow-hidden bg-[#0B0D10]">
      <div className="lg:col-span-5 p-4 overflow-auto border-b lg:border-b-0 lg:border-r border-white/10">
        <h1 className="text-lg font-semibold mb-1 text-[#F2F4F7]">Search the State</h1>
        <p className="text-[11px] text-slate-500 mb-3">
          Investigator-assisted trail. Purpose is mandatory and audited. Face search is logged and meant for enrolled adults on own/demo cameras.
        </p>
        <div className="flex gap-1 mb-3 text-xs">
          {(["plate", "face"] as const).map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => setMode(id)}
              className={`px-3 py-1 rounded border ${
                mode === id ? "border-brass-400 bg-brass-500/15 text-brass-300" : "border-white/10 text-slate-400"
              }`}
            >
              {id === "plate" ? "Plate" : "Face"}
            </button>
          ))}
        </div>
        <form onSubmit={onSearch} className="flex flex-col gap-2 mb-4">
          {mode === "plate" ? (
            <input
              className="bg-ink-900 border border-white/10 rounded px-3 py-2 text-sm font-mono"
              value={plate}
              onChange={(e) => setPlate(e.target.value)}
              aria-label="Plate or description"
            />
          ) : (
            <input
              type="file"
              accept="image/*"
              className="bg-ink-900 border border-white/10 rounded px-3 py-2 text-sm"
              aria-label="Face still"
              onChange={(e) => setFaceFile(e.target.files?.[0] ?? null)}
            />
          )}
          <div className="flex flex-col sm:flex-row gap-2">
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
        {mode === "face" && faceHits.length > 0 && (
          <div className="mb-3 rounded border border-white/10 bg-ink-900/60 p-3">
            <div className="text-[11px] text-slate-500 mb-2">
              Watchlist · engine {faceEngine || "—"}
            </div>
            {faceHits.map((hit) => (
              <div key={hit.id} className="text-sm mb-1">
                <span className="text-brass-400 font-semibold">{hit.name || "Unnamed"}</span>
                <span className="text-slate-400"> · {hit.category.replaceAll("_", " ")}</span>
                <span className="font-mono text-orange-300"> · {hit.score.toFixed(2)}</span>
              </div>
            ))}
          </div>
        )}
        <p className="text-[11px] text-slate-500 mb-3">
          {mode === "face"
            ? "Enroll an adult still on Watchlist (ArcFace). Search with another photo of the same person. Own/demo cameras only."
            : "Evaluation plate: add it on Watchlist, then wait for ANPR on government feeds."}
          {canExport ? (
            <>
              {" "}
              <button
                type="button"
                className="text-orange-300 underline"
                onClick={async () => {
                  const r = await fetch("/api/v1/feeds/anpr-report?fmt=csv", {
                    credentials: "same-origin",
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

        {searched && (
          <div className="mb-4 rounded border border-white/10 bg-ink-900/60 p-3">
            <div className="text-sm text-brass-400 font-semibold">
              {mode === "face"
                ? `${faceHits[0]?.name || "Person"} · ${faceHits[0] ? faceHits[0].score.toFixed(2) : "search"}`
                : `${[color, klass].filter(Boolean).join(" ") || "Vehicle"} · ${plate}`}
            </div>
            <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] text-slate-400">
              <div>
                Last seen{" "}
                <span className="text-slate-200">
                  {last ? new Date(last.timestamp).toLocaleString("en-IN", { hour12: false }) : "—"}
                </span>
              </div>
              <div>
                Place <span className="text-slate-200">{last?.city || first?.city || "—"}</span>
              </div>
              <div>
                Direction <span className="text-slate-200">{heading || "—"}</span>
              </div>
              <div>
                Cameras <span className="text-slate-200">{uniqueCams}</span>
              </div>
              <div>
                Confidence <span className="text-slate-200">{meanConf != null ? `${meanConf}%` : "—"}</span>
              </div>
              <div>
                Hops <span className="text-slate-200">{track.length}</span>
              </div>
            </div>
            {hopTimes.length > 0 && (
              <div className="mt-2 font-mono text-[11px] text-brass-400/90">{hopTimes.join(" → ")}</div>
            )}
          </div>
        )}

        {still && (
          <img src={still} alt="" className="mb-3 w-full max-h-40 object-contain rounded border border-white/10 bg-black" />
        )}

        <div className="text-xs text-slate-500 mb-2">{events.length} events · {track.length} hops — click a hop for the still</div>
        <ol className="space-y-2">
          {track.map((p, i) => {
            const active = p.camera_id === selectedCam;
            return (
              <li key={`${p.camera_id}-${p.timestamp}-${i}`}>
                <button
                  type="button"
                  onClick={() => setSelectedCam(p.camera_id)}
                  className={`w-full text-left text-sm border rounded p-2 ${
                    active ? "border-brass-400 bg-brass-500/10" : "border-white/10 hover:border-white/20"
                  }`}
                >
                  <span className="font-mono text-brass-400">{p.camera_code}</span> {p.camera_name}
                  <div className="text-xs text-slate-400">
                    {p.city} · {new Date(p.timestamp).toLocaleString("en-IN")}
                    {i > 0 ? ` · from ${track[i - 1].camera_code}` : " · first hit"}
                  </div>
                </button>
              </li>
            );
          })}
        </ol>
      </div>
      <div className="lg:col-span-7 min-h-[40vh] lg:min-h-0">
        <InvestigationMap
          points={invPoints}
          selectedEventId={selectedHopIndex >= 0 ? selectedHopIndex + 1 : undefined}
          onSelectEvent={(id) => {
            const hop = track[id - 1];
            if (hop) setSelectedCam(hop.camera_id);
          }}
        />
      </div>
    </div>
  );
}
