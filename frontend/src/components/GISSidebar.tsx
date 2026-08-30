import React from "react";
import { ChevronDown } from "lucide-react";

export interface CoverageGapItem {
  city: string;
  current: number;
  target: number;
  lat: number;
  lon: number;
  colorType: "critical" | "warning" | "moderate" | "good";
}

export const COVERAGE_GAP_DATA: CoverageGapItem[] = [
  { city: "Modasa", current: 2, target: 8, lat: 23.4632, lon: 73.2984, colorType: "critical" },
  { city: "Deesa", current: 3, target: 10, lat: 24.2585, lon: 72.1812, colorType: "critical" },
  { city: "Palanpur", current: 4, target: 12, lat: 24.1724, lon: 72.4346, colorType: "critical" },
  { city: "Mandvi", current: 3, target: 8, lat: 22.8335, lon: 69.3567, colorType: "warning" },
  { city: "Porbandar", current: 4, target: 10, lat: 21.6417, lon: 69.6293, colorType: "warning" },
  { city: "Bharuch", current: 6, target: 12, lat: 21.7051, lon: 72.9959, colorType: "warning" },
  { city: "Navsari", current: 8, target: 12, lat: 20.9467, lon: 72.9520, colorType: "moderate" },
  { city: "Morbi", current: 9, target: 12, lat: 22.8173, lon: 70.8377, colorType: "moderate" },
  { city: "Jamnagar", current: 12, target: 14, lat: 22.4707, lon: 70.0577, colorType: "good" },
  { city: "Rajkot", current: 15, target: 16, lat: 22.3039, lon: 70.8022, colorType: "good" },
  { city: "Gandhidham", current: 7, target: 10, lat: 23.0753, lon: 70.1337, colorType: "moderate" },
  { city: "Junagadh", current: 8, target: 10, lat: 21.5222, lon: 70.4579, colorType: "moderate" },
  { city: "Bhavnagar", current: 10, target: 12, lat: 21.7645, lon: 72.1519, colorType: "good" },
  { city: "Vadodara", current: 18, target: 20, lat: 22.3072, lon: 73.1812, colorType: "good" },
  { city: "Ahmedabad", current: 28, target: 30, lat: 23.0225, lon: 72.5714, colorType: "good" },
  { city: "Surat", current: 22, target: 24, lat: 21.1702, lon: 72.8311, colorType: "good" },
];

interface GISSidebarProps {
  statusFilter: string;
  onStatusFilterChange: (val: string) => void;
  deptFilter: string;
  onDeptFilterChange: (val: string) => void;
  departments: { id: string | number; name: string }[];
  onSelectCity: (city: CoverageGapItem) => void;
  selectedCityName?: string | null;
}

