/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#03111f",
        card: "rgba(255, 255, 255, 0.065)",
        "card-border": "rgba(186, 230, 253, 0.16)",
        accent: {
          cyan: "#22d3ee",
          teal: "#0e7490",
          violet: "#6d28d9",
        },
        text: {
          main: "#e6f6ff",
          muted: "#9fc3d6",
        },
        agent: {
          searcher: "#60a5fa",
          explainer: "#f0abfc",
          mapper: "#a78bfa",
          guide: "#fbbf24",
        },
      },
      fontFamily: {
        heading: ["Sora", "sans-serif"],
        body: ["Manrope", "sans-serif"],
        code: ["JetBrains Mono", "monospace"],
      },
      backdropBlur: {
        glass: "18px",
      },
      borderRadius: {
        panel: "22px",
      },
    },
  },
  plugins: [],
}
