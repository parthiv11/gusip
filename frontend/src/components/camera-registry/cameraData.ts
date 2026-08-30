export interface RegistryCamera {
  id: number;
  code: string;
  name: string;
  city: string;
  source_type: string;
  camera_type: string;
  status: "online" | "offline" | string;
  amc_status: "active" | "expired" | string;
  department: string;
}

export interface CityCameraGroup {
  city: string;
  cityNameUppercase: string;
  totalCount: number;
  cameras: RegistryCamera[];
}

export function groupCameras(cameras: RegistryCamera[]): CityCameraGroup[] {
  const byCity = new Map<string, RegistryCamera[]>();
  for (const cam of cameras) {
    const city = cam.city?.trim() || "Unknown";
    const list = byCity.get(city);
    if (list) list.push(cam);
    else byCity.set(city, [cam]);
  }
  return [...byCity.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([city, cams]) => ({
      city,
      cityNameUppercase: city.toUpperCase(),
      totalCount: cams.length,
      cameras: cams,
    }));
}
