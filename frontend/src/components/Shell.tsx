import { FormEvent, useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Bell,
  Camera,
  FolderSearch,
  LayoutGrid,
  LogOut,
  Map,
  Search,
  Shield,
  Unlock,
  Users,
  Menu,
  X,
} from "lucide-react";
import { api, can, getSession, refreshSession, setSession } from "../api/client";
import type { BreakGlass, Session } from "../types";

const NAV = [
  { to: "/", label: "Control Room", icon: LayoutGrid, cap: "view_live" },
  { to: "/map", label: "GIS", icon: Map, cap: "view_live" },
  { to: "/cameras", label: "Cameras", icon: Camera, cap: "view_live" },
  { to: "/alerts", label: "Alerts", icon: Bell, cap: "ack_alert" },
  { to: "/search", label: "Investigate", icon: Search, cap: "search" },
  { to: "/watchlist", label: "Watchlist", icon: Users, cap: "view_live" },
  { to: "/cases", label: "Cases", icon: FolderSearch, cap: "create_case" },
  { to: "/admin", label: "Admin", icon: Shield, cap: "admin_stats" },
];

export default function Shell() {
  const nav = useNavigate();
  const [session, setLocal] = useState<Session | null>(getSession());
  const [reason, setReason] = useState("FIR 112/2026 — suspect vehicle left home district");
  const [minutes, setMinutes] = useState(30);
  const [open, setOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    refreshSession()
      .then(setLocal)
      .catch(() => setLocal(getSession()));
  }, []);

  useEffect(() => {
    if (!session?.break_glass?.active) return;
    const t = window.setInterval(() => {
      refreshSession()
        .then(setLocal)
        .catch(() => undefined);
    }, 15000);
    return () => window.clearInterval(t);
  }, [session?.break_glass?.active]);

  const glass = session?.break_glass;
  const showBreakGlass = can("break_glass") && session?.scope === "department";

  async function requestGlass(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const g = await api<BreakGlass>("/api/v1/auth/break-glass", {
        method: "POST",
        body: JSON.stringify({ reason, duration_minutes: minutes }),
      });
      const next = await refreshSession();
      setLocal(next ? { ...next, break_glass: g } : getSession());
      setOpen(false);
    } catch (err) {
      setError(String(err));
    }
  }

  async function revokeGlass() {
    await api("/api/v1/auth/break-glass", { method: "DELETE" });
    setLocal(await refreshSession());
  }

  return (
    <div className="h-full flex flex-col relative">
      {glass?.active && (
        <div className="shrink-0 bg-orange-500/15 text-orange-200 text-[11px] px-3 sm:px-4 py-1.5 flex items-center gap-2 sm:gap-3 border-b border-orange-500/30">
          <Unlock size={12} className="shrink-0" />
          <span className="font-semibold uppercase tracking-wide hidden sm:inline">Break-glass statewide</span>
          <span className="truncate flex-1">{glass.reason}</span>
          <span className="font-mono hidden md:inline">until {new Date(glass.expires_at).toLocaleTimeString("en-IN")}</span>
          <button className="underline shrink-0" onClick={revokeGlass}>
            End now
          </button>
        </div>
      )}
      <header className="shrink-0 border-b border-white/10 bg-ink-900">
        <div className="flex items-center px-3 sm:px-4 gap-2 sm:gap-4 min-h-14">
          <button
            className="lg:hidden text-slate-300 p-1.5 -ml-1"
            aria-label="Menu"
            onClick={() => setNavOpen((v) => !v)}
          >
            {navOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <div className="h-8 w-8 shrink-0 rounded-sm bg-brass-500 text-ink-950 font-bold grid place-items-center">
              GP
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold tracking-wide text-brass-400">GUSIP</div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-slate-400 hidden sm:block truncate">
                Gujarat Police · Unified Surveillance
              </div>
            </div>
          </div>
          <nav className="hidden lg:flex flex-1 items-center gap-1 ml-6 overflow-x-auto">
            {NAV.filter((n) => can(n.cap)).map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === "/"}
                className={({ isActive }) =>
                  `flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium whitespace-nowrap ${
                    isActive ? "bg-white/10 text-brass-400" : "text-slate-400 hover:text-white"
                  }`
                }
              >
                <n.icon size={14} />
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2 sm:gap-3 shrink-0">
            {showBreakGlass && (
              <button
                className="text-[11px] px-2 py-1 border border-orange-500/40 text-orange-300 rounded"
                onClick={() => setOpen(true)}
              >
                Break-glass
              </button>
            )}
            <div className="text-right hidden md:block mr-1">
              <div className="text-xs font-medium">{session?.full_name}</div>
              <div className="text-[10px] uppercase tracking-wider text-slate-500">
                {session?.role?.replaceAll("_", " ")}
                {session?.scope === "department" ? " · home dept" : " · statewide"}
              </div>
            </div>
            <button
              className="text-slate-400 hover:text-white p-1"
              onClick={() => {
                setSession(null);
                nav("/login");
              }}
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
        {navOpen && (
          <nav className="lg:hidden grid grid-cols-2 sm:grid-cols-3 gap-1 px-3 pb-3">
            {NAV.filter((n) => can(n.cap)).map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === "/"}
                onClick={() => setNavOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-1.5 px-3 py-2 rounded text-xs font-medium ${
                    isActive ? "bg-white/10 text-brass-400" : "text-slate-400 hover:text-white bg-white/5"
                  }`
                }
              >
                <n.icon size={14} />
                {n.label}
              </NavLink>
            ))}
          </nav>
        )}
      </header>
      {open && (
        <div className="fixed inset-0 z-20 bg-black/60 grid place-items-center p-4">
          <form onSubmit={requestGlass} className="w-full max-w-md bg-ink-900 border border-orange-500/40 rounded p-4 space-y-3">
            <h2 className="text-sm font-semibold text-orange-300">Time-boxed statewide access</h2>
            <p className="text-xs text-slate-400">
              Opens cameras outside your department. Reason is written to the audit log. Access expires automatically.
            </p>
            <textarea
              className="w-full bg-ink-950 border border-white/10 rounded px-3 py-2 text-sm min-h-[80px]"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              minLength={16}
              required
            />
            <label className="text-xs text-slate-400 flex items-center gap-2">
              Duration
              <select
                className="bg-ink-950 border border-white/10 rounded px-2 py-1"
                value={minutes}
                onChange={(e) => setMinutes(Number(e.target.value))}
              >
                <option value={15}>15 min</option>
                <option value={30}>30 min</option>
                <option value={60}>60 min</option>
                <option value={120}>120 min</option>
              </select>
            </label>
            {error && <div className="text-red-400 text-xs">{error}</div>}
            <div className="flex justify-end gap-2">
              <button type="button" className="text-xs px-3 py-1.5" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button className="text-xs px-3 py-1.5 bg-orange-500 text-ink-950 rounded font-semibold">Grant access</button>
            </div>
          </form>
        </div>
      )}
      <main className="flex-1 min-h-0">
        <Outlet />
      </main>
    </div>
  );
}
