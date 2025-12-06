/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class', // Enable dark mode by class
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ocean: {
          // Inverted palette for Light Mode text mapping
          50: '#0f172a',  // Slate 900 (Main Text)
          100: '#1e293b', // Slate 800
          200: '#334155', // Slate 700 (Labels)
          300: '#475569', // Slate 600 (Secondary Text)
          400: '#94a3b8', // Slate 400 (Icons/Muted)
          500: '#3b82f6', // Blue 500 (Primary Brand)
          600: '#2563eb', // Blue 600 (Hover)
          700: '#60a5fa', // Blue 400 (Lighter accent)
          800: '#93c5fd', // Blue 300
          900: '#dbeafe', // Blue 100
          950: '#eff6ff', // Blue 50
        },
        whale: {
          DEFAULT: '#f1f5f9', // Slate 100
          surface: '#ffffff', // White (Cards)
          dark: '#f8fafc',    // Slate 50 (Background)
          border: '#e2e8f0',  // Slate 200 (Borders)
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
