import type { Session } from "../types";

const TOKEN_KEY = "gusip.session";

function cookie(name: string): string | undefined {
  const prefix = `${encodeURIComponent(name)}=`;
  return document.cookie
    .split("; ")
    .find((part) => part.startsWith(prefix))
    ?.slice(prefix.length);
}

export function getSession(): Session | null {
  const raw = sessionStorage.getItem(TOKEN_KEY);
  return raw ? (JSON.parse(raw) as Session) : null;
}

export function setSession(s: Session | null) {
  if (!s) sessionStorage.removeItem(TOKEN_KEY);
  else sessionStorage.setItem(TOKEN_KEY, JSON.stringify(s));
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData) && !headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  const method = (init.method || "GET").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrf = cookie("gusip_csrf");
    if (csrf) headers.set("X-CSRF-Token", decodeURIComponent(csrf));
  }
  const res = await fetch(path, { ...init, headers, credentials: "same-origin" });
  if (res.status === 401) {
    setSession(null);
    if (!path.includes("/auth/token")) window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function login(username: string, password: string): Promise<Session> {
  const body = new URLSearchParams({ username, password });
  const res = await fetch("/api/v1/auth/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
    credentials: "same-origin",
  });
  if (!res.ok) throw new Error("Invalid credentials");
  const data = await res.json();
  const session: Session = {
    username: data.username,
    full_name: data.full_name,
    role: data.role,
    department_id: data.department_id,
    capabilities: data.capabilities ?? [],
    scope: data.scope ?? "statewide",
    break_glass: data.break_glass ?? null,
  };
  setSession(session);
  return session;
}

export async function logout(): Promise<void> {
  try {
    await api<void>("/api/v1/auth/logout", { method: "POST" });
  } finally {
    setSession(null);
  }
}

export function can(action: string): boolean {
  const session = getSession();
  if (!session) return false;
  if (session.role === "system_admin") return true;
  const caps = session.capabilities;
  if (caps && caps.length) return caps.includes(action);
  const fallback: Record<string, string[]> = {
    control_room_operator: ["view_live", "ack_alert", "search", "create_case"],
    investigation_officer: ["view_live", "ack_alert", "search", "export", "watchlist_write", "create_case", "break_glass"],
    department_coordinator: [
      "view_live",
      "ack_alert",
      "search",
      "export",
      "watchlist_write",
      "onboard_camera",
      "admin_stats",
      "create_case",
      "break_glass",
    ],
  };
  return (fallback[session.role] ?? []).includes(action);
}

export async function refreshSession(): Promise<Session | null> {
  const session = getSession();
  if (!session) return null;
  const me = await api<{
    capabilities: string[];
    scope: string;
    break_glass: Session["break_glass"];
    full_name: string;
    role: Session["role"];
    department_id: number | null;
  }>("/api/v1/auth/me");
  const next: Session = {
    ...session,
    capabilities: me.capabilities ?? [],
    scope: me.scope,
    break_glass: me.break_glass ?? null,
    full_name: me.full_name,
    role: me.role,
    department_id: me.department_id,
  };
  setSession(next);
  return next;
}

export async function restoreSession(): Promise<Session | null> {
  const res = await fetch("/api/v1/auth/me", { credentials: "same-origin" });
  if (!res.ok) return null;
  const me = await res.json();
  const session: Session = {
    username: me.username,
    full_name: me.full_name,
    role: me.role,
    department_id: me.department_id,
    capabilities: me.capabilities ?? [],
    scope: me.scope ?? "department",
    break_glass: me.break_glass ?? null,
  };
  setSession(session);
  return session;
}

export function wsUrl(path: string): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}${path}`;
}

export function evidenceUrl(path?: string | null): string | undefined {
  return path || undefined;
}
