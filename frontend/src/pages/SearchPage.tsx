import { FormEvent, useState } from "react";
import { ChevronDown, Info, Shield } from "lucide-react";
import InvestigationMap, {
  INVESTIGATION_ROUTE_POINTS,
  InvestigationPoint,
} from "../components/InvestigationMap";

const PURPOSES = [
  { value: "stolen_vehicle", label: "Stolen Vehicle" },
  { value: "blacklisted_vehicle", label: "Blacklisted Vehicle" },
  { value: "wanted_person", label: "Wanted Person" },
  { value: "missing_person", label: "Missing Person" },
  { value: "traffic_incident", label: "Traffic Incident" },
  { value: "law_and_order", label: "Law and Order" },
  { value: "evaluation", label: "Evaluation / Demo" },
];

export default function SearchPage() {
  const [plate, setPlate] = useState("GJ 01 ST 0001");
  const [purpose, setPurpose] = useState("stolen_vehicle");
  const [selectedEventId, setSelectedEventId] = useState<number>(5);
  const [eventsList] = useState<InvestigationPoint[]>(INVESTIGATION_ROUTE_POINTS);

  function handleSearch(e: FormEvent) {
    e.preventDefault();
    // Default to the latest event (Event 5) on search
    setSelectedEventId(5);
  }

  return (
    <div className="h-full flex flex-col lg:flex-row min-h-0 overflow-hidden bg-[#0B0D10]">
      {/* Left 36-38% Investigation Panel */}
      <div className="w-full lg:w-[38%] xl:w-[36%] shrink-0 border-b lg:border-b-0 lg:border-r border-white/[0.08] bg-[#0B0D10] flex flex-col overflow-y-auto px-5 sm:px-6 py-5 z-10">
        <h1 className="text-[20px] font-semibold text-[#F2F3F5] tracking-tight mb-3.5">
          Investigation search
        </h1>

        {/* Plate Search Input */}
        <form onSubmit={handleSearch} className="flex flex-col gap-2.5 mb-2">
          <div>
            <input
              type="text"
              aria-label="License plate number"
              className="w-full bg-[#121620] border border-[#252B33] text-[#F2F3F5] font-mono text-[16px] font-semibold tracking-wider rounded-[5px] px-4 py-2.5 outline-none focus:border-[#D9A441]/80 transition-colors shadow-inner"
              value={plate}
              onChange={(e) => setPlate(e.target.value)}
              placeholder="GJ 01 ST 0001"
              spellCheck={false}
            />
          </div>

          {/* Search Controls: Purpose Select & Search Button */}
          <div className="flex items-center gap-2.5">
            {/* Purpose Audited Dropdown */}
            <div className="relative flex-1 bg-[#121620] border border-[#252B33] rounded-[5px] flex items-center px-3 py-2 focus-within:border-[#D9A441]/80 transition-colors">
              <Shield size={14} className="text-[#D9A441] shrink-0 mr-2" />
              <select
                aria-label="Investigation purpose"
                className="w-full bg-transparent text-[#F2F3F5] text-[13px] font-medium outline-none cursor-pointer appearance-none pr-6"
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
              >
                {PURPOSES.map((p) => (
                  <option key={p.value} value={p.value} className="bg-[#121620] text-[#F2F3F5]">
                    {p.label}
                  </option>
                ))}
              </select>
              <ChevronDown
                size={14}
                className="text-[#687386] absolute right-3 pointer-events-none"
              />
            </div>

            {/* Amber Search Button */}
            <button
              type="submit"
              className="bg-[#D9A441] hover:bg-[#E2B34D] active:bg-[#C89433] text-[#0B0D10] font-semibold text-[13px] px-6 py-2 rounded-[5px] transition-colors shrink-0 shadow-sm tracking-wide"
            >
              Search
            </button>
          </div>
        </form>

        {/* Compliance / ABAC Message */}
        <div className="flex items-center gap-1.5 text-[11.5px] text-[#687587] mt-1 mb-4">
          <Info size={13} className="shrink-0 text-[#687587]" />
          <span>Purpose is mandatory and audited (ABAC).</span>
        </div>

        {/* Result Summary Card */}
        <div className="bg-[#10141C] border border-[#252B33] rounded-[5px] px-3.5 py-2.5 flex items-center justify-between mb-4 shadow-sm">
          <div className="text-[12px] text-[#8E9AA8] flex items-center gap-1.5 font-sans">
            <span className="font-mono font-semibold text-[#F2F3F5]">8 events</span>
            <span className="text-[#687587]">·</span>
            <span className="font-mono font-semibold text-[#F2F3F5]">5 hops</span>
            <span className="text-[#687587]">·</span>
            <span className="text-[#8E9AA8]">route traced in</span>
            <span className="font-mono font-semibold text-[#F2F3F5]">6.4s</span>
          </div>
          <div className="px-2 py-0.5 rounded-[3px] border border-[#D9A441]/80 bg-[#D9A441]/10 text-[#D9A441] font-mono text-[11px] font-bold tracking-tight">
            &lt; 8s
          </div>
        </div>

        {/* Section Heading: EVENT TIMELINE */}
        <div className="text-[11px] font-semibold tracking-[0.12em] text-[#687587] uppercase mb-3 select-none">
          EVENT TIMELINE
        </div>

        {/* Vertical Event Timeline */}
        <div className="relative flex flex-col gap-2.5 pb-2">
          {/* Vertical connecting line */}
          <div className="absolute left-[13px] top-[24px] bottom-[24px] w-[1px] bg-[#252B33] pointer-events-none" />

          {eventsList.map((item) => {
            const isLatest = Boolean(item.isLatest);
            const isSelected = selectedEventId === item.id;

            return (
              <div
                key={item.id}
                onClick={() => setSelectedEventId(item.id)}
                className="flex items-center gap-3 relative group select-none"
              >
                {/* Numbered circular marker */}
                <div
                  className={`w-[26px] h-[26px] rounded-full text-[12px] font-bold flex items-center justify-center font-mono shrink-0 z-10 transition-all ${
                    isLatest
                      ? "bg-[#D9A441] text-[#0B0D10] ring-4 ring-[#D9A441]/20 shadow-[0_0_12px_rgba(217,164,65,0.6)]"
                      : isSelected
                      ? "bg-[#1A202C] border-2 border-[#D9A441] text-[#D9A441]"
                      : "bg-[#121620] border border-white/20 text-[#F2F3F5]"
                  }`}
                >
                  {item.id}
                </div>

                {/* Event Card */}
                <div
                  className={`flex-1 min-w-0 rounded-[5px] p-2 flex items-center justify-between gap-3 transition-all cursor-pointer ${
                    isLatest
                      ? "bg-[#10141C] border border-[#D9A441] shadow-[0_0_15px_rgba(217,164,65,0.18)]"
                      : isSelected
                      ? "bg-[#121622] border border-[#D9A441]/60"
                      : "bg-[#10141C] border border-[#252B33] hover:border-white/20"
                  }`}
                >
                  {/* CCTV Thumbnail on Left */}
                  <div className="relative w-[124px] sm:w-[130px] h-[72px] rounded-[3px] overflow-hidden shrink-0 bg-[#080B10] border border-white/[0.08]">
                    <img
                      src={item.thumbnail}
                      alt={`${item.camCode} CCTV frame`}
                      className="w-full h-full object-cover filter brightness-[0.92] contrast-[1.08]"
                      loading="lazy"
                    />
                  </div>

                  {/* Center: Camera Code, Location, City */}
                  <div className="flex-1 min-w-0 pr-1">
                    <div
                      className={`font-mono text-[12.5px] font-bold tracking-tight truncate ${
                        isLatest ? "text-[#D9A441]" : "text-[#F2F3F5]"
                      }`}
                    >
                      {item.camCode}
                    </div>
                    <div
                      className={`text-[12px] leading-snug mt-0.5 truncate ${
                        isLatest ? "text-[#F2F3F5] font-medium" : "text-[#C4CBD4]"
                      }`}
                    >
                      {item.name}
                    </div>
                    <div
                      className={`text-[11px] leading-snug mt-0.5 truncate ${
                        isLatest ? "text-[#9AA3AF]" : "text-[#687587]"
                      }`}
                    >
                      {item.city}
                    </div>
                  </div>

                  {/* Right: Date, Timestamp, Confidence */}
                  <div className="text-right shrink-0">
                    <div
                      className={`text-[11px] font-mono leading-tight ${
                        isLatest ? "text-[#D9A441]/85" : "text-[#687587]"
                      }`}
                    >
                      {item.date}
                    </div>
                    <div
                      className={`font-mono text-[12px] leading-tight mt-1 ${
                        isLatest ? "text-[#D9A441] font-bold" : "text-[#C4CBD4] font-medium"
                      }`}
                    >
                      {item.time}
                    </div>
                    <div
                      className={`font-mono text-[13px] font-bold leading-tight mt-1.5 ${
                        isLatest ? "text-[#D9A441]" : "text-[#F2F3F5]"
                      }`}
                    >
                      {item.confidence}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer timestamp note */}
        <div className="text-[11px] text-[#687587] font-sans mt-3 pt-2 select-none">
          All times are IST (+05:30)
        </div>
      </div>

      {/* Right 62-64% Full Height GIS Map */}
      <div className="flex-1 h-[55vh] lg:h-full min-h-0 relative">
        <InvestigationMap
          selectedEventId={selectedEventId}
          onSelectEvent={(id) => setSelectedEventId(id)}
        />
      </div>
    </div>
  );
}
