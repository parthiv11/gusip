import { useEffect, useMemo, useState } from "react";
import type { Camera, LiveDetection } from "../types";
import { previewSrc, sentinelId } from "./GovPlayer";

const SOURCE_COLOR: Record<string, string> = {
  rtsp: "bg-emerald-500/20 text-emerald-300",
  onvif: "bg-sky-500/20 text-sky-300",
  vendor_api: "bg-violet-500/20 text-violet-300",
  sentinel: "bg-orange-500/20 text-orange-300",
};

export default function CameraTile({
  camera,
  live,
  selected,
  onSelect,
}: {
  camera: Camera;
  live?: LiveDetection;
  selected?: boolean;
  onSelect?: () => void;
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
  const [bust, setBust] = useState(() => Date.now());
  useEffect(() => {
    if (!sentinelId(camera)) return;
    const t = setInterval(() => setBust(Date.now()), 12000);
    return () => clearInterval(t);
  }, [camera.code]);
  const preview = sentinelId(camera) ? previewSrc(camera, bust) : undefined;

  return (
    <button
      onClick={onSelect}
      className={`relative aspect-video rounded overflow-hidden border text-left ${
        selected ? "border-brass-400 ring-1 ring-brass-400" : "border-white/10"
      }`}
    >
      {preview ? (
        <img
          src={preview}
          alt=""
          className="absolute inset-0 w-full h-full object-cover opacity-80"
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = "none";
          }}
        />
      ) : (
        <div
          className="absolute inset-0"
          style={{
            background: `radial-gradient(circle at 30% 20%, hsl(${hue} 20% 18%), #070b12)`,
          }}
        />
      )}
      <div className="absolute inset-0 opacity-30 scanlines pointer-events-none" />
      <div className="absolute inset-x-0 top-0 h-8 bg-gradient-to-b from-black/60 to-transparent px-2 flex items-center justify-between text-[10px] font-mono">
        <span className="flex items-center gap-1.5">
          <span className={`h-1.5 w-1.5 rounded-full ${camera.status === "online" ? "bg-emerald-400 live-dot" : "bg-red-500"}`} />
          {camera.code}
        </span>
        <span className={`px-1.5 py-0.5 rounded ${SOURCE_COLOR[camera.source_type] ?? "bg-white/10"}`}>
          {camera.source_type}
        </span>
      </div>

      {bbox && live && (
        <div
          className="absolute border border-brass-400/90 bg-brass-400/10"
          style={{
            left: `${(bbox.x / 400) * 100}%`,
            top: `${(bbox.y / 240) * 100}%`,
            width: `${(bbox.w / 400) * 100}%`,
            height: `${(bbox.h / 240) * 100}%`,
          }}
        >
          <div className="absolute -top-4 left-0 text-[9px] font-mono text-brass-400 whitespace-nowrap">
            {live.object_type}
            {live.plate ? ` · ${live.plate}` : ""} {Math.round(live.confidence * 100)}%
          </div>
        </div>
      )}

      <div className="absolute inset-x-0 bottom-0 p-2 bg-gradient-to-t from-black/80 to-transparent">
        <div className="text-[11px] font-medium truncate">{camera.address || camera.name}</div>
        <div className="text-[10px] text-slate-400 font-mono flex justify-between">
          <span>
            {camera.city} · {camera.vendor ?? camera.camera_type}
          </span>
          <span>{clock.toLocaleTimeString("en-IN", { hour12: false })}</span>
        </div>
      </div>
    </button>
  );
}
