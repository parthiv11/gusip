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
        critical: {
          red: "#D94848",
          bg: "rgba(217, 72, 72, 0.10)",
          border: "rgba(217, 72, 72, 0.40)",
        },
        warning: {
          orange: "#E58A27",
          bg: "rgba(229, 138, 39, 0.10)",
          border: "rgba(229, 138, 39, 0.40)",
        },
        blacklisted: {
          yellow: "#D8B431",
          bg: "rgba(216, 180, 49, 0.10)",
          border: "rgba(216, 180, 49, 0.40)",
        },
        online: {
          green: "#35B86B",
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
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "IBM Plex Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
