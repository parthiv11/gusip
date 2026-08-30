import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import {
  CameraTable,
  SortField,
  SortOrder,
} from "../components/camera-registry/CameraTable";
import { FilterDropdown, FilterOption } from "../components/camera-registry/FilterDropdown";
import { Pagination } from "../components/camera-registry/Pagination";
import { SearchBar } from "../components/camera-registry/SearchBar";
import { groupCameras, RegistryCamera } from "../components/camera-registry/cameraData";
import type { Camera } from "../types";

function toRegistry(c: Camera): RegistryCamera {
  return {
    id: c.id,
    code: c.code,
    name: c.name,
    city: c.city || "Unknown",
    source_type: (c.source_type || "rtsp").toUpperCase(),
    camera_type: c.camera_type || "ip",
    status: c.status === "offline" ? "offline" : "online",
    amc_status: c.amc_status === "expired" ? "expired" : "active",
    department: c.department?.name || "",
  };
}

export default function CamerasPage() {
  const [cameras, setCameras] = useState<RegistryCamera[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [deptFilter, setDeptFilter] = useState("all");
  const [cityFilter, setCityFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [sortField, setSortField] = useState<SortField>("code");
  const [sortOrder, setSortOrder] = useState<SortOrder>("asc");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [expandedCities, setExpandedCities] = useState<Record<string, boolean>>({});
  const [error, setError] = useState("");

  useEffect(() => {
    api<Camera[]>("/api/v1/cameras")
      .then((rows) => setCameras(rows.map(toRegistry)))
      .catch((err) => setError(String(err)));
  }, []);

  const filtered = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return cameras.filter((c) => {
      if (statusFilter !== "all" && c.status !== statusFilter) return false;
      if (deptFilter !== "all" && c.department !== deptFilter) return false;
      if (cityFilter !== "all" && c.city !== cityFilter) return false;
      if (sourceFilter !== "all" && c.source_type !== sourceFilter) return false;
      if (!q) return true;
      return (
        c.code.toLowerCase().includes(q) ||
        c.name.toLowerCase().includes(q) ||
        c.city.toLowerCase().includes(q)
      );
    });
  }, [cameras, searchQuery, statusFilter, deptFilter, cityFilter, sourceFilter]);

  const sorted = useMemo(() => {
    const copy = [...filtered];
    copy.sort((a, b) => {
      const av = String(a[sortField] ?? "");
      const bv = String(b[sortField] ?? "");
      const cmp = av.localeCompare(bv, undefined, { numeric: true, sensitivity: "base" });
      return sortOrder === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [filtered, sortField, sortOrder]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const pageRows = sorted.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const groups = useMemo(() => groupCameras(pageRows), [pageRows]);

  const onlineCount = cameras.filter((c) => c.status === "online").length;
  const offlineCount = cameras.filter((c) => c.status === "offline").length;
  const cities = [...new Set(cameras.map((c) => c.city))].sort();
  const depts = [...new Set(cameras.map((c) => c.department).filter(Boolean))].sort();
  const sources = [...new Set(cameras.map((c) => c.source_type))].sort();

  const statusOptions: FilterOption[] = [
    { value: "all", label: "All status" },
    { value: "online", label: `Online (${onlineCount})` },
    { value: "offline", label: `Offline (${offlineCount})` },
  ];
  const departmentOptions: FilterOption[] = [
    { value: "all", label: "All departments" },
    ...depts.map((d) => ({ value: d, label: d })),
  ];
  const cityOptions: FilterOption[] = [
    { value: "all", label: "All cities" },
    ...cities.map((c) => ({ value: c, label: c })),
  ];
  const sourceOptions: FilterOption[] = [
    { value: "all", label: "All sources" },
    ...sources.map((s) => ({ value: s, label: s })),
  ];

  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, statusFilter, deptFilter, cityFilter, sourceFilter, pageSize]);

  return (
    <div className="h-full p-4 overflow-auto bg-[#0B0D10]">
      <div className="flex flex-col lg:flex-row lg:items-center gap-3 mb-4">
        <h1 className="text-lg font-semibold text-[#F2F4F7]">Camera registry</h1>
        <div className="lg:ml-auto flex flex-wrap items-center gap-2">
          <SearchBar value={searchQuery} onChange={setSearchQuery} />
          <FilterDropdown value={statusFilter} options={statusOptions} onChange={setStatusFilter} />
          <FilterDropdown value={cityFilter} options={cityOptions} onChange={setCityFilter} />
          <FilterDropdown value={sourceFilter} options={sourceOptions} onChange={setSourceFilter} />
          <FilterDropdown value={deptFilter} options={departmentOptions} onChange={setDeptFilter} />
        </div>
      </div>
      {error && <div className="text-red-400 text-xs mb-2">{error}</div>}
      <CameraTable
        groups={groups}
        expandedCities={expandedCities}
        onToggleCity={(city) =>
          setExpandedCities((prev) => ({ ...prev, [city]: !(prev[city] ?? true) }))
        }
        sortField={sortField}
        sortOrder={sortOrder}
        onSort={(field) => {
          if (sortField === field) setSortOrder((o) => (o === "asc" ? "desc" : "asc"));
          else {
            setSortField(field);
            setSortOrder("asc");
          }
        }}
      />
      <Pagination
        currentPage={Math.min(currentPage, totalPages)}
        totalPages={totalPages}
        totalItems={sorted.length}
        pageSize={pageSize}
        onPageChange={setCurrentPage}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setCurrentPage(1);
        }}
      />
    </div>
  );
}
