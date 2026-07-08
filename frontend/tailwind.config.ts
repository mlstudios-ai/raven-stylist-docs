import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Espresso palette — restrained, editorial.
        espresso: {
          50: "#FAF6F1",  // cream — paper
          100: "#F2EBE0", // cream + warm
          200: "#E5D9C7", // cream darker
          300: "#C9B89E", // taupe
          400: "#9F8568", // muted bronze
          500: "#6E5840", // mid brown
          600: "#4A3A2A", // espresso
          700: "#33271C", // dark roast
          800: "#1F1812", // near-black brown
          900: "#0E0A07", // ink
        },
        // Accent — only used sparingly.
        accent: {
          DEFAULT: "#B8956C", // warm gold-bronze
          muted: "#9F8568",
        },
      },
      fontFamily: {
        // Editorial serif for display + brand
        display: ["var(--font-display)", "serif"],
        // Clean sans for UI / body
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      letterSpacing: {
        // Fashion editorial brand spacing
        brand: "0.18em",
      },
    },
  },
  plugins: [],
};

export default config;
