import React, { useState, useRef, useEffect } from "react";
import { ChevronDown, Check } from "lucide-react";

export interface FilterOption {
  value: string;
  label: string;
  count?: number;
  customLabel?: React.ReactNode;
}

interface FilterDropdownProps {
  label?: string;
  value: string;
  options: FilterOption[];
  onChange: (value: string) => void;
  customButtonContent?: React.ReactNode;
}

export const FilterDropdown: React.FC<FilterDropdownProps> = ({
  value,
  options,
  onChange,
  customButtonContent,
}) => {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const selectedOption = options.find((o) => o.value === value) || options[0];

  return (
    <div className="relative inline-block text-left" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={`h-[34px] bg-[#0D1219] hover:bg-[#101620] text-[#F2F4F7] text-[13px] px-3 rounded-[6px] border border-white/[0.09] flex items-center gap-2 transition-colors ${
          open ? "border-[#D9A441]/50 bg-[#101620]" : ""
        }`}
      >
        {customButtonContent ? (
          customButtonContent
        ) : (
          <span className="font-normal truncate">{selectedOption?.label}</span>
        )}
        <ChevronDown size={13} className="text-[#6F7D91] shrink-0 ml-0.5" />
      </button>

      {open && (
        <div className="absolute right-0 mt-1.5 min-w-[170px] bg-[#0D1219] border border-white/[0.12] rounded-[6px] shadow-2xl py-1 z-50 animate-in fade-in zoom-in-95 duration-100">
          {options.map((opt) => {
            const isSelected = opt.value === value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => {
                  onChange(opt.value);
                  setOpen(false);
                }}
                className={`w-full text-left px-3 py-1.5 text-xs flex items-center justify-between transition-colors ${
                  isSelected
                    ? "bg-[#D9A441]/10 text-[#D9A441] font-medium"
                    : "text-[#A8B2C1] hover:bg-white/[0.05] hover:text-[#F2F4F7]"
                }`}
              >
                <span>{opt.label}</span>
                {isSelected && <Check size={13} className="text-[#D9A441]" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
