export type Role =
  | "system_admin"
  | "control_room_operator"
  | "investigation_officer"
  | "department_coordinator";

export interface BreakGlass {
  active: boolean;
  reason: string;
  granted_at: string;
  expires_at: string;
  duration_minutes: number;
  home_department_id?: number | null;
}

export interface Session {
  username: string;
  full_name: string;
  role: Role;
  department_id: number | null;
  capabilities?: string[];
  scope?: "statewide" | "department" | string;
  break_glass?: BreakGlass | null;
}

export interface Camera {
  id: number;
  code: string;
  name: string;
  department_id: number;
  camera_type: string;
  ownership: string;
  source_type: string;
  vendor?: string | null;
  status: string;
  connectivity: string;
  amc_status: string;
  coverage_radius_m: number;
  latitude: number;
  longitude: number;
  city: string;
  address?: string | null;
  last_seen_at?: string | null;
  extra?: Record<string, unknown>;
  department?: { id: number; code: string; name: string; zone: string } | null;
}

export interface Alert {
  id: number;
  camera_id: number;
  timestamp: string;
  confidence: number;
  snapshot_url?: string | null;
  status: string;
  payload: Record<string, unknown>;
  camera?: Camera | null;
  watchlist?: {
    id: number;
    category: string;
    name?: string | null;
    plate_number?: string | null;
    description?: string | null;
    priority: string;
    entity_type: string;
  } | null;
}

export interface EventItem {
  id: number;
  camera_id: number;
  timestamp: string;
  event_type: string;
  object_type: string;
  global_track_id?: string | null;
  plate_number?: string | null;
  plate_normalized?: string | null;
  confidence: number;
  snapshot_url?: string | null;
  clip_url?: string | null;
  attributes: Record<string, unknown>;
  bbox: Record<string, number>;
}

export interface TrackPoint {
  id?: number;
  global_track_id: string;
  camera_id: number;
  timestamp: string;
  latitude: number;
  longitude: number;
  camera_code?: string | null;
  camera_name?: string | null;
  city?: string | null;
  plate_normalized?: string | null;
  hits?: number;
  first_seen?: string | null;
}

export interface LiveDetection {
  camera_id: number;
  camera_code: string;
  city: string;
  lat: number;
  lon: number;
  timestamp: string;
  object_type: string;
  plate?: string | null;
  global_track_id?: string;
  confidence: number;
  bbox?: { x: number; y: number; w: number; h: number };
  attributes?: Record<string, unknown>;
}
