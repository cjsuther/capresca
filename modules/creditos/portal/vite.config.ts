import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Portal público del ciudadano. Portezuelo lo publica bajo /portal-creditos/ (nginx → contenedor
// creditos-portal) y su API bajo /api/creditos/portal (nginx → módulo créditos, sin pasar por el gateway).
// En dev (`npm run dev`, puerto 5174) se hace proxy de /api hacia Portezuelo.
export default defineConfig({
  base: "/portal-creditos/",
  plugins: [react()],
  server: {
    host: true,
    port: 5174,
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET || "http://localhost",
        changeOrigin: true,
      },
    },
  },
});
