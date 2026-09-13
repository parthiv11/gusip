import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, can } from "../api/client";
import { snapSrc } from "../api/media";
import { AlertInbox } from "../components/AlertInbox";
import ModeTabs from "../components/ModeTabs";
import type { OperationalAlert } from "../components/AlertCard";
import type { Alert } from "../types";

function severityOf(category: string, matchKind?: string): OperationalAlert["severity"] {
  if (category.includes("stolen")) return "stolen";
  if (category.includes("wanted") || category.includes("missing")) return "wanted";
  if (
    category.includes("crowd") ||
    category.includes("stopped") ||
    category.includes("wrong") ||
    matchKind === "scene" ||
    matchKind === "appearance"
  ) {
    return "activity";
  }
  return "blacklisted";
}

function toCard(a: Alert): OperationalAlert {
  const category = a.watchlist?.category || String(a.payload?.category || "");
  const matchKind = String(a.payload?.match_kind || "");
  const hits = Number(a.payload?.hit_count || 1);
  const track = a.payload?.global_track_id || a.payload?.fingerprint || a.id;
  const color = typeof a.payload?.color === "string" ? a.payload.color : "";
  const klass = typeof a.payload?.vehicle_class === "string" ? a.payload.vehicle_class : "";
  const appearance = [color, klass].filter(Boolean).join(" ");
  const unread = a.payload?.plate_status === "unreadable" || matchKind === "appearance";
  return {
    id: a.id,
    severity: severityOf(category, matchKind),
    severityLabel: unread && matchKind === "appearance" ? "appearance" : category.replaceAll("_", " ") || "alert",
    title:
      [a.watchlist?.name, a.watchlist?.plate_number || (unread ? "plate unreadable" : ""), appearance]
        .filter(Boolean)
        .join(" · ") || "Watchlist hit",
    cameraCode: a.camera?.code || String(a.payload?.camera_code || ""),
    confidence: `${Math.round(a.confidence * 100)}%`,
    trackId: String(track),
    hits: Number.isFinite(hits) && hits > 0 ? hits : 1,
    timestamp: new Date(a.timestamp).toLocaleTimeString("en-IN", { hour12: false }),
    evidenceImage: snapSrc(a.snapshot_url) ?? null,
    acknowledged: a.status === "acknowledged",
  };
}

type AlertStatus = "" | "new" | "acknowledged";

function parseStatus(raw: string | null): AlertStatus {
  if (raw === "new" || raw === "acknowledged") return raw;
  return "";
}

export default function AlertsPage() {
  const [params, setParams] = useSearchParams();
  const status = parseStatus(params.get("status"));
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [error, setError] = useState("");
  const canAck = can("ack_alert");

  function setStatus(next: AlertStatus) {
    setParams(
      (p) => {
        const copy = new URLSearchParams(p);
        if (next) copy.set("status", next);
        else copy.delete("status");
        return copy;
      },
      { replace: true }
    );
  }

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
        <ModeTabs
          idPrefix="alert-status"
          label="Alert status"
          value={status === "new" || status === "acknowledged" ? status : "all"}
          onChange={(id) => setStatus(id === "all" ? "" : id)}
          options={[
            { id: "all" as const, label: "All" },
            { id: "new" as const, label: "New" },
            { id: "acknowledged" as const, label: "Acknowledged" },
          ]}
        />
        <nav className="sm:ml-auto flex gap-3 text-[11px]" aria-label="Related views">
          <Link className="text-slate-400 hover:text-brass-400" to="/search?mode=plate">
            Plate search
          </Link>
          <Link className="text-slate-400 hover:text-brass-400" to="/search?mode=appearance">
            Appearance
          </Link>
          <Link className="text-slate-400 hover:text-brass-400" to="/?wall=demo">
            Control room
          </Link>
        </nav>
      </div>
      {error && (
        <div className="text-red-400 text-xs mb-2 shrink-0" role="alert">
          {error}
        </div>
      )}
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
