import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import type { LucideIcon } from "lucide-react";
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
import { api, can, getSession, logout, refreshSession } from "../api/client";
import { NAV, pageTitle } from "../nav";
import { toggleTheme } from "../theme";
import ThemeToggle from "./ThemeToggle";
import type { BreakGlass, Session } from "../types";

const ICONS: Record<(typeof NAV)[number]["to"], LucideIcon> = {
  "/": LayoutGrid,
  "/map": Map,
  "/cameras": Camera,
  "/alerts": Bell,
  "/search": Search,
  "/watchlist": Users,
  "/cases": FolderSearch,
  "/admin": Shield,
};

function documentTitle(pathname: string, search: string): string {
  const params = new URLSearchParams(search);
  const page = pageTitle(pathname);
  if (pathname === "/") {
    const wall = params.get("wall") || "demo";
    const wallLabel = wall === "gov" ? "Gov feeds" : wall === "all" ? "All cameras" : "Own/demo";
    return `Control Room · ${wallLabel} · GUSIP`;
  }
  if (pathname.startsWith("/search")) {
    const mode = params.get("mode") || "plate";
    const modeLabel = mode === "appearance" ? "Appearance" : mode === "face" ? "Face" : "Plate";
    return `Investigate · ${modeLabel} · GUSIP`;
  }
  if (pathname.startsWith("/admin")) {
    const tab = params.get("tab");
    const tabLabel = tab === "people" ? "People" : tab === "roles" ? "Roles" : tab === "audit" ? "Audit" : "Admin";
    return `${tabLabel} · GUSIP`;
  }
  return `${page} · GUSIP`;
}

