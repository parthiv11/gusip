import { MapContainer, Marker, Popup, TileLayer, Circle, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import { useEffect } from "react";
import { snapSrc } from "../api/media";
import type { Alert, Camera, TrackPoint } from "../types";

delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: string })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

function pin(color: string) {
  return L.divIcon({
    className: "",
    html: `<div style="width:12px;height:12px;border-radius:99px;background:${color};border:2px solid #fff;box-shadow:0 0 0 3px ${color}55"></div>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6],
  });
}

function alertPin(n: number) {
  const label = n > 99 ? "99+" : String(Math.max(1, n));
  return L.divIcon({
    className: "",
    html: `<div class="gusip-alert-pin"><span>${label}</span></div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  });
}

function Fit({ cameras, alerts }: { cameras: Camera[]; alerts?: Alert[] }) {
  const map = useMap();
  useEffect(() => {
    const pts: [number, number][] = cameras.map((c) => [c.latitude, c.longitude]);
    for (const a of alerts || []) {
      const ll = alertLatLng(a, cameras);
      if (ll) pts.push(ll);
    }
    if (!pts.length) return;
    const b = L.latLngBounds(pts);
    map.fitBounds(b.pad(0.2));
  }, [cameras, alerts, map]);
  return null;
}

function hitCount(a: Alert): number {
  const n = Number(a.payload?.hit_count ?? 1);
  return Number.isFinite(n) && n > 0 ? n : 1;
}

function alertLatLng(a: Alert, cameras: Camera[]): [number, number] | null {
  const cam = a.camera || cameras.find((c) => c.id === a.camera_id);
  const lat = Number(cam?.latitude ?? a.payload?.lat ?? a.payload?.latitude);
  const lon = Number(cam?.longitude ?? a.payload?.lon ?? a.payload?.longitude);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  return [lat, lon];
}

function withOffset(lat: number, lon: number, index: number): [number, number] {
  if (index <= 0) return [lat, lon];
  const ring = 0.004;
  const angle = (index * 2.4) % (Math.PI * 2);
  return [lat + Math.cos(angle) * ring, lon + Math.sin(angle) * ring];
}

export default function GujaratMap({
  cameras,
  selectedId,
  onSelect,
  track,
  showCoverage,
  alerts,
  onAlertClick,
}: {
  cameras: Camera[];
  selectedId?: number;
  onSelect?: (c: Camera) => void;
  track?: TrackPoint[];
  showCoverage?: boolean;
  alerts?: Alert[];
  onAlertClick?: (a: Alert) => void;
}) {
  const openAlerts = (alerts || []).filter((a) => a.status === "new");
  const seen = new Map<string, number>();

  return (
    <MapContainer center={[22.8, 71.8]} zoom={7} className="h-full w-full rounded" scrollWheelZoom>
      <TileLayer
        attribution="&copy; OpenStreetMap"
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />
      <Fit cameras={cameras} alerts={openAlerts} />
      {cameras.map((c) => (
        <Marker
          key={`cam-${c.id}`}
          position={[c.latitude, c.longitude]}
          icon={pin(c.id === selectedId ? "#e8c36a" : c.status === "online" ? "#34d399" : "#f87171")}
          eventHandlers={{ click: () => onSelect?.(c) }}
        >
          <Popup>
            <div className="text-sm">
              <div className="font-semibold">{c.code}</div>
              <div>{c.name}</div>
              <div className="text-xs opacity-70">
                {c.city} · {c.source_type} · {c.status}
              </div>
            </div>
          </Popup>
        </Marker>
      ))}
      {openAlerts.map((a) => {
        const base = alertLatLng(a, cameras);
        if (!base) return null;
        const key = `${base[0].toFixed(4)},${base[1].toFixed(4)}`;
        const n = seen.get(key) || 0;
        seen.set(key, n + 1);
        const pos = withOffset(base[0], base[1], n);
        const hits = hitCount(a);
        const cam = a.camera || cameras.find((c) => c.id === a.camera_id);
        const snap = a.snapshot_url ? snapSrc(a.snapshot_url) : undefined;
        const title = (a.watchlist?.category || String(a.payload?.category || "alert")).replaceAll("_", " ");
        const who = a.watchlist?.plate_number || a.watchlist?.name || String(a.payload?.plate || a.payload?.name || "");
        return (
          <Marker
            key={`alert-${a.id}`}
            position={pos}
            icon={alertPin(hits)}
            zIndexOffset={900}
            eventHandlers={{
              click: () => {
                if (cam) onSelect?.(cam);
                onAlertClick?.(a);
              },
            }}
          >
            <Popup maxWidth={260}>
              <div className="text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold uppercase text-yellow-300">{title}</span>
                  <span className="font-mono text-yellow-300">×{hits}</span>
                </div>
                {who && <div className="font-mono mt-0.5">{who}</div>}
                <div className="text-xs opacity-70 mt-0.5">
                  {(cam?.code || String(a.payload?.camera_code || ""))} · {(cam?.city || String(a.payload?.city || ""))} ·{" "}
                  {Math.round(a.confidence * 100)}%
                </div>
                {snap ? (
                  <img src={snap} alt="alert evidence" />
                ) : (
                  <div className="text-[11px] opacity-50 mt-2">No screenshot evidence yet</div>
                )}
              </div>
            </Popup>
          </Marker>
        );
      })}
      {showCoverage &&
        cameras.map((c) => (
          <Circle
            key={`cov-${c.id}`}
            center={[c.latitude, c.longitude]}
            radius={c.coverage_radius_m}
            pathOptions={{ color: "#e8c36a", weight: 0, fillOpacity: 0.08 }}
          />
        ))}
      {track && track.length > 1 && (
        <Polyline
          positions={track.map((p) => [p.latitude, p.longitude])}
          pathOptions={{ color: "#f59e0b", weight: 3 }}
        />
      )}
    </MapContainer>
  );
}
