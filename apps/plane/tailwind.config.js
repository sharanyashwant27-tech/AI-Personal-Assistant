/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        mono: ["JetBrains Mono", "Cascadia Code", "Consolas", "monospace"],
        sans: ["Inter", "Segoe UI", "system-ui", "sans-serif"],
      },
      colors: {
        plane: {
          bg: "var(--bg)",
          surface: "var(--surface)",
          border: "var(--border)",
          text: "var(--text)",
          muted: "var(--muted)",
          accent: "var(--accent)",
          success: "var(--success)",
          warn: "var(--warn)",
          user: "var(--user-bg)",
          agent: "var(--agent-bg)",
        },
      },
    },
  },
  plugins: [],
};
