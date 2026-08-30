import React from "react";
import { Shield } from "lucide-react";

export type FilterOption = "gov" | "demo" | "all";

interface CameraControlStripProps {
  wallCount: number;
  onlineCount: number;
  openAlertsCount: number;
  currentFilter: FilterOption;
  onFilterChange: (filter: FilterOption) => void;
  syncSentinelActive: boolean;
  onToggleSyncSentinel: () => void;
  currentPage: number;
  totalPages: number;
  onPrevPage: () => void;
  onNextPage: () => void;
}

export const CameraControlStrip: React.FC<CameraControlStripProps> = ({
  wallCount,
  onlineCount,
  openAlertsCount,
  currentFilter,
  onFilterChange,
  syncSentinelActive,
  onToggleSyncSentinel,
  currentPage,
  totalPages,
  onPrevPage,
  onNextPage,
}) => {
  return (
    <div className="h-8 shrink-0 flex items-center justify-between text-xs px-1 select-none">
      {/* Left: Online / Wall indicators */}
      <div className="flex items-center gap-3 font-medium">
        <div className="flex items-center gap-1.5 text-[#F2F4F7]">
          <span className="w-2 h-2 rounded-full bg-[#35B86B] live-dot shadow-[0_0_8px_#35B86B]" />
          <span className="font-semibold">{wallCount} on wall</span>
        </div>
        <div className="text-[#9AA4B2]">
          <span>{onlineCount} online</span>
        </div>
        <div className="text-[#D94848] font-semibold">
          <span>{openAlertsCount} open alerts</span>
        </div>
      </div>

      {/* Center: Filter Buttons */}
      <div className="hidden sm:flex items-center gap-2">
        <button
          onClick={() => onFilterChange("gov")}
          className={`px-3 py-0.5 rounded-[3px] text-[12px] font-medium transition-colors border ${
            currentFilter === "gov"
              ? "border-[#D9A441] bg-[#D9A441]/10 text-[#D9A441]"
              : "border-white/10 bg-[#11151C] text-[#9AA4B2] hover:text-[#F2F4F7] hover:bg-white/5"
          }`}
        >
          Gov feeds
        </button>
        <button
          onClick={() => onFilterChange("demo")}
          className={`px-3 py-0.5 rounded-[3px] text-[12px] font-medium transition-colors border ${
            currentFilter === "demo"
              ? "border-[#D9A441] bg-[#D9A441]/10 text-[#D9A441]"
              : "border-white/10 bg-[#11151C] text-[#9AA4B2] hover:text-[#F2F4F7] hover:bg-white/5"
          }`}
        >
          Own/Demo
        </button>
        <button
          onClick={() => onFilterChange("all")}
          className={`px-3 py-0.5 rounded-[3px] text-[12px] font-medium transition-colors border ${
            currentFilter === "all"
              ? "border-[#D9A441] bg-[#D9A441]/10 text-[#D9A441]"
              : "border-white/10 bg-[#11151C] text-[#9AA4B2] hover:text-[#F2F4F7] hover:bg-white/5"
          }`}
        >
          All
        </button>
        <button
          onClick={onToggleSyncSentinel}
          className={`px-3 py-0.5 rounded-[3px] text-[12px] font-medium transition-colors border flex items-center gap-1.5 ${
            syncSentinelActive
              ? "border-[#D9A441] bg-[#D9A441]/10 text-[#D9A441]"
              : "border-white/10 bg-[#11151C] text-[#9AA4B2] hover:text-[#F2F4F7] hover:bg-white/5"
          }`}
        >
          <Shield size={12} className={syncSentinelActive ? "text-[#D9A441]" : "text-[#9AA4B2]"} />
          Sync Sentinel
        </button>
      </div>

      {/* Right: Pagination */}
      <div className="flex items-center gap-2 font-mono text-[12px]">
        <span className="text-[#9AA4B2] mr-1">
          {currentPage} / {totalPages}
        </span>
        <button
          onClick={onPrevPage}
          disabled={currentPage <= 1}
          className="px-2.5 py-0.5 rounded-[3px] border border-white/10 bg-[#11151C] text-[#9AA4B2] hover:text-[#F2F4F7] hover:border-white/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-[11px]"
        >
          Prev
        </button>
        <button
          onClick={onNextPage}
          disabled={currentPage >= totalPages}
          className="px-2.5 py-0.5 rounded-[3px] border border-[#D9A441] bg-[#11151C] text-[#D9A441] hover:bg-[#D9A441]/10 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-[11px] font-semibold"
        >
          Next
        </button>
      </div>
    </div>
  );
};