export default function GISSidebar({
  statusFilter,
  onStatusFilterChange,
  deptFilter,
  onDeptFilterChange,
  departments,
  onSelectCity,
  selectedCityName,
}: GISSidebarProps) {
  const getProgressBarClass = (colorType: CoverageGapItem["colorType"]) => {
    switch (colorType) {
      case "critical":
        return "bg-gradient-to-r from-[#F05252] to-[#F28C3B]";
      case "warning":
        return "bg-gradient-to-r from-[#F28C3B] to-[#F2A93B]";
      case "moderate":
        return "bg-gradient-to-r from-[#F2A93B] to-[#F0C45A]";
      case "good":
        return "bg-gradient-to-r from-[#48C78E] to-[#35D49A]";
    }
  };

  return (
    <aside className="w-full lg:w-[380px] shrink-0 h-full bg-[#080C14] border-t lg:border-t-0 lg:border-l border-white/[0.08] p-5 flex flex-col min-h-0 select-none overflow-hidden">
      {/* 1. FILTERS SECTION */}
      <div className="shrink-0">
        <h2 className="text-[13px] font-semibold tracking-wide text-[#D9A441] uppercase mb-3">
          Filters
        </h2>
        <div className="space-y-2.5">
          {/* Status Dropdown */}
          <div className="relative">
            <select
              value={statusFilter}
              onChange={(e) => onStatusFilterChange(e.target.value)}
              className="w-full h-[40px] bg-[#10151D] border border-white/[0.08] hover:border-white/20 focus:border-[#D9A441]/50 rounded-[4px] px-3.5 pr-9 text-[13px] text-[#F2F4F7] font-medium appearance-none focus:outline-none cursor-pointer transition-colors"
            >
              <option value="all">All status</option>
              <option value="online">Online</option>
              <option value="offline">Offline</option>
            </select>
            <ChevronDown
              size={15}
              className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[#687386] pointer-events-none"
            />
          </div>

          {/* Department Dropdown */}
          <div className="relative">
            <select
              value={deptFilter}
              onChange={(e) => onDeptFilterChange(e.target.value)}
              className="w-full h-[40px] bg-[#10151D] border border-white/[0.08] hover:border-white/20 focus:border-[#D9A441]/50 rounded-[4px] px-3.5 pr-9 text-[13px] text-[#F2F4F7] font-medium appearance-none focus:outline-none cursor-pointer transition-colors"
            >
              <option value="all">All departments</option>
              {departments.map((d) => (
                <option key={d.id} value={String(d.id)}>
                  {d.name}
                </option>
              ))}
            </select>
            <ChevronDown
              size={15}
              className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[#687386] pointer-events-none"
            />
          </div>
        </div>
      </div>

      {/* Divider */}
      <div className="shrink-0 h-px bg-white/[0.08] my-4" />

      {/* 2. LEGEND SECTION */}
      <div className="shrink-0">
        <h3 className="text-[13px] font-semibold tracking-wide text-[#D9A441] uppercase mb-3">
          Legend
        </h3>
        <div className="space-y-2.5">
          {/* Online Marker */}
          <div className="flex items-center gap-3">
            <div className="w-3.5 h-3.5 rounded-full border-2 border-[#35D49A] bg-[#0B0D10] flex items-center justify-center shrink-0 shadow-[0_0_6px_rgba(53,212,154,0.4)]">
              <div className="w-1 h-1 rounded-full bg-[#35D49A]" />
            </div>
            <span className="text-[13px] text-[#A7B0BE] font-normal">Camera online</span>
          </div>

          {/* Offline Marker */}
          <div className="flex items-center gap-3">
            <div className="w-3.5 h-3.5 rounded-full border-2 border-[#F05252] bg-[#0B0D10] flex items-center justify-center shrink-0 shadow-[0_0_6px_rgba(240,82,82,0.4)]">
              <div className="w-1 h-1 rounded-full bg-[#F05252]" />
            </div>
            <span className="text-[13px] text-[#A7B0BE] font-normal">Camera offline</span>
          </div>

          {/* Open Alert Starburst */}
          <div className="flex items-center gap-3">
            <div className="relative w-4 h-4 flex items-center justify-center shrink-0">
              <svg className="absolute w-5 h-5 text-[#D9A441] animate-spin-slow" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 0L14 8L22 4L16 11L24 12L16 13L22 20L14 16L12 24L10 16L2 20L8 13L0 12L8 11L2 4L10 8Z" />
              </svg>
              <div className="relative w-2.5 h-2.5 rounded-full bg-[#F0C45A] border border-[#FFF8DB]" />
            </div>
            <span className="text-[13px] text-[#A7B0BE] font-normal">
              Open alert — number = hit count
            </span>
          </div>
        </div>
      </div>

      {/* Divider */}
      <div className="shrink-0 h-px bg-white/[0.08] my-4" />

      {/* 3. COVERAGE GAPS SECTION (Scrollable list) */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="shrink-0 flex items-center justify-between mb-3">
          <h3 className="text-[13px] font-semibold tracking-wide text-[#D9A441] uppercase">
            Coverage Gaps
          </h3>
          <span className="px-2.5 py-0.5 rounded-[4px] border border-[#F05252]/40 bg-[#F05252]/10 text-[#F05252] text-[11px] font-medium tracking-wide">
            7 cities under target
          </span>
        </div>

        {/* Scrollable list */}
        <div className="flex-1 overflow-y-auto space-y-2 pr-1.5 min-h-0">
          {COVERAGE_GAP_DATA.map((item) => {
            const isSelected = selectedCityName === item.city;
            const pct = Math.min(100, Math.round((item.current / item.target) * 100));
            return (
              <div
                key={item.city}
                onClick={() => onSelectCity(item)}
                className={`group p-2.5 rounded-[4px] bg-[#10151D]/60 hover:bg-[#131923] border cursor-pointer transition-all duration-150 ${
                  isSelected
                    ? "border-[#D9A441] bg-[#131923] shadow-[0_0_12px_rgba(217,164,65,0.15)]"
                    : "border-white/[0.04] hover:border-white/15"
                }`}
              >
                <div className="flex items-center justify-between text-[13px] mb-1.5">
                  <span
                    className={`font-medium transition-colors ${
                      isSelected ? "text-[#D9A441]" : "text-[#F2F4F7] group-hover:text-white"
                    }`}
                  >
                    {item.city}
                  </span>
                  <span className="font-mono text-[#A7B0BE] text-[12px] font-medium">
                    {item.current} / {item.target}
                  </span>
                </div>
                {/* Thin progress bar */}
                <div className="w-full h-1 bg-white/[0.06] rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ${getProgressBarClass(
                      item.colorType
                    )}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </aside>
  );
}
