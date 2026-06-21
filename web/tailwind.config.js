/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        forest: {
          700: "#1b4332",
          600: "#2d6a4f",
          500: "#40916c",
        },
      },
    },
  },
  plugins: [],
};
