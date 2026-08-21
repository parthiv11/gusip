import { useEffect, useMemo, useRef, useState } from "react";
import { api, wsUrl } from "../api/client";
import { snapSrc } from "../api/media";
import CameraTile from "../components/CameraTile";
import FocusPlayer from "../components/FocusPlayer";
import GujaratMap from "../components/GujaratMap";
import type { Alert, Camera, LiveDetection } from "../types";

type Wall = "gov" | "demo" | "all";

function playAlertTone() {
  if (localStorage.getItem("gusip.alertSound") === "off") return;
  try {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "square";
    osc.frequency.value = 880;
    gain.gain.value = 0.04;
    osc.connect(gain).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.16);
    osc.onended = () => ctx.close().catch(() => undefined);
  } catch {
    /* browsers may block until a click */
  }
}

function fingerprint(a: Pick<Alert, "camera_id" | "watchlist" | "payload">): string {
  const fromPayload = a.payload?.fingerprint;
  if (typeof fromPayload === "string" && fromPayload) return fromPayload;
  const wl = a.watchlist?.id ?? a.payload?.watchlist_id ?? "";
  return `${wl}:${a.camera_id}`;
}

function hitCount(a: Alert): number {
  const n = Number(a.payload?.hit_count ?? 1);
  return Number.isFinite(n) && n > 0 ? n : 1;
}

function asAlert(d: Record<string, unknown>): Alert {
  return {
    id: Number(d.id),
    camera_id: Number(d.camera_id),
    timestamp: String(d.timestamp ?? new Date().toISOString()),
    confidence: Number(d.confidence ?? 0),
    snapshot_url: (d.snapshot_url as string | null) ?? null,
    status: String(d.status ?? "new"),
    payload: d,
    watchlist: {
      id: Number(d.watchlist_id ?? 0),
      category: String(d.category ?? ""),
      name: (d.name as string | null) ?? null,
      plate_number: (d.plate as string | null) ?? null,
      description: (d.description as string | null) ?? null,
      priority: String(d.priority ?? "high"),
      entity_type: String(d.entity_type ?? "vehicle"),
    },
  };
}

/** Keep one open card per camera+watchlist; prefer the latest timestamp. */
function coalesceInbox(rows: Alert[]): Alert[] {
  const open = new Map<string, Alert>();
  const rest: Alert[] = [];
  const ordered = [...rows].sort((a, b) => +new Date(a.timestamp) - +new Date(b.timestamp));
  for (const row of ordered) {
    if (row.status !== "new") {
      rest.push(row);
      continue;
    }
    const key = fingerprint(row);
    const prev = open.get(key);
    if (!prev) {
      open.set(key, { ...row, payload: { ...row.payload, hit_count: hitCount(row) } });
      continue;
    }
    const count = prev.id === row.id ? Math.max(hitCount(prev), hitCount(row)) : hitCount(prev) + hitCount(row);
    open.set(key, {
      ...row,
      id: Math.min(prev.id, row.id),
      payload: { ...prev.payload, ...row.payload, hit_count: count },
      watchlist: row.watchlist ?? prev.watchlist,
    });
  }
  return [...open.values(), ...rest].sort((a, b) => +new Date(b.timestamp) - +new Date(a.timestamp));
}

