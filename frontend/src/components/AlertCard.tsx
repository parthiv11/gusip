import React from "react";
import { Check } from "lucide-react";

export type AlertSeverity = "stolen" | "wanted" | "blacklisted";

export interface OperationalAlert {
  id: number;
  severity: AlertSeverity;
  severityLabel: string;
  title: string;
  cameraCode: string;
  confidence: string;
  trackId: string;
  hits: number;
  timestamp: string;
  evidenceImage: string;
  acknowledged: boolean;
}

interface AlertCardProps {
  alert: OperationalAlert;
  onAcknowledge: (id: number) => void;
  onClick?: () => void;
}

export const AlertCard: React.FC<AlertCardProps> = ({ alert, onAcknowledge, onClick }) => {
  const getSeverityStyles = () => {
    switch (alert.severity) {
      case "stolen":
        return {
          badgeBorder: "border-[#D94848]/60",
          badgeBg: "bg-[#D94848]/10",
          badgeText: "text-[#D94848]",
        };
      case "wanted":
        return {
          badgeBorder: "border-[#E58A27]/60",
          badgeBg: "bg-[#E58A27]/10",
          badgeText: "text-[#E58A27]",
        };
      case "blacklisted":
        return {
          badgeBorder: "border-[#D8B431]/60",
          badgeBg: "bg-[#D8B431]/10",
          badgeText: "text-[#D8B431]",
        };
      default:
        return {
          badgeBorder: "border-white/20",
          badgeBg: "bg-white/5",
          badgeText: "text-[#F2F4F7]",
        };
    }
  };

  const styles = getSeverityStyles();

  return (
    <div
      onClick={onClick}
      className={`p-3 rounded-[4px] bg-[#11151C] border border-white/10 flex gap-3 transition-colors ${
        onClick ? "cursor-pointer hover:border-white/20" : ""
      }`}
    >
      {/* Evidence Snapshot Thumbnail */}
      <div className="w-[108px] h-[108px] shrink-0 rounded-[3px] border border-white/10 overflow-hidden bg-black/40">
        <img
          src={alert.evidenceImage}
          alt={alert.title}
          className="w-full h-full object-cover"
        />
      </div>

      {/* Alert Details */}
      <div className="flex-1 min-w-0 flex flex-col justify-between">
        <div>
          {/* Top Row: Severity Badge & Time */}
          <div className="flex items-center justify-between gap-2">
            <span
              className={`px-2 py-0.5 rounded-[2px] border text-[10px] font-bold tracking-wider uppercase leading-none ${styles.badgeBorder} ${styles.badgeBg} ${styles.badgeText}`}
            >
              {alert.severityLabel}
            </span>
            <span className="font-mono text-[11.5px] text-[#9AA4B2] shrink-0">
              {alert.timestamp}
            </span>
          </div>

          {/* Alert Title */}
          <h3 className="text-[13.5px] font-bold text-[#F2F4F7] leading-snug mt-1.5 truncate">
            {alert.title}
          </h3>

          {/* Telemetry Metadata */}
          <div className="font-mono text-[11px] text-[#9AA4B2] mt-1 leading-snug truncate">
            {alert.cameraCode} · {alert.confidence} · Track: {alert.trackId} · Hits: {alert.hits}
          </div>
        </div>

        {/* Bottom: Acknowledge Action Button */}
        <div className="flex justify-end mt-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onAcknowledge(alert.id);
            }}
            disabled={alert.acknowledged}
            className={`px-3 py-1 rounded-[3px] text-[11.5px] font-medium flex items-center gap-1.5 transition-all ${
              alert.acknowledged
                ? "bg-[#151A22] border border-white/10 text-[#667085] cursor-default"
                : "bg-[#151A22] border border-[#D9A441] text-[#D9A441] hover:bg-[#D9A441]/10 active:scale-95 shadow-sm"
            }`}
          >
            <Check size={13} className={alert.acknowledged ? "text-[#667085]" : "text-[#D9A441]"} />
            <span>{alert.acknowledged ? "Acknowledged" : "Acknowledge"}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
