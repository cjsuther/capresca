import { useSyncExternalStore } from "react";

/**
 * Tema del portal: claro, oscuro o el del dispositivo. La preferencia es por navegador
 * (localStorage) y se refleja en `<html data-tema>`, que es lo que leen los estilos.
 */
export type Tema = "light" | "dark" | "system";

const CLAVE = "portal-creditos-theme";
const consulta = () => window.matchMedia?.("(prefers-color-scheme: dark)");

/** Resuelve "system" contra el dispositivo. */
export function temaEfectivo(tema: Tema): "light" | "dark" {
  if (tema === "light" || tema === "dark") return tema;
  return consulta()?.matches ? "dark" : "light";
}

function leerPreferencia(): Tema {
  try {
    const v = localStorage.getItem(CLAVE);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch { /* modo privado */ }
  return "system";
}

let tema: Tema = leerPreferencia();
const oyentes = new Set<() => void>();

/** Pinta el tema en el <html>. Devuelve el tema efectivo aplicado. */
export function aplicarTema(t: Tema) {
  const efectivo = temaEfectivo(t);
  document.documentElement.dataset.tema = efectivo;
  return efectivo;
}

export function getTema() {
  return tema;
}

export function setTema(t: Tema) {
  tema = t;
  try { localStorage.setItem(CLAVE, t); } catch { /* modo privado */ }
  aplicarTema(t);
  oyentes.forEach((avisar) => avisar());
}

/**
 * Arranca el tema al cargar y sigue al dispositivo mientras la preferencia sea "system"
 * (si el ciudadano eligió claro u oscuro, el cambio del sistema operativo no lo pisa).
 */
export function iniciarTema() {
  tema = leerPreferencia();
  aplicarTema(tema);
  const mq = consulta();
  const alCambiar = () => {
    if (tema !== "system") return;
    aplicarTema("system");
    oyentes.forEach((avisar) => avisar());
  };
  mq?.addEventListener?.("change", alCambiar);
  return () => mq?.removeEventListener?.("change", alCambiar);
}

function suscribir(avisar: () => void) {
  oyentes.add(avisar);
  return () => { oyentes.delete(avisar); };
}

export function useTema(): [Tema, (t: Tema) => void] {
  const actual = useSyncExternalStore(suscribir, getTema, getTema);
  return [actual, setTema];
}
