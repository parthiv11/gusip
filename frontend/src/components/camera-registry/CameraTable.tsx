import React from "react";
import { ChevronsUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { CityCameraGroup, RegistryCamera } from "./cameraData";
import { CityGroupRow } from "./CityGroupRow";
import { CameraRow } from "./CameraRow";

export type SortField = "code" | "name" | "city" | "source_type" | "camera_type" | "status" | "amc_status" | "department";
export type SortOrder = "asc" | "desc";

interface CameraTableProps {
  groups: CityCameraGroup[];
  expandedCities: Record<string, boolean>;
  onToggleCity: (city: string) => void;
  sortField: SortField;
  sortOrder: SortOrder;
  onSort: (field: SortField) => void;
  highlightedCode?: string;
}

export const CameraTable: React.FC<CameraTableProps> = ({
  groups,
  expandedCities,
  onToggleCity,
  sortField,
  sortOrder,
  onSort,
  highlightedCode,
}) => {
  const columns: { field: SortField; label: string; width?: string; align?: string }[] = [
    { field: "code", label: "CODE", width: "w-[150px]" },
    { field: "name", label: "NAME", width: "w-[240px]" },
    { field: "city", label: "CITY", width: "w-[150px]" },
    { field: "source_type", label: "SOURCE", width: "w-[130px]" },
    { field: "camera_type", label: "TYPE", width: "w-[100px]" },
    { field: "status", label: "STATUS", width: "w-[120px]" },
    { field: "amc_status", label: "AMC", width: "w-[110px]" },
    { field: "department", label: "DEPT", width: "flex-1" },
  ];

  return (
    <div className="w-full overflow-hidden rounded-[4px] border border-white/[0.07] bg-[#0B0F14]">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse min-w-[1050px]">
          {/* Header */}
          <thead>
            <tr className="h-[40px] bg-[#0D1219] border-b border-white/[0.07]">
              {columns.map((col, idx) => {
                const isActive = sortField === col.field;
                return (
                  <th
                    key={col.field}
                    onClick={() => onSort(col.field)}
                    className={`${idx === 0 ? "pl-6" : "px-4"} py-2 text-[11.5px] font-semibold tracking-wider text-[#6F7D91] uppercase cursor-pointer select-none hover:text-[#A8B2C1] transition-colors`}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className={isActive ? "text-[#F2F4F7]" : ""}>
                        {col.label}
                      </span>
                      {isActive ? (
                        sortOrder === "asc" ? (
                          <ArrowUp size={12} className="text-[#D9A441]" />
                        ) : (
                          <ArrowDown size={12} className="text-[#D9A441]" />
                        )
                      ) : (
                        <ChevronsUpDown size={12} className="text-[#4A5568]" />
                      )}
                    </div>
                  </th>
                );
              })}
              {/* Actions Header */}
              <th className="pr-5 pl-2 py-2 w-[48px]"></th>
            </tr>
          </thead>

          {/* Body */}
          <tbody>
            {groups.length === 0 ? (
              <tr>
                <td colSpan={9} className="py-12 text-center text-[#6F7D91] text-sm">
                  No cameras match the selected filters.
                </td>
              </tr>
            ) : (
              groups.map((group) => {
                const isExpanded = expandedCities[group.city] ?? true;
                return (
                  <React.Fragment key={group.city}>
                    {/* City Header Row */}
                    <CityGroupRow
                      cityName={group.cityNameUppercase}
                      count={group.totalCount}
                      isExpanded={isExpanded}
                      onToggle={() => onToggleCity(group.city)}
                      colSpan={9}
                    />

                    {/* Cameras in City */}
                    {isExpanded &&
                      group.cameras.map((cam: RegistryCamera) => (
                        <CameraRow
                          key={cam.id || cam.code}
                          camera={cam}
                          isHighlighted={cam.code === highlightedCode}
                        />
                      ))}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
