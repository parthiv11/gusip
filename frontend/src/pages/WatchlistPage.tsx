import React, { useMemo, useState } from "react";
import {
  Lock,
  Search,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  MoreVertical,
} from "lucide-react";

export type WatchlistCategory =
  | "missing_person"
  | "wanted_person"
  | "stolen_vehicle"
  | "blacklisted_vehicle";

export type WatchlistPriority = "critical" | "high" | "medium";

export interface WatchlistEntry {
  id: number;
  category: WatchlistCategory;
  name: string;
  plate: string | null;
  priority: WatchlistPriority;
  notes: string;
}

const DEFAULT_WATCHLIST_DATA: WatchlistEntry[] = [
  {
    id: 1,
    category: "missing_person",
    name: "Anjali P.",
    plate: null,
    priority: "high",
    notes: "Missing from Vadodara Alkapuri. Age 16. Non-criminal locating only.",
  },
  {
    id: 2,
    category: "wanted_person",
    name: "Rakesh M.",
    plate: null,
    priority: "critical",
    notes: "Wanted in NDPS case. Frequent SG Highway / Sarkhej.",
  },
  {
    id: 3,
    category: "stolen_vehicle",
    name: "White Toyota Fortuner",
    plate: "GJ 01 ST 0001",
    priority: "critical",
    notes: "Stolen from Satellite, Ahmedabad. Last FIR 112/2026.",
  },
  {
    id: 4,
    category: "blacklisted_vehicle",
    name: "Black Honda City",
    plate: "GJ 05 BL 9999",
    priority: "high",
    notes: "Linked to hit-and-run, Surat Varchha.",
  },
  {
    id: 5,
    category: "missing_person",
    name: "Karan S.",
    plate: null,
    priority: "high",
    notes: "Missing since 17/05/2025 from Rajkot. Family reported.",
  },
  {
    id: 6,
    category: "wanted_person",
    name: "Imran K.",
    plate: null,
    priority: "critical",
    notes: "Wanted in theft & arms act. Associates in Mehsana.",
  },
  {
    id: 7,
    category: "stolen_vehicle",
    name: "Maruti Suzuki Swift",
    plate: "GJ 27 AA 1234",
    priority: "high",
    notes: "Stolen on 14/04/2025, Nadiad. Case CR 89/2025.",
  },
  {
    id: 8,
    category: "blacklisted_vehicle",
    name: "Mahindra Bolero",
    plate: "GJ 17 BB 4321",
    priority: "medium",
    notes: "Multiple e-challan violations. Owner verification required.",
  },
  {
    id: 9,
    category: "missing_person",
    name: "Disha V.",
    plate: null,
    priority: "high",
    notes: "Missing from Bhavnagar. Last seen 12/05/2025.",
  },
  {
    id: 10,
    category: "wanted_person",
    name: "Suresh T.",
    plate: null,
    priority: "critical",
    notes: "Wanted in cheating case. Active in Ahmedabad city.",
  },
  {
    id: 11,
    category: "stolen_vehicle",
    name: "Hyundai Creta (Silver)",
    plate: "GJ 06 CD 5678",
    priority: "critical",
    notes: "Stolen from Vadodara Sayajigunj. Tracked toward Godhra.",
  },
  {
    id: 12,
    category: "wanted_person",
    name: "Vikram J.",
    plate: null,
    priority: "high",
    notes: "Wanted in extortion and land grab racket, Gandhinagar.",
  },
  {
    id: 13,
    category: "blacklisted_vehicle",
    name: "Tata Nexon (Red)",
    plate: "GJ 03 KL 8821",
    priority: "medium",
    notes: "Suspicious transport near interstate border checkpoint.",
  },
  {
    id: 14,
    category: "missing_person",
    name: "Harshil D.",
    plate: null,
    priority: "high",
    notes: "Missing from Anand campus. Student ID: AD-9912.",
  },
  {
    id: 15,
    category: "stolen_vehicle",
    name: "Kia Seltos (White)",
    plate: "GJ 01 EZ 9021",
    priority: "critical",
    notes: "Stolen from Vastrapur, Ahmedabad. FIR 204/2026.",
  },
  {
    id: 16,
    category: "wanted_person",
    name: "Farhan A.",
    plate: null,
    priority: "critical",
    notes: "Proclaimed offender in interstate smuggling syndicate.",
  },
  {
    id: 17,
    category: "blacklisted_vehicle",
    name: "Toyota Innova (Silver)",
    plate: "GJ 02 XY 4455",
    priority: "high",
    notes: "Involved in convoy evasion on Mehsana-Ahmedabad Toll.",
  },
  {
    id: 18,
    category: "missing_person",
    name: "Pooja N.",
    plate: null,
    priority: "medium",
    notes: "Missing from Jamnagar. Report registered by local police.",
  },
  {
    id: 19,
    category: "wanted_person",
    name: "Mahesh B.",
    plate: null,
    priority: "high",
    notes: "Bail jump in illegal liquor transport case, Bharuch.",
  },
  {
    id: 20,
    category: "stolen_vehicle",
    name: "Royal Enfield Classic 350",
    plate: "GJ 05 QW 1122",
    priority: "high",
    notes: "Stolen from Katargam, Surat. Last spotted on Ring Road.",
  },
  {
    id: 21,
    category: "blacklisted_vehicle",
    name: "Mahindra Scorpio (Black)",
    plate: "GJ 18 CR 7700",
    priority: "critical",
    notes: "Flashing unauthorized red beacon. Gandhinagar alert.",
  },
  {
    id: 22,
    category: "missing_person",
    name: "Devang R.",
    plate: null,
    priority: "high",
    notes: "Elderly missing person. Dementia patient, Navrangpura.",
  },
  {
    id: 23,
    category: "wanted_person",
    name: "Jayesh K.",
    plate: null,
    priority: "critical",
    notes: "Wanted in counterfeit currency racket, Morbi district.",
  },
  {
    id: 24,
    category: "stolen_vehicle",
    name: "Honda Activa 6G (Grey)",
    plate: "GJ 01 MP 3344",
    priority: "medium",
    notes: "Stolen from Paldi bus terminal parking area.",
  },
  {
    id: 25,
    category: "blacklisted_vehicle",
    name: "Eicher Pro Truck",
    plate: "GJ 12 ZT 8901",
    priority: "high",
    notes: "Overloaded freight evading weighbridge checkposts, Kutch.",
  },
  {
    id: 26,
    category: "wanted_person",
    name: "Sunil P.",
    plate: null,
    priority: "high",
    notes: "Wanted in industrial theft case, Sanand GIDC.",
  },
  {
    id: 27,
    category: "missing_person",
    name: "Sneha M.",
    plate: null,
    priority: "high",
    notes: "Missing from Junagadh since 20/05/2025. Search ongoing.",
  },
  {
    id: 28,
    category: "stolen_vehicle",
    name: "Maruti Dzire (White)",
    plate: "GJ 09 GH 6677",
    priority: "critical",
    notes: "Used as getaway vehicle in Himatnagar robbery case.",
  },
  {
    id: 29,
    category: "blacklisted_vehicle",
    name: "Hyundai i20 (Blue)",
    plate: "GJ 06 TR 5544",
    priority: "medium",
    notes: "Fake registration plate alert issued by Vadodara RTO.",
  },
  {
    id: 30,
    category: "wanted_person",
    name: "Dharmesh G.",
    plate: null,
    priority: "critical",
    notes: "Active warrant under PASA act. Porbandar jurisdiction.",
  },
  {
    id: 31,
    category: "missing_person",
    name: "Amit K.",
    plate: null,
    priority: "medium",
    notes: "Missing trekker in Girnar foothills. Forest dept alerted.",
  },
  {
    id: 32,
    category: "stolen_vehicle",
    name: "Tata Safari (Dark)",
    plate: "GJ 01 RK 1010",
    priority: "critical",
    notes: "Stolen from Bopal, Ahmedabad. High speed toll cross recorded.",
  },
  {
    id: 33,
    category: "wanted_person",
    name: "Naresh S.",
    plate: null,
    priority: "high",
    notes: "Financial fraud suspect. Travel ban lookout notice active.",
  },
  {
    id: 34,
    category: "blacklisted_vehicle",
    name: "Ashok Leyland Tanker",
    plate: "GJ 16 UV 3322",
    priority: "critical",
    notes: "Suspected chemical dumping violation, Dahej industrial zone.",
  },
  {
    id: 35,
    category: "missing_person",
    name: "Nisha B.",
    plate: null,
    priority: "high",
    notes: "Missing from Godhra station platform 2. Search broadcast active.",
  },
  {
    id: 36,
    category: "stolen_vehicle",
    name: "Hero Splendor Plus",
    plate: "GJ 23 LK 7788",
    priority: "medium",
    notes: "Stolen from Anand milk cooperative premises.",
  },
  {
    id: 37,
    category: "wanted_person",
    name: "Pradeep N.",
    plate: null,
    priority: "critical",
    notes: "Wanted in cybercrime phishing syndicate, Surat Cyber Cell.",
  },
  {
    id: 38,
    category: "blacklisted_vehicle",
    name: "Volkswagen Polo (White)",
    plate: "GJ 05 MN 1200",
    priority: "high",
    notes: "Reckless driving and toll barrier breach at Kamrej Plaza.",
  },
];

