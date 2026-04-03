import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#0a0a0a",
        card: "#111111",
        border: "#222222",
        muted: "#888888",
      },
    },
  },
  plugins: [],
};

export default config;
