import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Portezuelo publica esta app bajo /creditos/ (nginx → contenedor creditos-web). La API va por el gateway
// en /api/creditos. En dev (`npm run dev`) se hace proxy de /api hacia Portezuelo; para tener sesión hay
// que ingresar primero por el login de Portezuelo en el mismo origen.
export default defineConfig({
  base: "/creditos/",
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET || "http://localhost",
        changeOrigin: true,
      },
    },
  },
});
