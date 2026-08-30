import React, { useEffect, useState } from "react";
import { api } from "../api/client";
import GujaratMap from "../components/GujaratMap";
import GISSidebar, { CoverageGapItem } from "../components/GISSidebar";
import type { Alert, Camera } from "../types";

const DEFAULT_DEPARTMENTS = [
  { id: "1", name: "Traffic Management" },
  { id: "2", name: "Crime Branch" },
  { id: "3", name: "Highway Patrol" },
  { id: "4", name: "Law & Order" },
  { id: "5", name: "Gandhinagar Police" },
  { id: "6", name: "Coastal Police" },
  { id: "7", name: "Anti-Terrorism Squad" },
];

export default function MapPage() {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [departments, setDepartments] = useState<{ id: string | number; name: string }[]>(DEFAULT_DEPARTMENTS);
  const [statusFilter, setStatusFilter] = useState("all");
  const [deptFilter, setDeptFilter] = useState("all");
  const [selectedCity, setSelectedCity] = useState<CoverageGapItem | null>(null);

  useEffect(() => {
    // Attempt to load live backend data if connected
    api<{ id: number; name: string }[]>("/api/v1/cameras/departments")
      .then((data) => {
        if (data && data.length) {
          setDepartments(data);
        }
      })
      .catch(() => {
        // Fallback to default department list
      });

    api<Alert[]>("/api/v1/alerts?status=new&limit=80")
      .then((data) => {
        if (data && data.length) {
          setAlerts(data);
        }
      })
      .catch(() => {
        // Fallback alerts are rendered by GujaratMap
      });

    api<Camera[]>("/api/v1/cameras")
      .then((data) => {
        if (data && data.length) {
          setCameras(data);
        }
      })
      .catch(() => {
        // Fallback cameras are rendered by GujaratMap
      });
  }, []);

  const handleSelectCity = (city: CoverageGapItem) => {
    setSelectedCity(city);
  };

  return (
    <div className="h-full w-full flex flex-col lg:flex-row min-h-0 overflow-hidden bg-[#0B0D10]">
      {/* Left 78-80%: Dominant GIS Surveillance Map */}
      <div className="flex-1 h-full min-h-0 relative">
        <GujaratMap
          cameras={cameras}
          alerts={alerts}
          statusFilter={statusFilter}
          deptFilter={deptFilter}
          targetCity={selectedCity}
        />
      </div>

      {/* Right 20-22%: Fixed Operational Sidebar */}
      <GISSidebar
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
        deptFilter={deptFilter}
        onDeptFilterChange={setDeptFilter}
        departments={departments}
        onSelectCity={handleSelectCity}
        selectedCityName={selectedCity?.city}
      />
    </div>
  );
}
