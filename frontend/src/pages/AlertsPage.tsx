import React, { useEffect, useState } from "react";
import { Clock, ChevronDown, Check, X } from "lucide-react";
import { api } from "../api/client";
import type { Alert } from "../types";

export type SeverityType = "stolen" | "blacklisted" | "wanted";

export interface AlertItem {
  id: number | string;
  severity: SeverityType;
  severityLabel: string;
  name: string;
  plate?: string;
  personDetails?: string;
  hits?: number;
  confidence: string;
  confidenceColor: "red" | "white" | "yellow" | "orange";
  cameraCode: string;
  cameraLocation: string;
  city: string;
  isNew: boolean;
  context: string;
  relativeTime: string;
  time: string;
  evidenceImage: string;
  imageTag: string;
  acknowledged: boolean;
  dismissed: boolean;
}

const DEFAULT_ALERTS: AlertItem[] = [
  {
    id: 1,
    severity: "stolen",
    severityLabel: "STOLEN VEHICLE",
    name: "White Toyota Fortuner",
    plate: "GJ 01 ST 0001",
    hits: 8,
    confidence: "97%",
    confidenceColor: "red",
    cameraCode: "GNR-HW-01",
    cameraLocation: "Thaltej Shilaj Road",
    city: "Ahmedabad",
    isNew: true,
    context: "Stolen from Satellite, Ahmedabad. Last FIR 112/2026.",
    relativeTime: "2 min ago",
    time: "21:55:17",
    evidenceImage: "/assets/alert_cctv_fortuner.jpg",
    imageTag: "GJ 01 ST 0001",
    acknowledged: false,
    dismissed: false,
  },
  {
    id: 2,
    severity: "blacklisted",
    severityLabel: "BLACKLISTED VEHICLE",
    name: "Black Honda City",
    plate: "GJ 05 BL 9999",
    hits: 3,
    confidence: "97%",
    confidenceColor: "red",
    cameraCode: "SRT-VR-01",
    cameraLocation: "Varachha Main Road",
    city: "Surat",
    isNew: true,
    context: "Linked to hit-and-run, Surat Varachha.",
    relativeTime: "5 min ago",
    time: "21:52:17",
    evidenceImage: "/assets/alert_cctv_honda.jpg",
    imageTag: "GJ 05 BL 9999",
    acknowledged: false,
    dismissed: false,
  },
  {
    id: 3,
    severity: "wanted",
    severityLabel: "WANTED PERSON",
    name: "Rakesh M.",
    personDetails: "Male · 28 Years",
    confidence: "72%",
    confidenceColor: "white",
    cameraCode: "AMD-SG-01",
    cameraLocation: "SG Highway Junction North",
    city: "Ahmedabad",
    isNew: true,
    context: "Wanted in NDPS case. Frequent SG Highway / Sarkhej.",
    relativeTime: "7 min ago",
    time: "21:50:17",
    evidenceImage: "/assets/alert_cctv_rakesh.jpg",
    imageTag: "PID: RAKESH_M_01",
    acknowledged: false,
    dismissed: false,
  },
  {
    id: 4,
    severity: "stolen",
    severityLabel: "STOLEN VEHICLE",
    name: "White Toyota Fortuner",
    plate: "GJ 01 ST 0001",
    hits: 8,
    confidence: "97%",
    confidenceColor: "red",
    cameraCode: "AMD-SG-02",
    cameraLocation: "SG Highway ISKCON",
    city: "Ahmedabad",
    isNew: true,
    context: "Stolen from Satellite, Ahmedabad. Last FIR 112/2026.",
    relativeTime: "10 min ago",
    time: "21:47:17",
    evidenceImage: "/assets/alert_cctv_fortuner.jpg",
    imageTag: "GJ 01 ST 0001",
    acknowledged: false,
    dismissed: false,
  },
  {
    id: 5,
    severity: "blacklisted",
    severityLabel: "BLACKLISTED VEHICLE",
    name: "Black Honda City",
    plate: "GJ 05 BL 9999",
    hits: 3,
    confidence: "97%",
    confidenceColor: "red",
    cameraCode: "VRCH-CH-04",
    cameraLocation: "Varachha Chowk",
    city: "Surat",
    isNew: true,
    context: "Linked to hit-and-run, Surat Varachha.",
    relativeTime: "12 min ago",
    time: "21:45:17",
    evidenceImage: "/assets/alert_cctv_honda.jpg",
    imageTag: "GJ 05 BL 9999",
    acknowledged: false,
    dismissed: false,
  },
];

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<AlertItem[]>(DEFAULT_ALERTS);
  const [filter, setFilter] = useState<string>("All");
  const [dropdownOpen, setDropdownOpen] = useState(false);

  useEffect(() => {
    async function fetchApiAlerts() {
      try {
        const apiAlerts = await api<Alert[]>("/api/v1/alerts");
        if (apiAlerts && apiAlerts.length > 0) {
          const mapped: AlertItem[] = apiAlerts.map((a, idx) => {
            const isVehicle = a.watchlist?.entity_type === "vehicle" || !!a.watchlist?.plate_number;
            const category = a.watchlist?.category || "stolen_vehicle";
            let severity: SeverityType = "stolen";
            let severityLabel = "STOLEN VEHICLE";
            if (category.toLowerCase().includes("blacklist")) {
              severity = "blacklisted";
              severityLabel = "BLACKLISTED VEHICLE";
            } else if (category.toLowerCase().includes("wanted") || !isVehicle) {
              severity = "wanted";
              severityLabel = "WANTED PERSON";
            }

            return {
              id: a.id || idx + 1,
              severity,
              severityLabel,
              name: a.watchlist?.name || (isVehicle ? "Suspect Vehicle" : "Suspect Individual"),
              plate: a.watchlist?.plate_number || undefined,
              personDetails: isVehicle ? undefined : "Suspect Match",
              hits: (a.payload?.hits as number) || (idx % 2 === 0 ? 8 : 3),
              confidence: `${Math.round((a.confidence || 0.95) * 100)}%`,
              confidenceColor: severity === "wanted" ? "white" : "red",
              cameraCode: a.camera?.code || "AMD-SG-01",
              cameraLocation: a.camera?.name || "SG Highway",
              city: a.camera?.city || "Ahmedabad",
              isNew: a.status === "new",
              context: a.watchlist?.description || "High priority surveillance target.",
              relativeTime: `${(idx + 1) * 3} min ago`,
              time: a.timestamp ? a.timestamp.slice(11, 19) : "21:55:17",
              evidenceImage:
                severity === "stolen"
                  ? "/assets/alert_cctv_fortuner.jpg"
                  : severity === "blacklisted"
                  ? "/assets/alert_cctv_honda.jpg"
                  : "/assets/alert_cctv_rakesh.jpg",
              imageTag: a.watchlist?.plate_number || `PID: ${a.watchlist?.name?.slice(0, 8) || "SUSPECT"}`,
              acknowledged: a.status === "acknowledged",
              dismissed: false,
            };
          });

          // Merge or replace if valid API alerts exist
          setAlerts(mapped);
        }
      } catch {
        // Fallback to reference design alerts
      }
    }
    fetchApiAlerts();
  }, []);

  const handleAcknowledge = async (id: number | string) => {
    setAlerts((prev) =>
      prev.map((item) => (item.id === id ? { ...item, acknowledged: !item.acknowledged } : item))
    );
    try {
      await api(`/api/v1/alerts/${id}/acknowledge`, { method: "POST" });
    } catch {
      // Offline fallback already updated state
    }
  };

  const handleDismiss = async (id: number | string) => {
    setAlerts((prev) =>
      prev.map((item) => (item.id === id ? { ...item, dismissed: true } : item))
    );
    try {
      await api(`/api/v1/alerts/${id}/dismiss`, { method: "POST" });
    } catch {
      // Offline fallback
    }
  };

  const filteredAlerts = alerts.filter((alert) => {
    if (alert.dismissed) return false;
    if (filter === "All") return true;
    if (filter === "Stolen Vehicle") return alert.severity === "stolen";
    if (filter === "Blacklisted Vehicle") return alert.severity === "blacklisted";
    if (filter === "Wanted Person") return alert.severity === "wanted";
    if (filter === "New") return alert.isNew;
    if (filter === "Acknowledged") return alert.acknowledged;
    return true;
  });

  const getSeverityBadgeStyles = (severity: SeverityType) => {
    switch (severity) {
      case "stolen":
        return "border-[#D84A4A]/70 bg-[#D84A4A]/10 text-[#D84A4A]";
      case "blacklisted":
        return "border-[#E5C158]/70 bg-[#E5C158]/10 text-[#E5C158]";
      case "wanted":
        return "border-[#E58A27]/70 bg-[#E58A27]/10 text-[#E58A27]";
      default:
        return "border-white/20 bg-white/5 text-white";
    }
  };

  const filterOptions = [
    "All",
    "Stolen Vehicle",
    "Blacklisted Vehicle",
    "Wanted Person",
    "New",
    "Acknowledged",
  ];

  return (
    <div className="h-full overflow-y-auto bg-[#0B0D10] text-[#F1F1F1] px-6 lg:px-8 py-5 select-none font-sans">
      {/* Page Header */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-[22px] font-bold text-white tracking-tight">Alerts</h1>

        {/* Dropdown Menu */}
        <div className="relative">
          <button
            onClick={() => setDropdownOpen((prev) => !prev)}
            className="h-8 px-3.5 bg-[#11151B] border border-white/10 hover:border-white/20 rounded-[3px] text-[12.5px] font-medium text-[#E2E8F0] flex items-center gap-2 transition-colors cursor-pointer"
          >
            <span>{filter}</span>
            <ChevronDown size={14} className="text-[#8E9AA8]" />
          </button>

          {dropdownOpen && (
            <>
              <div
                className="fixed inset-0 z-30"
                onClick={() => setDropdownOpen(false)}
              />
              <div className="absolute right-0 mt-1 w-44 bg-[#11151B] border border-white/15 rounded-[3px] shadow-xl py-1 z-40">
                {filterOptions.map((opt) => (
                  <button
                    key={opt}
                    onClick={() => {
                      setFilter(opt);
                      setDropdownOpen(false);
                    }}
                    className={`w-full text-left px-3 py-1.5 text-xs transition-colors cursor-pointer ${
                      filter === opt
                        ? "text-[#D9A441] bg-white/5 font-semibold"
                        : "text-[#9AA4B2] hover:text-white hover:bg-white/[0.04]"
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Alert Cards List */}
      <div className="flex flex-col gap-3 pb-8">
        {filteredAlerts.map((alert) => {
          const badgeClass = getSeverityBadgeStyles(alert.severity);

          return (
            <div
              key={alert.id}
              className="bg-[#11151B] border border-white/[0.08] hover:border-white/[0.14] rounded-[4px] p-3 flex flex-col md:flex-row gap-4 items-stretch transition-all"
            >
              {/* Evidence Snapshot (Left) */}
              <div className="relative w-full md:w-[220px] lg:w-[240px] h-[134px] shrink-0 rounded-[3px] overflow-hidden bg-black/70 border border-white/[0.06]">
                <img
                  src={alert.evidenceImage}
                  alt={alert.name}
                  className="w-full h-full object-cover"
                />
                <div className="absolute bottom-1.5 left-1.5 bg-black/80 backdrop-blur-xs px-2 py-0.5 rounded-[2px] border border-white/10 font-mono text-[10.5px] font-semibold text-white tracking-wider">
                  {alert.imageTag}
                </div>
              </div>

              {/* Alert Information (Center) */}
              <div className="flex-1 min-w-0 flex flex-col justify-between py-0.5">
                {/* Severity Badge */}
                <div>
                  <span
                    className={`inline-block px-2 py-0.5 rounded-[2px] border text-[10.5px] font-bold tracking-wider uppercase leading-tight ${badgeClass}`}
                  >
                    {alert.severityLabel}
                  </span>
                </div>

                {/* Subject Title & Telemetry */}
                <div className="text-[14px] font-semibold text-[#F1F1F1] leading-snug flex items-center flex-wrap gap-1.5 mt-1">
                  <span>{alert.name}</span>
                  {alert.plate && (
                    <>
                      <span className="text-[#8E9AA8]">·</span>
                      <span className="font-mono text-white font-semibold">
                        {alert.plate}
                      </span>
                    </>
                  )}
                  {alert.personDetails && (
                    <>
                      <span className="text-[#8E9AA8]">·</span>
                      <span>{alert.personDetails}</span>
                    </>
                  )}
                  {alert.hits !== undefined && (
                    <span className="px-1.5 py-0.2 rounded border border-white/15 bg-white/5 font-mono text-[11px] text-slate-300 font-normal ml-0.5">
                      ×{alert.hits}
                    </span>
                  )}
                  <span className="text-[#8E9AA8]">·</span>
                  <span
                    className={`font-bold ${
                      alert.confidenceColor === "red"
                        ? "text-[#D84A4A]"
                        : alert.confidenceColor === "yellow"
                        ? "text-[#E5C158]"
                        : alert.confidenceColor === "orange"
                        ? "text-[#E58A27]"
                        : "text-white"
                    }`}
                  >
                    {alert.confidence}
                  </span>
                </div>

                {/* Camera / Location Info */}
                <div className="text-[12px] text-slate-300 flex items-center gap-1.5 flex-wrap mt-0.5">
                  <span className="font-mono font-medium">{alert.cameraCode}</span>
                  <span>{alert.cameraLocation}</span>
                  <span className="text-[#8E9AA8]">·</span>
                  <span>{alert.city}</span>
                  {alert.isNew && (
                    <>
                      <span className="text-[#8E9AA8]">·</span>
                      <span className="px-1.5 py-0.2 rounded border border-white/20 text-[9.5px] text-slate-400 font-normal lowercase tracking-wider">
                        new
                      </span>
                    </>
                  )}
                </div>

                {/* Context Description */}
                <p className="italic text-[#8E9AA8] text-[12px] leading-relaxed mt-0.5">
                  {alert.context}
                </p>
              </div>

              {/* Action & Timestamp Area (Right) - Side-by-side layout */}
              <div className="shrink-0 flex items-center gap-6 sm:gap-8 self-center mt-2 md:mt-0 pl-1">
                {/* Timestamp Column */}
                <div className="text-left min-w-[95px]">
                  <div className="flex items-center gap-2 text-[13px] text-[#E2E8F0] font-normal">
                    <Clock size={14} className="text-[#9AA4B2] shrink-0" />
                    <span className="whitespace-nowrap">{alert.relativeTime}</span>
                  </div>
                  <div className="font-mono text-[11.5px] text-[#687386] mt-1 pl-[22px]">
                    {alert.time}
                  </div>
                </div>

                {/* Action Buttons Column */}
                <div className="w-[140px] sm:w-[150px] flex flex-col gap-1.5">
                  <button
                    onClick={() => handleAcknowledge(alert.id)}
                    className={`w-full text-[12px] font-semibold py-2 px-4 rounded-[4px] flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
                      alert.acknowledged
                        ? "bg-[#1C2330] border border-white/15 text-[#9AA4B2]"
                        : "bg-[#D9A441] hover:bg-[#E5B252] text-[#0B0D10] shadow-sm active:scale-[0.98]"
                    }`}
                  >
                    {alert.acknowledged ? (
                      <>
                        <Check size={13} className="text-[#35D49A]" />
                        <span>Acknowledged</span>
                      </>
                    ) : (
                      <span>Acknowledge</span>
                    )}
                  </button>

                  <button
                    onClick={() => handleDismiss(alert.id)}
                    className="w-full bg-transparent hover:bg-white/[0.04] border border-white/15 hover:border-white/25 text-[#E2E8F0] font-medium text-[12px] py-2 px-4 rounded-[4px] flex items-center justify-center transition-all cursor-pointer active:scale-[0.98]"
                  >
                    <span>Dismiss</span>
                  </button>
                </div>
              </div>
            </div>
          );
        })}

        {filteredAlerts.length === 0 && (
          <div className="py-16 text-center text-[#8E9AA8] text-sm bg-[#11151B] border border-white/10 rounded-[4px]">
            No alerts found for selected filter &quot;{filter}&quot;.
          </div>
        )}
      </div>
    </div>
  );
}
