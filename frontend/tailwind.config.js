/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: '#1F3864', light: '#D6E4F7', result: '#E2EFDA' },
      },
    },
  },
  plugins: [],
}
