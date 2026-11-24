/**
 * Auto-layout con ELK (elkjs). ELK se carga con import dinámico la primera vez que se pide «Ordenar»:
 * no pesa en la carga de la pantalla ni en el resto del frontend.
 */
import { ALTO_NODO, ANCHO_NODO } from "./flow";

/** Grafo en el formato de ELK (capas de arriba hacia abajo). */
export function grafoAElk(grafo, medidas = {}) {
  return {
    id: "raiz",
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "DOWN",
      "elk.layered.spacing.nodeNodeBetweenLayers": "70",
      "elk.spacing.nodeNode": "60",
      "elk.edgeRouting": "ORTHOGONAL",
      "elk.layered.cycleBreaking.strategy": "DEPTH_FIRST",
    },
    children: (grafo?.nodos || []).map((n) => ({
      id: n.id,
      width: medidas[n.id]?.width || ANCHO_NODO,
      height: medidas[n.id]?.height || ALTO_NODO,
    })),
    edges: (grafo?.conexiones || [])
      .filter((c) => c.de && c.a)
      .map((c) => ({ id: c.id, sources: [c.de], targets: [c.a] })),
  };
}

/** Resultado de ELK → layout {id: {x, y}}. */
export function layoutDeElk(resultado) {
  const out = {};
  for (const n of resultado?.children || []) out[n.id] = { x: Math.round(n.x ?? 0), y: Math.round(n.y ?? 0) };
  return out;
}

let elk = null;

/** Calcula el layout (carga ELK la primera vez). */
export async function ordenar(grafo, medidas) {
  if (!elk) {
    const { default: ELK } = await import("elkjs/lib/elk.bundled.js");
    elk = new ELK();
  }
  return layoutDeElk(await elk.layout(grafoAElk(grafo, medidas)));
}
