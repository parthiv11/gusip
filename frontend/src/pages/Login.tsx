import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api/client";
import ThemeToggle from "../components/ThemeToggle";

export default function Login() {
  const nav = useNavigate();
  const [username, setUsername] = useState("operator");
  const [password, setPassword] = useState("GUSIP@ops2026");
  const [error, setError] = useState("");
  const [authProvider, setAuthProvider] = useState<"local" | "oidc">("local");

  useEffect(() => {
    document.title = "Sign in · GUSIP";
    fetch("/api/v1/meta")
      .then((response) => response.json())
      .then((meta) => setAuthProvider(meta.auth_provider === "oidc" ? "oidc" : "local"))
      .catch(() => undefined);
  }, []);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await login(username, password);
      nav("/");
    } catch {
      setError("Authentication failed. Check credentials.");
    }
  }

  return (
    <div className="h-full grid place-items-center bg-ink-950 p-4 relative">
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>
      <form onSubmit={onSubmit} className="w-full max-w-[420px] border border-white/10 bg-ink-900/80 p-6 sm:p-8 rounded-lg shadow-2xl" aria-labelledby="login-title">
        <div className="flex items-center gap-3 mb-6">
          <div className="h-12 w-12 bg-brass-500 text-ink-950 font-bold grid place-items-center rounded" aria-hidden>
            GP
          </div>
          <div>
            <h1 id="login-title" className="text-xl font-semibold text-brass-400">
              GUSIP
            </h1>
            <p className="text-[10px] sm:text-xs text-slate-400 uppercase tracking-[0.2em]">Gujarat Police Innovation Challenge 2026</p>
          </div>
        </div>
        <p className="text-sm text-slate-300 mb-6">
          Gujarat Unified Surveillance Intelligence Platform — authorised personnel only.
        </p>
        {authProvider === "local" && (
          <>
            <label htmlFor="username" className="block text-xs text-slate-400 mb-1">
              Username
            </label>
            <input
              id="username"
              name="username"
              autoComplete="username"
              className="w-full mb-3 bg-ink-950 border border-white/10 rounded px-3 py-2 text-sm"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? "login-error" : undefined}
            />
            <label htmlFor="password" className="block text-xs text-slate-400 mb-1">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              className="w-full mb-4 bg-ink-950 border border-white/10 rounded px-3 py-2 text-sm"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? "login-error" : undefined}
            />
          </>
        )}
        {error && (
          <div id="login-error" className="text-red-400 text-xs mb-3" role="alert">
            {error}
          </div>
        )}
        {authProvider === "oidc" ? (
          <button
            type="button"
            className="w-full bg-brass-500 text-ink-950 font-semibold py-2 rounded text-sm"
            onClick={() => {
              window.location.href = "/api/v1/auth/oidc/login";
            }}
          >
            Sign in with Police SSO
          </button>
        ) : (
          <button type="submit" className="w-full bg-brass-500 text-ink-950 font-semibold py-2 rounded text-sm">
            Sign in
          </button>
        )}
        {authProvider === "local" && (
          <div className="mt-4 text-[11px] text-slate-500 font-mono leading-5">
            operator / GUSIP@ops2026
            <br />
            investigator / GUSIP@inv2026
            <br />
            coordinator / GUSIP@coord2026
            <br />
            admin / GUSIP@admin2026
            <p className="mt-2 font-sans text-slate-500 leading-4">
              Admin is the super administrator: custom roles, assign/remove, statewide. Operator, investigator, and coordinator are home-department scoped. Investigator can break-glass for a statewide trail.
            </p>
          </div>
        )}
      </form>
    </div>
  );
}
