import { useEffect, useState } from "react";

export type Theme = "light" | "dark";

const KEY = "gusip.theme";
const listeners = new Set<(theme: Theme) => void>();

function systemTheme(): Theme {
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function readTheme(): Theme {
  try {
    const stored = localStorage.getItem(KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    /* private mode */
  }
  return systemTheme();
}

export function applyTheme(theme: Theme) {
  const root = document.documentElement;
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    /* private mode */
  }
  listeners.forEach((fn) => fn(theme));
}

export function toggleTheme() {
  applyTheme(readTheme() === "dark" ? "light" : "dark");
}

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() =>
    typeof document !== "undefined" && document.documentElement.dataset.theme === "light" ? "light" : "dark"
  );

  useEffect(() => {
    const current = readTheme();
    applyTheme(current);
    setTheme(current);
    const onChange = (next: Theme) => setTheme(next);
    listeners.add(onChange);
    return () => {
      listeners.delete(onChange);
    };
  }, []);

  return [theme, toggleTheme];
}
