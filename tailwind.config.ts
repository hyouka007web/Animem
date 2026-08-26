import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        midnight: {
          DEFAULT: "#0a0b12",
          deep: "#08090f",
          light: "#101118",
        },
        realm: {
          cyan: "#4ce3f0",
          violet: "#7c3aed",
          "violet-deep": "#4c1d95",
          copper: "#e0a458",
          "copper-light": "#f0c987",
        },
      },
      backgroundImage: {
        "realm-glow": "radial-gradient(circle at 50% 0%, rgba(124,58,237,0.25), transparent 60%)",
        "realm-drift": "linear-gradient(135deg, #08090f 0%, #14102b 45%, #0a1a1f 100%)",
      },
      animation: {
        "aura-pulse": "auraPulse 4s ease-in-out infinite",
        glitch: "glitch 2.5s ease-in-out infinite",
        "star-drop": "starDrop 1.4s ease-out forwards",
        drift: "drift 18s ease-in-out infinite",
        shimmer: "shimmer 3s linear infinite",
      },
      keyframes: {
        auraPulse: {
          "0%, 100%": { opacity: "0.35", filter: "hue-rotate(0deg)" },
          "50%": { opacity: "0.65", filter: "hue-rotate(25deg)" },
        },
        glitch: {
          "0%, 92%, 100%": { transform: "translate(0,0)", opacity: "1" },
          "93%": { transform: "translate(-1.5px,0.5px)", opacity: "0.85" },
          "95%": { transform: "translate(1.5px,-0.5px)", opacity: "0.9" },
          "97%": { transform: "translate(-1px,0)", opacity: "1" },
        },
        starDrop: {
          "0%": { transform: "translateY(-24px) scale(0.4)", opacity: "0" },
          "60%": { opacity: "1" },
          "100%": { transform: "translateY(0) scale(1)", opacity: "0.9" },
        },
        drift: {
          "0%, 100%": { transform: "translate(0,0) scale(1)" },
          "50%": { transform: "translate(-2%,3%) scale(1.05)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
