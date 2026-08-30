import { FormEvent, useState, useEffect } from "react";
import {
  Camera,
  Film,
  FileText,
  MapPin,
  Folder,
  X,
  Download,
  Share2,
  Clock,
  Shield,
  Plus,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { api, can } from "../api/client";

interface CaseItem {
  id: string;
  title: string;
  identifier: string;
  category: string;
  snapshots: number;
  clips: number;
  documentType: string;
  documentCount: number;
  locations: number;
  updated: string;
  status: "open" | "closed";
  isHighlighted?: boolean;
  description?: string;
  assignedOfficer?: string;
  department?: string;
  locationNames?: string[];
}

const INITIAL_CASES: CaseItem[] = [
  {
    id: "case-1",
    title: "Stolen Fortuner — Satellite FIR 112/2026",
    identifier: "GJ 01 ST 0001",
    category: "stolen vehicle",
    snapshots: 6,
    clips: 2,
    documentType: "FIR",
    documentCount: 1,
    locations: 5,
    updated: "Updated 2h ago",
    status: "open",
    isHighlighted: true,
    description: "Toyota Fortuner White (GJ 01 ST 0001) flagged on ANPR camera feed leaving Satellite area towards SG Highway junction.",
    assignedOfficer: "Insp. V. K. Jadeja",
    department: "Ahmedabad Crime Branch — Sector 1",
    locationNames: ["Satellite Crossroads", "SG Highway Flyover", "Iskcon Junction", "Pakwan Crossroad", "Thaltej Underpass"],
  },
  {
    id: "case-2",
    title: "Armed Robbery — Maninagar 56/2026",
    identifier: "GJ 01 BR 4567",
    category: "robbery",
    snapshots: 8,
    clips: 3,
    documentType: "FIR",
    documentCount: 1,
    locations: 7,
    updated: "Updated 5h ago",
    status: "open",
    description: "Two suspects on black Pulsar motorcycle armed with firearm at jewelry outlet near Maninagar Railway Station.",
    assignedOfficer: "Sub-Insp. R. M. Patel",
    department: "Maninagar Police Station",
    locationNames: ["Maninagar Station Road", "Kankaria Lake Gate 3", "Bhairavnath Crossroad", "Ghodasar Canal Rd", "CTM Double Decker"],
  },
  {
    id: "case-3",
    title: "Missing Person — Riya Shah",
    identifier: "Riya Shah",
    category: "missing person",
    snapshots: 4,
    clips: 1,
    documentType: "Report",
    documentCount: 1,
    locations: 3,
    updated: "Updated 1d ago",
    status: "closed",
    description: "Subject located safely at maternal grandparents residence in Vadodara. Investigation concluded.",
    assignedOfficer: "W/PSI K. B. Chaudhari",
    department: "Navrangpura Division",
    locationNames: ["Navrangpura Bus Stand", "Geeta Mandir Central Bus Terminus", "Vadodara Express Highway Junction"],
  },
  {
    id: "case-4",
    title: "Chain Snatching — Bapunagar 23/2026",
    identifier: "GJ 01 ST 7890",
    category: "theft",
    snapshots: 5,
    clips: 2,
    documentType: "FIR",
    documentCount: 1,
    locations: 4,
    updated: "Updated 3h ago",
    status: "open",
    description: "Gold chain snatching incident near Shyam Shikhar complex. Suspects tracked heading towards Naroda.",
    assignedOfficer: "Insp. H. S. Solanki",
    department: "Bapunagar Police Station",
    locationNames: ["Shyam Shikhar Crossroad", "Bapunagar General Hospital", "Naroda Patiya Circle", "Memco Junction"],
  },
  {
    id: "case-5",
    title: "Hit & Run — SG Highway 98/2026",
    identifier: "GJ 01 HR 2345",
    category: "hit and run",
    snapshots: 7,
    clips: 2,
    documentType: "FIR",
    documentCount: 1,
    locations: 6,
    updated: "Updated 4h ago",
    status: "open",
    description: "Dark grey SUV involved in pedestrian collision at Gota flyover descending lane. Front bumper damage verified.",
    assignedOfficer: "Traffic Insp. A. P. Vaghela",
    department: "Traffic Division 'SG-1'",
    locationNames: ["Gota Flyover North", "Vaishnodevi Circle", "Sola Bridge Underpass", "Nirma University Junction"],
  },
  {
    id: "case-6",
    title: "Cyber Fraud — Online Trading Complaint",
    identifier: "CYB 2026 0012",
    category: "cyber crime",
    snapshots: 3,
    clips: 0,
    documentType: "FIR",
    documentCount: 1,
    locations: 2,
    updated: "Updated 2d ago",
    status: "closed",
    description: "Fraudulent WhatsApp investment scheme with mule bank accounts traced to Surat and Ahmedabad. Bank freeze initiated.",
    assignedOfficer: "Cyber Cell Insp. N. D. Trivedi",
    department: "Cyber Crime Police Station — Gandhinagar",
    locationNames: ["Gift City Cyber Hub", "Surat Ring Road ATM Cluster"],
  },
];

export default function CasesPage() {
  const [cases, setCases] = useState<CaseItem[]>(INITIAL_CASES);
  const [newCaseTitle, setNewCaseTitle] = useState("");
  const [activeCaseModal, setActiveCaseModal] = useState<CaseItem | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "evidence" | "locations">("overview");

  // Synchronize with API if available
  useEffect(() => {
    async function fetchCases() {
      try {
        const res = await api<{ id: number; title: string; description?: string; status: string }[]>("/api/v1/cases");
        if (res && Array.isArray(res) && res.length > 0) {
          // Merge or supplement API cases
        }
      } catch {
        // Fallback to initial state
      }
    }
    fetchCases();
  }, []);

  function handleCreateCase(e: FormEvent) {
    e.preventDefault();
    const trimmed = newCaseTitle.trim();
    if (!trimmed) return;

    // Parse identifier and category from title if present
    let parsedIdentifier = `FIR ${Math.floor(100 + Math.random() * 900)}/2026`;
    let parsedCategory = "investigation";

    if (trimmed.toLowerCase().includes("stolen") || trimmed.toLowerCase().includes("vehicle")) {
      parsedCategory = "stolen vehicle";
      parsedIdentifier = `GJ 01 ${String.fromCharCode(65 + Math.floor(Math.random() * 26))}${String.fromCharCode(65 + Math.floor(Math.random() * 26))} ${Math.floor(1000 + Math.random() * 9000)}`;
    } else if (trimmed.toLowerCase().includes("robbery")) {
      parsedCategory = "robbery";
    } else if (trimmed.toLowerCase().includes("missing")) {
      parsedCategory = "missing person";
      parsedIdentifier = trimmed.split("—")[1]?.trim() || "Subject";
    } else if (trimmed.toLowerCase().includes("cyber") || trimmed.toLowerCase().includes("fraud")) {
      parsedCategory = "cyber crime";
      parsedIdentifier = `CYB 2026 ${String(Math.floor(10 + Math.random() * 90)).padStart(4, "0")}`;
    }

    const newCase: CaseItem = {
      id: `case-${Date.now()}`,
      title: trimmed,
      identifier: parsedIdentifier,
      category: parsedCategory,
      snapshots: 0,
      clips: 0,
      documentType: "FIR",
      documentCount: 1,
      locations: 1,
      updated: "Updated just now",
      status: "open",
      isHighlighted: true,
      description: `New active case initiated by SOC Operator: ${trimmed}`,
      assignedOfficer: "SOC Command Unit",
      department: "Gujarat Police Unified Operations",
      locationNames: ["Command Center Junction"],
    };

    // Remove highlight from previous cases and add new case at the top or update
    setCases((prev) => [newCase, ...prev.map((c) => ({ ...c, isHighlighted: false }))]);
    setNewCaseTitle("");

    // Try posting to API in background
    api("/api/v1/cases", {
      method: "POST",
      body: JSON.stringify({ title: trimmed, description: newCase.description }),
    }).catch(() => undefined);
  }

  function handleSelectCase(id: string) {
    setCases((prev) =>
      prev.map((c) => ({
        ...c,
        isHighlighted: c.id === id,
      }))
    );
  }

  function handleOpenCaseDetail(c: CaseItem, e: React.MouseEvent) {
    e.stopPropagation();
    setActiveCaseModal(c);
    setActiveTab("overview");
  }

  function exportCaseData(c: CaseItem) {
    const data = {
      caseId: c.id,
      title: c.title,
      identifier: c.identifier,
      category: c.category,
      status: c.status,
      lastUpdated: c.updated,
      evidenceSummary: {
        snapshots: c.snapshots,
        clips: c.clips,
        documents: `${c.documentCount} ${c.documentType}`,
        locations: c.locations,
      },
      assignedOfficer: c.assignedOfficer,
      department: c.department,
      locationTimeline: c.locationNames,
      exportedAt: new Date().toISOString(),
      platform: "GUSIP - Gujarat Unified Surveillance Intelligence Platform",
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `GUSIP-Case-${c.identifier.replace(/\s+/g, "_")}.json`;
    a.click();
  }

  const activeCount = cases.filter((c) => c.status === "open").length;

  return (
    <div className="h-full overflow-y-auto bg-[#0B0D10] text-[#F2F4F7]">
      <div className="max-w-[1720px] mx-auto px-6 sm:px-10 py-7">
        {/* Page Header */}
        <div>
          <h1 className="text-[28px] sm:text-[32px] font-bold text-white tracking-tight leading-none">
            Case folders
          </h1>
          <p className="text-[13.5px] text-[#7E8B9B] mt-2 font-normal">
            {activeCount} active {activeCount === 1 ? "case" : "cases"}
          </p>
        </div>

        {/* Case Creation Bar */}
        <form onSubmit={handleCreateCase} className="mt-6 flex items-center gap-3">
          <input
            type="text"
            className="flex-1 h-[46px] bg-[#10141B] border border-white/[0.08] rounded-[4px] px-4 text-[13.5px] text-[#F2F4F7] placeholder:text-[#556070] focus:outline-none focus:border-[#D9A441]/70 transition-colors"
            placeholder="Case name — e.g. Stolen Fortuner — Satellite FIR 112/2026"
            value={newCaseTitle}
            onChange={(e) => setNewCaseTitle(e.target.value)}
          />
          <button
            type="submit"
            className="h-[46px] px-8 bg-[#D9A441] hover:bg-[#E5B252] text-[#0B0D10] font-bold text-[14px] rounded-[4px] transition-colors flex items-center justify-center shrink-0 shadow-sm"
          >
            Create
          </button>
        </form>

        {/* 3 × 2 Case Card Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 mt-7">
          {cases.map((c) => {
            const isHighlight = c.isHighlighted;
            return (
              <div
                key={c.id}
                onClick={() => handleSelectCase(c.id)}
                className={`bg-[#10141A] rounded-[4px] p-6 flex flex-col justify-between transition-all duration-150 cursor-pointer ${
                  isHighlight
                    ? "border border-[#D9A441] shadow-[0_0_15px_rgba(217,164,65,0.04)]"
                    : "border border-white/[0.07] hover:border-white/[0.18]"
                }`}
              >
                <div>
                  {/* Top Row: Folder Icon & Status Badge */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center">
                      <Folder className="w-[26px] h-[26px] text-[#D9A441] fill-[#D9A441]" />
                    </div>
                    {c.status === "open" ? (
                      <span className="px-3.5 py-0.5 rounded-full text-[11.5px] font-medium bg-[#133126] text-[#35D49A] border border-[#1F4D3C]/60 tracking-normal">
                        open
                      </span>
                    ) : (
                      <span className="px-3.5 py-0.5 rounded-full text-[11.5px] font-medium bg-[#1B212B] text-[#7E8B9B] border border-white/[0.04] tracking-normal">
                        closed
                      </span>
                    )}
                  </div>

                  {/* Case Title */}
                  <h2 className="text-[17px] font-bold text-[#F2F4F7] tracking-tight leading-snug mt-4">
                    {c.title}
                  </h2>

                  {/* Identifier & Category Chips */}
                  <div className="flex items-center gap-2 mt-3.5">
                    <span className="font-mono text-[11.5px] text-[#A0AEC0] bg-[#161C24] px-2.5 py-1 rounded-[3px] border border-white/[0.06]">
                      {c.identifier}
                    </span>
                    <span className="text-[11.5px] text-[#7E8B9B] bg-[#161C24] px-2.5 py-1 rounded-[3px] border border-white/[0.04]">
                      {c.category}
                    </span>
                  </div>

                  {/* Thin Divider */}
                  <div className="border-t border-white/[0.07] my-4" />

                  {/* Evidence Metadata Row */}
                  <div className="flex items-center justify-between text-[12px] text-[#8E9AA8]">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <Camera size={14} className="shrink-0 text-[#8E9AA8]" />
                      <span className="truncate">{c.snapshots} snapshots</span>
                    </div>
                    <div className="flex items-center gap-1.5 min-w-0">
                      <Film size={14} className="shrink-0 text-[#8E9AA8]" />
                      <span className="truncate">{c.clips} clips</span>
                    </div>
                    <div className="flex items-center gap-1.5 min-w-0">
                      <FileText size={14} className="shrink-0 text-[#8E9AA8]" />
                      <span className="truncate">
                        {c.documentCount} {c.documentType}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 min-w-0">
                      <MapPin size={14} className="shrink-0 text-[#8E9AA8]" />
                      <span className="truncate">{c.locations} locations</span>
                    </div>
                  </div>
                </div>

                {/* Bottom Row: Timestamp & Open case action */}
                <div className="flex items-center justify-between pt-4 mt-2">
                  <span className="text-[#687386] text-[12.5px]">{c.updated}</span>
                  <button
                    type="button"
                    onClick={(e) => handleOpenCaseDetail(c, e)}
                    className="text-[#D9A441] hover:text-[#ECC265] font-medium text-[13.5px] flex items-center gap-1 transition-colors group"
                  >
                    <span>Open case</span>
                    <span className="group-hover:translate-x-0.5 transition-transform">→</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Case Investigation Modal Drawer */}
      {activeCaseModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-[2px] flex items-center justify-center p-4">
          <div className="w-full max-w-3xl bg-[#0F131A] border border-white/10 rounded-[6px] shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-white/[0.08] bg-[#0B0E14] flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-[4px] bg-[#D9A441]/15 border border-[#D9A441]/30 flex items-center justify-center text-[#D9A441]">
                  <Folder className="w-4 h-4 text-[#D9A441] fill-[#D9A441]" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-[#D9A441] font-bold">
                      {activeCaseModal.identifier}
                    </span>
                    <span className="text-xs text-[#7E8B9B]">·</span>
                    <span className="text-xs uppercase tracking-wider text-[#8E9AA8]">
                      {activeCaseModal.category}
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-white mt-0.5">
                    {activeCaseModal.title}
                  </h3>
                </div>
              </div>
              <button
                onClick={() => setActiveCaseModal(null)}
                className="text-[#8E9AA8] hover:text-white p-1 rounded hover:bg-white/5 transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            {/* Modal Navigation Tabs */}
            <div className="px-6 border-b border-white/[0.08] bg-[#0E1218] flex gap-4 text-xs font-medium">
              <button
                onClick={() => setActiveTab("overview")}
                className={`py-3 border-b-2 transition-colors ${
                  activeTab === "overview"
                    ? "border-[#D9A441] text-[#D9A441]"
                    : "border-transparent text-[#8E9AA8] hover:text-white"
                }`}
              >
                Overview & Brief
              </button>
              <button
                onClick={() => setActiveTab("evidence")}
                className={`py-3 border-b-2 transition-colors flex items-center gap-1.5 ${
                  activeTab === "evidence"
                    ? "border-[#D9A441] text-[#D9A441]"
                    : "border-transparent text-[#8E9AA8] hover:text-white"
                }`}
              >
                Evidence Dossier
                <span className="px-1.5 py-0.2 bg-white/10 rounded text-[10px] text-white">
                  {activeCaseModal.snapshots + activeCaseModal.clips + activeCaseModal.documentCount}
                </span>
              </button>
              <button
                onClick={() => setActiveTab("locations")}
                className={`py-3 border-b-2 transition-colors flex items-center gap-1.5 ${
                  activeTab === "locations"
                    ? "border-[#D9A441] text-[#D9A441]"
                    : "border-transparent text-[#8E9AA8] hover:text-white"
                }`}
              >
                Surveillance Hops
                <span className="px-1.5 py-0.2 bg-white/10 rounded text-[10px] text-white">
                  {activeCaseModal.locations}
                </span>
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-5 flex-1">
              {activeTab === "overview" && (
                <>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="p-3 bg-[#141922] border border-white/[0.06] rounded">
                      <div className="text-[11px] text-[#7E8B9B] uppercase font-semibold">Status</div>
                      <div className="text-sm font-bold text-white mt-1 capitalize flex items-center gap-1.5">
                        {activeCaseModal.status === "open" ? (
                          <>
                            <span className="w-2 h-2 rounded-full bg-[#35D49A]" />
                            <span className="text-[#35D49A]">Active Open</span>
                          </>
                        ) : (
                          <>
                            <span className="w-2 h-2 rounded-full bg-[#7E8B9B]" />
                            <span className="text-[#8E9AA8]">Closed / Filed</span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="p-3 bg-[#141922] border border-white/[0.06] rounded">
                      <div className="text-[11px] text-[#7E8B9B] uppercase font-semibold">Assigned Unit</div>
                      <div className="text-xs font-semibold text-[#F2F4F7] mt-1 truncate">
                        {activeCaseModal.assignedOfficer || "SOC Team"}
                      </div>
                    </div>
                    <div className="p-3 bg-[#141922] border border-white/[0.06] rounded">
                      <div className="text-[11px] text-[#7E8B9B] uppercase font-semibold">Jurisdiction</div>
                      <div className="text-xs font-semibold text-[#F2F4F7] mt-1 truncate">
                        {activeCaseModal.department || "Ahmedabad Police"}
                      </div>
                    </div>
                    <div className="p-3 bg-[#141922] border border-white/[0.06] rounded">
                      <div className="text-[11px] text-[#7E8B9B] uppercase font-semibold">Last Activity</div>
                      <div className="text-xs font-mono text-[#D9A441] mt-1">
                        {activeCaseModal.updated}
                      </div>
                    </div>
                  </div>

                  <div className="p-4 bg-[#141922] border border-white/[0.06] rounded space-y-2">
                    <div className="text-xs font-bold text-white uppercase tracking-wide">Case Summary</div>
                    <p className="text-sm text-[#B0BCCB] leading-relaxed">
                      {activeCaseModal.description}
                    </p>
                  </div>

                  <div className="p-4 bg-[#141922] border border-white/[0.06] rounded space-y-3">
                    <div className="text-xs font-bold text-white uppercase tracking-wide">Evidence Breakdown</div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                      <div className="flex items-center gap-2 text-[#8E9AA8]">
                        <Camera size={16} className="text-[#D9A441]" />
                        <span><strong>{activeCaseModal.snapshots}</strong> ANPR Snapshots</span>
                      </div>
                      <div className="flex items-center gap-2 text-[#8E9AA8]">
                        <Film size={16} className="text-[#D9A441]" />
                        <span><strong>{activeCaseModal.clips}</strong> Video Feeds</span>
                      </div>
                      <div className="flex items-center gap-2 text-[#8E9AA8]">
                        <FileText size={16} className="text-[#D9A441]" />
                        <span><strong>{activeCaseModal.documentCount}</strong> {activeCaseModal.documentType} Doc</span>
                      </div>
                      <div className="flex items-center gap-2 text-[#8E9AA8]">
                        <MapPin size={16} className="text-[#D9A441]" />
                        <span><strong>{activeCaseModal.locations}</strong> Geo Hops</span>
                      </div>
                    </div>
                  </div>
                </>
              )}

              {activeTab === "evidence" && (
                <div className="space-y-4">
                  <div className="text-xs font-semibold text-[#8E9AA8] uppercase">Captured ANPR Snapshots & Records</div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {Array.from({ length: Math.max(activeCaseModal.snapshots, 3) }).map((_, idx) => (
                      <div key={idx} className="bg-[#141922] border border-white/[0.06] rounded p-3 text-xs space-y-2">
                        <div className="flex items-center justify-between text-[#7E8B9B]">
                          <span className="font-mono text-[#D9A441]">CAM-GJ-{idx + 101}</span>
                          <span>Frame #{idx * 42 + 10}</span>
                        </div>
                        <div className="h-24 bg-[#0B0D10] border border-white/5 rounded flex items-center justify-center text-[#556070]">
                          <Camera size={22} className="opacity-40" />
                        </div>
                        <div className="text-[11px] text-[#A0AEC0] flex justify-between">
                          <span>Confidence: 98.4%</span>
                          <span className="font-mono text-[#687386]">08:24:{idx}0</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {activeTab === "locations" && (
                <div className="space-y-3">
                  <div className="text-xs font-semibold text-[#8E9AA8] uppercase">Camera Location Corridor</div>
                  <div className="space-y-2">
                    {(activeCaseModal.locationNames || ["Primary Junction", "Highway Corridor"]).map((loc, idx) => (
                      <div key={idx} className="flex items-center gap-3 p-3 bg-[#141922] border border-white/[0.06] rounded text-xs">
                        <div className="w-6 h-6 rounded-full bg-[#D9A441]/10 text-[#D9A441] font-bold flex items-center justify-center shrink-0 border border-[#D9A441]/30">
                          {idx + 1}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-[#F2F4F7] font-semibold">{loc}</div>
                          <div className="text-[#687386] text-[11px]">Sensor Node: AHMD-GJ-0{idx + 1}</div>
                        </div>
                        <span className="text-[#35D49A] text-[11px] font-mono">CONFIRMED PASS</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer Actions */}
            <div className="px-6 py-3.5 border-t border-white/[0.08] bg-[#0B0E14] flex items-center justify-between">
              <div className="text-xs text-[#687386]">
                GUSIP Police Investigation System · Confidential
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => exportCaseData(activeCaseModal)}
                  className="px-3.5 py-1.5 bg-white/5 hover:bg-white/10 text-white rounded text-xs font-medium border border-white/10 flex items-center gap-1.5 transition-colors"
                >
                  <Download size={13} />
                  <span>Export Dossier</span>
                </button>
                <button
                  type="button"
                  onClick={() => setActiveCaseModal(null)}
                  className="px-4 py-1.5 bg-[#D9A441] hover:bg-[#E5B252] text-[#0B0D10] rounded text-xs font-bold transition-colors"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
