// tailwind.config.js

module.exports = {
  // CRITICAL: Configure content to scan all HTML and Python files
  content: [
    './templates/**/*.html',
    './**/templates/**/*.html', 
    './accounts/forms.py', // Scan Python files that may contain classes
    // Add any other directories/files that use Tailwind classes
  ],
  theme: {
    extend: {}, 
  },
  plugins: [],
}