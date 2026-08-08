/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        /* ── Page & Card Surfaces ── */
        page: "#F4F6F8",
        card: "#FFFFFF",
        surface: {
          DEFAULT: "#FFFFFF",
          elevated: "#F8FAFC",
          hover: "#F1F5F9",
        },
        border: {
          DEFAULT: "#E2E8F0",
          soft: "#E2E8F0",
          medium: "#CBD5E1",
          bold: "#94A3B8",
        },
        /* ── Text Color Hierarchy (High Contrast) ── */
        ink: {
          DEFAULT: "#0F172A",
          primary: "#0F172A",
          secondary: "#475569",
          muted: "#64748B",
          disabled: "#94A3B8",
          inverse: "#FFFFFF",
        },
        navy: {
          DEFAULT: "#0F172A",
          light: "#1E293B",
          dark: "#020617",
        },
        /* ── Primary Green Brand Colors ── */
        emerald: {
          DEFAULT: "#10B981",
          dark: "#059669",
          light: "#ECFDF5",
          border: "#A7F3D0",
          bright: "#34D399",
        },
        /* ── Secondary Gold/Yellow Accent ── */
        gold: {
          DEFAULT: "#F59E0B",
          light: "#FFFBEB",
          border: "#FDE68A",
          dark: "#92400E",
          bright: "#FBBF24",
        },
        /* ── Secondary Accent Colors ── */
        lime: {
          DEFAULT: "#84CC16",
          light: "#F7FEE7",
          dark: "#3F6212",
        },
        signal: {
          DEFAULT: "#6366F1",
          light: "#EEF2FF",
          dark: "#3730A3",
        },
        sky: {
          DEFAULT: "#0EA5E9",
          light: "#F0F9FF",
          dark: "#075985",
        },
        coral: {
          DEFAULT: "#EF4444",
          light: "#FEF2F2",
          dark: "#991B1B",
        },
        /* ── Football Pitch Surface ── */
        pitch: {
          DEFAULT: "#15803D",
          dark: "#166534",
          deep: "#14532D",
          light: "#22C55E",
        },
      },
      fontFamily: {
        display: ["'Space Grotesk'", "sans-serif"],
        body: ["'Inter'", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
      borderRadius: {
        chunky: "0.875rem",
        "chunky-lg": "1.25rem",
        "chunky-xl": "1.75rem",
      },
      boxShadow: {
        glow: "0 4px 20px -2px rgba(16,185,129,0.3)",
        "glow-gold": "0 4px 20px -2px rgba(245,158,11,0.3)",
        card: "0 2px 12px -2px rgba(15,23,42,0.06), 0 1px 3px rgba(15,23,42,0.04)",
        "card-hover": "0 10px 28px -4px rgba(15,23,42,0.1), 0 2px 6px rgba(15,23,42,0.04)",
        "card-playful": "0 6px 20px -4px rgba(16,185,129,0.15), 0 2px 4px rgba(0,0,0,0.04)",
        "btn-raised": "0 2px 0 0 rgba(15,23,42,0.12), 0 2px 4px -1px rgba(15,23,42,0.08)",
        "btn-pressed": "0 1px 0 0 rgba(15,23,42,0.12), 0 1px 2px -1px rgba(15,23,42,0.08)",
        soft: "0 2px 6px -2px rgba(15,23,42,0.05)",
      },
      animation: {
        "fade-up": "fadeUp 0.4s cubic-bezier(0.16,1,0.3,1) both",
        "pulse-soft": "pulseSoft 2s ease-in-out infinite",
        "bounce-sm": "bounceSm 0.4s cubic-bezier(0.34,1.56,0.64,1) both",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulseSoft: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.6" },
        },
        bounceSm: {
          "0%": { transform: "scale(0.92)" },
          "60%": { transform: "scale(1.06)" },
          "100%": { transform: "scale(1)" },
        },
      },
    },
  },
  plugins: [],
};
