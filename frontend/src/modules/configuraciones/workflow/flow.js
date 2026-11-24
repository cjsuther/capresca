/**
 * Conversión entre el grafo del workflow y los nodos/aristas de React Flow. Funciones puras.
 *
 * El estado "verdadero" del editor es {grafo, layout}; los nodos de React Flow se derivan de ahí.
 * `leerCambiosNodos` traduce los cambios que emite React Flow (posición, selección, borrado, medidas)
 * a cambios sobre ese estado.
 */
import { etiquetaConexion } from "./condiciones";

export const ANCHO_NODO = 220;
export const ALTO_NODO = 72;

// Colores del tema (tokens de index.css): cambian solos con el tema claro/oscuro.
const tema = (token) => `rgb(var(--c-${token}))`;
const COLOR_SALIDA = { aprobado: tema("green-600"), rechazado: tema("red-600") };

export function posicionDe(layout, id, i = 0) {
  const p = layout?.[id];
  return p && Number.isFinite(p.x) && Number.isFinite(p.y) ? { x: p.x, y: p.y } : { x: 40 + (i % 4) * 260, y: 40 + Math.floor(i / 4) * 140 };
}

/** Nodos para React Flow. `marcas`: {id: "agregado"|"modificado"} al comparar versiones. */
export function aNodosFlow(grafo, layout, { problemas = {}, seleccion = null, medidas = {}, marcas = {}, soloLectura = false } = {}) {
  return (grafo?.nodos || []).map((n, i) => ({
    id: n.id,
    type: "workflow",
    position: posicionDe(layout, n.id, i),
    data: { nodo: n, problemas: problemas[n.id] || [], marca: marcas[n.id] || null },
    selected: seleccion?.tipo === "nodo" && seleccion.id === n.id,
    draggable: !soloLectura,
    connectable: !soloLectura,
    deletable: !soloLectura && n.tipo !== "inicio",
    ...(medidas[n.id] ? { measured: medidas[n.id] } : {}),
  }));
}

/** ¿La flecha sube (destino más arriba que el origen)? Entonces entra por el costado. */
function esVueltaAtras(c, posiciones) {
  const de = posiciones?.[c.de]; const a = posiciones?.[c.a];
  return Boolean(de && a && a.y < de.y);
}

export function aAristasFlow(grafo, { variables = {}, problemas = {}, seleccion = null, soloLectura = false, posiciones = {} } = {}) {
  return (grafo?.conexiones || []).map((c) => {
    const conError = (problemas[c.id] || []).some((x) => x.nivel === "error");
    const color = conError ? tema("red-600") : COLOR_SALIDA[c.salida] || tema("gray-500");
    return {
      id: c.id,
      source: c.de,
      target: c.a,
      // El «rechazado» (y toda vuelta atrás) va por el costado derecho: sale y entra por la derecha.
      sourceHandle: c.salida === "rechazado" ? "der" : "abajo",
      targetHandle: c.salida === "rechazado" || esVueltaAtras(c, posiciones) ? "der-entrada" : "arriba",
      type: "smoothstep",
      label: etiquetaConexion(c, variables),
      selected: seleccion?.tipo === "conexion" && seleccion.id === c.id,
      deletable: !soloLectura,
      markerEnd: { type: "arrowclosed" },   // sin color: el id del marcador se arma con el color y var() lo rompería
      style: { stroke: color, strokeWidth: conError ? 2.5 : 1.6, strokeDasharray: c.salida === "rechazado" ? "6 4" : undefined },
      labelStyle: { fill: color, fontSize: 11, fontWeight: 600 },
      labelBgStyle: { fill: "rgb(var(--c-surface))" },
      data: { conexion: c },
    };
  });
}

const listaCambios = (cambios) => (typeof cambios?.toArray === "function" ? cambios.toArray() : [...(cambios || [])]);

/**
 * Traduce los cambios de nodos de React Flow. Devuelve
 * {layout, medidas, seleccion, quitar: [ids], movio: bool (terminó un arrastre)}.
 */
export function leerCambiosNodos(cambios, { layout, medidas, seleccion }) {
  let lay = layout; let med = medidas; let sel = seleccion; let movio = false;
  const quitar = [];
  for (const ch of listaCambios(cambios)) {
    if (ch.type === "position" && ch.position) {
      lay = { ...lay, [ch.id]: { x: Math.round(ch.position.x), y: Math.round(ch.position.y) } };
      if (ch.dragging === false) movio = true;
    } else if (ch.type === "position" && ch.dragging === false) {
      movio = true;
    } else if (ch.type === "dimensions" && ch.dimensions) {
      med = { ...med, [ch.id]: { width: ch.dimensions.width, height: ch.dimensions.height } };
    } else if (ch.type === "select") {
      if (ch.selected) sel = { tipo: "nodo", id: ch.id };
      else if (sel?.tipo === "nodo" && sel.id === ch.id) sel = null;
    } else if (ch.type === "remove") {
      quitar.push(ch.id);
    }
  }
  return { layout: lay, medidas: med, seleccion: sel, quitar, movio };
}

/** Igual para aristas: {seleccion, quitar}. */
export function leerCambiosAristas(cambios, { seleccion }) {
  let sel = seleccion;
  const quitar = [];
  for (const ch of listaCambios(cambios)) {
    if (ch.type === "select") {
      if (ch.selected) sel = { tipo: "conexion", id: ch.id };
      else if (sel?.tipo === "conexion" && sel.id === ch.id) sel = null;
    } else if (ch.type === "remove") {
      quitar.push(ch.id);
    }
  }
  return { seleccion: sel, quitar };
}

/** Marcas de comparación sobre la versión NUEVA: nodos agregados y modificados. */
export function marcasDiff(diff) {
  const m = {};
  for (const id of diff?.nodos?.agregados || []) m[id] = "agregado";
  for (const x of diff?.nodos?.modificados || []) m[x.id] = "modificado";
  return m;
}

/** Posición libre para un nodo nuevo: debajo del más bajo, alineado con el seleccionado si hay. */
export function posicionNueva(layout, seleccionado) {
  const ys = Object.values(layout || {}).map((p) => p.y);
  const base = seleccionado && layout?.[seleccionado] ? layout[seleccionado] : null;
  return { x: base ? base.x + ANCHO_NODO + 60 : 0, y: base ? base.y : (ys.length ? Math.max(...ys) + 140 : 0) };
}
