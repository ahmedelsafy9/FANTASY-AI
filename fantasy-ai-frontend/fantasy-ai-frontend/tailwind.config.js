/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        /* ── Stadium Luxe Core Palette ── */
        stadium: {
          DEFAULT: "#10291F",
          deep: "#10291F",
          dark: "#091B15",
          forest: "#234735",
          surface: "#153528",
          subtle: "#1B4031",
          border: "#2A5240",
          lines: "rgba(255, 255, 255, 0.75)",
        },
        ivory: {
          DEFAULT: "#F5F0E5",
          base: "#F5F0E5",
          surface: "#FFFCF5",
          soft: "#FFFDF9",
          subtle: "#EFE8DA",
          muted: "#E3DC sample",
          border: "#E2DDD1",
        },
        gold: {
          DEFAULT: "#C5A15B",
          metallic: "#C5A15B",
          muted: "#9D7A3C",
          bright: "#D4B36D",
          light: "#FDF8EC",
          soft: "#F8F3E8",
          border: "#E5D08E",
          dark: "#82632A",
        },
        /* ── Text Hierarchy ── */
        ink: {
          DEFAULT: "#18231D",
          primary: "#18231D",
          secondary: "#697168",
          muted: "#8A9289",
          disabled: "#B6BCB4",
          light: "#F5F0E5",
          "light-secondary": "#C1C9C0",
          "light-muted": "#8F9A8E",
          inverse: "#FFFFFF",
        },
        /* ── Page & Surfaces ── */
        page: "#F5F0E5",
        card: "#FFFCF5",
        surface: {
          DEFAULT: "#FFFCF5",
          elevated: "#F5F0E5",
          hover: "#EFE8DA",
          subtle: "#F9F6EE",
          dark: "#10291F",
        },
        border: {
          DEFAULT: "#E2DDD1",
          soft: "#EAE5DA",
          medium: "#D5CFBF",
          bold: "#B8B09E",
          gold: "#E5D08E",
          dark: "#2A5240",
        },
        /* ── Brand Tokens ── */
        brand: {
          DEFAULT: "#10291F",
          primary: "#10291F",
          deep: "#091B15",
          forest: "#234735",
          gold: "#C5A15B",
          accent: "#C5A15B",
          hover: "#0D221A",
          soft: "#E8F0EC",
          border: "#C5A15B",
        },
        /* ── Compatibility Aliases for Smooth Transition ── */
        pitch: {
          DEFAULT: "#10291F",
          dark: "#091B15",
          deep: "#091B15",
          forest: "#234735",
          light: "#234735",
          lines: "rgba(255, 255, 255, 0.75)",
        },
        mustard: {
          DEFAULT: "#C5A15B",
          light: "#FDF8EC",
          border: "#E5D08E",
          dark: "#9D7A3C",
        },
        accent: {
          mustard: "#C5A15B",
          mustardLight: "#FDF8EC",
          mustardBorder: "#E5D08E",
          mustardDark: "#9D7A3C",
          baby: "#3282B8",
          babyDark: "#1E5A84",
          babySoft: "#EEF5F9",
        },
      },
      fontFamily: {
        display: ["'Space Grotesk'", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
        body: ["'Inter'", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
      borderRadius: {
        chunky: "0.875rem",
        "chunky-lg": "1.25rem",
        "chunky-xl": "1.75rem",
      },
      boxShadow: {
        glow: "0 4px 20px -2px rgba(197,161,91,0.25)",
        "glow-gold": "0 4px 24px -2px rgba(197,161,91,0.35)",
        "glow-pitch": "0 4px 24px -2px rgba(16,41,31,0.5)",
        card: "0 2px 10px -2px rgba(24,35,29,0.06), 0 1px 3px rgba(24,35,29,0.04)",
        "card-hover": "0 10px 30px -4px rgba(16,41,31,0.12), 0 2px 8px rgba(197,161,91,0.08)",
        "card-dark": "0 8px 30px -4px rgba(0,0,0,0.5), 0 2px 8px rgba(197,161,91,0.15)",
        "btn-raised": "0 2px 0 0 rgba(16,41,31,0.3), 0 2px 4px -1px rgba(24,35,29,0.1)",
        "btn-pressed": "0 1px 0 0 rgba(16,41,31,0.3), 0 1px 2px -1px rgba(24,35,29,0.1)",
        soft: "0 2px 6px -2px rgba(24,35,29,0.05)",
      },
      animation: {
        "fade-up": "fadeUp 0.4s cubic-bezier(0.16,1,0.3,1) both",
        "pulse-soft": "pulseSoft 2.5s ease-in-out infinite",
        "bounce-sm": "bounceSm 0.4s cubic-bezier(0.34,1.56,0.64,1) both",
        "shimmer-gold": "shimmerGold 3s linear infinite",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        pulseSoft: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.65" },
        },
        bounceSm: {
          "0%": { transform: "scale(0.92)" },
          "60%": { transform: "scale(1.06)" },
          "100%": { transform: "scale(1)" },
        },
        shimmerGold: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
    },
  },
  plugins: [],
};
