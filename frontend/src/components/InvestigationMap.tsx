import { useEffect, useMemo } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Polyline,
  useMap,
} from "react-leaflet";
import L from "leaflet";

// Coordinate definition for the 5 investigation checkpoints
export interface InvestigationPoint {
  id: number;
  camCode: string;
  name: string;
  city: string;
  lat: number;
  lng: number;
  time: string;
  date: string;
  confidence: string;
  thumbnail: string;
  isLatest?: boolean;
}

export const INVESTIGATION_ROUTE_POINTS: InvestigationPoint[] = [
  {
    id: 1,
    camCode: "CAM-AHD-PLD-001",
    name: "Paldi Cross Road",
    city: "Ahmedabad",
    lat: 23.0125,
    lng: 72.5620,
    time: "20:14:23",
    date: "27 Aug 2025",
    confidence: "94%",
    thumbnail: "/assets/cctv_paldi.jpg",
  },
  {
    id: 2,
    camCode: "CAM-SGHW-045",
    name: "SG Highway Toll Plaza",
    city: "Ahmedabad",
    lat: 23.0820,
    lng: 72.5180,
    time: "20:28:51",
    date: "27 Aug 2025",
    confidence: "92%",
    thumbnail: "/assets/cctv_sghighway_toll.jpg",
  },
  {
    id: 3,
    camCode: "CAM-KALOL-012",
    name: "Kalol Naka",
    city: "Gandhinagar",
    lat: 23.2380,
    lng: 72.4960,
    time: "20:48:07",
    date: "27 Aug 2025",
    confidence: "90%",
    thumbnail: "/assets/cctv_kalol_naka.jpg",
  },
  {
    id: 4,
    camCode: "CAM-INFOCITY-007",
    name: "Infocity Junction",
    city: "Gandhinagar",
    lat: 23.1950,
    lng: 72.6320,
    time: "21:02:13",
    date: "27 Aug 2025",
    confidence: "91%",
    thumbnail: "/assets/cctv_infocity.jpg",
  },
  {
    id: 5,
    camCode: "CAM-GANDHI-099",
    name: "Gandhinagar Sector 21",
    city: "Gandhinagar",
    lat: 23.2390,
    lng: 72.6510,
    time: "21:15:44",
    date: "27 Aug 2025",
    confidence: "95%",
    thumbnail: "/assets/cctv_gandhinagar_sec21.jpg",
    isLatest: true,
  },
];

// Reference geographic labels matching the reference screenshot
const MAP_LABELS = [
  { text: "AHMEDABAD", lat: 23.018, lng: 72.570, type: "major" as const },
  { text: "GANDHINAGAR", lat: 23.220, lng: 72.685, type: "major" as const },
  { text: "Kalol", lat: 23.218, lng: 72.496, type: "kalol" as const },
  { text: "Siddhpur", lat: 23.910, lng: 72.375, type: "subtle" as const },
  { text: "Patan", lat: 23.850, lng: 72.130, type: "subtle" as const },
  { text: "Kadi", lat: 23.300, lng: 72.330, type: "subtle" as const },
  { text: "Mehsana", lat: 23.600, lng: 72.390, type: "subtle" as const },
  { text: "Visnagar", lat: 23.700, lng: 72.550, type: "subtle" as const },
  { text: "Unjha", lat: 23.800, lng: 72.400, type: "subtle" as const },
  { text: "Viramgam", lat: 23.120, lng: 72.030, type: "subtle" as const },
  { text: "Bavla", lat: 22.840, lng: 72.360, type: "subtle" as const },
  { text: "Dholka", lat: 22.720, lng: 72.440, type: "subtle" as const },
  { text: "Trangodar", lat: 22.990, lng: 72.380, type: "subtle" as const },
  { text: "Deroja", lat: 22.580, lng: 72.520, type: "subtle" as const },
  { text: "Kheda", lat: 22.750, lng: 72.690, type: "subtle" as const },
  { text: "Nadiad", lat: 22.690, lng: 72.860, type: "subtle" as const },
  { text: "Vasod", lat: 22.600, lng: 72.780, type: "subtle" as const },
  { text: "Anand", lat: 22.550, lng: 72.950, type: "subtle" as const },
  { text: "Dahgam", lat: 23.170, lng: 72.810, type: "subtle" as const },
  { text: "Vijapur", lat: 23.560, lng: 72.750, type: "subtle" as const },
  { text: "Kbreja", lat: 23.400, lng: 72.880, type: "subtle" as const },
  { text: "Capadvanj", lat: 23.100, lng: 71.950, type: "subtle" as const },
  { text: "Uldan", lat: 23.900, lng: 71.980, type: "subtle" as const },
  { text: "Maturu", lat: 23.550, lng: 72.050, type: "subtle" as const },
  { text: "Gulf of Khambhat", lat: 22.450, lng: 72.550, type: "water" as const },
];

