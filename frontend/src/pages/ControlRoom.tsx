import React, { useState, useEffect } from "react";
import { CameraControlStrip, FilterOption } from "../components/CameraControlStrip";
import { PrimaryCameraFeed, CameraData } from "../components/PrimaryCameraFeed";
import { AlertInbox } from "../components/AlertInbox";
import { OperationalAlert } from "../components/AlertCard";
import { GISSliver } from "../components/GISSliver";
import { api } from "../api/client";

const INITIAL_CAMERAS: CameraData[] = [
  {
    id: 1,
    code: "SEN-1",
    source: "GOV",
    name: "Chimanbhai Bridge CSITMS-32",
    location: "Chiman bhai Bridge CSITMS-32 PTZ2",
    image: "/assets/cctv_chimanbhai.jpg",
    status: "online",
    fps: 25,
  },
  {
    id: 2,
    code: "SEN-2",
    source: "GOV",
    name: "SG Highway Junction CSITMS-18",
    location: "SG Highway Junction CSITMS-18 PTZ1",
    image: "/assets/cctv_sghighway.jpg",
    status: "online",
    fps: 30,
  },
  {
    id: 3,
    code: "SEN-3",
    source: "GOV",
    name: "Ashram Road Flyover CSITMS-07",
    location: "Ashram Road Flyover CSITMS-07 PTZ3",
    image: "/assets/cctv_ashramroad.jpg",
    status: "online",
    fps: 25,
  },
  {
    id: 4,
    code: "SEN-4",
    source: "GOV",
    name: "SP Ring Road Toll CSITMS-44",
    location: "SP Ring Road Toll CSITMS-44 PTZ2",
    image: "/assets/cctv_chimanbhai.jpg",
    status: "online",
    fps: 25,
  },
];

const INITIAL_ALERTS: OperationalAlert[] = [
  {
    id: 101,
    severity: "stolen",
    severityLabel: "STOLEN VEHICLE",
    title: "White Toyota Fortuner · GJ 01 ST 0001",
    cameraCode: "GNR-HW-01",
    confidence: "97%",
    trackId: "veh-GJ01ST0001",
    hits: 8,
    timestamp: "21:27:08",
    evidenceImage: "/assets/alert_fortuner.jpg",
    acknowledged: false,
  },
  {
    id: 102,
    severity: "wanted",
    severityLabel: "WANTED PERSON",
    title: "Rakesh M.",
    cameraCode: "AMD-SK-01",
    confidence: "72%",
    trackId: "per-1-155344",
    hits: 8,
    timestamp: "21:27:04",
    evidenceImage: "/assets/alert_rakesh.jpg",
    acknowledged: false,
  },
  {
    id: 103,
    severity: "blacklisted",
    severityLabel: "BLACKLISTED VEHICLE",
    title: "Black Honda City · GJ 05 BL 9999",
    cameraCode: "SRT-HW-01",
    confidence: "97%",
    trackId: "veh-GJ05BL9999",
    hits: 9,
    timestamp: "21:26:56",
    evidenceImage: "/assets/alert_honda.jpg",
    acknowledged: false,
  },
];

export default function ControlRoom() {
  const [cameras, setCameras] = useState<CameraData[]>(INITIAL_CAMERAS);
  const [currentCameraIndex, setCurrentCameraIndex] = useState(0);
  const [filter, setFilter] = useState<FilterOption>("gov");
  const [syncSentinel, setSyncSentinel] = useState(true);
  const [alerts, setAlerts] = useState<OperationalAlert[]>(INITIAL_ALERTS);
  const [stats, setStats] = useState({
    onWall: 30,
    online: 79,
    openAlerts: 11,
  });

  // Attempt to load backend data if available, without breaking UI if offline
  useEffect(() => {
    api<any[]>("/api/v1/cameras")
      .then((data) => {
        if (data && data.length > 0) {
          const mapped: CameraData[] = data.map((c, idx) => ({
            id: c.id,
            code: c.code || `SEN-${idx + 1}`,
            source: c.source_type === "sentinel" ? "GOV" : "DEMO",
            name: c.name || `Camera ${c.id}`,
            location: c.address || c.name || "Ahmedabad Surveillance Grid",
            image: c.source_type === "sentinel" ? "/assets/cctv_chimanbhai.jpg" : "/assets/cctv_sghighway.jpg",
            status: "online",
          }));
          setCameras(mapped);
        }
      })
      .catch(() => {
        // Fallback already in state
      });

    api<Record<string, number>>("/api/v1/admin/stats")
      .then((s) => {
        if (s) {
          setStats({
            onWall: s.wall ?? 30,
            online: s.online ?? 79,
            openAlerts: s.open_alerts ?? 11,
          });
        }
      })
      .catch(() => {
        // Fallback already in state
      });
  }, []);

  const handleAcknowledge = (id: number) => {
    setAlerts((prev) =>
      prev.map((a) => (a.id === id ? { ...a, acknowledged: true } : a))
    );
    setStats((prev) => ({
      ...prev,
      openAlerts: Math.max(0, prev.openAlerts - 1),
    }));

    // Post to API if active
    api(`/api/v1/alerts/${id}/ack`, { method: "POST" }).catch(() => undefined);
  };

  const handlePrevPage = () => {
    setCurrentCameraIndex((prev) => Math.max(0, prev - 1));
  };

  const handleNextPage = () => {
    setCurrentCameraIndex((prev) => Math.min(cameras.length - 1, prev + 1));
  };

  const activeCamera = cameras[currentCameraIndex] || INITIAL_CAMERAS[0];

  return (
    <div className="h-full flex flex-col justify-between p-3 gap-2 bg-[#0B0D10] text-[#F2F4F7] overflow-hidden">
      {/* Top 75%: Main Content Grid (70% Camera area / 30% Alert Inbox) */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-3 min-h-0">
        {/* Left Column (Approx 70% width): Camera Controls + Live Video Feed */}
        <section className="lg:col-span-8 xl:col-span-8 flex flex-col gap-2 min-h-0">
          <CameraControlStrip
            wallCount={stats.onWall}
            onlineCount={stats.online}
            openAlertsCount={stats.openAlerts}
            currentFilter={filter}
            onFilterChange={setFilter}
            syncSentinelActive={syncSentinel}
            onToggleSyncSentinel={() => setSyncSentinel((v) => !v)}
            currentPage={currentCameraIndex + 1}
            totalPages={cameras.length}
            onPrevPage={handlePrevPage}
            onNextPage={handleNextPage}
          />
          <div className="flex-1 min-h-0 w-full">
            <PrimaryCameraFeed camera={activeCamera} />
          </div>
        </section>

        {/* Right Column (Approx 30% width): Alert Inbox */}
        <aside className="lg:col-span-4 xl:col-span-4 flex flex-col min-h-0 bg-[#0B0D10]">
          <AlertInbox
            alerts={alerts}
            focusText={`${activeCamera.code} · ${activeCamera.location.split(" ")[0]} ${activeCamera.location.split(" ")[1] || ""} · sentinel`}
            onAcknowledge={handleAcknowledge}
          />
        </aside>
      </div>

      {/* Bottom ~10%: GIS Map Sliver */}
      <div className="shrink-0">
        <GISSliver currentLocationName={activeCamera.name.split(" ")[0] + " " + (activeCamera.name.split(" ")[1] || "")} />
      </div>
    </div>
  );
}
