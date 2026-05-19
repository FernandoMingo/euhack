import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Semantic palette from UI_FEATURES.md
        background: "var(--background)",
        foreground: "var(--foreground)",
        card: "var(--card)",
        "card-foreground": "var(--card-foreground)",
        primary: "var(--primary)",
        "primary-foreground": "var(--primary-foreground)",
        secondary: "var(--secondary)",
        "secondary-foreground": "var(--secondary-foreground)",
        muted: "var(--muted)",
        "muted-foreground": "var(--muted-foreground)",
        accent: "var(--accent)",
        "accent-foreground": "var(--accent-foreground)",
        destructive: "var(--destructive)",
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
        sage: "var(--sage)",
        mist: "var(--mist)",
        peach: "var(--peach)",
      },
      borderRadius: {
        sm: "16px",
        md: "18px",
        lg: "20px",
        xl: "24px",
        "2xl": "28px",
        "3xl": "32px",
        "4xl": "36px",
      },
      fontFamily: {
        sans: ['Inter', 'DM Sans', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        soft: "var(--shadow-soft)",
        float: "var(--shadow-float)",
      },
    },
  },
  plugins: [],
};

export default config;
