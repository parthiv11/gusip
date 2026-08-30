import React, { useState, useRef, useEffect } from "react";
import { MoreVertical, Play, Settings, Activity, Copy, Check } from "lucide-react";
import { RegistryCamera } from "./cameraData";
import { SourceBadge } from "./SourceBadge";
import { StatusIndicator } from "./StatusIndicator";
import { AMCBadge } from "./AMCBadge";

interface CameraRowProps {
  camera: RegistryCamera;
  isHighlighted?: boolean;
}

export const CameraRow: React.FC<CameraRowProps> = ({
  camera,
  isHighlighted = false,
}) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleCopy = () => {
    navigator.clipboard.writeText(`rtsp://stream.gusip.gujarat.gov.in/live/${camera.code.toLowerCase()}`);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <tr
      className={`h-[44px] border-t border-white/[0.05] transition-colors group ${
        isHighlighted
          ? "bg-[#181611]/70 hover:bg-[#1C1A14]"
          : "bg-[#0B0F14] hover:bg-[#121722]"
      }`}
    >
      {/* CODE */}
      <td className="pl-6 pr-4 py-2 font-mono text-[13px] font-medium text-[#D9A441] whitespace-nowrap">
        {camera.code}
      </td>

      {/* NAME */}
      <td className="px-4 py-2 text-[13px] text-[#F2F4F7] font-normal whitespace-nowrap">
        {camera.name}
      </td>

      {/* CITY */}
      <td className="px-4 py-2 text-[13px] text-[#A8B2C1] whitespace-nowrap">
        {camera.city}
      </td>

      {/* SOURCE */}
      <td className="px-4 py-2 whitespace-nowrap">
        <SourceBadge source={camera.source_type} />
      </td>

      {/* TYPE */}
      <td className="px-4 py-2 text-[13px] text-[#A8B2C1] whitespace-nowrap font-normal">
        {camera.camera_type}
      </td>

      {/* STATUS */}
      <td className="px-4 py-2 whitespace-nowrap">
        <StatusIndicator status={camera.status} />
      </td>

      {/* AMC */}
      <td className="px-4 py-2 whitespace-nowrap">
        <AMCBadge status={camera.amc_status} />
      </td>

      {/* DEPT */}
      <td className="px-4 py-2 text-[13px] text-[#A8B2C1] whitespace-nowrap">
        {camera.department}
      </td>

      {/* ACTION THREE DOTS */}
      <td className="pl-2 pr-5 py-2 text-right relative" ref={menuRef}>
        <button
          type="button"
          onClick={() => setMenuOpen(!menuOpen)}
          className="p-1 rounded text-[#6F7D91] hover:text-[#F2F4F7] hover:bg-white/[0.06] transition-colors inline-flex items-center justify-center"
          title="Actions"
        >
          <MoreVertical size={15} />
        </button>

        {menuOpen && (
          <div className="absolute right-4 mt-1 w-44 bg-[#0D1219] border border-white/[0.12] rounded-[6px] shadow-2xl py-1 z-50 text-left animate-in fade-in zoom-in-95 duration-100">
            <button
              onClick={() => setMenuOpen(false)}
              className="w-full px-3 py-1.5 text-xs text-[#A8B2C1] hover:text-[#F2F4F7] hover:bg-white/[0.05] flex items-center gap-2"
            >
              <Play size={13} className="text-[#D9A441]" />
              <span>View live feed</span>
            </button>
            <button
              onClick={handleCopy}
              className="w-full px-3 py-1.5 text-xs text-[#A8B2C1] hover:text-[#F2F4F7] hover:bg-white/[0.05] flex items-center gap-2"
            >
              {copied ? <Check size={13} className="text-[#35D58A]" /> : <Copy size={13} />}
              <span>{copied ? "Copied stream URL" : "Copy RTSP stream"}</span>
            </button>
            <button
              onClick={() => setMenuOpen(false)}
              className="w-full px-3 py-1.5 text-xs text-[#A8B2C1] hover:text-[#F2F4F7] hover:bg-white/[0.05] flex items-center gap-2"
            >
              <Activity size={13} />
              <span>Diagnostics</span>
            </button>
            <button
              onClick={() => setMenuOpen(false)}
              className="w-full px-3 py-1.5 text-xs text-[#A8B2C1] hover:text-[#F2F4F7] hover:bg-white/[0.05] flex items-center gap-2 border-t border-white/[0.06]"
            >
              <Settings size={13} />
              <span>Camera config</span>
            </button>
          </div>
        )}
      </td>
    </tr>
  );
};
