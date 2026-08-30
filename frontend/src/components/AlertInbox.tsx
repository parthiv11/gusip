import React from "react";
import { ExternalLink } from "lucide-react";
import { AlertCard, OperationalAlert } from "./AlertCard";

interface AlertInboxProps {
  alerts: OperationalAlert[];
  focusText: string;
  onAcknowledge: (id: number) => void;
  onSelectAlert?: (alert: OperationalAlert) => void;
}

export const AlertInbox: React.FC<AlertInboxProps> = ({
  alerts,
  focusText,
  onAcknowledge,
  onSelectAlert,
}) => {
  return (
    <div className="flex flex-col h-full select-none">
      {/* Header */}
      <div className="flex items-center justify-between mb-0.5">
        <h2 className="text-base font-bold text-[#D9A441] tracking-wide">
          Alert Inbox
        </h2>
        <a
          href="/search"
          className="text-xs text-[#D9A441] hover:text-[#E8B858] flex items-center gap-1 font-medium transition-colors"
        >
          <span>ANPR report</span>
          <ExternalLink size={12} />
        </a>
      </div>

      {/* Focus Subtitle */}
      <div className="text-xs text-[#9AA4B2] mb-2.5 truncate font-normal">
        Focus: {focusText}
      </div>

      {/* Stacked Alert Cards */}
      <div className="flex flex-col gap-2.5 overflow-y-auto pr-0.5 flex-1 min-h-0">
        {alerts.map((alert) => (
          <AlertCard
            key={alert.id}
            alert={alert}
            onAcknowledge={onAcknowledge}
            onClick={onSelectAlert ? () => onSelectAlert(alert) : undefined}
          />
        ))}
      </div>
    </div>
  );
};
