import React from "react";

interface AMCBadgeProps {
  status: "active" | "expired" | string;
}

export const AMCBadge: React.FC<AMCBadgeProps> = ({ status }) => {
  const isActive = status.toLowerCase() === "active";

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-[4px] text-[11.5px] font-medium leading-tight select-none ${
        isActive
          ? "bg-[#0C2418] text-[#35D58A] border border-[#35D58A]/30"
          : "bg-[#191F28] text-[#7E8B9D] border border-white/[0.08]"
      }`}
    >
      {isActive ? "active" : "expired"}
    </span>
  );
};
