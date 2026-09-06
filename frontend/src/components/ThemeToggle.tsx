import { Moon, Sun } from "lucide-react";
import { useTheme } from "../theme";

export default function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const [theme, toggle] = useTheme();
  const light = theme === "light";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={light}
      aria-label={light ? "Switch to dark mode" : "Switch to light mode"}
      title={light ? "Dark mode" : "Light mode"}
      className={`text-slate-400 hover:text-white p-1.5 rounded border border-white/10 min-h-8 min-w-8 grid place-items-center ${
        compact ? "" : "sm:px-2 sm:gap-1.5 sm:flex sm:items-center"
      }`}
    >
      {light ? <Moon size={15} aria-hidden /> : <Sun size={15} aria-hidden />}
      {!compact && <span className="hidden sm:inline text-[11px] font-medium">{light ? "Dark" : "Light"}</span>}
    </button>
  );
}
