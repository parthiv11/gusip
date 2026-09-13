import React from "react";
import { Check, ImageOff } from "lucide-react";

export type AlertSeverity = "stolen" | "wanted" | "blacklisted" | "activity";

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
  evidenceImage: string | null;
  acknowledged: boolean;
}

interface AlertCardProps {
  alert: OperationalAlert;
  onAcknowledge: (id: number) => void;
  onClick?: () => void;
}

const NoEvidencePlaceholder: React.FC = () => (
  <div className="w-full h-full flex flex-col items-center justify-center gap-1 text-[#5A6472]" aria-label="No evidence image captured">
    <ImageOff size={20} />
    <span className="text-[9px] uppercase tracking-wide text-center px-1">No image</span>
  </div>
);

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
      case "activity":
        return {
          badgeBorder: "border-[#5B8DEF]/60",
          badgeBg: "bg-[#5B8DEF]/10",
          badgeText: "text-[#8BB4FF]",
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
    <article className="p-3 rounded-[4px] bg-[#11151C] border border-white/10 flex gap-3 transition-colors">
      {onClick ? (
        <button type="button" onClick={onClick} className="w-[108px] h-[108px] shrink-0 rounded-[3px] border border-white/10 overflow-hidden bg-black/40 p-0" aria-label={`Open ${alert.title}`}>
          {alert.evidenceImage ? (
            <img src={alert.evidenceImage} alt="" className="w-full h-full object-cover" />
          ) : (
            <NoEvidencePlaceholder />
          )}
        </button>
      ) : (
        <div className="w-[108px] h-[108px] shrink-0 rounded-[3px] border border-white/10 overflow-hidden bg-black/40">
          {alert.evidenceImage ? (
            <img src={alert.evidenceImage} alt={alert.title} className="w-full h-full object-cover" />
          ) : (
            <NoEvidencePlaceholder />
          )}
        </div>
      )}

      <div className="flex-1 min-w-0 flex flex-col justify-between">
        <div>
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

          {onClick ? (
            <button type="button" onClick={onClick} className="text-left w-full">
              <h3 className="text-[13.5px] font-bold text-[#F2F4F7] leading-snug mt-1.5 truncate">{alert.title}</h3>
            </button>
          ) : (
            <h3 className="text-[13.5px] font-bold text-[#F2F4F7] leading-snug mt-1.5 truncate">{alert.title}</h3>
          )}

          <div className="font-mono text-[11px] text-[#9AA4B2] mt-1 leading-snug truncate">
            {alert.cameraCode} · {alert.confidence} · Track: {alert.trackId} · Hits: {alert.hits}
          </div>
        </div>

        <div className="flex justify-end mt-2">
          <button
            type="button"
            onClick={() => onAcknowledge(alert.id)}
            disabled={alert.acknowledged}
            aria-label={alert.acknowledged ? "Already acknowledged" : `Acknowledge ${alert.title}`}
            className={`px-3 py-1 rounded-[3px] text-[11.5px] font-medium flex items-center gap-1.5 transition-all ${
              alert.acknowledged
                ? "bg-[#151A22] border border-white/10 text-[#667085] cursor-default"
                : "bg-[#151A22] border border-[#D9A441] text-[#D9A441] hover:bg-[#D9A441]/10 active:scale-95 shadow-sm"
            }`}
          >
            <Check size={13} className={alert.acknowledged ? "text-[#667085]" : "text-[#D9A441]"} aria-hidden />
            <span>{alert.acknowledged ? "Acknowledged" : "Acknowledge"}</span>
          </button>
        </div>
      </div>
    </article>
  );
};
