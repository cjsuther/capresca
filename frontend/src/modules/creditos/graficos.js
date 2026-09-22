import { useEffect, useState } from "react";
import { useThemeStore, temaEfectivo } from "../../context/themeStore";

/**
 * Colores de los gráficos del módulo, por tema.
 *
 * Ambos modos están ELEGIDOS y validados con el verificador de dataviz (all-pairs):
 *  - claro sobre superficie blanca: verde #15803d, ámbar #b45309, azul #1d4ed8 → pasan; el par
 *    ámbar–verde queda en la banda 6–8 de CVD, por eso los segmentos llevan etiqueta directa y 2px
 *    de separación (encoding secundario).
 *  - oscuro sobre la superficie #1e293b: verde #199e70, ámbar #c98500, azul #3987e5 → pasan todos
 *    los chequeos (banda de luminosidad del modo oscuro, croma, CVD y contraste ≥ 3:1).
 * Los estados de cola no inventan hues nuevos: se agrupan en "Otros" (gris).
 */
const PALETAS = {
  light: {
    verde: "#15803d", ambar: "#b45309", azul: "#1d4ed8", gris: "#9ca3af",
    pista: "#f3f4f6", grilla: "#e5e7eb", tinta: "#1f2937", tintaSuave: "#6b7280",
  },
  dark: {
    verde: "#199e70", ambar: "#c98500", azul: "#3987e5", gris: "#94a3b8",
    pista: "#334155", grilla: "#334155", tinta: "#f1f5f9", tintaSuave: "#94a3b8",
  },
};

/** Paleta de gráficos del tema activo (se recalcula al cambiar el tema o el del sistema). */
export function usePaletaGraficos() {
  const tema = useThemeStore((s) => s.tema);
  const [efectivo, setEfectivo] = useState(() => temaEfectivo(tema));

  useEffect(() => {
    setEfectivo(temaEfectivo(tema));
    if (tema !== "system") return;
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    const alCambiar = () => setEfectivo(temaEfectivo("system"));
    mq?.addEventListener?.("change", alCambiar);
    return () => mq?.removeEventListener?.("change", alCambiar);
  }, [tema]);

  return PALETAS[efectivo];
}
