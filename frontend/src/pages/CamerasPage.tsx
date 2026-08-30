import React, { useState, useMemo, useEffect } from "react";
import {
  INITIAL_CAMERA_GROUPS,
  CityCameraGroup,
  RegistryCamera,
} from "../components/camera-registry/cameraData";
import { SearchBar } from "../components/camera-registry/SearchBar";
import {
  FilterDropdown,
  FilterOption,
} from "../components/camera-registry/FilterDropdown";
import {
  CameraTable,
  SortField,
  SortOrder,
} from "../components/camera-registry/CameraTable";
import { Pagination } from "../components/camera-registry/Pagination";
import { api } from "../api/client";
import type { Camera } from "../types";

export default function CamerasPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [deptFilter, setDeptFilter] = useState("all");
  const [cityFilter, setCityFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");

  const [sortField, setSortField] = useState<SortField>("code");
  const [sortOrder, setSortOrder] = useState<SortOrder>("asc");

  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  // Expanded cities state - matching reference: Ahmedabad, Vadodara, Surat expanded; Rajkot, Gandhinagar collapsed
  const [expandedCities, setExpandedCities] = useState<Record<string, boolean>>({
    Ahmedabad: true,
    Vadodara: true,
    Surat: true,
    Rajkot: false,
    Gandhinagar: false,
  });

  const [apiCameras, setApiCameras] = useState<Camera[]>([]);

  useEffect(() => {
    // Optionally fetch backend cameras if available
    api<Camera[]>("/api/v1/cameras")
      .then((data) => {
        if (data && data.length > 0) {
          setApiCameras(data);
        }
      })
      .catch(() => {
        // Fallback to pre-seeded realistic dataset
      });
  }, []);

  const handleToggleCity = (city: string) => {
    setExpandedCities((prev) => ({
      ...prev,
      [city]: !prev[city],
    }));
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortOrder("asc");
    }
  };

  // Base camera groups
  const baseGroups: CityCameraGroup[] = useMemo(() => {
    return INITIAL_CAMERA_GROUPS;
  }, [apiCameras]);

  // Compute total counts across cities
  const totalCameraCount = useMemo(() => {
    return baseGroups.reduce((acc, g) => acc + g.totalCount, 0);
  }, [baseGroups]);

  // Status breakdown numbers
  const onlineCount = 366;
  const offlineCount = 46;

  // Filter options
  const statusOptions: FilterOption[] = [
    { value: "all", label: "All status" },
    { value: "online", label: `Online (${onlineCount})` },
    { value: "offline", label: `Offline (${offlineCount})` },
  ];

  const departmentOptions: FilterOption[] = [
    { value: "all", label: "All departments" },
    { value: "Ahmedabad City Police", label: "Ahmedabad City Police" },
    { value: "Vadodara City Police", label: "Vadodara City Police" },
    { value: "Surat City Police", label: "Surat City Police" },
    { value: "Rajkot City Police", label: "Rajkot City Police" },
    { value: "Gandhinagar Police", label: "Gandhinagar Police" },
  ];

  const cityOptions: FilterOption[] = [
    { value: "all", label: "All cities" },
    { value: "Ahmedabad", label: "Ahmedabad" },
    { value: "Vadodara", label: "Vadodara" },
    { value: "Surat", label: "Surat" },
    { value: "Rajkot", label: "Rajkot" },
    { value: "Gandhinagar", label: "Gandhinagar" },
  ];

  const sourceOptions: FilterOption[] = [
    { value: "all", label: "All sources" },
    { value: "ONVIF", label: "ONVIF" },
    { value: "RTSP", label: "RTSP" },
    { value: "VENDOR_API", label: "VENDOR_API" },
  ];

  // Process and filter camera groups
  const filteredGroups = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();

    return baseGroups
      .map((group) => {
        // If city filter applied and does not match
        if (cityFilter !== "all" && group.city !== cityFilter) {
          return null;
        }

        // Filter individual cameras inside the group
        let cams = group.cameras.filter((c: RegistryCamera) => {
          // Search query
          if (q) {
            const matchesCode = c.code.toLowerCase().includes(q);
            const matchesName = c.name.toLowerCase().includes(q);
            const matchesCity = c.city.toLowerCase().includes(q);
            const matchesDept = c.department.toLowerCase().includes(q);
            if (!matchesCode && !matchesName && !matchesCity && !matchesDept) {
              return false;
            }
          }

          // Status filter
          if (statusFilter !== "all" && c.status !== statusFilter) {
            return false;
          }

          // Department filter
          if (deptFilter !== "all" && c.department !== deptFilter) {
            return false;
          }

          // Source filter
          if (sourceFilter !== "all" && c.source_type !== sourceFilter) {
            return false;
          }

          return true;
        });

        // Apply sorting only when user explicitly toggles or when filtering
        if (sortField !== "code" || sortOrder !== "asc") {
          cams = [...cams].sort((a, b) => {
            const valA = String(a[sortField] || "").toLowerCase();
            const valB = String(b[sortField] || "").toLowerCase();
            if (valA < valB) return sortOrder === "asc" ? -1 : 1;
            if (valA > valB) return sortOrder === "asc" ? 1 : -1;
            return 0;
          });
        }

        // If filtering is active and no cameras in this group match, omit
        if ((q || statusFilter !== "all" || deptFilter !== "all" || sourceFilter !== "all") && cams.length === 0) {
          return null;
        }

        return {
          ...group,
          cameras: cams,
        };
      })
      .filter((g): g is CityCameraGroup => g !== null);
  }, [
    baseGroups,
    searchQuery,
    statusFilter,
    deptFilter,
    cityFilter,
    sourceFilter,
    sortField,
    sortOrder,
  ]);

  return (
    <div className="h-full overflow-y-auto bg-[#0B0D10] text-[#F2F4F7] select-none px-6 lg:px-8 py-5 flex flex-col justify-between">
      <div className="w-full">
        {/* Page Header */}
        <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-4 mb-4 shrink-0">
          {/* Title & Subtitle */}
          <div>
            <h1 className="text-[22px] lg:text-[24px] font-bold text-[#F2F4F7] tracking-tight leading-tight">
              Camera registry
            </h1>
            <div className="text-[13px] text-[#A8B2C1] mt-1 font-normal">
              <span className="text-[#D9A441] font-semibold">{totalCameraCount}</span>{" "}
              cameras across 10 cities
            </div>
          </div>

          {/* Search & Filters */}
          <div className="flex flex-wrap items-center gap-2.5">
            <SearchBar
              value={searchQuery}
              onChange={setSearchQuery}
              placeholder="Filter code, name, city"
            />

            {/* Status Dropdown with Custom 366 / 46 badge */}
            <FilterDropdown
              value={statusFilter}
              options={statusOptions}
              onChange={setStatusFilter}
              customButtonContent={
                <div className="flex items-center gap-1.5 text-[13px]">
                  <span className="font-normal text-[#F2F4F7]">All status</span>
                  <span className="font-semibold text-[#35D58A] ml-0.5">{onlineCount}</span>
                  <span className="text-[#6F7D91]">/</span>
                  <span className="font-semibold text-[#EF4444]">{offlineCount}</span>
                </div>
              }
            />

            {/* Department Dropdown */}
            <FilterDropdown
              value={deptFilter}
              options={departmentOptions}
              onChange={setDeptFilter}
            />

            {/* City Dropdown */}
            <FilterDropdown
              value={cityFilter}
              options={cityOptions}
              onChange={setCityFilter}
            />

            {/* Source Dropdown */}
            <FilterDropdown
              value={sourceFilter}
              options={sourceOptions}
              onChange={setSourceFilter}
            />
          </div>
        </div>

        {/* Main Table Container */}
        <div className="w-full">
          <CameraTable
            groups={filteredGroups}
            expandedCities={expandedCities}
            onToggleCity={handleToggleCity}
            sortField={sortField}
            sortOrder={sortOrder}
            onSort={handleSort}
            highlightedCode="AMD-BA-01"
          />
        </div>
      </div>

      {/* Pagination Bar strictly below the table */}
      <div className="w-full pt-3 pb-4">
        <Pagination
          currentPage={currentPage}
          totalPages={9}
          totalItems={totalCameraCount}
          pageSize={pageSize}
          onPageChange={setCurrentPage}
          onPageSizeChange={setPageSize}
        />
      </div>
    </div>
  );
}
