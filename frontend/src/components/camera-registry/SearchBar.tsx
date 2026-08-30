import React from "react";
import { Search, X } from "lucide-react";

interface SearchBarProps {
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
}

export const SearchBar: React.FC<SearchBarProps> = ({
  value,
  onChange,
  placeholder = "Filter code, name, city",
}) => {
  return (
    <div className="relative flex items-center">
      <Search
        size={14}
        className="absolute left-3 text-[#6F7D91] pointer-events-none"
      />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-[34px] w-[230px] lg:w-[250px] bg-[#0D1219] hover:bg-[#101620] focus:bg-[#101620] text-[#F2F4F7] placeholder-[#6F7D91] text-[13px] pl-8 pr-7 rounded-[6px] border border-white/[0.09] focus:border-[#D9A441]/50 focus:outline-none transition-colors"
      />
      {value && (
        <button
          onClick={() => onChange("")}
          className="absolute right-2.5 text-[#6F7D91] hover:text-[#F2F4F7] p-0.5"
          title="Clear search"
        >
          <X size={12} />
        </button>
      )}
    </div>
  );
};