export default function WatchlistPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [selectedPriority, setSelectedPriority] = useState<string>("all");
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(10);

  // Filtered dataset
  const filteredData = useMemo(() => {
    return DEFAULT_WATCHLIST_DATA.filter((item) => {
      // Category filter
      if (selectedCategory !== "all" && item.category !== selectedCategory) {
        return false;
      }
      // Priority filter
      if (selectedPriority !== "all" && item.priority !== selectedPriority) {
        return false;
      }
      // Search filter (name, plate, notes)
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchesName = item.name.toLowerCase().includes(q);
        const matchesPlate = item.plate
          ? item.plate.toLowerCase().includes(q)
          : false;
        const matchesNotes = item.notes.toLowerCase().includes(q);
        if (!matchesName && !matchesPlate && !matchesNotes) {
          return false;
        }
      }
      return true;
    });
  }, [searchQuery, selectedCategory, selectedPriority]);

  const totalEntries = filteredData.length;
  const totalPages = Math.max(1, Math.ceil(totalEntries / pageSize));

  // Reset page when filters change
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
    setCurrentPage(1);
  };

  const handleCategoryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedCategory(e.target.value);
    setCurrentPage(1);
  };

  const handlePriorityChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedPriority(e.target.value);
    setCurrentPage(1);
  };

  const handlePageChange = (page: number) => {
    if (page >= 1 && page <= totalPages) {
      setCurrentPage(page);
    }
  };

  const startIndex = (currentPage - 1) * pageSize;
  const currentRows = filteredData.slice(startIndex, startIndex + pageSize);
  const startCount = totalEntries === 0 ? 0 : startIndex + 1;
  const endCount = Math.min(startIndex + pageSize, totalEntries);

  return (
    <div className="h-full flex flex-col bg-[#0B0D10] text-[#E6E8EB] overflow-y-auto">
      <div className="flex-1 px-8 md:px-10 py-6 max-w-[1920px] mx-auto w-full flex flex-col">
        {/* Watchlist Header Area */}
        <div className="shrink-0 mb-6">
          {/* Top Row: Heading + Read-Only Badge (Left), Filters (Right) */}
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            {/* Left: Heading & Read-only State Pill */}
            <div className="flex items-center gap-3.5 flex-wrap">
              <h1 className="text-[26px] font-bold text-white tracking-tight leading-none">
                Watchlist
              </h1>

              {/* View-Only Bordered Pill */}
              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[4px] bg-[#14120C] border border-[#D9A441]/40 text-[#D9A441] text-[12px] font-medium select-none shadow-sm">
                <Lock size={12} className="text-[#D9A441] shrink-0" />
                <span className="leading-tight">
                  View only — operators cannot mutate the watchlist
                </span>
              </div>
            </div>

            {/* Right: Search Input & Category/Priority Dropdowns */}
            <div className="flex items-center gap-3 flex-wrap">
              {/* Search input */}
              <div className="relative flex items-center">
                <Search
                  size={14}
                  className="absolute left-3.5 text-[#687384] pointer-events-none"
                />
                <input
                  type="text"
                  placeholder="Filter name, plate, notes"
                  value={searchQuery}
                  onChange={handleSearchChange}
                  className="bg-[#0E1217] text-[#E6E8EB] placeholder-[#687384] text-[13px] pl-9 pr-3.5 py-2 rounded-[4px] border border-white/[0.09] hover:border-white/[0.18] focus:border-[#D9A441]/70 focus:outline-none w-[220px] sm:w-[260px] h-[38px] transition-all"
                />
              </div>

              {/* Category dropdown */}
              <div className="relative">
                <select
                  value={selectedCategory}
                  onChange={handleCategoryChange}
                  aria-label="Filter by category"
                  className="appearance-none bg-[#0E1217] text-[#E6E8EB] text-[13px] pl-3.5 pr-8 py-2 rounded-[4px] border border-white/[0.09] hover:border-white/[0.18] focus:border-[#D9A441]/70 focus:outline-none cursor-pointer h-[38px] transition-all"
                >
                  <option value="all" className="bg-[#0E1217] text-[#E6E8EB]">
                    All categories
                  </option>
                  <option
                    value="missing_person"
                    className="bg-[#0E1217] text-[#E6E8EB]"
                  >
                    Missing person
                  </option>
                  <option
                    value="wanted_person"
                    className="bg-[#0E1217] text-[#E6E8EB]"
                  >
                    Wanted person
                  </option>
                  <option
                    value="stolen_vehicle"
                    className="bg-[#0E1217] text-[#E6E8EB]"
                  >
                    Stolen vehicle
                  </option>
                  <option
                    value="blacklisted_vehicle"
                    className="bg-[#0E1217] text-[#E6E8EB]"
                  >
                    Blacklisted vehicle
                  </option>
                </select>
                <ChevronDown
                  size={14}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#687384] pointer-events-none"
                />
              </div>

              {/* Priority dropdown */}
              <div className="relative">
                <select
                  value={selectedPriority}
                  onChange={handlePriorityChange}
                  aria-label="Filter by priority"
                  className="appearance-none bg-[#0E1217] text-[#E6E8EB] text-[13px] pl-3.5 pr-8 py-2 rounded-[4px] border border-white/[0.09] hover:border-white/[0.18] focus:border-[#D9A441]/70 focus:outline-none cursor-pointer h-[38px] transition-all"
                >
                  <option value="all" className="bg-[#0E1217] text-[#E6E8EB]">
                    All priorities
                  </option>
                  <option
                    value="critical"
                    className="bg-[#0E1217] text-[#E6E8EB]"
                  >
                    Critical
                  </option>
                  <option value="high" className="bg-[#0E1217] text-[#E6E8EB]">
                    High
                  </option>
                  <option
                    value="medium"
                    className="bg-[#0E1217] text-[#E6E8EB]"
                  >
                    Medium
                  </option>
                </select>
                <ChevronDown
                  size={14}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#687384] pointer-events-none"
                />
              </div>
            </div>
          </div>

          {/* Active entry count text */}
          <div className="text-[13px] text-[#8E9AA8] font-normal mt-2 select-none">
            {totalEntries === 38
              ? "38 active entries"
              : `${totalEntries} active entries`}
          </div>
        </div>

        {/* Watchlist Data Table Container */}
        <div className="flex-1 min-h-0 overflow-x-auto select-text">
          <table className="w-full text-left border-collapse min-w-[900px]">
            {/* Table Header */}
            <thead>
              <tr className="border-b border-white/[0.08] text-[11.5px] font-semibold text-[#687384] tracking-[0.06em] uppercase select-none">
                <th className="py-3 px-3 w-[15%]">CATEGORY</th>
                <th className="py-3 px-3 w-[19%]">NAME</th>
                <th className="py-3 px-3 w-[18%]">PLATE</th>
                <th className="py-3 px-3 w-[10%]">PRIORITY</th>
                <th className="py-3 px-3 w-[34%]">NOTES</th>
                <th className="py-3 px-2 w-[4%] text-right"></th>
              </tr>
            </thead>

            {/* Table Body */}
            <tbody>
              {currentRows.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="py-12 text-center text-[#687384] text-[13.5px]"
                  >
                    No matching watchlist entries found.
                  </td>
                </tr>
              ) : (
                currentRows.map((entry) => (
                  <tr
                    key={entry.id}
                    className="border-b border-white/[0.05] hover:bg-[#12161E] transition-colors duration-100 group"
                  >
                    {/* Category Column */}
                    <td className="py-3.5 px-3 align-middle">
                      <CategoryBadge category={entry.category} />
                    </td>

                    {/* Name Column */}
                    <td className="py-3.5 px-3 align-middle text-[13.5px] font-medium text-[#E6E8EB]">
                      {entry.name}
                    </td>

                    {/* Plate Column */}
                    <td className="py-3.5 px-3 align-middle font-mono text-[13.5px] tracking-wider text-[#E6E8EB]">
                      {entry.plate ? (
                        entry.plate
                      ) : (
                        <span className="text-[#687384] font-sans font-normal">
                          —
                        </span>
                      )}
                    </td>

                    {/* Priority Column */}
                    <td className="py-3.5 px-3 align-middle">
                      <PriorityBadge priority={entry.priority} />
                    </td>

                    {/* Notes Column */}
                    <td className="py-3.5 px-3 align-middle text-[13px] text-[#8E9AA8] max-w-[500px]">
                      <span className="truncate block" title={entry.notes}>
                        {entry.notes}
                      </span>
                    </td>

                    {/* Action Icon Column (3 dots) */}
                    <td className="py-3.5 px-2 align-middle text-right">
                      <button
                        type="button"
                        aria-label="More options"
                        className="text-[#4A5565] group-hover:text-[#8E9AA8] hover:text-[#E6E8EB] p-1 rounded transition-colors inline-flex items-center justify-center focus:outline-none"
                      >
                        <MoreVertical size={14} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination & Footer Controls */}
        <div className="shrink-0 pt-4 pb-2 flex flex-col sm:flex-row items-center justify-between gap-3 text-[12.5px] text-[#8E9AA8] select-none border-t border-white/[0.04] mt-2">
          {/* Left: Showing entries counter */}
          <div>
            Showing {startCount}-{endCount} of {totalEntries}
          </div>

          {/* Right: Page Navigation & Page Size */}
          <div className="flex items-center gap-1.5">
            {/* Previous Page Button */}
            <button
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage <= 1}
              aria-label="Previous Page"
              className="w-7 h-7 flex items-center justify-center rounded-[3px] border border-white/[0.09] bg-[#0E1217] text-[#8E9AA8] hover:text-white hover:border-white/20 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >
              <ChevronLeft size={14} />
            </button>

            {/* Page Numbers */}
            <div className="flex items-center gap-1">
              <button
                onClick={() => handlePageChange(1)}
                className={`min-w-[28px] h-7 px-2 flex items-center justify-center rounded-[3px] text-[12px] font-medium transition-all ${
                  currentPage === 1
                    ? "border border-[#D9A441] bg-[#10141D] text-[#D9A441]"
                    : "text-[#8E9AA8] hover:text-white hover:bg-white/[0.04]"
                }`}
              >
                1
              </button>

              {totalPages > 1 && (
                <button
                  onClick={() => handlePageChange(2)}
                  className={`min-w-[28px] h-7 px-2 flex items-center justify-center rounded-[3px] text-[12px] font-medium transition-all ${
                    currentPage === 2
                      ? "border border-[#D9A441] bg-[#10141D] text-[#D9A441]"
                      : "text-[#8E9AA8] hover:text-white hover:bg-white/[0.04]"
                  }`}
                >
                  2
                </button>
              )}

              {totalPages > 2 && (
                <button
                  onClick={() => handlePageChange(3)}
                  className={`min-w-[28px] h-7 px-2 flex items-center justify-center rounded-[3px] text-[12px] font-medium transition-all ${
                    currentPage === 3
                      ? "border border-[#D9A441] bg-[#10141D] text-[#D9A441]"
                      : "text-[#8E9AA8] hover:text-white hover:bg-white/[0.04]"
                  }`}
                >
                  3
                </button>
              )}

              {totalPages > 3 && (
                <button
                  onClick={() => handlePageChange(4)}
                  className={`min-w-[28px] h-7 px-2 flex items-center justify-center rounded-[3px] text-[12px] font-medium transition-all ${
                    currentPage === 4
                      ? "border border-[#D9A441] bg-[#10141D] text-[#D9A441]"
                      : "text-[#8E9AA8] hover:text-white hover:bg-white/[0.04]"
                  }`}
                >
                  4
                </button>
              )}

              {totalPages > 5 && (
                <span className="px-1 text-[#687384] text-[11px]">···</span>
              )}

              {totalPages > 4 && (
                <button
                  onClick={() => handlePageChange(totalPages)}
                  className={`min-w-[28px] h-7 px-2 flex items-center justify-center rounded-[3px] text-[12px] font-medium transition-all ${
                    currentPage === totalPages
                      ? "border border-[#D9A441] bg-[#10141D] text-[#D9A441]"
                      : "text-[#8E9AA8] hover:text-white hover:bg-white/[0.04]"
                  }`}
                >
                  {totalPages}
                </button>
              )}
            </div>

            {/* Next Page Button */}
            <button
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage >= totalPages}
              aria-label="Next Page"
              className="w-7 h-7 flex items-center justify-center rounded-[3px] border border-white/[0.09] bg-[#0E1217] text-[#8E9AA8] hover:text-white hover:border-white/20 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >
              <ChevronRight size={14} />
            </button>

            {/* Page Size Selector */}
            <div className="relative ml-2">
              <select
                value={pageSize}
                onChange={(e) => {
                  setPageSize(Number(e.target.value));
                  setCurrentPage(1);
                }}
                aria-label="Rows per page"
                className="appearance-none bg-[#0E1217] text-[#8E9AA8] text-[12px] pl-2.5 pr-6 py-1 rounded-[3px] border border-white/[0.09] hover:border-white/20 focus:border-[#D9A441]/70 focus:outline-none cursor-pointer h-7 transition-all"
              >
                <option value={10} className="bg-[#0E1217] text-[#E6E8EB]">
                  10 / page
                </option>
                <option value={20} className="bg-[#0E1217] text-[#E6E8EB]">
                  20 / page
                </option>
                <option value={50} className="bg-[#0E1217] text-[#E6E8EB]">
                  50 / page
                </option>
              </select>
              <ChevronDown
                size={12}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[#687384] pointer-events-none"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Category Badge Component
 */
function CategoryBadge({ category }: { category: WatchlistCategory }) {
  switch (category) {
    case "missing_person":
      return (
        <span className="inline-flex items-center justify-center px-2.5 py-0.5 rounded-[4px] border border-[#1FA6B2]/45 bg-[#1FA6B2]/10 text-[#1FA6B2] text-[12px] font-medium lowercase tracking-normal select-none">
          missing person
        </span>
      );
    case "wanted_person":
      return (
        <span className="inline-flex items-center justify-center px-2.5 py-0.5 rounded-[4px] border border-[#D9A441]/45 bg-[#D9A441]/10 text-[#D9A441] text-[12px] font-medium lowercase tracking-normal select-none">
          wanted person
        </span>
      );
    case "stolen_vehicle":
      return (
        <span className="inline-flex items-center justify-center px-2.5 py-0.5 rounded-[4px] border border-[#D84A4A]/45 bg-[#D84A4A]/10 text-[#D84A4A] text-[12px] font-medium lowercase tracking-normal select-none">
          stolen vehicle
        </span>
      );
    case "blacklisted_vehicle":
      return (
        <span className="inline-flex items-center justify-center px-2.5 py-0.5 rounded-[4px] border border-[#D9A441]/45 bg-[#D9A441]/10 text-[#D9A441] text-[12px] font-medium lowercase tracking-normal select-none">
          blacklisted vehicle
        </span>
      );
    default:
      return null;
  }
}

/**
 * Priority Badge Component
 */
function PriorityBadge({ priority }: { priority: WatchlistPriority }) {
  switch (priority) {
    case "critical":
      return (
        <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-[4px] border border-[#D84A4A]/60 bg-[#D84A4A]/10 text-[#D84A4A] text-[11.5px] font-semibold lowercase min-w-[62px] text-center select-none">
          critical
        </span>
      );
    case "high":
      return (
        <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-[4px] border border-[#D98A2B]/60 bg-[#D98A2B]/10 text-[#D98A2B] text-[11.5px] font-semibold lowercase min-w-[62px] text-center select-none">
          high
        </span>
      );
    case "medium":
      return (
        <span className="inline-flex items-center justify-center px-2 py-0.5 rounded-[4px] border border-white/20 bg-white/[0.04] text-[#8E9AA8] text-[11.5px] font-semibold lowercase min-w-[62px] text-center select-none">
          medium
        </span>
      );
    default:
      return null;
  }
}
