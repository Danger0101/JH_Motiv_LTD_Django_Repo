// tailwind.config.js
const plugin = require("tailwindcss/plugin");

module.exports = {
  darkMode: "class", // Ensure this is set to 'class'
  // CRITICAL: Configure content to scan all HTML and Python files
  content: [
    "./templates/**/*.html",
    "./**/templates/**/*.html",
    "./accounts/forms.py", // Scan Python files that may contain classes
    "./static/js/**/*.js", // <--- ADD THIS LINE to fix the visual bugs
    // Add any other directories/files that use Tailwind classes
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ["Courier New", "monospace"], // For Matrix/Retro
        sans: ["Inter", "sans-serif"],
      },
    },
  },
  plugins: [
    plugin(function ({ addVariant }) {
      addVariant("matrix", ".matrix &");
      addVariant("cyber", ".cyber &");
      addVariant("retro", ".retro &");
      addVariant("doom", ".doom &");
      addVariant("bighead", ".bighead &");
      addVariant("devmode", ".devmode &");
    }),
  ],
};
