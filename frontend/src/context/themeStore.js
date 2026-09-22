import { create } from "zustand";
import { persist } from "zustand/middleware";

// Tema de la plataforma: claro, oscuro o el del sistema operativo. La preferencia es por navegador
// (localStorage, no sessionStorage) para que sobreviva al cierre de sesión.
const CLAVE = "portezuelo-theme";
const consulta = () => window.matchMedia?.("(prefers-color-scheme: dark)");

/** ¿Qué tema toca pintar, resolviendo "sistema" contra el navegador? */
export function temaEfectivo(tema) {
  if (tema === "dark" || tema === "light") return tema;
  return consulta()?.matches ? "dark" : "light";
}

/** Aplica el tema al <html>: Tailwind lo lee con la estrategia `class`. */
export function aplicarTema(tema) {
  const efectivo = temaEfectivo(tema);
  document.documentElement.classList.toggle("dark", efectivo === "dark");
  document.documentElement.dataset.theme = efectivo;
  return efectivo;
}

export const useThemeStore = create(
  persist(
    (set) => ({
      tema: "system",
      setTema: (tema) => { aplicarTema(tema); set({ tema }); },
    }),
    {
      name: CLAVE,
      storage: {
        getItem: (n) => { try { const s = localStorage.getItem(n); return s ? JSON.parse(s) : null; } catch { return null; } },
        setItem: (n, v) => { try { localStorage.setItem(n, JSON.stringify(v)); } catch { /* modo privado */ } },
        removeItem: (n) => { try { localStorage.removeItem(n); } catch { /* modo privado */ } },
      },
      onRehydrateStorage: () => (estado) => aplicarTema(estado?.tema ?? "system"),
    }
  )
);

/**
 * Arranca el tema al cargar la app y sigue al sistema operativo mientras la preferencia sea
 * "sistema" (si el usuario eligió claro u oscuro, el cambio del SO no lo pisa).
 */
export function iniciarTema() {
  aplicarTema(useThemeStore.getState().tema);
  const mq = consulta();
  const alCambiar = () => { if (useThemeStore.getState().tema === "system") aplicarTema("system"); };
  mq?.addEventListener?.("change", alCambiar);
  return () => mq?.removeEventListener?.("change", alCambiar);
}
