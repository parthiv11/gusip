import { FormEvent, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Bell,
  Camera,
  Clock,
  Folder,
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
import { api, can, getSession, hasRealSession, refreshSession, setSession } from "../api/client";
import type { BreakGlass, Session } from "../types";

const NAV = [
  { to: "/", label: "Control Room", icon: LayoutGrid, cap: "view_live" },
  { to: "/map", label: "GIS", icon: Map, cap: "view_live" },
  { to: "/cameras", label: "Cameras", icon: Camera, cap: "view_live" },
  { to: "/alerts", label: "Alerts", icon: Bell, cap: "ack_alert" },
  { to: "/search", label: "Investigate", icon: Search, cap: "search" },
  { to: "/watchlist", label: "Watchlist", icon: Users, cap: "view_live" },
  { to: "/cases", label: "Cases", icon: Folder, cap: "create_case" },
];

export default function Shell() {
  const nav = useNavigate();
  const location = useLocation();
  const [session, setLocal] = useState<Session | null>(getSession());
  const [reason, setReason] = useState("FIR 112/2026 — suspect vehicle left home district");
  const [minutes, setMinutes] = useState(30);
  const [open, setOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [error, setError] = useState("");
  const [currentTime, setCurrentTime] = useState("21:27:08");

  useEffect(() => {
    // Only attempt to refresh session when a real token is stored
    if (hasRealSession()) {
      refreshSession()
        .then(setLocal)
        .catch(() => setLocal(getSession()));
    }
  }, []);


  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      const h = String(now.getHours()).padStart(2, "0");
      const m = String(now.getMinutes()).padStart(2, "0");
      const s = String(now.getSeconds()).padStart(2, "0");
      setCurrentTime(`${h}:${m}:${s}`);
    }, 1000);
    return () => clearInterval(timer);
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
    <div className="h-full flex flex-col relative bg-[#0B0D10] text-[#F2F4F7] select-none">
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
      
      {/* Top Navigation Bar */}
      <header className="shrink-0 h-[72px] bg-[#0B0D10] border-b border-white/[0.08] px-8 flex items-center justify-between z-20">
        {/* Left Side: GP Badge & Platform Title */}
        <div className="flex items-center gap-3.5 min-w-0">
          <button
            className="lg:hidden text-[#9AA4B2] hover:text-white p-1 -ml-1"
            aria-label="Menu"
            onClick={() => setNavOpen((v) => !v)}
          >
            {navOpen ? <X size={18} /> : <Menu size={18} />}
          </button>

          <div className="h-10 w-10 shrink-0 rounded-[4px] bg-[#D9A441] text-[#0B0D10] font-extrabold text-[17px] flex items-center justify-center tracking-tight shadow-md">
            GP
          </div>
          <div className="min-w-0 flex flex-col justify-center">
            <div className="text-[17px] font-bold tracking-wide text-white leading-tight">
              GUSIP
            </div>
            <div className="text-[11px] font-normal text-[#8E9AA8] tracking-wider uppercase hidden sm:block truncate leading-tight mt-0.5">
              GUJARAT POLICE · UNIFIED SURVEILLANCE
            </div>
          </div>
        </div>

        {/* Center: Navigation Tabs */}
        <nav className="hidden lg:flex items-center gap-2">
          {NAV.filter((n) => can(n.cap)).map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-2 px-3.5 py-1.5 text-[13.5px] font-medium transition-all rounded-[4px] ${
                  isActive
                    ? "bg-[#10141D] text-[#D9A441] border border-[#D9A441] shadow-sm"
                    : "text-[#8E9AA8] hover:text-[#F2F4F7] hover:bg-white/[0.03]"
                }`
              }
            >
              <n.icon size={16} className="shrink-0" />
              <span>{n.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Right Side: Operator Info & Sign-Out */}
        <div className="flex items-center gap-5 shrink-0">
          {showBreakGlass && (
            <button
              className="text-[11px] px-2.5 py-1 border border-orange-500/40 bg-orange-500/10 text-orange-300 rounded-[3px] hover:bg-orange-500/20"
              onClick={() => setOpen(true)}
            >
              Break-glass
            </button>
          )}
          <div className="text-right hidden md:block">
            <div className="text-[13.5px] font-medium text-[#F2F4F7] leading-tight">
              SOC Operator – Ahmedabad
            </div>
            <div className="text-[10.5px] text-[#687386] font-semibold tracking-wider uppercase leading-tight mt-0.5">
              CONTROL ROOM OPERATOR · STATEWIDE
            </div>
          </div>
          <button
            title="Sign out"
            className="text-[#8E9AA8] hover:text-[#F2F4F7] p-1.5 rounded hover:bg-white/5 transition-colors"
            onClick={() => {
              setSession(null);
              nav("/login");
            }}
          >
            <LogOut size={17} />
          </button>
        </div>
      </header>

      {/* Critical Alert Ticker */}
      {["/", "/alerts", "/watchlist"].includes(location.pathname) && (
        <div className="shrink-0 h-[42px] bg-[#12080B] border-b border-[#D84A4A]/25 px-8 flex items-center justify-between text-xs overflow-hidden">
          <div className="flex items-center gap-3 min-w-0">
            <span className="px-2 py-0.5 rounded-[3px] border border-[#D84A4A]/80 bg-[#D84A4A]/15 text-[#D84A4A] text-[11px] font-bold tracking-wider uppercase shrink-0">
              CRITICAL
            </span>
            <div className="truncate text-[#9E5D5D] text-[12.5px] flex items-center gap-1.5">
              <span>Watchlist hit</span>
              <span className="text-[#663333]">·</span>
              <span className="text-[#F2F4F7] font-bold">STOLEN VEHICLE</span>
              <span className="text-[#663333]">·</span>
              <span className="font-mono text-[#F2F4F7] font-bold">GJ 01 ST 0001</span>
              <span className="text-[#663333]">·</span>
              <span className="font-mono text-[#8E9AA8]">GNR-HW-01</span>
              <span className="text-[#663333]">·</span>
              <span className="text-[#8E9AA8]">Hit count:</span>
              <span className="font-mono text-[#F2F4F7] font-bold">x8</span>
            </div>
          </div>
          <div className="flex items-center gap-1.5 font-mono text-[13px] text-[#D84A4A] font-semibold tracking-wider shrink-0 pl-4">
            <span>{currentTime}</span>
          </div>
        </div>
      )}

      {/* Mobile navigation drawer */}
      {navOpen && (
        <nav className="lg:hidden grid grid-cols-2 sm:grid-cols-3 gap-1 px-3 py-2 bg-[#11151C] border-b border-white/10 shrink-0 z-30">
          {NAV.filter((n) => can(n.cap)).map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              onClick={() => setNavOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-2 px-3 py-2 rounded text-xs font-medium ${
                  isActive ? "bg-[#151A22] text-[#D9A441] border border-[#D9A441]/80" : "text-[#9AA4B2] hover:text-white bg-white/5"
                }`
              }
            >
              <n.icon size={14} />
              {n.label}
            </NavLink>
          ))}
        </nav>
      )}
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
