/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        void: {
          DEFAULT: "#0B0D10",
          soft: "#0F1216",
        },
        surface: {
          DEFAULT: "#12151A",
          elevated: "#181C22",
          hover: "#1D222A",
        },
        border: {
          soft: "rgba(255,255,255,0.08)",
          medium: "rgba(255,255,255,0.14)",
        },
        ink: {
          DEFAULT: "#F5F6F8",
          secondary: "#9AA3AE",
          tertiary: "#626B76",
        },
        gold: {
          DEFAULT: "#E8B85C",
          bright: "#F5CB7C",
          dim: "#8A6B36",
        },
        signal: {
          DEFAULT: "#7C86FF",
          bright: "#9AA2FF",
          dim: "#4A4F99",
        },
        teal: {
          DEFAULT: "#34D1B8",
          dim: "#1F7A6C",
        },
        coral: {
          DEFAULT: "#E5695A",
          dim: "#8A3D34",
        },
      },
      fontFamily: {
        display: ["'Space Grotesk'", "sans-serif"],
        body: ["'Inter'", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
      boxShadow: {
        glow: "0 0 40px -8px rgba(232,184,92,0.25)",
        "glow-signal": "0 0 40px -8px rgba(124,134,255,0.3)",
        card: "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 12px 32px -16px rgba(0,0,0,0.6)",
      },
      backgroundImage: {
        "grid-fade":
          "linear-gradient(to bottom, rgba(11,13,16,0) 0%, rgba(11,13,16,1) 85%)",
      },
      animation: {
        "fade-up": "fadeUp 0.6s cubic-bezier(0.16,1,0.3,1) both",
        "drift": "drift 18s ease-in-out infinite",
        "pulse-soft": "pulseSoft 2.4s ease-in-out infinite",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        drift: {
          "0%, 100%": { transform: "translate(0,0)" },
          "50%": { transform: "translate(12px,-16px)" },
        },
        pulseSoft: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
      },
    },
  },
  plugins: [],
};
