import { useEffect, useMemo, useState } from "react";
import { api, can } from "../api/client";
import { snapSrc } from "../api/media";
import { AlertInbox } from "../components/AlertInbox";
import type { OperationalAlert } from "../components/AlertCard";
import type { Alert } from "../types";

function severityOf(category: string): OperationalAlert["severity"] {
  if (category.includes("stolen")) return "stolen";
  if (category.includes("wanted") || category.includes("missing")) return "wanted";
  return "blacklisted";
}

function toCard(a: Alert): OperationalAlert {
  const category = a.watchlist?.category || String(a.payload?.category || "");
  const hits = Number(a.payload?.hit_count || 1);
  const track = a.payload?.global_track_id || a.payload?.fingerprint || a.id;
  return {
    id: a.id,
    severity: severityOf(category),
    severityLabel: category.replaceAll("_", " ") || "alert",
    title: [a.watchlist?.name, a.watchlist?.plate_number].filter(Boolean).join(" · ") || "Watchlist hit",
    cameraCode: a.camera?.code || String(a.payload?.camera_code || ""),
    confidence: `${Math.round(a.confidence * 100)}%`,
    trackId: String(track),
    hits: Number.isFinite(hits) && hits > 0 ? hits : 1,
    timestamp: new Date(a.timestamp).toLocaleTimeString("en-IN", { hour12: false }),
    evidenceImage: snapSrc(a.snapshot_url) || "/assets/alert_fortuner.jpg",
    acknowledged: a.status === "acknowledged",
  };
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const canAck = can("ack_alert");

  async function load() {
    const q = status ? `?status=${encodeURIComponent(status)}` : "";
    setAlerts(await api<Alert[]>(`/api/v1/alerts${q}`));
  }

  useEffect(() => {
    load().catch((err) => setError(String(err)));
  }, [status]);

  async function onAcknowledge(id: number) {
    if (!canAck) return;
    setError("");
    try {
      await api(`/api/v1/alerts/${id}/ack`, { method: "POST" });
      await load();
    } catch (err) {
      setError(String(err));
    }
  }

  const cards = useMemo(() => alerts.map(toCard), [alerts]);
  const openCount = alerts.filter((a) => a.status === "new").length;

  return (
    <div className="h-full p-4 overflow-hidden flex flex-col bg-[#0B0D10]">
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 mb-4 shrink-0">
        <h1 className="text-lg font-semibold text-[#F2F4F7]">Alerts</h1>
        <select
          className="sm:ml-auto bg-[#11151C] border border-white/10 rounded px-2 py-1 text-sm w-full sm:w-auto text-[#F2F4F7]"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          <option value="">All</option>
          <option value="new">New</option>
          <option value="acknowledged">Acknowledged</option>
        </select>
      </div>
      {error && <div className="text-red-400 text-xs mb-2 shrink-0">{error}</div>}
      <div className="flex-1 min-h-0">
        <AlertInbox
          alerts={cards}
          focusText={openCount ? `${openCount} open hits across Gujarat` : "No open hits"}
          onAcknowledge={onAcknowledge}
        />
      </div>
    </div>
  );
}
