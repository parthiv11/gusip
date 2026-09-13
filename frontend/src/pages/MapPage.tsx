import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import GISSidebar, { CoverageGapItem } from "../components/GISSidebar";
import GujaratMap from "../components/GujaratMap";
import type { Alert, Camera } from "../types";

interface Gap {
  city: string;
  camera_count: number;
  uncovered_hint: string;
  recommended_cameras: number;
}

function gapTone(current: number, target: number): CoverageGapItem["colorType"] {
  const pct = target > 0 ? current / target : 1;
  if (pct < 0.4) return "critical";
  if (pct < 0.7) return "warning";
  if (pct < 0.9) return "moderate";
  return "good";
}

export default function MapPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [gaps, setGaps] = useState<Gap[]>([]);
  const [status, setStatus] = useState("");
  const [dept, setDept] = useState("");
  const [departments, setDepartments] = useState<{ id: number; name: string }[]>([]);
  const [selectedCity, setSelectedCity] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ id: number; name: string }[]>("/api/v1/cameras/departments")
      .then(setDepartments)
      .catch((err) => setError(String(err)));
    api<Gap[]>("/api/v1/gis/gaps")
      .then(setGaps)
      .catch(() => setGaps([]));
    api<Alert[]>("/api/v1/alerts?status=new&limit=80")
      .then(setAlerts)
      .catch((err) => setError(String(err)));
  }, []);

  useEffect(() => {
    const q = new URLSearchParams();
    if (status) q.set("status", status);
    if (dept) q.set("department_id", dept);
    api<Camera[]>(`/api/v1/cameras?${q.toString()}`)
      .then(setCameras)
      .catch((err) => setError(String(err)));
  }, [status, dept]);

  const gapItems = useMemo<CoverageGapItem[]>(() => {
    return gaps.map((g) => {
      const inCity = cameras.filter((c) => c.city === g.city);
      const lat =
        inCity.length > 0
          ? inCity.reduce((s, c) => s + c.latitude, 0) / inCity.length
          : 23.02;
      const lon =
        inCity.length > 0
          ? inCity.reduce((s, c) => s + c.longitude, 0) / inCity.length
          : 72.57;
      const target = g.camera_count + g.recommended_cameras;
      return {
        city: g.city,
        current: g.camera_count,
        target: target || g.camera_count,
        lat,
        lon,
        colorType: gapTone(g.camera_count, target || 1),
      };
    });
  }, [gaps, cameras]);

  const mapCameras = selectedCity ? cameras.filter((c) => c.city === selectedCity) : cameras;

  return (
    <div className="relative h-full flex flex-col lg:flex-row min-h-0 overflow-hidden bg-[#0B0D10]">
      <h1 className="sr-only">GIS coverage</h1>
      {error && (
        <div role="alert" className="absolute top-2 left-2 z-[1000] bg-red-950/90 border border-red-500/50 text-red-200 text-xs px-3 py-1.5 rounded">
          {error}
        </div>
      )}
      <div className="flex-1 min-h-[50vh] lg:min-h-0">
        <GujaratMap cameras={mapCameras} showCoverage alerts={alerts} />
      </div>
      <GISSidebar
        statusFilter={status || "all"}
        onStatusFilterChange={(val) => setStatus(val === "all" ? "" : val)}
        deptFilter={dept || "all"}
        onDeptFilterChange={(val) => setDept(val === "all" ? "" : val)}
        departments={departments}
        onSelectCity={(item) => setSelectedCity((prev) => (prev === item.city ? null : item.city))}
        selectedCityName={selectedCity}
        gaps={gapItems}
      />
    </div>
  );
}
