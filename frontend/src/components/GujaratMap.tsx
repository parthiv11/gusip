import React, { useEffect, useMemo, useRef } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  useMap,
} from "react-leaflet";
import L from "leaflet";
import { snapSrc } from "../api/media";
import type { Alert, Camera } from "../types";
import { CoverageGapItem } from "./GISSidebar";

// Reset default leaflet icon paths
delete (L.Icon.Default.prototype as unknown as { _getIconUrl?: string })._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

// Create Online / Offline Camera DivIcons
function createCameraIcon(status: "online" | "offline") {
  const isOnline = status === "online";
  const ringClass = isOnline ? "cam-ring-online" : "cam-ring-offline";
  const dotClass = isOnline ? "cam-dot-online" : "cam-dot-offline";

  return L.divIcon({
    className: "gis-cam-marker",
    html: `<div class="${ringClass}"><div class="${dotClass}"></div></div>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
    popupAnchor: [0, -10],
  });
}

// Generate Starburst SVG rays
function renderStarburstRays() {
  const rays: string[] = [];
  const numRays = 24;
  const cx = 32;
  const cy = 32;
  const innerR = 12;

  for (let i = 0; i < numRays; i++) {
    const angle = (i * 360) / numRays;
    const rad = (angle * Math.PI) / 180;
    const outerR = i % 2 === 0 ? 25 : 20; // Alternating length spikes
    const x1 = cx + innerR * Math.cos(rad);
    const y1 = cy + innerR * Math.sin(rad);
    const x2 = cx + outerR * Math.cos(rad);
    const y2 = cy + outerR * Math.sin(rad);
    rays.push(`<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" stroke="#D9A441" stroke-width="1.8" stroke-linecap="round" />`);
  }
  return rays.join("");
}

const STARBURST_RAYS_HTML = renderStarburstRays();

// Create Starburst Alert Cluster DivIcon
function createAlertStarburstIcon(count: number) {
  const label = count > 99 ? "99+" : String(count);
  return L.divIcon({
    className: "gis-starburst-marker",
    html: `
      <svg class="starburst-svg" width="64" height="64" viewBox="0 0 64 64">
        ${STARBURST_RAYS_HTML}
      </svg>
      <div class="starburst-core">${label}</div>
    `,
    iconSize: [48, 48],
    iconAnchor: [24, 24],
    popupAnchor: [0, -22],
  });
}

// Create Geographic Label DivIcon
function createMapLabelIcon(text: string, type: "city" | "region" | "water" = "city") {
  const className =
    type === "region"
      ? "gis-region-label"
      : type === "water"
      ? "gis-water-label"
      : "gis-map-label";

  return L.divIcon({
    className: "",
    html: `<div class="${className}">${text}</div>`,
    iconSize: [100, 20],
    iconAnchor: [50, 10],
  });
}

// Map geographic label reference points
const GEO_LABELS = [
  { text: "RAJASTHAN", lat: 24.55, lon: 73.25, type: "region" as const },
  { text: "MADHYA PRADESH", lat: 22.65, lon: 74.45, type: "region" as const },
  { text: "MAHARASHTRA", lat: 20.55, lon: 73.85, type: "region" as const },
  { text: "Arabian Sea", lat: 20.65, lon: 69.35, type: "water" as const },
  { text: "Rann of Kutch", lat: 23.85, lon: 69.75, type: "city" as const },
  { text: "Ahmedabad", lat: 22.98, lon: 72.63, type: "city" as const },
  { text: "Gandhinagar", lat: 23.25, lon: 72.62, type: "city" as const },
  { text: "Rajkot", lat: 22.25, lon: 70.83, type: "city" as const },
  { text: "Vadodara", lat: 22.28, lon: 73.20, type: "city" as const },
  { text: "Surat", lat: 21.15, lon: 72.86, type: "city" as const },
  { text: "Bhavnagar", lat: 21.72, lon: 72.18, type: "city" as const },
  { text: "Jamnagar", lat: 22.42, lon: 70.08, type: "city" as const },
  { text: "Junagadh", lat: 21.47, lon: 70.47, type: "city" as const },
  { text: "Bhuj", lat: 23.21, lon: 69.70, type: "city" as const },
  { text: "Gandhidham", lat: 23.05, lon: 70.18, type: "city" as const },
  { text: "Mandvi", lat: 22.80, lon: 69.38, type: "city" as const },
  { text: "Anand", lat: 22.52, lon: 72.95, type: "city" as const },
  { text: "Bharuch", lat: 21.66, lon: 73.02, type: "city" as const },
  { text: "Navsari", lat: 20.91, lon: 72.97, type: "city" as const },
  { text: "Valsad", lat: 20.57, lon: 72.95, type: "city" as const },
  { text: "Porbandar", lat: 21.60, lon: 69.65, type: "city" as const },
  { text: "Dwarka", lat: 22.20, lon: 68.99, type: "city" as const },
  { text: "Veraval", lat: 20.87, lon: 70.38, type: "city" as const },
  { text: "Amreli", lat: 21.57, lon: 71.24, type: "city" as const },
  { text: "Surendranagar", lat: 22.68, lon: 71.66, type: "city" as const },
  { text: "Mehsana", lat: 23.55, lon: 72.40, type: "city" as const },
  { text: "Patan", lat: 23.80, lon: 72.15, type: "city" as const },
  { text: "Palanpur", lat: 24.13, lon: 72.45, type: "city" as const },
  { text: "Deesa", lat: 24.22, lon: 72.20, type: "city" as const },
  { text: "Himmatnagar", lat: 23.56, lon: 73.00, type: "city" as const },
  { text: "Modasa", lat: 23.42, lon: 73.32, type: "city" as const },
  { text: "Morbi", lat: 22.78, lon: 70.86, type: "city" as const },
];

// Reference surveillance alerts matching the design
export interface AlertCluster {
  id: string;
  city: string;
  count: number;
  lat: number;
  lon: number;
  category: string;
  plate?: string;
  target?: string;
  severity: "critical" | "high";
  time: string;
  cameraCode: string;
}

export const REFERENCE_ALERT_CLUSTERS: AlertCluster[] = [
  {
    id: "alert-ahm-24",
    city: "Ahmedabad",
    count: 24,
    lat: 23.0225,
    lon: 72.5714,
    category: "STOLEN VEHICLE / RED-CORNER WANTED",
    plate: "GJ 01 ST 0001",
    target: "Silver Toyota Fortuner · Suspect heading West",
    severity: "critical",
    time: "2 mins ago",
    cameraCode: "AMD-SG-01",
  },
  {
    id: "alert-raj-17",
    city: "Rajkot",
    count: 17,
    lat: 22.3039,
    lon: 70.8022,
    category: "WATCHLIST SUSPECT MATCH",
    plate: "GJ 03 KL 8821",
    target: "Target Subject: Imran K. (Organized Theft Ring)",
    severity: "critical",
    time: "6 mins ago",
    cameraCode: "RAJ-YR-01",
  },
  {
    id: "alert-anand-14",
    city: "Anand",
    count: 14,
    lat: 22.5645,
    lon: 72.9289,
    category: "INTER-DISTRICT CONTRABAND SUSPECT",
    plate: "GJ 23 BB 4099",
    target: "Heavy Commercial Truck · Express Corridor",
    severity: "high",
    time: "11 mins ago",
    cameraCode: "VAD-RC-01",
  },
  {
    id: "alert-jun-13",
    city: "Junagadh / Amreli",
    count: 13,
    lat: 21.5222,
    lon: 70.4579,
    category: "EVADING CHECKPOINT ALERT",
    plate: "GJ 11 MH 3110",
    target: "Black SUV · Speed violation > 130 km/h",
    severity: "high",
    time: "15 mins ago",
    cameraCode: "JUN-MG-01",
  },
  {
    id: "alert-pat-11",
    city: "Patan / Mehsana",
    count: 11,
    lat: 23.8500,
    lon: 72.1250,
    category: "UNAUTHORIZED BORDER TRANSIT",
    plate: "RJ 14 CC 9012",
    target: "Interstate Transit · North Checkpost 04",
    severity: "high",
    time: "19 mins ago",
    cameraCode: "PAT-CL-01",
  },
  {
    id: "alert-sur-21",
    city: "Surat / Navsari",
    count: 21,
    lat: 21.1702,
    lon: 72.8311,
    category: "FINANCIAL CRIMES SUSPECT CONVOY",
    plate: "GJ 05 XY 9900",
    target: "Dual Convoy · Ring Road Surveillance Sector 2",
    severity: "critical",
    time: "4 mins ago",
    cameraCode: "SRT-RD-01",
  },
];

// Realistic base camera positions across Gujarat
export const REFERENCE_CAMERAS: Camera[] = [
  // ONLINE CAMERAS
  { id: 101, code: "AMD-SG-01", name: "SG Highway Junction North", city: "Ahmedabad", latitude: 23.0475, longitude: 72.5310, status: "online", camera_type: "ip", ownership: "Traffic Police", source_type: "rtsp", department_id: 1, connectivity: "fiber", amc_status: "active", coverage_radius_m: 500 },
  { id: 102, code: "GNR-HW-01", name: "CH-0 Circle Highway", city: "Gandhinagar", latitude: 23.2156, longitude: 72.6369, status: "online", camera_type: "ip", ownership: "Gandhinagar Police", source_type: "onvif", department_id: 5, connectivity: "fiber", amc_status: "active", coverage_radius_m: 500 },
  { id: 103, code: "RAJ-YR-01", name: "Yagnik Road Chowk", city: "Rajkot", latitude: 22.2980, longitude: 70.7950, status: "online", camera_type: "ip", ownership: "Rajkot City Police", source_type: "rtsp", department_id: 4, connectivity: "fiber", amc_status: "active", coverage_radius_m: 500 },
  { id: 104, code: "JAM-TC-01", name: "Town Hall Circle", city: "Jamnagar", latitude: 22.4707, longitude: 70.0577, status: "online", camera_type: "ip", ownership: "Traffic Police", source_type: "rtsp", department_id: 1, connectivity: "fiber", amc_status: "active", coverage_radius_m: 500 },
  { id: 105, code: "DWK-TM-01", name: "Dwarkadhish Temple Approach", city: "Dwarka", latitude: 22.2442, longitude: 68.9685, status: "online", camera_type: "ip", ownership: "Coastal Police", source_type: "vendor_api", department_id: 6, connectivity: "fiber", amc_status: "active", coverage_radius_m: 500 },
  { id: 106, code: "PBD-CH-01", name: "Chowpati Beach Road", city: "Porbandar", latitude: 21.6417, longitude: 69.6293, status: "online", camera_type: "ip", ownership: "Coastal Police", source_type: "rtsp", department_id: 6, connectivity: "wireless", amc_status: "active", coverage_radius_m: 500 },
  { id: 107, code: "VRV-SM-01", name: "Somnath Bypass Junction", city: "Veraval", latitude: 20.9077, longitude: 70.3678, status: "online", camera_type: "ip", ownership: "Highway Police", source_type: "onvif", department_id: 3, connectivity: "leased", amc_status: "active", coverage_radius_m: 500 },
  { id: 108, code: "JUN-MG-01", name: "Majevadi Gate", city: "Junagadh", latitude: 21.5222, longitude: 70.4579, status: "online", camera_type: "ip", ownership: "Law & Order", source_type: "rtsp", department_id: 2, connectivity: "fiber", amc_status: "active", coverage_radius_m: 500 },
  { id: 109, code: "AMR-ST-01", name: "Station Road Circle", city: "Amreli", latitude: 21.6032, longitude: 71.2221, status: "online", camera_type: "ip", ownership: "Traffic Police", source_type: "rtsp", department_id: 1, connectivity: "copper", amc_status: "active", coverage_radius_m: 500 },
  { id: 110, code: "BHV-NP-01", name: "Nilambag Palace Circle", city: "Bhavnagar", latitude: 21.7645, longitude: 72.1519, status: "online", camera_type: "ip", ownership: "Traffic Police", source_type: "rtsp", department_id: 1, connectivity: "fiber", amc_status: "active", coverage_radius_m: 500 },
  { id: 111, code: "BHR-NH-01", name: "Golden Bridge Toll", city: "Bharuch", latitude: 21.7051, longitude: 72.9959, status: "online", camera_type: "ip", ownership: "Highway Police", source_type: "onvif", department_id: 3, connectivity: "leased", amc_status: "active", coverage_radius_m: 500 },
  { id: 112, code: "SRT-RD-01", name: "Ring Road Adajan", city: "Surat", latitude: 21.1970, longitude: 72.7936, status: "online", camera_type: "ip", ownership: "Surat City Police", source_type: "rtsp", department_id: 1, connectivity: "fiber", amc_status: "active", coverage_radius_m: 500 },
  { id: 113, code: "SRT-HW-01", name: "Sachin GIDC Highway", city: "Surat", latitude: 21.0870, longitude: 72.8775, status: "online", camera_type: "ip", ownership: "Highway Police", source_type: "onvif", department_id: 3, connectivity: "leased", amc_status: "active", coverage_radius_m: 500 },
  { id: 114, code: "BHJ-JB-01", name: "Jubilee Ground North", city: "Bhuj", latitude: 23.2420, longitude: 69.6669, status: "online", camera_type: "ip", ownership: "Law & Order", source_type: "rtsp", department_id: 2, connectivity: "fiber", amc_status: "active", coverage_radius_m: 500 },
  { id: 115, code: "GDM-PT-01", name: "Kandla Port Highway", city: "Gandhidham", latitude: 23.0753, longitude: 70.1337, status: "online", camera_type: "ip", ownership: "Coastal Police", source_type: "vendor_api", department_id: 6, connectivity: "fiber", amc_status: "active", coverage_radius_m: 500 },
  { id: 116, code: "PLN-AR-01", name: "Abu Road Toll Plaza", city: "Palanpur", latitude: 24.1724, longitude: 72.4346, status: "online", camera_type: "ip", ownership: "Highway Police", source_type: "onvif", department_id: 3, connectivity: "fiber", amc_status: "active", coverage_radius_m: 500 },
  { id: 117, code: "MSH-MC-01", name: "Modhera Crossroads", city: "Mehsana", latitude: 23.5880, longitude: 72.3693, status: "online", camera_type: "ip", ownership: "Traffic Police", source_type: "rtsp", department_id: 1, connectivity: "fiber", amc_status: "active", coverage_radius_m: 500 },
  { id: 118, code: "SDR-MJ-01", name: "Main Junction Wadhwan", city: "Surendranagar", latitude: 22.7284, longitude: 71.6371, status: "online", camera_type: "ip", ownership: "Traffic Police", source_type: "rtsp", department_id: 1, connectivity: "copper", amc_status: "active", coverage_radius_m: 500 },
  { id: 119, code: "MRB-NH-01", name: "Ceramic Zone Expressway", city: "Morbi", latitude: 22.8173, longitude: 70.8377, status: "online", camera_type: "ip", ownership: "Highway Police", source_type: "onvif", department_id: 3, connectivity: "leased", amc_status: "active", coverage_radius_m: 500 },
  { id: 120, code: "DSA-HW-01", name: "Deesa Bypass Junction", city: "Deesa", latitude: 24.2585, longitude: 72.1812, status: "online", camera_type: "ip", ownership: "Highway Police", source_type: "rtsp", department_id: 3, connectivity: "fiber", amc_status: "active", coverage_radius_m: 500 },
  { id: 121, code: "MDS-TN-01", name: "Modasa Town Square", city: "Modasa", latitude: 23.4632, longitude: 73.2984, status: "online", camera_type: "ip", ownership: "Law & Order", source_type: "rtsp", department_id: 2, connectivity: "copper", amc_status: "active", coverage_radius_m: 500 },
  { id: 122, code: "VLS-MG-01", name: "Valsad Main Highway Checkpost", city: "Valsad", latitude: 20.5992, longitude: 72.9342, status: "online", camera_type: "ip", ownership: "Traffic Police", source_type: "rtsp", department_id: 1, connectivity: "fiber", amc_status: "active", coverage_radius_m: 500 },

  // OFFLINE CAMERAS
  { id: 201, code: "MDV-CS-01", name: "Mandvi Port Coastal Checkpoint", city: "Mandvi", latitude: 22.8335, longitude: 69.1567, status: "offline", camera_type: "ip", ownership: "Coastal Police", source_type: "rtsp", department_id: 6, connectivity: "wireless", amc_status: "pending", coverage_radius_m: 500 },
  { id: 202, code: "KTC-NB-01", name: "North Kutch Border Observation 2", city: "Bhuj", latitude: 23.6500, longitude: 69.2500, status: "offline", camera_type: "ip", ownership: "Anti-Terrorism Squad", source_type: "vendor_api", department_id: 7, connectivity: "satellite", amc_status: "pending", coverage_radius_m: 500 },
  { id: 203, code: "HMT-NE-01", name: "Himmatnagar Bypass North", city: "Himmatnagar", latitude: 23.6800, longitude: 73.1200, status: "offline", camera_type: "ip", ownership: "Highway Police", source_type: "rtsp", department_id: 3, connectivity: "fiber", amc_status: "pending", coverage_radius_m: 500 },
  { id: 204, code: "SDR-ST-02", name: "Surendranagar South Rural Post", city: "Surendranagar", latitude: 22.5000, longitude: 71.4000, status: "offline", camera_type: "analog", ownership: "Law & Order", source_type: "onvif", department_id: 2, connectivity: "copper", amc_status: "active", coverage_radius_m: 500 },
  { id: 205, code: "AND-KH-01", name: "Khambhat Coastal Pier", city: "Anand", latitude: 22.2500, longitude: 72.6500, status: "offline", camera_type: "ip", ownership: "Coastal Police", source_type: "rtsp", department_id: 6, connectivity: "wireless", amc_status: "pending", coverage_radius_m: 500 },
  { id: 206, code: "NVS-BL-01", name: "Navsari South Rural Border", city: "Navsari", latitude: 20.7800, longitude: 72.9200, status: "offline", camera_type: "ip", ownership: "Traffic Police", source_type: "rtsp", department_id: 1, connectivity: "copper", amc_status: "pending", coverage_radius_m: 500 },
  { id: 207, code: "VLS-BD-02", name: "Maharashtra Border Checkpoint South", city: "Valsad", latitude: 20.3500, longitude: 72.9000, status: "offline", camera_type: "ip", ownership: "Highway Police", source_type: "onvif", department_id: 3, connectivity: "leased", amc_status: "pending", coverage_radius_m: 500 },
];

interface MapFlyControllerProps {
  targetLocation: { lat: number; lon: number } | null;
}

function MapFlyController({ targetLocation }: MapFlyControllerProps) {
  const map = useMap();
  useEffect(() => {
    if (targetLocation) {
      map.flyTo([targetLocation.lat, targetLocation.lon], 11, {
        duration: 1.2,
        easeLinearity: 0.25,
      });
    }
  }, [targetLocation, map]);

  return null;
}

// Custom Zoom Control Buttons inside Leaflet context
function CustomZoomControls() {
  const map = useMap();
  return (
    <div className="absolute top-4 left-4 z-[1000] flex flex-col rounded-[4px] overflow-hidden border border-white/10 bg-[#10151D] shadow-[0_4px_16px_rgba(0,0,0,0.6)]">
      <button
        type="button"
        title="Zoom In"
        onClick={() => map.zoomIn()}
        className="w-7 h-7 flex items-center justify-center text-[#F2F4F7] hover:bg-white/10 hover:text-[#D9A441] text-base font-semibold border-b border-white/10 transition-colors"
      >
        +
      </button>
      <button
        type="button"
        title="Zoom Out"
        onClick={() => map.zoomOut()}
        className="w-7 h-7 flex items-center justify-center text-[#F2F4F7] hover:bg-white/10 hover:text-[#D9A441] text-base font-semibold transition-colors"
      >
        −
      </button>
    </div>
  );
}

interface GujaratMapProps {
  cameras?: Camera[];
  alerts?: Alert[];
  statusFilter?: string;
  deptFilter?: string;
  targetCity?: CoverageGapItem | null;
  onSelectCamera?: (c: Camera) => void;
  onSelectAlert?: (a: AlertCluster) => void;
}

export default function GujaratMap({
  cameras: propCameras,
  alerts: propAlerts,
  statusFilter = "all",
  deptFilter = "all",
  targetCity,
  onSelectCamera,
  onSelectAlert,
}: GujaratMapProps) {
  // Merge prop cameras with reference cameras
  const allCameras = useMemo(() => {
    if (propCameras && propCameras.length > 10) {
      return propCameras;
    }
    return REFERENCE_CAMERAS;
  }, [propCameras]);

  // Filter cameras
  const visibleCameras = useMemo(() => {
    return allCameras.filter((cam) => {
      // Status filter
      if (statusFilter !== "all" && cam.status !== statusFilter) {
        return false;
      }
      // Department filter
      if (deptFilter !== "all") {
        if (
          String(cam.department_id) !== deptFilter &&
          !cam.ownership?.toLowerCase().includes(deptFilter.toLowerCase())
        ) {
          return false;
        }
      }
      return true;
    });
  }, [allCameras, statusFilter, deptFilter]);

  // Alert clusters
  const alertClusters = REFERENCE_ALERT_CLUSTERS;

  return (
    <div className="relative w-full h-full bg-[#0B0D10] overflow-hidden select-none">
      <MapContainer
        center={[22.75, 71.35]}
        zoom={7}
        minZoom={6}
        maxZoom={15}
        zoomControl={false}
        attributionControl={false}
        scrollWheelZoom
        className="w-full h-full"
      >
        {/* Deep dark Surveillance Basemap Tiles */}
        <TileLayer
          className="dark-gis-tiles"
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
          maxZoom={19}
        />

        {/* Custom Zoom Controls */}
        <CustomZoomControls />

        {/* Map Fly Controller for City Clicks */}
        <MapFlyController
          targetLocation={
            targetCity ? { lat: targetCity.lat, lon: targetCity.lon } : null
          }
        />

        {/* Geographic Labels Overlay (Subdued Muted Gray) */}
        {GEO_LABELS.map((g, idx) => (
          <Marker
            key={`geo-${idx}-${g.text}`}
            position={[g.lat, g.lon]}
            icon={createMapLabelIcon(g.text, g.type)}
            interactive={false}
            zIndexOffset={50}
          />
        ))}

        {/* Camera Markers (Online / Offline) */}
        {visibleCameras.map((cam) => {
          const isOnline = cam.status === "online";
          return (
            <Marker
              key={`cam-${cam.id}`}
              position={[cam.latitude, cam.longitude]}
              icon={createCameraIcon(isOnline ? "online" : "offline")}
              zIndexOffset={isOnline ? 200 : 250}
              eventHandlers={{
                click: () => onSelectCamera?.(cam),
              }}
            >
              <Popup maxWidth={280}>
                <div className="text-[12px] font-sans">
                  <div className="flex items-center justify-between gap-2 border-b border-white/10 pb-1.5 mb-2">
                    <span className="font-mono font-bold text-[#F2F4F7] text-[13px]">
                      {cam.code}
                    </span>
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase ${
                        isOnline
                          ? "bg-[#35D49A]/15 text-[#35D49A] border border-[#35D49A]/40"
                          : "bg-[#F05252]/15 text-[#F05252] border border-[#F05252]/40"
                      }`}
                    >
                      {cam.status}
                    </span>
                  </div>
                  <div className="font-medium text-[#F2F4F7] mb-1">{cam.name}</div>
                  <div className="text-[#A7B0BE] text-[11px] space-y-0.5">
                    <div>
                      <span className="text-[#687386]">Location:</span> {cam.city} · {cam.ownership || "Police"}
                    </div>
                    <div>
                      <span className="text-[#687386]">Stream:</span> {cam.source_type?.toUpperCase() || "RTSP"} · 4K UHD · 30 FPS
                    </div>
                    <div>
                      <span className="text-[#687386]">Heartbeat:</span> 2s ago (Active)
                    </div>
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        })}

        {/* Open Alert Starburst Markers */}
        {alertClusters.map((alert) => (
          <Marker
            key={alert.id}
            position={[alert.lat, alert.lon]}
            icon={createAlertStarburstIcon(alert.count)}
            zIndexOffset={800}
            eventHandlers={{
              click: () => onSelectAlert?.(alert),
            }}
          >
            <Popup maxWidth={300}>
              <div className="text-[12px] font-sans">
                <div className="flex items-center justify-between gap-2 border-b border-white/10 pb-1.5 mb-2">
                  <span className="font-bold text-[#D9A441] text-[12px] tracking-wide uppercase">
                    ALERT CLUSTER
                  </span>
                  <span className="font-mono font-bold px-2 py-0.5 rounded bg-[#D9A441]/20 text-[#D9A441] border border-[#D9A441]/50 text-[11px]">
                    ×{alert.count} HITS
                  </span>
                </div>
                <div className="font-semibold text-[#F2F4F7] text-[13px] mb-1">
                  {alert.category}
                </div>
                {alert.plate && (
                  <div className="font-mono font-bold text-[12px] text-[#F0C45A] bg-[#151A22] px-2 py-1 rounded border border-white/10 mb-1.5">
                    {alert.plate}
                  </div>
                )}
                <div className="text-[#A7B0BE] text-[11px] space-y-0.5 mb-2">
                  <div>
                    <span className="text-[#687386]">City/Sector:</span> {alert.city} ({alert.cameraCode})
                  </div>
                  <div>
                    <span className="text-[#687386]">Target info:</span> {alert.target}
                  </div>
                  <div>
                    <span className="text-[#687386]">Last detected:</span> {alert.time}
                  </div>
                </div>
                <div className="border-t border-white/10 pt-1.5 flex justify-between items-center text-[10px] text-[#687386]">
                  <span>Severity: <strong className="text-[#F05252] uppercase">{alert.severity}</strong></span>
                  <span className="text-[#D9A441] hover:underline cursor-pointer">View Dossier →</span>
                </div>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>

      {/* Map Attribution (Bottom-Left: © Mapbox © OpenStreetMap Improve this map) */}
      <div className="absolute bottom-3 left-3 z-[1000] text-[11px] text-[#687386] select-none flex items-center gap-1.5 pointer-events-auto bg-[#080C14]/70 px-2 py-0.5 rounded border border-white/[0.04]">
        <span>© Mapbox</span>
        <span>© OpenStreetMap</span>
        <span className="text-[#8B95A5] hover:underline cursor-pointer">Improve this map</span>
      </div>
    </div>
  );
}