// Helper to create teardrop numbered pin icons
function createInvestigationPinIcon(num: number, isLatest: boolean = false, isSelected: boolean = false) {
  if (isLatest) {
    return L.divIcon({
      className: "investigation-pin-container",
      html: `
        <div class="investigation-pin-wrapper">
          <div class="investigation-pin-5-glow"></div>
          <svg class="investigation-pin-5-body" viewBox="0 0 38 46" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M19 0.5C8.8 0.5 0.5 8.8 0.5 19C0.5 29.5 19 45.5 19 45.5C19 45.5 37.5 29.5 37.5 19C37.5 8.8 29.2 0.5 19 0.5Z" fill="#0B0D10" stroke="#D9A441" stroke-width="2"/>
            <circle cx="19" cy="19" r="13" fill="#141822" stroke="#D9A441" stroke-width="1.5" stroke-opacity="0.8"/>
            <text x="19" y="24" text-anchor="middle" fill="#E2B34D" font-family="'JetBrains Mono', monospace" font-size="14" font-weight="700">${num}</text>
          </svg>
        </div>
      `,
      iconSize: [38, 46],
      iconAnchor: [19, 46],
    });
  }

  const strokeColor = isSelected ? "#F0C45A" : "#D9A441";
  const numColor = isSelected ? "#F0C45A" : "#F2F3F5";

  return L.divIcon({
    className: "investigation-pin-container",
    html: `
      <div class="investigation-pin-wrapper">
        <svg class="investigation-pin-body" viewBox="0 0 28 34" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M14 0.5C6.5 0.5 0.5 6.5 0.5 14C0.5 21.8 14 33.5 14 33.5C14 33.5 27.5 21.8 27.5 14C27.5 6.5 21.5 0.5 14 0.5Z" fill="#0B0D10" stroke="${strokeColor}" stroke-width="1.6"/>
          <circle cx="14" cy="14" r="9.5" fill="#131720" stroke="${strokeColor}" stroke-width="0.8" stroke-opacity="0.6"/>
          <text x="14" y="18" text-anchor="middle" fill="${numColor}" font-family="'JetBrains Mono', monospace" font-size="11.5" font-weight="700">${num}</text>
        </svg>
      </div>
    `,
    iconSize: [28, 34],
    iconAnchor: [14, 34],
  });
}

