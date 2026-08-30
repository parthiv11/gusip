import { useEffect, useMemo, useRef, useState } from "react";
import { ImageOff } from "lucide-react";
import { api, wsUrl } from "../api/client";
import { snapSrc } from "../api/media";
import CameraTile from "../components/CameraTile";
import FocusPlayer from "../components/FocusPlayer";
import GujaratMap from "../components/GujaratMap";
import SplitPane from "../components/SplitPane";
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

function useDesktop() {
  const [desktop, setDesktop] = useState(() => window.matchMedia("(min-width: 1024px)").matches);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    const onChange = () => setDesktop(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return desktop;
}

function SnapshotThumb({ src, alt = "" }: { src?: string; alt?: string }) {
  const [ok, setOk] = useState(true);
  useEffect(() => {
    setOk(true);
  }, [src]);
  if (!src || !ok) {
    return (
      <div className="mt-2 h-20 w-full rounded border border-white/10 bg-ink-950 text-slate-500 grid place-items-center">
        <span className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-wide">
          <ImageOff size={12} />
          No still
        </span>
      </div>
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      className="mt-2 h-20 w-full object-cover rounded border border-white/10 bg-ink-950"
      onError={() => setOk(false)}
    />
  );
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

  const desktop = useDesktop();

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

  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const wallLabel = { gov: "Gov feeds", demo: "Own/demo", all: "All" } as const;

  const toolbar = (
    <div className="shrink-0 flex items-center gap-3 text-xs px-1 min-h-8 flex-wrap">
      <div className="flex items-center gap-3 text-slate-300">
        <span>
          <span className="text-brass-400 font-semibold tabular-nums">{filtered.length}</span> on wall
        </span>
        <span className="text-slate-500">·</span>
        <span>
          <span className="tabular-nums text-emerald-300">{stats.online ?? "—"}</span> online
        </span>
        <span className="text-slate-500">·</span>
        <span>
          <span className="tabular-nums text-red-400">{openCount}</span> open alerts
        </span>
      </div>
      <div className="flex rounded border border-white/10 overflow-hidden" role="tablist" aria-label="Camera wall">
        {(["gov", "demo", "all"] as Wall[]).map((w) => (
          <button
            key={w}
            role="tab"
            aria-selected={wall === w}
            onClick={() => {
              setWall(w);
              setPage(0);
            }}
            className={`px-2.5 py-1 ${
              wall === w ? "bg-white/10 text-brass-400" : "text-slate-400 hover:text-white hover:bg-white/5"
            }`}
          >
            {wallLabel[w]}
          </button>
        ))}
      </div>
      <button
        className="px-2.5 py-1 border border-white/10 text-slate-300 hover:text-white rounded"
        onClick={syncGov}
      >
        Sync Sentinel
      </button>
      <button
        className="px-2.5 py-1 border border-white/10 text-slate-300 hover:text-white rounded"
        onClick={toggleSound}
      >
        Sound {soundOn ? "on" : "off"}
      </button>
      {syncMsg && <span className="text-orange-300/90 truncate max-w-[16rem]">{syncMsg}</span>}
      <div className="ml-auto flex items-center gap-1 font-mono text-slate-400">
        <span className="px-1">
          {page + 1}/{pages}
        </span>
        <button
          className="px-2 py-1 border border-white/10 rounded hover:text-white disabled:opacity-30"
          disabled={page <= 0}
          onClick={() => setPage((p) => Math.max(0, p - 1))}
        >
          Prev
        </button>
        <button
          className="px-2 py-1 border border-white/10 rounded hover:text-white disabled:opacity-30"
          disabled={page >= pages - 1}
          onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}
        >
          Next
        </button>
      </div>
    </div>
  );

  const focus = selected ? (
    <FocusPlayer camera={selected} live={live[selected.id]} alert={focusAlertRow} />
  ) : (
    <div className="h-full grid place-items-center text-sm text-slate-500 border border-white/10 bg-ink-900">
      No camera selected
    </div>
  );

  const tiles = (
    <div className="h-full min-h-0 overflow-auto p-0.5 grid grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 content-start gap-2">
      {slice.map((c) => (
        <CameraTile key={c.id} camera={c} live={live[c.id]} selected={selected?.id === c.id} onSelect={() => setSelected(c)} />
      ))}
    </div>
  );

  const mapPane = (
    <div className="h-full min-h-0 border border-white/10 overflow-hidden bg-ink-900">
      <GujaratMap
        cameras={filtered}
        selectedId={selected?.id}
        onSelect={setSelected}
        alerts={inbox}
        onAlertClick={(a) => focusAlert(a.camera_id, a.camera?.source_type || (a.payload?.source_type as string | undefined))}
      />
    </div>
  );

  const inboxPane = (
    <aside className="h-full min-h-0 flex flex-col border border-white/10 bg-ink-900">
      <div className="px-3 py-2 border-b border-white/10 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-brass-400">Alert inbox</h2>
        <a className="text-[11px] text-slate-400 hover:text-brass-400" href="/search">
          ANPR report
        </a>
      </div>
      {selected && (
        <div className="px-3 py-2 text-xs border-b border-white/10 text-slate-300">
          Focus <span className="text-white font-medium">{selected.code}</span>
          <span className="text-slate-500"> · {selected.address || selected.name}</span>
        </div>
      )}
      <div className="flex-1 overflow-auto">
        {inbox.map((a) => {
          const n = hitCount(a);
          const active = selected?.id === a.camera_id;
          return (
            <article
              key={a.id}
              className={`px-3 py-3 border-b border-white/5 cursor-pointer ${
                active ? "bg-brass-500/10" : "hover:bg-white/[0.04]"
              }`}
              onClick={() =>
                focusAlert(
                  a.camera_id,
                  a.camera?.source_type || (a.payload?.source_type as string | undefined),
                  undefined,
                  { fromInbox: true }
                )
              }
            >
              <div className="flex justify-between gap-2 text-[10px] uppercase tracking-wide">
                <span className={a.status === "new" ? "text-red-400" : "text-slate-500"}>
                  {a.watchlist?.category?.replaceAll("_", " ")}
                  {n > 1 ? ` · ×${n}` : ""}
                </span>
                <span className="font-mono text-slate-400">{new Date(a.timestamp).toLocaleTimeString("en-IN")}</span>
              </div>
              <div className="text-sm font-medium mt-1 text-slate-100">
                {a.watchlist?.name}
                {a.watchlist?.plate_number ? ` · ${a.watchlist.plate_number}` : ""}
              </div>
              <div className="text-xs text-slate-400 mt-0.5">
                {(a.payload?.camera_code as string) ?? a.camera?.code} · {Math.round(a.confidence * 100)}%
                {n > 1 ? ` · ${n} hits` : ""}
              </div>
              <SnapshotThumb src={snapSrc(a.snapshot_url)} />
              {a.status === "new" && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    ack(a.id);
                  }}
                  className="mt-2 text-[11px] px-2.5 py-1 border border-brass-400/40 text-brass-400 rounded hover:bg-brass-500/10"
                >
                  Acknowledge
                </button>
              )}
            </article>
          );
        })}
      </div>
    </aside>
  );

  return (
    <div className="h-full min-h-0 flex flex-col gap-2 p-2 overflow-hidden">
      {toast && (
        <div className="shrink-0 px-3 py-2 rounded border border-red-500/40 bg-red-500/10 text-red-100 text-xs">
          {toast}
        </div>
      )}
      {toolbar}
      <SplitPane direction="horizontal" defaultSize={74} min={52} max={86} storageKey="gusip.cr.inbox" stacked={!desktop}>
        <SplitPane direction="vertical" defaultSize={58} min={36} max={78} storageKey="gusip.cr.focus" stacked={!desktop}>
          {focus}
          <SplitPane direction="horizontal" defaultSize={56} min={32} max={78} storageKey="gusip.cr.map" stacked={!desktop}>
            {tiles}
            {mapPane}
          </SplitPane>
        </SplitPane>
        {inboxPane}
      </SplitPane>
    </div>
  );
}
