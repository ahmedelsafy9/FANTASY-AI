/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        /* ── Page & Card Surfaces ── */
        page: "#F8F7FA",
        card: "#FFFFFF",
        surface: {
          DEFAULT: "#FFFFFF",
          elevated: "#F8F7FA",
          hover: "#F2EEF8",
          subtle: "#FAF9FC",
        },
        border: {
          DEFAULT: "#E8E3ED",
          soft: "#E8E3ED",
          medium: "#D8D2E0",
          bold: "#B8AFC4",
          purple: "#D8C7F4",
        },
        /* ── Text Color Hierarchy (High Contrast) ── */
        ink: {
          DEFAULT: "#19171D",
          primary: "#19171D",
          secondary: "#6F6A76",
          muted: "#938E9B",
          disabled: "#B5B0BC",
          inverse: "#FFFFFF",
        },
        /* ── Premier League Purple Brand Identity ── */
        brand: {
          DEFAULT: "#7041C5",
          primary: "#7041C5",
          deep: "#452477",
          soft: "#EEE7FA",
          lavender: "#EEE7FA",
          border: "#D8C7F4",
          hover: "#5B32A8",
          dark: "#371B62",
        },
        purple: {
          DEFAULT: "#7041C5",
          50: "#F8F5FD",
          100: "#EEE7FA",
          200: "#DCCEF6",
          300: "#C4ABEF",
          400: "#A17FE5",
          500: "#865CD6",
          600: "#7041C5",
          700: "#5B32A8",
          800: "#452477",
          900: "#33185B",
          950: "#210C3F",
        },
        /* ── Secondary Accents (Baby Blue & Selective Dark Mustard) ── */
        accent: {
          baby: "#B9DDF5",
          babyDark: "#4A98CF",
          babySoft: "#EDF6FC",
          mustard: "#B58A18",
          mustardLight: "#FDF8EC",
          mustardBorder: "#E5D08E",
          mustardDark: "#8C680E",
        },
        mustard: {
          DEFAULT: "#B58A18",
          light: "#FDF8EC",
          border: "#E5D08E",
          dark: "#8C680E",
        },
        baby: {
          DEFAULT: "#B9DDF5",
          light: "#EDF6FC",
          dark: "#4A98CF",
        },
        /* ── Football Pitch Surface (Tactical Board) ── */
        pitch: {
          DEFAULT: "#1F4E38",
          dark: "#163E2B",
          deep: "#113222",
          light: "#2B684C",
          lines: "rgba(255, 255, 255, 0.75)",
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
        glow: "0 4px 20px -2px rgba(112,65,197,0.25)",
        "glow-purple": "0 4px 20px -2px rgba(112,65,197,0.3)",
        "glow-mustard": "0 4px 18px -2px rgba(181,138,24,0.3)",
        card: "0 2px 10px -2px rgba(25,23,29,0.05), 0 1px 3px rgba(25,23,29,0.03)",
        "card-hover": "0 8px 24px -4px rgba(69,36,119,0.12), 0 2px 6px rgba(25,23,29,0.04)",
        "card-playful": "0 6px 20px -4px rgba(112,65,197,0.15), 0 2px 4px rgba(0,0,0,0.04)",
        "btn-raised": "0 2px 0 0 rgba(69,36,119,0.2), 0 2px 4px -1px rgba(25,23,29,0.08)",
        "btn-pressed": "0 1px 0 0 rgba(69,36,119,0.2), 0 1px 2px -1px rgba(25,23,29,0.08)",
        soft: "0 2px 6px -2px rgba(25,23,29,0.04)",
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