// Directional arrow icon along the polyline path
function createDirectionArrowIcon(angleDeg: number) {
  return L.divIcon({
    className: "",
    html: `
      <div style="transform: rotate(${angleDeg}deg); transform-origin: center; display: flex; align-items: center; justify-content: center; width: 18px; height: 18px;">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M4 2L9 7L4 12" stroke="#E2B34D" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </div>
    `,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
}

// Custom Top-Left Zoom Controls
function CustomZoomControls() {
  const map = useMap();
  return (
    <div className="absolute top-4 left-4 z-[1000] flex flex-col gap-1 select-none">
      <button
        onClick={() => map.zoomIn()}
        className="w-7 h-7 bg-[#10141D] hover:bg-[#1A202C] text-[#F2F3F5] hover:text-[#D9A441] border border-white/[0.12] rounded-[4px] flex items-center justify-center text-sm font-semibold transition-colors shadow-md"
        aria-label="Zoom in"
      >
        +
      </button>
      <button
        onClick={() => map.zoomOut()}
        className="w-7 h-7 bg-[#10141D] hover:bg-[#1A202C] text-[#F2F3F5] hover:text-[#D9A441] border border-white/[0.12] rounded-[4px] flex items-center justify-center text-sm font-semibold transition-colors shadow-md"
        aria-label="Zoom out"
      >
        −
      </button>
    </div>
  );
}

// Helper to calculate midpoints and bearing angles for segment directional arrows
function calculateArrowPositions(points: InvestigationPoint[]) {
  const arrows: { lat: number; lng: number; angle: number }[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const p1 = points[i];
    const p2 = points[i + 1];

    // Midpoint
    const midLat = (p1.lat + p2.lat) / 2;
    const midLng = (p1.lng + p2.lng) / 2;

    // Angle in degrees from p1 to p2
    const dLat = p2.lat - p1.lat;
    const dLng = (p2.lng - p1.lng) * Math.cos((p1.lat * Math.PI) / 180);
    let angle = (Math.atan2(dLng, dLat) * 180) / Math.PI;
    // rotate arrow from pointing right (0 deg) to heading
    angle = angle - 90;

    arrows.push({ lat: midLat, lng: midLng, angle });
  }
  return arrows;
}

function FitRoute({ points }: { points: InvestigationPoint[] }) {
  const map = useMap();
  useEffect(() => {
    if (!points.length) return;
    if (points.length === 1) {
      map.setView([points[0].lat, points[0].lng], 13);
      return;
    }
    map.fitBounds(
      points.map((p) => [p.lat, p.lng] as [number, number]),
      { padding: [48, 48], maxZoom: 13 }
    );
  }, [map, points]);
  return null;
}

interface InvestigationMapProps {
  points?: InvestigationPoint[];
  selectedEventId?: number;
  onSelectEvent?: (id: number) => void;
}

export default function InvestigationMap({
  points = INVESTIGATION_ROUTE_POINTS,
  selectedEventId,
  onSelectEvent,
}: InvestigationMapProps) {
  const polylineCoords = useMemo(
    () => points.map((p) => [p.lat, p.lng] as [number, number]),
    [points]
  );

  const arrowPositions = useMemo(() => calculateArrowPositions(points), [points]);

  return (
    <div className="relative w-full h-full bg-[#0B0D10] overflow-hidden select-none">
      <MapContainer
        center={[23.16, 72.58]}
        zoom={10}
        minZoom={8}
        maxZoom={16}
        zoomControl={false}
        attributionControl={false}
        scrollWheelZoom
        className="w-full h-full"
      >
        <TileLayer
          className="dark-gis-tiles"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          subdomains="abc"
          maxZoom={19}
          attribution="&copy; OpenStreetMap"
        />

        {/* Custom Zoom Controls */}
        <CustomZoomControls />
        <FitRoute points={points} />

        {/* Geographic Labels Overlay */}
        {MAP_LABELS.map((item, idx) => (
          <Marker
            key={`label-${idx}`}
            position={[item.lat, item.lng]}
            icon={L.divIcon({
              className: "",
              html: `<div class="${
                item.type === "major"
                  ? "investigation-map-label-major"
                  : item.type === "kalol"
                  ? "investigation-map-label-kalol"
                  : item.type === "water"
                  ? "investigation-map-label-water"
                  : "investigation-map-label-subtle"
              }">${item.text}</div>`,
              iconSize: [120, 20],
              iconAnchor: [60, 10],
            })}
            interactive={false}
            zIndexOffset={50}
          />
        ))}

        {polylineCoords.length >= 2 && (
        <>
        {/* Investigation Route - Outer Soft Amber Glow */}
        <Polyline
          positions={polylineCoords}
          pathOptions={{
            color: "#D9A441",
            weight: 8,
            opacity: 0.28,
            lineCap: "round",
            lineJoin: "round",
          }}
        />

        {/* Investigation Route - Medium Amber Glow */}
        <Polyline
          positions={polylineCoords}
          pathOptions={{
            color: "#D9A441",
            weight: 4.5,
            opacity: 0.65,
            lineCap: "round",
            lineJoin: "round",
          }}
        />

        {/* Investigation Route - Core Sharp Amber Polyline */}
        <Polyline
          positions={polylineCoords}
          pathOptions={{
            color: "#E2B34D",
            weight: 2,
            opacity: 1.0,
            lineCap: "round",
            lineJoin: "round",
          }}
        />

        {/* Directional Arrows Along Segments */}
        {arrowPositions.map((arrow, idx) => (
          <Marker
            key={`arrow-${idx}`}
            position={[arrow.lat, arrow.lng]}
            icon={createDirectionArrowIcon(arrow.angle)}
            interactive={false}
            zIndexOffset={300}
          />
        ))}
        </>
        )}

        {points.map((pt) => {
          const isLatest = Boolean(pt.isLatest);
          const isSelected = selectedEventId === pt.id;
          return (
            <Marker
              key={`pt-${pt.id}`}
              position={[pt.lat, pt.lng]}
              icon={createInvestigationPinIcon(pt.id, isLatest, isSelected)}
              zIndexOffset={isLatest ? 900 : 500}
              eventHandlers={{
                click: () => onSelectEvent?.(pt.id),
              }}
            />
          );
        })}
      </MapContainer>

      {/* Map Attribution at Bottom-Right */}
      <div className="absolute bottom-3 right-4 z-[1000] text-[11px] text-[#687587] select-none flex items-center gap-1.5 pointer-events-auto bg-[#080C14]/70 px-2 py-0.5 rounded border border-white/[0.04]">
        <span>Leaflet</span>
        <span>|</span>
        <span>© OpenStreetMap</span>
      </div>
    </div>
  );
}
