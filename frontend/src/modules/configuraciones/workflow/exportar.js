/** Exportar el diagrama a PNG (html-to-image se carga recién al exportar). */

/** Nombre de archivo: workflow-tesoreria-LOTE_PAGO-v3.png */
export function nombreArchivo(proceso, version) {
  const limpio = (s) => String(s || "").replace(/[^A-Za-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "");
  return `workflow-${limpio(proceso?.modulo)}-${limpio(proceso?.objeto)}-v${version?.numero ?? "x"}.png`;
}

/** Caja que encierra todos los nodos, con margen. */
export function cajaDeNodos(nodos, margen = 40) {
  if (!nodos.length) return { x: 0, y: 0, width: 1, height: 1 };
  let x0 = Infinity; let y0 = Infinity; let x1 = -Infinity; let y1 = -Infinity;
  for (const n of nodos) {
    const w = n.measured?.width ?? n.width ?? 220; const h = n.measured?.height ?? n.height ?? 72;
    x0 = Math.min(x0, n.position.x); y0 = Math.min(y0, n.position.y);
    x1 = Math.max(x1, n.position.x + w); y1 = Math.max(y1, n.position.y + h);
  }
  return { x: x0 - margen, y: y0 - margen, width: x1 - x0 + 2 * margen, height: y1 - y0 + 2 * margen };
}

/**
 * Dibuja el viewport de React Flow (`.react-flow__viewport` dentro de `contenedor`) a escala 1 con
 * todos los nodos y descarga el PNG.
 */
export async function exportarPng(contenedor, nodos, archivo) {
  const viewport = contenedor?.querySelector(".react-flow__viewport");
  if (!viewport) throw new Error("No se encontró el diagrama para exportar.");
  const { toPng } = await import("html-to-image");
  const caja = cajaDeNodos(nodos);
  const fondo = getComputedStyle(contenedor).backgroundColor || "#ffffff";
  const url = await toPng(viewport, {
    backgroundColor: fondo,
    width: caja.width,
    height: caja.height,
    style: { width: `${caja.width}px`, height: `${caja.height}px`, transform: `translate(${-caja.x}px, ${-caja.y}px) scale(1)` },
  });
  const a = document.createElement("a");
  a.download = archivo;
  a.href = url;
  a.click();
  return url;
}
