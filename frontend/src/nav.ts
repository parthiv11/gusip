export const NAV = [
  { to: "/", label: "Control Room", cap: "view_live", shortcut: "1" },
  { to: "/map", label: "GIS", cap: "view_live", shortcut: "2" },
  { to: "/cameras", label: "Cameras", cap: "view_live", shortcut: "3" },
  { to: "/alerts", label: "Alerts", cap: "ack_alert", shortcut: "4" },
  { to: "/search", label: "Investigate", cap: "search", shortcut: "5" },
  { to: "/watchlist", label: "Watchlist", cap: "view_live", shortcut: "6" },
  { to: "/cases", label: "Cases", cap: "create_case", shortcut: "7" },
  { to: "/admin", label: "Admin", cap: "admin_stats", shortcut: "8" },
] as const;

export function pageTitle(pathname: string): string {
  if (pathname === "/") return "Control Room";
  const hit = NAV.find((n) => n.to !== "/" && pathname.startsWith(n.to));
  return hit?.label ?? "GUSIP";
}
