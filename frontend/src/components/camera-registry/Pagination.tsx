import React, { useState, useRef, useEffect } from "react";
import { ChevronLeft, ChevronRight, ChevronDown, Check } from "lucide-react";

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
}

export const Pagination: React.FC<PaginationProps> = ({
  currentPage = 1,
  totalPages = 9,
  totalItems = 412,
  pageSize = 50,
  onPageChange,
  onPageSizeChange,
}) => {
  const [pageSizeOpen, setPageSizeOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const startItem = Math.min((currentPage - 1) * pageSize + 1, totalItems);
  const endItem = Math.min(currentPage * pageSize, totalItems);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setPageSizeOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="flex flex-col sm:flex-row items-center justify-between gap-4 py-4 select-none">
      {/* Left: Showing X-Y of Total */}
      <div className="text-[13px] text-[#A8B2C1] font-normal">
        Showing {startItem}-{endItem} of{" "}
        <span className="text-[#D9A441] font-medium">{totalItems}</span>
      </div>

      {/* Right: Controls */}
      <div className="flex items-center gap-1.5 sm:gap-2">
        {/* Prev button */}
        <button
          type="button"
          onClick={() => onPageChange(Math.max(1, currentPage - 1))}
          disabled={currentPage === 1}
          className="w-8 h-8 rounded-[4px] bg-[#10151F] border border-white/[0.08] flex items-center justify-center text-[#8E9AA8] hover:text-[#F2F4F7] hover:bg-[#151B27] disabled:opacity-40 disabled:hover:bg-[#10151F] disabled:hover:text-[#8E9AA8] transition-colors"
          aria-label="Previous page"
        >
          <ChevronLeft size={15} />
        </button>

        {/* Page buttons (1, 2, 3, 4, 5, ..., 9) */}
        {[1, 2, 3, 4, 5].map((pageNum) => {
          const isActive = currentPage === pageNum;
          return (
            <button
              key={pageNum}
              type="button"
              onClick={() => onPageChange(pageNum)}
              className={`w-8 h-8 rounded-[4px] text-xs font-medium flex items-center justify-center transition-colors ${
                isActive
                  ? "bg-[#D9A441] text-[#0B0D10] font-bold shadow-[0_0_8px_rgba(217,164,65,0.3)]"
                  : "bg-[#10151F] border border-white/[0.08] text-[#8E9AA8] hover:text-[#F2F4F7] hover:bg-[#151B27]"
              }`}
            >
              {pageNum}
            </button>
          );
        })}

        <span className="w-5 text-center text-xs text-[#6F7D91] font-medium">...</span>

        {/* Last page (e.g. 9) */}
        <button
          type="button"
          onClick={() => onPageChange(totalPages)}
          className={`w-8 h-8 rounded-[4px] text-xs font-medium flex items-center justify-center transition-colors ${
            currentPage === totalPages
              ? "bg-[#D9A441] text-[#0B0D10] font-bold shadow-[0_0_8px_rgba(217,164,65,0.3)]"
              : "bg-[#10151F] border border-white/[0.08] text-[#8E9AA8] hover:text-[#F2F4F7] hover:bg-[#151B27]"
          }`}
        >
          {totalPages}
        </button>

        {/* Next button */}
        <button
          type="button"
          onClick={() => onPageChange(Math.min(totalPages, currentPage + 1))}
          disabled={currentPage === totalPages}
          className="w-8 h-8 rounded-[4px] bg-[#10151F] border border-white/[0.08] flex items-center justify-center text-[#8E9AA8] hover:text-[#F2F4F7] hover:bg-[#151B27] disabled:opacity-40 disabled:hover:bg-[#10151F] disabled:hover:text-[#8E9AA8] transition-colors"
          aria-label="Next page"
        >
          <ChevronRight size={15} />
        </button>

        {/* Page size dropdown */}
        <div className="relative ml-2" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => setPageSizeOpen(!pageSizeOpen)}
            className="h-8 px-3 rounded-[4px] bg-[#10151F] border border-white/[0.08] flex items-center gap-2 text-xs text-[#A8B2C1] hover:text-[#F2F4F7] hover:bg-[#151B27] transition-colors"
          >
            <span>{pageSize} / page</span>
            <ChevronDown size={13} className="text-[#6F7D91]" />
          </button>

          {pageSizeOpen && (
            <div className="absolute right-0 bottom-full mb-1.5 w-28 bg-[#0D1219] border border-white/[0.12] rounded-[6px] shadow-2xl py-1 z-50 animate-in fade-in zoom-in-95 duration-100">
              {[25, 50, 100].map((size) => (
                <button
                  key={size}
                  type="button"
                  onClick={() => {
                    onPageSizeChange(size);
                    setPageSizeOpen(false);
                  }}
                  className={`w-full text-left px-3 py-1.5 text-xs flex items-center justify-between ${
                    pageSize === size
                      ? "text-[#D9A441] font-medium bg-[#D9A441]/10"
                      : "text-[#A8B2C1] hover:bg-white/[0.05] hover:text-[#F2F4F7]"
                  }`}
                >
                  <span>{size} / page</span>
                  {pageSize === size && <Check size={12} className="text-[#D9A441]" />}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
