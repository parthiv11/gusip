import { useEffect, useRef, useState } from "react";
import { getSession } from "../api/client";
import type { Camera, LiveDetection } from "../types";

export function sentinelId(camera: Camera): string | null {
  const extra = camera.extra || {};
  const id = extra.sentinel_id;
  if (typeof id === "string" || typeof id === "number") return String(id);
  if (camera.code.startsWith("SEN-")) return camera.code.slice(4);
  return null;
}

/** Same-origin HLS from the Camera Grid. Inference uses RTSP/HLS upstream, not this URL. */
export function hlsProxy(camera: Camera): string | null {
  const sid = sentinelId(camera);
  if (!sid) return null;
  return `/api/v1/feeds/sentinel/${encodeURIComponent(sid)}/hls/index.m3u8`;
}

/** Browser playback fallback (range requests). Inference never uses this URL. */
export function streamProxy(camera: Camera): string | null {
  const sid = sentinelId(camera);
  if (!sid) return null;
  return `/api/v1/feeds/sentinel/${encodeURIComponent(sid)}/stream`;
}

type HlsCtor = {
  isSupported(): boolean;
  Events: { MANIFEST_PARSED: string; ERROR: string; FRAG_BUFFERED: string };
  ErrorTypes: { MEDIA_ERROR: string };
  new (opts?: Record<string, unknown>): {
    attachMedia(video: HTMLVideoElement): void;
    loadSource(src: string): void;
    on(event: string, cb: (...args: unknown[]) => void): void;
    recoverMediaError(): void;
    startLoad(): void;
    destroy(): void;
  };
};

function hlsApi(): HlsCtor | null {
  const ctor = (window as unknown as { Hls?: HlsCtor }).Hls;
  return ctor && ctor.isSupported() ? ctor : null;
}

export function previewSrc(camera: Camera, bust?: number): string | undefined {
  const sid = sentinelId(camera);
  if (!sid) return undefined;
  const t = bust != null ? `?t=${bust}` : "";
  return `/api/v1/feeds/sentinel/${encodeURIComponent(sid)}/preview${t}`;
}

export default function GovPlayer({
  camera,
  live,
  autoPlay = true,
}: {
  camera: Camera;
  live?: LiveDetection;
  autoPlay?: boolean;
}) {
  const ref = useRef<HTMLVideoElement>(null);
  const sid = sentinelId(camera);
  const hlsSrc = hlsProxy(camera);
  const src = streamProxy(camera);
  const portal =
    typeof camera.extra?.portal === "string" ? camera.extra.portal.replace(/\/$/, "") : "";
  const [videoReady, setVideoReady] = useState(false);
  const [bust, setBust] = useState(() => Date.now());
  const [posterOk, setPosterOk] = useState(true);
  const poster = previewSrc(camera, bust);

  useEffect(() => {
    setVideoReady(false);
    setPosterOk(true);
    setBust(Date.now());
  }, [sid]);

  useEffect(() => {
    const t = setInterval(() => {
      if (!videoReady) setBust(Date.now());
    }, 8000);
    return () => clearInterval(t);
  }, [sid, videoReady]);

  useEffect(() => {
    const video = ref.current;
    if (!video || !sid) return;
    let cancelled = false;

    const markReady = () => {
      if ((video.videoWidth || 0) > 16) setVideoReady(true);
    };
    const Hls = hlsApi();
    let destroyHls: (() => void) | undefined;
    if (Hls && hlsSrc) {
      const hls = new Hls({
        maxBufferLength: 6,
        startPosition: -1,
        xhrSetup: (xhr: XMLHttpRequest) => {
          xhr.withCredentials = true;
        },
      });
      hls.attachMedia(video);
      hls.loadSource(hlsSrc);
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        if (!cancelled && autoPlay) video.play().catch(() => undefined);
      });
      hls.on(Hls.Events.FRAG_BUFFERED, markReady);
      hls.on(Hls.Events.ERROR, (...args: unknown[]) => {
        const data = args[1] as { fatal?: boolean; type?: string } | undefined;
        if (!data?.fatal) return;
        if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
          try {
            hls.recoverMediaError();
          } catch {
            /* recover is best-effort */
          }
        }
      });
      destroyHls = () => hls.destroy();
    } else if (hlsSrc && video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = hlsSrc;
      video.addEventListener("playing", markReady);
      if (autoPlay) video.play().catch(() => undefined);
    } else if (src) {
      video.src = src;
      video.addEventListener("playing", markReady);
      if (autoPlay) video.play().catch(() => undefined);
    }
    return () => {
      cancelled = true;
      destroyHls?.();
      video.removeAttribute("src");
      video.load();
    };
  }, [sid, hlsSrc, src, autoPlay]);

  const bbox = live?.bbox;

  return (
    <div className="relative h-full min-h-[200px] w-full bg-black overflow-hidden border border-white/10">
      {poster && posterOk && (
        <img
          src={poster}
          alt=""
          className={`absolute inset-0 w-full h-full object-contain bg-black ${videoReady ? "opacity-0" : "opacity-100"}`}
          onError={() => setPosterOk(false)}
        />
      )}
      <video
        ref={ref}
        className={`absolute inset-0 w-full h-full object-contain bg-transparent ${videoReady ? "opacity-100" : "opacity-0"}`}
        muted
        loop
        playsInline
        autoPlay={autoPlay}
        controls={false}
        poster={poster}
      />
      {bbox && live && (
        <div
          className="absolute border border-brass-400/90 pointer-events-none"
          style={{
            left: `${(bbox.x / 400) * 100}%`,
            top: `${(bbox.y / 240) * 100}%`,
            width: `${(bbox.w / 400) * 100}%`,
            height: `${(bbox.h / 240) * 100}%`,
          }}
        >
          <div className="absolute -top-4 left-0 text-[9px] font-mono text-brass-400 whitespace-nowrap">
            {typeof live.attributes?.color === "string" ? `${live.attributes.color} ` : ""}
            {live.plate ?? (live.attributes?.plate_status === "unreadable" ? "no plate" : live.object_type)}{" "}
            {Math.round(live.confidence * 100)}%
          </div>
        </div>
      )}
      <div className="absolute top-2 left-2 text-[10px] font-mono bg-black/60 px-1.5 py-0.5 rounded text-orange-300">
        GOV · {camera.code} · {(portal || "sentinel").replace(/^https?:\/\//, "")}
      </div>
      {(camera.extra?.plate_status === "unreadable" || live?.attributes?.plate_status === "unreadable") && (
        <div className="absolute top-2 right-2 text-[10px] font-mono bg-black/70 text-amber-200 px-1.5 py-0.5 rounded max-w-[60%] truncate">
          Plate unreadable · night PTZ
          {typeof camera.extra?.anpr_burst === "number" ? ` · burst ${camera.extra.anpr_burst}` : ""}
        </div>
      )}
      <div className="absolute bottom-2 left-2 right-2 flex justify-between gap-2 text-[10px] font-mono text-white/80">
        <span className="truncate">{camera.address || camera.name}</span>
        <span className="shrink-0 bg-black/50 px-1.5 py-0.5 rounded">
          {getSession()?.username} · {new Date().toLocaleString("en-IN", { hour12: false })}
        </span>
      </div>
    </div>
  );
}