export default function Shell() {
  const nav = useNavigate();
  const location = useLocation();
  const [session, setLocal] = useState<Session | null>(getSession());
  const [reason, setReason] = useState("FIR 112/2026 — suspect vehicle left home district");
  const [minutes, setMinutes] = useState(30);
  const [open, setOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [error, setError] = useState("");
  const reasonRef = useRef<HTMLTextAreaElement>(null);
  const items = useMemo(() => NAV.filter((n) => can(n.cap)), [session]);

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

  useEffect(() => {
    document.title = documentTitle(location.pathname, location.search);
  }, [location.pathname, location.search]);

  useEffect(() => {
    setNavOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (open) reasonRef.current?.focus();
  }, [open]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement | null;
      const typing =
        t?.tagName === "INPUT" ||
        t?.tagName === "TEXTAREA" ||
        t?.tagName === "SELECT" ||
        Boolean(t?.isContentEditable);
      if (e.key === "Escape") {
        setNavOpen(false);
        setOpen(false);
        return;
      }
      if (typing) return;
      if (e.key === "/" && can("search")) {
        e.preventDefault();
        nav("/search");
        return;
      }
      if (e.altKey && e.shiftKey && (e.key === "L" || e.key === "l" || e.key === "D" || e.key === "d")) {
        e.preventDefault();
        toggleTheme();
        return;
      }
      if (e.altKey && !e.ctrlKey && !e.metaKey) {
        const hit = items.find((n) => n.shortcut === e.key);
        if (hit) {
          e.preventDefault();
          nav(hit.to);
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [items, nav]);

  const glass = session?.break_glass;
  const showBreakGlass = can("break_glass") && session?.scope === "department";
  const here = pageTitle(location.pathname);

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
      <a href="#main" className="skip-link">
        Skip to main content
      </a>
      <p className="sr-only">
        Press Alt plus 1 through 8 to switch pages. Press slash to open Investigate. Press Escape to close menus. Press Alt Shift L to toggle light and dark.
      </p>
      {glass?.active && (
        <div
          className="shrink-0 bg-orange-500/15 text-orange-200 text-[11px] px-3 sm:px-4 py-1.5 flex items-center gap-2 sm:gap-3 border-b border-orange-500/30"
          role="status"
          aria-live="polite"
        >
          <Unlock size={12} className="shrink-0" aria-hidden />
          <span className="font-semibold uppercase tracking-wide hidden sm:inline">Break-glass statewide</span>
          <span className="truncate flex-1">{glass.reason}</span>
          <span className="font-mono hidden md:inline">until {new Date(glass.expires_at).toLocaleTimeString("en-IN")}</span>
          <button type="button" className="underline shrink-0" onClick={revokeGlass}>
            End now
          </button>
        </div>
      )}
      <header className="shrink-0 border-b border-white/10 bg-ink-900">
        <div className="flex items-center px-3 sm:px-4 gap-2 sm:gap-4 min-h-14">
          <button
            type="button"
            className="lg:hidden text-slate-300 p-1.5 -ml-1"
            aria-label={navOpen ? "Close menu" : "Open menu"}
            aria-expanded={navOpen}
            aria-controls="primary-nav"
            onClick={() => setNavOpen((v) => !v)}
          >
            {navOpen ? <X size={18} aria-hidden /> : <Menu size={18} aria-hidden />}
          </button>
          <div className="flex items-center gap-2 sm:gap-3 min-w-0">
            <div className="h-8 w-8 shrink-0 rounded-sm bg-brass-500 text-ink-950 font-bold grid place-items-center" aria-hidden>
              GP
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold tracking-wide text-brass-400">GUSIP</div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-slate-400 hidden sm:block truncate">
                Gujarat Police · Unified Surveillance
              </div>
            </div>
          </div>
          <p className="lg:hidden text-xs text-slate-300 truncate" aria-current="page">
            {here}
          </p>
          <nav className="hidden lg:flex flex-1 items-center gap-1 ml-6 overflow-x-auto" aria-label="Primary">
            {items.map((n) => {
              const Icon = ICONS[n.to];
              return (
                <NavLink
                  key={n.to}
                  to={n.to}
                  end={n.to === "/"}
                  title={`Alt+${n.shortcut}`}
                  className={({ isActive }) =>
                    `flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium whitespace-nowrap ${
                      isActive ? "bg-white/10 text-brass-400" : "text-slate-400 hover:text-white"
                    }`
                  }
                >
                  <Icon size={14} aria-hidden />
                  {n.label}
                </NavLink>
              );
            })}
          </nav>
          <div className="ml-auto flex items-center gap-2 sm:gap-3 shrink-0">
            {showBreakGlass && (
              <button
                type="button"
                className="text-[11px] px-2 py-1 border border-orange-500/40 text-orange-300 rounded"
                aria-haspopup="dialog"
                aria-expanded={open}
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
            <ThemeToggle />
            <button
              type="button"
              className="text-slate-400 hover:text-white p-1"
              aria-label="Sign out"
              onClick={async () => {
                await logout();
                nav("/login");
              }}
            >
              <LogOut size={16} aria-hidden />
            </button>
          </div>
        </div>
        {navOpen && (
          <nav id="primary-nav" className="lg:hidden grid grid-cols-2 sm:grid-cols-3 gap-1 px-3 pb-3" aria-label="Primary">
            {items.map((n) => {
              const Icon = ICONS[n.to];
              return (
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
                  <Icon size={14} aria-hidden />
                  {n.label}
                </NavLink>
              );
            })}
          </nav>
        )}
      </header>
      {open && (
        <div
          className="fixed inset-0 z-20 bg-black/60 grid place-items-center p-4"
          role="presentation"
          onClick={() => setOpen(false)}
        >
          <form
            role="dialog"
            aria-modal="true"
            aria-labelledby="break-glass-title"
            onSubmit={requestGlass}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-md bg-ink-900 border border-orange-500/40 rounded p-4 space-y-3"
          >
            <h2 id="break-glass-title" className="text-sm font-semibold text-orange-300">
              Time-boxed statewide access
            </h2>
            <p className="text-xs text-slate-400">
              Opens cameras outside your department. Reason is written to the audit log. Access expires automatically.
            </p>
            <label htmlFor="break-glass-reason" className="block text-xs text-slate-400">
              Reason
            </label>
            <textarea
              id="break-glass-reason"
              ref={reasonRef}
              className="w-full bg-ink-950 border border-white/10 rounded px-3 py-2 text-sm min-h-[80px]"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              minLength={16}
              required
            />
            <label className="text-xs text-slate-400 flex items-center gap-2" htmlFor="break-glass-duration">
              Duration
              <select
                id="break-glass-duration"
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
            {error && (
              <div className="text-red-400 text-xs" role="alert">
                {error}
              </div>
            )}
            <div className="flex justify-end gap-2">
              <button type="button" className="text-xs px-3 py-1.5" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button type="submit" className="text-xs px-3 py-1.5 bg-orange-500 text-ink-950 rounded font-semibold">
                Grant access
              </button>
            </div>
          </form>
        </div>
      )}
      <main id="main" tabIndex={-1} className="flex-1 min-h-0 outline-none">
        <Outlet />
      </main>
    </div>
  );
}
