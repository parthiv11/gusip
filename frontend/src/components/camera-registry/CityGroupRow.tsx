import React from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

interface CityGroupRowProps {
  cityName: string;
  count: number;
  isExpanded: boolean;
  onToggle: () => void;
  colSpan?: number;
}

export const CityGroupRow: React.FC<CityGroupRowProps> = ({
  cityName,
  count,
  isExpanded,
  onToggle,
  colSpan = 9,
}) => {
  return (
    <tr
      onClick={onToggle}
      className="h-[42px] bg-[#10151E] hover:bg-[#131924] border-t border-b border-white/[0.06] cursor-pointer transition-colors select-none"
    >
      <td colSpan={colSpan} className="pl-6 pr-4 py-2">
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            className="text-[#8E9AA8] hover:text-[#F2F4F7] p-0.5 rounded transition-colors inline-flex items-center justify-center"
            aria-label={isExpanded ? "Collapse city" : "Expand city"}
          >
            {isExpanded ? (
              <ChevronDown size={14} className="text-[#8E9AA8]" />
            ) : (
              <ChevronRight size={14} className="text-[#8E9AA8]" />
            )}
          </button>
          <span className="text-[12.5px] font-bold text-[#F2F4F7] tracking-wider uppercase">
            {cityName}
          </span>
          <span className="inline-flex items-center px-2 py-0.5 rounded-[4px] text-[11px] font-normal text-[#8E9AA8] bg-[#18202D] border border-white/[0.04]">
            {count} cameras
          </span>
        </div>
      </td>
    </tr>
  );
};
