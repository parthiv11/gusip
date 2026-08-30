import React from "react";

interface SourceBadgeProps {
  source: "ONVIF" | "RTSP" | "VENDOR_API" | string;
}

export const SourceBadge: React.FC<SourceBadgeProps> = ({ source }) => {
  if (source === "ONVIF") {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-[4px] text-[11px] font-mono font-medium tracking-wide bg-[#101C2B] text-[#5293D6] border border-[#5293D6]/20 select-none">
        ONVIF
      </span>
    );
  }

  if (source === "RTSP") {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-[4px] text-[11px] font-mono font-medium tracking-wide bg-[#0E2026] text-[#2CB4C8] border border-[#2CB4C8]/20 select-none">
        RTSP
      </span>
    );
  }

  if (source === "VENDOR_API") {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-[4px] text-[11px] font-mono font-medium tracking-wide bg-[#20152F] text-[#A574E3] border border-[#A574E3]/20 select-none">
        VENDOR_API
      </span>
    );
  }

  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-[4px] text-[11px] font-mono font-medium tracking-wide bg-[#151A22] text-[#9AA4B2] border border-white/10 select-none">
      {source}
    </span>
  );
};