export default function ControlRoom() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [live, setLive] = useState<Record<number, LiveDetection>>({});
  const [selected, setSelected] = useState<Camera | null>(null);
  const [page, setPage] = useState(0);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [wall, setWall] = useState<Wall>("gov");
  const [syncMsg, setSyncMsg] = useState("");
  const [toast, setToast] = useState<string | null>(null);
  const [focusId, setFocusId] = useState<number | null>(null);
  const [soundOn, setSoundOn] = useState(() => localStorage.getItem("gusip.alertSound") !== "off");
  const camerasRef = useRef<Camera[]>([]);
  const selectedRef = useRef<Camera | null>(null);
  const wallRef = useRef<Wall>("gov");
  camerasRef.current = cameras;
  selectedRef.current = selected;
  wallRef.current = wall;

  const filtered = useMemo(() => {
    if (wall === "gov") return cameras.filter((c) => c.source_type === "sentinel");
    if (wall === "demo") return cameras.filter((c) => c.source_type !== "sentinel");
    return cameras;
  }, [cameras, wall]);

  const inbox = useMemo(() => coalesceInbox(alerts), [alerts]);
  const openCount = inbox.filter((a) => a.status === "new").length;
  const focusAlertRow = inbox.find((a) => a.status === "new" && a.camera_id === selected?.id) ?? null;

  const pageSize = 8;
  const slice = useMemo(() => filtered.slice(page * pageSize, page * pageSize + pageSize), [filtered, page, pageSize]);

  async function loadCameras() {
    const c = await api<Camera[]>("/api/v1/cameras");
    setCameras(c);
    setSelected((prev) => {
      if (prev && c.some((x) => x.id === prev.id)) return prev;
      const gov = c.find((x) => x.source_type === "sentinel");
      return gov ?? c[0] ?? null;
    });
  }

  function focusAlert(
    cameraId: number | undefined,
    sourceType?: string | null,
    banner?: string,
    opts?: { fromInbox?: boolean }
  ) {
    if (banner) {
      setToast(banner);
      window.setTimeout(() => setToast(null), 12000);
    }
    if (!cameraId) return;
    const cam = camerasRef.current.find((x) => x.id === cameraId);
    if (!cam) {
      setToast((prev) => prev ?? "Alert camera is outside current scope — break-glass if you need that district");
      return;
    }
    const src = sourceType || cam.source_type;
    const onGov = wallRef.current === "gov";
    setWall((current) => {
      if (current === "all") return current;
      if (src === "sentinel") return "gov";
      if (current === "gov" && !opts?.fromInbox) return current;
      return "demo";
    });
    if (onGov && src !== "sentinel" && !opts?.fromInbox) return;
    setSelected(cam);
    setFocusId(cam.id);
  }

  useEffect(() => {
    if (focusId == null) return;
    const idx = filtered.findIndex((c) => c.id === focusId);
    if (idx >= 0) setPage(Math.floor(idx / pageSize));
  }, [focusId, filtered, pageSize]);

  useEffect(() => {
    loadCameras();
    api<Alert[]>("/api/v1/alerts?limit=80").then((rows) => setAlerts(coalesceInbox(rows)));
    api<Record<string, number>>("/api/v1/admin/stats").then((s) => setStats(s));
  }, []);

  useEffect(() => {
    const a = new WebSocket(wsUrl("/ws/alerts"));
    const l = new WebSocket(wsUrl("/ws/live"));
    a.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type !== "alert") return;
      const incoming = asAlert(msg.data);
      const coalesced = Boolean(msg.data?.coalesced);
      setAlerts((prev) => {
        const key = fingerprint(incoming);
        const idx = prev.findIndex((x) => x.id === incoming.id || (x.status === "new" && fingerprint(x) === key));
        if (idx >= 0) {
          const copy = [...prev];
          const prior = copy[idx];
          copy[idx] = {
            ...prior,
            ...incoming,
            id: prior.id,
            payload: {
              ...prior.payload,
              ...incoming.payload,
              hit_count: Math.max(hitCount(incoming), hitCount(prior)),
            },
            watchlist: incoming.watchlist ?? prior.watchlist,
          };
          return copy;
        }
        return [incoming, ...prev].slice(0, 40);
      });
      if (coalesced && selectedRef.current?.id === incoming.camera_id) return;
      const label = [incoming.watchlist?.category?.replaceAll("_", " "), incoming.watchlist?.plate_number || incoming.watchlist?.name, msg.data.camera_code]
        .filter(Boolean)
        .join(" · ");
      const hits = hitCount(incoming);
      focusAlert(incoming.camera_id, String(msg.data.source_type || ""), `Watchlist hit · ${label}${hits > 1 ? ` · ×${hits}` : ""}`);
      const pri = String(msg.data.priority || "").toLowerCase();
      if (!coalesced && (pri === "critical" || pri === "high")) playAlertTone();
    };
    l.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "detection") {
        const d = msg.data as LiveDetection;
        setLive((prev) => ({ ...prev, [d.camera_id]: d }));
      }
    };
    const keep = setInterval(() => {
      if (a.readyState === 1) a.send("ping");
      if (l.readyState === 1) l.send("ping");
    }, 15000);
    return () => {
      clearInterval(keep);
      a.close();
      l.close();
    };
  }, []);

  async function ack(id: number) {
    const target = alerts.find((a) => a.id === id);
    await api(`/api/v1/alerts/${id}/ack`, { method: "POST" });
    setAlerts((prev) =>
      prev.map((a) =>
        target && a.status === "new" && fingerprint(a) === fingerprint(target) ? { ...a, status: "acknowledged" } : a
      )
    );
  }

  async function syncGov() {
    setSyncMsg("Syncing…");
    try {
      const r = await api<{ synced: number }>("/api/v1/feeds/sentinel/sync", { method: "POST" });
      setSyncMsg(`${r.synced} government feeds onboarded`);
      await loadCameras();
    } catch (e) {
      setSyncMsg(String(e));
    }
  }

  function toggleSound() {
    const next = !soundOn;
    setSoundOn(next);
    localStorage.setItem("gusip.alertSound", next ? "on" : "off");
  }

  return (
    <div className="h-full grid grid-cols-12 gap-2 p-2">
      <section className="col-span-8 flex flex-col min-h-0 gap-2">
        {toast && (
          <div className="px-3 py-2 rounded border border-red-500/50 bg-red-500/15 text-red-100 text-xs font-medium">
            {toast}
          </div>
        )}
        <div className="flex items-center gap-2 text-xs text-slate-400 px-1 flex-wrap">
          <span className="text-brass-400 font-semibold">{filtered.length} on wall</span>
          <span>{stats.online ?? "—"} online</span>
          <span className="text-red-400">{openCount} open alerts</span>
          {(["gov", "demo", "all"] as Wall[]).map((w) => (
            <button
              key={w}
              onClick={() => {
                setWall(w);
                setPage(0);
              }}
              className={`px-2 py-0.5 rounded border ${wall === w ? "border-brass-400 text-brass-400" : "border-white/10"}`}
            >
              {w === "gov" ? "Gov feeds" : w === "demo" ? "Own/demo" : "All"}
            </button>
          ))}
          <button className="px-2 py-0.5 border border-orange-500/40 text-orange-300 rounded" onClick={syncGov}>
            Sync Sentinel
          </button>
          <button className="px-2 py-0.5 border border-white/10 rounded" onClick={toggleSound}>
            {soundOn ? "Alert sound on" : "Alert sound off"}
          </button>
          {syncMsg && <span className="text-orange-300/80">{syncMsg}</span>}
          <span className="ml-auto font-mono">
            {page + 1}/{Math.max(1, Math.ceil(filtered.length / pageSize))}
          </span>
          <button className="px-2 py-0.5 border border-white/10 rounded" onClick={() => setPage((p) => Math.max(0, p - 1))}>
            Prev
          </button>
          <button
            className="px-2 py-0.5 border border-white/10 rounded"
            onClick={() => setPage((p) => Math.min(Math.ceil(filtered.length / pageSize) - 1, p + 1))}
          >
            Next
          </button>
        </div>
        {selected && <FocusPlayer camera={selected} live={live[selected.id]} alert={focusAlertRow} />}
        <div className="grid grid-cols-4 gap-2 overflow-auto min-h-0">
          {slice.map((c) => (
            <CameraTile key={c.id} camera={c} live={live[c.id]} selected={selected?.id === c.id} onSelect={() => setSelected(c)} />
          ))}
        </div>
        <div className="h-40 shrink-0 border border-white/10 rounded overflow-hidden">
          <GujaratMap
            cameras={filtered}
            selectedId={selected?.id}
            onSelect={setSelected}
            alerts={inbox}
            onAlertClick={(a) => focusAlert(a.camera_id, a.camera?.source_type || (a.payload?.source_type as string | undefined))}
          />
        </div>
      </section>
      <aside className="col-span-4 min-h-0 flex flex-col border border-white/10 rounded bg-ink-900">
        <div className="px-3 py-2 border-b border-white/10 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-brass-400">Alert inbox</h2>
          <a className="text-[10px] text-orange-300" href="/search">
            ANPR report
          </a>
        </div>
        {selected && (
          <div className="px-3 py-2 text-xs border-b border-white/5 text-slate-400">
            Focus: <span className="text-white">{selected.code}</span> · {selected.address || selected.name} · {selected.source_type}
          </div>
        )}
        <div className="flex-1 overflow-auto divide-y divide-white/5">
          {inbox.map((a) => {
            const n = hitCount(a);
            return (
              <article
                key={a.id}
                className={`p-3 hover:bg-white/5 cursor-pointer ${selected?.id === a.camera_id ? "bg-brass-500/10" : ""}`}
                onClick={() =>
                  focusAlert(
                    a.camera_id,
                    a.camera?.source_type || (a.payload?.source_type as string | undefined),
                    undefined,
                    { fromInbox: true }
                  )
                }
              >
                <div className="flex justify-between text-[10px] uppercase tracking-wide">
                  <span className={a.status === "new" ? "text-red-400" : "text-slate-500"}>
                    {a.watchlist?.category?.replaceAll("_", " ")}
                    {n > 1 ? ` · ×${n}` : ""}
                  </span>
                  <span className="font-mono text-slate-500">{new Date(a.timestamp).toLocaleTimeString("en-IN")}</span>
                </div>
                <div className="text-sm font-medium mt-0.5">
                  {a.watchlist?.name} {a.watchlist?.plate_number ? `· ${a.watchlist.plate_number}` : ""}
                </div>
                <div className="text-xs text-slate-400">
                  {(a.payload?.camera_code as string) ?? a.camera?.code} · {Math.round(a.confidence * 100)}% · track{" "}
                  {(a.payload?.global_track_id as string) ?? "—"}
                  {n > 1 ? ` · last of ${n} hits` : ""}
                </div>
                {a.snapshot_url && <img src={snapSrc(a.snapshot_url)} alt="" className="mt-2 w-full h-20 object-cover rounded border border-white/10" />}
                {a.status === "new" && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      ack(a.id);
                    }}
                    className="mt-2 text-[11px] px-2 py-1 bg-brass-500/20 text-brass-400 rounded"
                  >
                    Acknowledge
                  </button>
                )}
              </article>
            );
          })}
        </div>
      </aside>
    </div>
  );
}
