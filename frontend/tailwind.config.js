/** @type {import('tailwindcss').Config} */

// Tema claro/oscuro: en vez de duplicar `dark:` en cada clase del código, la escala de grises, los
// tintes de acento y la superficie apuntan a variables CSS que se invierten en `.dark` (ver
// index.css). Así `bg-surface`, `text-gray-700` o `bg-blue-50` ya significan lo correcto en ambos
// temas. `white` y `black` quedan literales: los usan los botones (`text-white` sobre color).
const v = (nombre) => `rgb(var(${nombre}) / <alpha-value>)`;

const escala = (prefijo, pasos) =>
  Object.fromEntries(pasos.map((p) => [p, v(`--c-${prefijo}-${p}`)]));

export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        surface: v("--c-surface"),
        gray: escala("gray", [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]),
        blue: escala("blue", [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]),
        red: escala("red", [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]),
        green: escala("green", [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]),
        yellow: escala("yellow", [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]),
        amber: escala("amber", [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]),
      },
    },
  },
  plugins: [],
};
