import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "oklch(0.962 0.012 80 / <alpha-value>)",
        foreground: "oklch(0.305 0.008 150 / <alpha-value>)",
        card: "oklch(0.992 0.008 90 / <alpha-value>)",
        "card-foreground": "oklch(0.305 0.008 150 / <alpha-value>)",
        secondary: "oklch(0.94 0.014 80 / <alpha-value>)",
        "secondary-foreground": "oklch(0.305 0.008 150 / <alpha-value>)",
        muted: "oklch(0.94 0.014 80 / <alpha-value>)",
        "muted-foreground": "oklch(0.55 0.012 155 / <alpha-value>)",
        border: "oklch(0.9 0.012 80 / <alpha-value>)",
        input: "oklch(0.9 0.012 80 / <alpha-value>)",
        sage: "oklch(0.78 0.04 145 / <alpha-value>)",
        mist: "oklch(0.83 0.04 235 / <alpha-value>)",
        peach: "oklch(0.86 0.045 50 / <alpha-value>)",
        paper: "#f6f1e8",
        ink: "#333331",
        line: "#6e6a61",
        moss: "#657a63",
        clay: "#bd8266",
        water: "#8aa3a4",
        oat: "#e8dcc8"
      },
      boxShadow: {
        soft: "var(--shadow-soft)",
        float: "var(--shadow-float)"
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"]
      }
    }
  },
  plugins: []
};

export default config;
