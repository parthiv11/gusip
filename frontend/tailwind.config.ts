import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "rgb(var(--ink-950) / <alpha-value>)",
        panel: {
          primary: "rgb(var(--ink-900) / <alpha-value>)",
          secondary: "rgb(var(--ink-800) / <alpha-value>)",
          border: "rgb(var(--hairline) / <alpha-value>)",
        },
        text: {
          primary: "rgb(var(--fg) / <alpha-value>)",
          secondary: "rgb(var(--fg-muted) / <alpha-value>)",
          muted: "rgb(var(--fg-subtle) / <alpha-value>)",
        },
        amber: {
          gold: "rgb(var(--brass) / <alpha-value>)",
          hover: "rgb(var(--brass-bright) / <alpha-value>)",
          tint: "rgb(var(--brass) / 0.10)",
        },
        ink: {
          950: "rgb(var(--ink-950) / <alpha-value>)",
          900: "rgb(var(--ink-900) / <alpha-value>)",
          800: "rgb(var(--ink-800) / <alpha-value>)",
          700: "rgb(var(--ink-700) / <alpha-value>)",
        },
        brass: {
          400: "rgb(var(--brass-bright) / <alpha-value>)",
          500: "rgb(var(--brass) / <alpha-value>)",
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
