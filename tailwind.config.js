// tailwind.config.js

module.exports = {
  // CRITICAL: Configure content to scan all HTML and Python files
  content: [
    // 1. Scans all Django templates in the base 'templates' folder
    "./templates/**/*.html",
    // 2. Scans all templates within every Django app
    "./**/templates/**/*.html",
    // 3. Scans Python files that dynamically use Tailwind classes
    "./accounts/forms.py",
    "./products/views.py",
  ],
  theme: {
    extend: {
      // Optional: Add custom colors, fonts, etc. here later
    },
  },
  plugins: [],
};
