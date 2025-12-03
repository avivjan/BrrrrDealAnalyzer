/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}'
  ],
  theme: {
    extend: {
      colors: {
        ocean: {
          50: '#0b1224',
          100: '#0e1b33',
          200: '#102440',
          300: '#122c4d',
          400: '#15385f',
          500: '#1b4b7d',
          600: '#1f5b9b',
          700: '#3b75b3',
          800: '#5c93c6',
          900: '#82b4da'
        }
      },
      boxShadow: {
        glow: '0 10px 50px rgba(31, 91, 155, 0.35)'
      }
    }
  },
  plugins: []
};
