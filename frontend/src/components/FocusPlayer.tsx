import { useEffect, useMemo, useState } from "react";
import { getSession } from "../api/client";
import { snapSrc } from "../api/media";
import type { Alert, Camera, LiveDetection } from "../types";
import GovPlayer, { sentinelId } from "./GovPlayer";

export default function FocusPlayer({
  camera,
  live,
  alert,
}: {
  camera: Camera;
  live?: LiveDetection;
  alert?: Alert | null;
}) {
  if (sentinelId(camera)) {
    return (
      <div className="relative h-full min-h-0 w-full">
        <GovPlayer camera={camera} live={live} />
        {alert && <AlertBanner alert={alert} />}
      </div>
    );
  }
  return <DemoFocus camera={camera} live={live} alert={alert} />;
}

function hitCount(alert?: Alert | null): number {
  const n = Number(alert?.payload?.hit_count ?? 1);
  return Number.isFinite(n) && n > 0 ? n : 1;
}

function AlertBanner({ alert }: { alert: Alert }) {
  const n = hitCount(alert);
  return (
    <div className="absolute top-2 right-2 z-10 max-w-[70%] text-right">
      <div className="inline-flex items-center gap-1.5 bg-yellow-400 text-ink-950 text-[11px] font-bold uppercase tracking-wide px-2 py-1 rounded">
        <span className="min-w-[1.25rem] h-4 grid place-items-center rounded-full bg-ink-950 text-yellow-400 text-[10px] normal-case">
          {n}
        </span>
        {(alert.watchlist?.category || "watchlist").replaceAll("_", " ")}
      </div>
      <div className="text-[11px] text-white/90 mt-1 bg-black/55 px-2 py-0.5 rounded font-mono">
        {alert.watchlist?.name}
        {alert.watchlist?.plate_number ? ` · ${alert.watchlist.plate_number}` : ""}
      </div>
    </div>
  );
}

function DemoFocus({
  camera,
  live,
  alert,
}: {
  camera: Camera;
  live?: LiveDetection;
  alert?: Alert | null;
}) {
  const [clock, setClock] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const hash = useMemo(() => {
    let h = 0;
    for (const c of camera.code) h = (h * 31 + c.charCodeAt(0)) | 0;
    return Math.abs(h);
  }, [camera.code]);
  const hue = 200 + (hash % 40);
  const bbox = live?.bbox;
  const snap = alert?.snapshot_url ? snapSrc(alert.snapshot_url) : undefined;

  return (
    <div className="relative h-full min-h-[200px] w-full bg-black overflow-hidden border border-brass-400/50">
      {snap ? (
        <img src={snap} alt="" className="absolute inset-0 w-full h-full object-cover opacity-70" />
      ) : (
        <div
          className="absolute inset-0"
          style={{ background: `radial-gradient(circle at 30% 20%, hsl(${hue} 20% 18%), #070b12)` }}
        />
      )}
      <div className="absolute inset-0 opacity-30 scanlines pointer-events-none" />
      {bbox && live && (
        <div
          className="absolute border-2 border-brass-400/90 pointer-events-none"
          style={{
            left: `${(bbox.x / 400) * 100}%`,
            top: `${(bbox.y / 240) * 100}%`,
            width: `${(bbox.w / 400) * 100}%`,
            height: `${(bbox.h / 240) * 100}%`,
          }}
        >
          <div className="absolute -top-5 left-0 text-[11px] font-mono text-brass-400 whitespace-nowrap">
            {live.object_type}
            {live.plate ? ` · ${live.plate}` : ""} {Math.round(live.confidence * 100)}%
          </div>
        </div>
      )}
      {alert && <AlertBanner alert={alert} />}
      <div className="absolute top-2 left-2 text-[10px] font-mono bg-black/60 px-1.5 py-0.5 rounded text-sky-300">
        OWN · {camera.code} · {camera.source_type}
      </div>
      <div className="absolute bottom-2 left-2 right-2 flex justify-between gap-2 text-[10px] font-mono text-white/80">
        <span className="truncate">
          {camera.address || camera.name} · {camera.city}
        </span>
        <span className="shrink-0 bg-black/50 px-1.5 py-0.5 rounded">
          {getSession()?.username} · {clock.toLocaleString("en-IN", { hour12: false })}
        </span>
      </div>
    </div>
  );
}
