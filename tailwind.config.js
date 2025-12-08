// tailwind.config.js
module.exports = {
  // CRITICAL: Configure content to scan all Django template files
  content: [
    "./templates/**/*.html",
    "./**/templates/**/*.html",
    "./accounts/forms.py",
    "./products/views.py",
  ],
  theme: {
    // You can customize colors, fonts, etc. here if needed.
    extend: {},
  },
  plugins: [],
};
