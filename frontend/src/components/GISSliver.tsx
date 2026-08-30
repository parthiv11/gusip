import React, { useState } from "react";
import { Crosshair, Plus, Minus, ChevronUp, ChevronDown, Video } from "lucide-react";

interface GISSliverProps {
  currentLocationName?: string;
  onExpandToggle?: (expanded: boolean) => void;
}

export const GISSliver: React.FC<GISSliverProps> = ({
  currentLocationName = "Chimanbhai Bridge",
  onExpandToggle,
}) => {
  const [expanded, setExpanded] = useState(false);
  const [zoomLevel, setZoomLevel] = useState(1);

  const toggleExpand = () => {
    const next = !expanded;
    setExpanded(next);
    if (onExpandToggle) onExpandToggle(next);
  };

  return (
    <div
      className={`relative w-full transition-all duration-300 rounded-[4px] border border-white/10 overflow-hidden select-none bg-[#090C10] ${
        expanded ? "h-64" : "h-[74px]"
      }`}
    >
      {/* Background Map Image */}
      <img
        src="/assets/gis_sliver.jpg"
        alt="GIS Map Preview"
        className="absolute inset-0 w-full h-full object-cover opacity-85 pointer-events-none filter contrast-125 brightness-90"
        style={{ transform: `scale(${zoomLevel})`, transformOrigin: "center center", transition: "transform 0.2s ease" }}
      />

      {/* Map Grid / Vignette Overlay */}
      <div className="absolute inset-0 bg-gradient-to-t from-[#0B0D10]/70 via-transparent to-[#0B0D10]/40 pointer-events-none" />

      {/* Left: Map Controls */}
      <div className="absolute top-2 left-2 z-10 flex flex-col gap-1">
        <button
          onClick={() => setZoomLevel(1)}
          title="Center on Target"
          className="w-5 h-5 rounded-[2px] bg-[#11151C]/90 border border-white/15 text-[#9AA4B2] hover:text-[#F2F4F7] hover:bg-[#151A22] flex items-center justify-center transition-colors"
        >
          <Crosshair size={11} />
        </button>
        <button
          onClick={() => setZoomLevel((z) => Math.min(1.5, z + 0.1))}
          title="Zoom In"
          className="w-5 h-5 rounded-[2px] bg-[#11151C]/90 border border-white/15 text-[#9AA4B2] hover:text-[#F2F4F7] hover:bg-[#151A22] flex items-center justify-center transition-colors font-bold text-xs"
        >
          <Plus size={11} />
        </button>
        <button
          onClick={() => setZoomLevel((z) => Math.max(0.8, z - 0.1))}
          title="Zoom Out"
          className="w-5 h-5 rounded-[2px] bg-[#11151C]/90 border border-white/15 text-[#9AA4B2] hover:text-[#F2F4F7] hover:bg-[#151A22] flex items-center justify-center transition-colors font-bold text-xs"
        >
          <Minus size={11} />
        </button>
      </div>

      {/* Geographic Labels Positioned across Map */}
      <div className="absolute inset-0 pointer-events-none flex items-center justify-around px-16 text-[11px] font-medium text-[#9AA4B2]/90 tracking-wide">
        <span className="hidden sm:inline">Sola</span>
        <span className="hidden md:inline">Gota</span>
        
        {/* Center Active Location Pin */}
        <div className="flex flex-col items-center gap-1 z-10 pointer-events-auto">
          <div className="bg-[#11151C]/90 border border-[#D9A441]/80 px-2.5 py-0.5 rounded-[3px] text-[11px] text-[#F2F4F7] font-semibold tracking-wide shadow-md flex items-center gap-1.5">
            <span>{currentLocationName}</span>
          </div>
          <div className="w-6 h-6 rounded-full bg-[#D9A441] border-2 border-[#11151C] shadow-[0_0_12px_#D9A441] flex items-center justify-center text-[#11151C]">
            <Video size={12} className="fill-current" />
          </div>
        </div>

        <span className="hidden lg:inline text-[#667085]">Sabarmati River</span>
        <span className="hidden md:inline">Vastrapur</span>
        <span className="hidden sm:inline">Naranpura</span>
        <span className="hidden xl:inline">Navrangpura</span>
      </div>

      {/* Right: Expand Toggle Button */}
      <div className="absolute top-2 right-2 z-10">
        <button
          onClick={toggleExpand}
          title={expanded ? "Collapse Map" : "Expand Map"}
          className="w-6 h-6 rounded-[3px] bg-[#11151C]/90 border border-white/15 text-[#9AA4B2] hover:text-[#F2F4F7] hover:bg-[#151A22] flex items-center justify-center transition-colors"
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
        </button>
      </div>
    </div>
  );
};
