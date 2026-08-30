import React, { useEffect, useState } from "react";
import { MapPin } from "lucide-react";

export interface CameraData {
  id: number;
  code: string;
  source: string;
  name: string;
  location: string;
  image: string;
  status: string;
  fps?: number;
}

interface PrimaryCameraFeedProps {
  camera: CameraData;
}

function formatStamp(now: Date): string {
  const d = String(now.getDate()).padStart(2, "0");
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const y = now.getFullYear();
  const h = String(now.getHours()).padStart(2, "0");
  const min = String(now.getMinutes()).padStart(2, "0");
  const s = String(now.getSeconds()).padStart(2, "0");
  return `${d}/${m}/${y} ${h}:${min}:${s}`;
}

export const PrimaryCameraFeed: React.FC<PrimaryCameraFeedProps> = ({ camera }) => {
  const [timestamp, setTimestamp] = useState(() => formatStamp(new Date()));

  useEffect(() => {
    const tick = () => setTimestamp(formatStamp(new Date()));
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="relative w-full h-full min-h-[380px] bg-[#000] border border-white/10 rounded-[4px] overflow-hidden group shadow-lg flex items-center justify-center">
      {/* Background Surveillance Camera Feed */}
      <img
        src={camera.image}
        alt={camera.name}
        className="w-full h-full object-cover select-none pointer-events-none"
      />

      {/* CCTV Texture & Scanline Effect */}
      <div className="absolute inset-0 scanlines pointer-events-none opacity-40" />
      <div className="absolute inset-0 vignette pointer-events-none" />

      {/* Top Left: Source & Camera ID Badge */}
      <div className="absolute top-3.5 left-3.5 z-10 flex items-center gap-2 bg-[#0B0D10]/80 backdrop-blur-md border border-white/15 px-2.5 py-1 rounded-[3px] text-[#F2F4F7] font-mono text-[11.5px] font-medium shadow-md">
        <span className="w-2 h-2 rounded-full bg-[#35B86B] live-dot shadow-[0_0_6px_#35B86B]" />
        <span>{camera.source} · {camera.code}</span>
      </div>

      {/* Bottom Left: Location Label */}
      <div className="absolute bottom-3.5 left-3.5 z-10 flex items-center gap-2 bg-[#0B0D10]/85 backdrop-blur-md border border-white/15 px-3 py-1.5 rounded-[4px] text-[#F2F4F7] text-[12.5px] font-medium shadow-md max-w-[75%] truncate">
        <MapPin size={14} className="text-[#D9A441] shrink-0" />
        <span className="truncate">{camera.location}</span>
      </div>

      {/* Bottom Right: Date & Time Stamp */}
      <div className="absolute bottom-3.5 right-3.5 z-10 flex items-center bg-[#0B0D10]/85 backdrop-blur-md border border-white/15 px-3 py-1.5 rounded-[4px] font-mono text-[12px] font-medium text-[#F2F4F7] shadow-md tracking-wide">
        {timestamp}
      </div>
    </div>
  );
};
