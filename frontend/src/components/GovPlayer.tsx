import { useEffect, useRef, useState } from "react";
import Hls from "hls.js";
import { getSession } from "../api/client";
import type { Camera, LiveDetection } from "../types";

export function sentinelId(camera: Camera): string | null {
  const extra = camera.extra || {};
  const id = extra.sentinel_id;
  if (typeof id === "string" || typeof id === "number") return String(id);
  if (camera.code.startsWith("SEN-")) return camera.code.slice(4);
  return null;
}

export function streamProxy(camera: Camera): string | null {
  const sid = sentinelId(camera);
  if (!sid) return null;
  const token = getSession()?.token ?? "";
  return `/api/v1/feeds/sentinel/${encodeURIComponent(sid)}/stream?token=${encodeURIComponent(token)}`;
}

export function previewSrc(camera: Camera, bust?: number): string | undefined {
  const sid = sentinelId(camera);
  if (!sid) return undefined;
  const token = getSession()?.token ?? "";
  const t = bust != null ? `&t=${bust}` : "";
  return `/api/v1/feeds/sentinel/${encodeURIComponent(sid)}/preview?token=${encodeURIComponent(token)}${t}`;
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
  const src = streamProxy(camera);
  const hlsUrl =
    (typeof camera.extra?.hls_url === "string" && camera.extra.hls_url) ||
    (typeof camera.extra?.hls_live_url === "string" && camera.extra.hls_live_url) ||
    null;
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
    let hls: Hls | null = null;
    let cancelled = false;

    async function start() {
      const state = await fetch(`/api/v1/feeds/sentinel/${sid}/state`, {
        headers: { Authorization: `Bearer ${getSession()?.token ?? ""}` },
      }).then((r) => (r.ok ? r.json() : null));
      if (cancelled || !video) return;
      const offset = Number(state?.slot_offset ?? state?.offset ?? 0);

      const markReady = () => {
        if ((video.videoWidth || 0) > 16) setVideoReady(true);
      };

      function playHttpFallback() {
        if (!src) return;
        video.src = src;
        const onMeta = () => {
          try {
            if (offset && isFinite(video.duration) && video.duration > 1) {
              video.currentTime = offset % video.duration;
            }
          } catch {
            /* live RTSP/HLS has no seek; HTTP /stream is a looping file */
          }
          if (autoPlay) video.play().catch(() => undefined);
        };
        video.addEventListener("loadedmetadata", onMeta, { once: true });
        video.addEventListener("playing", markReady);
      }

      if (hlsUrl && Hls.isSupported()) {
        const resolved = hlsUrl.startsWith("http") ? hlsUrl : `https://live.sentinelgujarat.in${hlsUrl}`;
        hls = new Hls({ startPosition: offset, maxBufferLength: 30 });
        hls.loadSource(resolved);
        hls.attachMedia(video);
        hls.on(Hls.Events.MANIFEST_PARSED, () => video.play().catch(() => undefined));
        hls.on(Hls.Events.ERROR, (_e, data) => {
          if (data.fatal) {
            hls?.destroy();
            hls = null;
            playHttpFallback();
          }
        });
        video.addEventListener("playing", markReady);
        return;
      }
      playHttpFallback();
    }
    start();
    return () => {
      cancelled = true;
      if (hls) hls.destroy();
      video.removeAttribute("src");
      video.load();
    };
  }, [sid, src, hlsUrl, autoPlay]);

  const bbox = live?.bbox;

  return (
    <div className="relative aspect-video bg-black rounded overflow-hidden border border-white/10">
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
        playsInline
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
          <div className="absolute -top-4 left-0 text-[9px] font-mono text-brass-400">
            {live.plate ?? live.object_type}
          </div>
        </div>
      )}
      <div className="absolute top-2 left-2 text-[10px] font-mono bg-black/60 px-1.5 py-0.5 rounded text-orange-300">
        GOV · {camera.code} · live.sentinelgujarat.in
      </div>
      <div className="absolute bottom-2 left-2 right-2 flex justify-between gap-2 text-[10px] font-mono text-white/80">
        <span className="truncate">{camera.address || camera.name}</span>
        <span className="shrink-0 bg-black/50 px-1.5 py-0.5 rounded">
          {getSession()?.username} · {new Date().toLocaleString("en-IN", { hour12: false })}
        </span>
      </div>
    </div>
  );
}
