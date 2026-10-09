import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Portal público del ciudadano. En dev se publica bajo /portal-creditos/; en producción, en la raíz de su
// propio dominio (mi.ccypp.gob.ar): la ruta la fija PORTAL_BASE al compilar (build arg de la imagen).
// La API va bajo /api/creditos/portal (nginx → módulo créditos, sin pasar por el gateway).
// En dev (`npm run dev`, puerto 5174) se hace proxy de /api hacia Portezuelo.
export default defineConfig({
  base: process.env.PORTAL_BASE || "/portal-creditos/",
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
