import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0B0D10",
        panel: {
          primary: "#11151C",
          secondary: "#151A22",
          border: "rgba(255, 255, 255, 0.10)",
        },
        text: {
          primary: "#F2F4F7",
          secondary: "#9AA4B2",
          muted: "#667085",
        },
        amber: {
          gold: "#D9A441",
          hover: "#E8B858",
          tint: "rgba(217, 164, 65, 0.10)",
        },
        ink: {
          950: "#0B0D10",
          900: "#11151C",
          800: "#151A22",
          700: "#1E2430",
        },
        brass: {
          400: "#E8B858",
          500: "#D9A441",
        },
      },
      fontFamily: {
        sans: ["Inter", "IBM Plex Sans", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "IBM Plex Mono", "ui-monospace", "monospace"],
      },
      keyframes: {
        "spin-slow": {
          from: { transform: "rotate(0deg)" },
          to: { transform: "rotate(360deg)" },
        },
      },
      animation: {
        "spin-slow": "spin-slow 8s linear infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
