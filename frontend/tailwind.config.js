/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        kannada: ['Noto Sans Kannada', 'sans-serif'],
      },
      colors: {
        saffron: {
          400: '#FB923C',
          500: '#F97316',
          600: '#EA580C',
        },
      },
    },
  },
  plugins: [],
};
