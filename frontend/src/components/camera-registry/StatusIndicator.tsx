import React from "react";

interface StatusIndicatorProps {
  status: "online" | "offline" | string;
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({ status }) => {
  const isOnline = status.toLowerCase() === "online";

  return (
    <div className="inline-flex items-center gap-2 select-none">
      <span
        className={`w-2 h-2 rounded-full ${
          isOnline
            ? "bg-[#35D58A] shadow-[0_0_6px_rgba(53,213,138,0.7)]"
            : "bg-[#EF4444] shadow-[0_0_6px_rgba(239,68,68,0.7)]"
        }`}
      />
      <span className="text-[13px] text-[#F2F4F7] font-normal leading-none">
        {isOnline ? "online" : "offline"}
      </span>
    </div>
  );
};
