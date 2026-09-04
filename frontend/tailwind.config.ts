import type { Config } from "tailwindcss";

/**
 * Paleta Works2Data (a empresa). W2Health Intelligence é o produto demonstrado.
 * Navy #0b1b32 · Gold #d3a63e · Steel #a9bbd0 (retirados do logotipo).
 */
const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef2f7",
          100: "#e0e7f0",
          200: "#c2cfe0",
          300: "#93a9c6",
          400: "#5c7aa6",
          500: "#2f5286",
          600: "#22406a",
          700: "#1b3557",
          800: "#122744",
          900: "#0b1b32",
        },
        gold: {
          50: "#fbf5e6",
          100: "#f6e8c4",
          400: "#e0bd6a",
          500: "#d3a63e",
          600: "#b78c2c",
          700: "#8a6a1f",
        },
        steel: {
          100: "#e2e9f2",
          300: "#a9bbd0",
          500: "#7d95b5",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
