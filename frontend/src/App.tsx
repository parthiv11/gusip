import { useEffect, useState, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { getSession, restoreSession } from "./api/client";
import Shell from "./components/Shell";
import Login from "./pages/Login";
import ControlRoom from "./pages/ControlRoom";
import MapPage from "./pages/MapPage";
import CamerasPage from "./pages/CamerasPage";
import AlertsPage from "./pages/AlertsPage";
import SearchPage from "./pages/SearchPage";
import WatchlistPage from "./pages/WatchlistPage";
import CasesPage from "./pages/CasesPage";
import AdminPage from "./pages/AdminPage";

function RequireAuth({ children }: { children: ReactNode }) {
  const [state, setState] = useState<"loading" | "authenticated" | "anonymous">(
    getSession() ? "authenticated" : "loading",
  );
  useEffect(() => {
    if (state !== "loading") return;
    restoreSession().then((session) => setState(session ? "authenticated" : "anonymous"));
  }, [state]);
  if (state === "loading") return <div className="h-full grid place-items-center text-slate-400">Validating session…</div>;
  if (state === "anonymous") return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            <Shell />
          </RequireAuth>
        }
      >
        <Route index element={<ControlRoom />} />
        <Route path="map" element={<MapPage />} />
        <Route path="cameras" element={<CamerasPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="watchlist" element={<WatchlistPage />} />
        <Route path="cases" element={<CasesPage />} />
        <Route path="admin" element={<AdminPage />} />
      </Route>
    </Routes>
  );
}
