import { describe, expect, it } from "vitest";
import { cambiarRegla, describirCondicion, etiquetaConexion, leerValor, operadoresPara, reglaNueva, valorInicial } from "./condiciones";
import { aAristasFlow, aNodosFlow, leerCambiosAristas, leerCambiosNodos, marcasDiff, posicionDe, posicionNueva } from "./flow";
import { grafoAElk, layoutDeElk, ordenar } from "./layout";
import { cajaDeNodos, nombreArchivo } from "./exportar";

const VARS = {
  monto: { nombre: "Monto solicitado", tipo: "numero" },
  origen: { nombre: "Origen", tipo: "opcion", opciones: ["PORTAL", "SUCURSAL"] },
  urgente: { nombre: "Urgente", tipo: "booleano" },
};

describe("condiciones", () => {
  it("operadores y valores iniciales según el tipo de variable", () => {
    expect(operadoresPara(VARS.monto)).toContain(">");
    expect(operadoresPara(undefined)).toEqual([]);
    expect(valorInicial(VARS.origen, "en")).toEqual(["PORTAL"]);
    expect(valorInicial(VARS.urgente, "=")).toBe(true);
    expect(reglaNueva(VARS)).toEqual({ variable: "monto", op: "=", valor: 0 });
    expect(reglaNueva({})).toBeNull();
  });

  it("cambiar la variable reinicia operador y valor; pasar a «en» arma una lista", () => {
    const r = { variable: "monto", op: ">", valor: 10 };
    expect(cambiarRegla(r, "variable", "origen", VARS)).toEqual({ variable: "origen", op: "=", valor: "PORTAL" });
    const o = { variable: "origen", op: "=", valor: "SUCURSAL" };
    expect(cambiarRegla(o, "op", "en", VARS).valor).toEqual(["SUCURSAL"]);
    expect(cambiarRegla({ ...o, op: "en", valor: ["PORTAL"] }, "op", "!=", VARS).valor).toBe("PORTAL");
  });

  it("lee números en formato es-AR", () => {
    expect(leerValor(VARS.monto, "5.000.000")).toBe(5000000);
    expect(leerValor(VARS.monto, "12,5")).toBe(12.5);
    expect(leerValor(VARS.monto, "abc")).toBeNaN();
    expect(leerValor(VARS.urgente, "true")).toBe(true);
  });

  it("describe la condición en castellano para la flecha y el panel", () => {
    const cond = { modo: "alguna", reglas: [{ variable: "monto", op: ">", valor: 5000000 }, { variable: "origen", op: "en", valor: ["PORTAL"] }] };
    expect(describirCondicion(cond, VARS)).toBe("Monto solicitado es mayor que 5.000.000 o Origen es alguno de PORTAL");
    expect(etiquetaConexion({ salida: "aprobado" })).toBe("aprobado");
    expect(etiquetaConexion({ defecto: true })).toBe("si no");
    expect(etiquetaConexion({ condicion: cond }, VARS)).toMatch(/…$/);
    expect(etiquetaConexion({ condicion: { reglas: [] } })).toBe("sin condición");
  });
});

describe("conversión a React Flow", () => {
  const grafo = {
    nodos: [{ id: "i", tipo: "inicio" }, { id: "a", tipo: "aprobacion", nombre: "Aprobación" }, { id: "f", tipo: "fin" }],
    conexiones: [{ id: "c1", de: "i", a: "a" }, { id: "c2", de: "a", a: "f", salida: "aprobado" }, { id: "c3", de: "a", a: "i", salida: "rechazado" }],
  };

  it("nodos con posición, problemas, selección, marcas y medidas", () => {
    const nodos = aNodosFlow(grafo, { a: { x: 5, y: 9 } }, {
      problemas: { a: [{ codigo: "X" }] }, seleccion: { tipo: "nodo", id: "a" }, medidas: { a: { width: 1, height: 2 } },
      marcas: { a: "agregado" },
    });
    expect(nodos[1]).toMatchObject({ id: "a", type: "workflow", position: { x: 5, y: 9 }, selected: true,
      measured: { width: 1, height: 2 }, data: { marca: "agregado", problemas: [{ codigo: "X" }] }, draggable: true });
    expect(nodos[0].deletable).toBe(false);                    // el Inicio no se borra
    expect(aNodosFlow(grafo, {}, { soloLectura: true }).every((n) => !n.draggable && !n.connectable && !n.deletable)).toBe(true);
    expect(posicionDe({}, "x", 5)).toEqual({ x: 300, y: 180 });
  });

  it("aristas con etiqueta, color por salida y error", () => {
    const aristas = aAristasFlow(grafo, { problemas: { c2: [{ nivel: "error" }] }, seleccion: { tipo: "conexion", id: "c3" } });
    expect(aristas.map((a) => a.label)).toEqual(["", "aprobado", "rechazado"]);
    expect(aristas[1].style.strokeWidth).toBe(2.5);
    expect(aristas[2]).toMatchObject({ selected: true, style: { strokeDasharray: "6 4" } });
  });

  it("el «rechazado» y las vueltas atrás van por el costado para no cruzar los nodos", () => {
    const pos = { i: { x: 0, y: 0 }, a: { x: 0, y: 140 }, f: { x: 0, y: 280 } };
    const conVuelta = { ...grafo, conexiones: [...grafo.conexiones, { id: "c4", de: "f", a: "a" }] };
    const h = Object.fromEntries(aAristasFlow(conVuelta, { posiciones: pos }).map((a) => [a.id, [a.sourceHandle, a.targetHandle]]));
    expect(h).toEqual({ c1: ["abajo", "arriba"], c2: ["abajo", "arriba"], c3: ["der", "der-entrada"], c4: ["abajo", "der-entrada"] });
  });

  it("traduce los cambios de nodos y aristas de React Flow", () => {
    const estado = { layout: {}, medidas: {}, seleccion: null };
    const r = leerCambiosNodos({ toArray: () => [
      { id: "a", type: "position", position: { x: 10.4, y: 20.6 }, dragging: true },
      { id: "a", type: "dimensions", dimensions: { width: 200, height: 70 } },
      { id: "a", type: "select", selected: true },
      { id: "f", type: "remove" },
    ] }, estado);
    expect(r).toEqual({ layout: { a: { x: 10, y: 21 } }, medidas: { a: { width: 200, height: 70 } },
      seleccion: { tipo: "nodo", id: "a" }, quitar: ["f"], movio: false });
    expect(leerCambiosNodos([{ id: "a", type: "position", dragging: false }], estado).movio).toBe(true);
    expect(leerCambiosNodos([{ id: "a", type: "select", selected: false }], { ...estado, seleccion: { tipo: "nodo", id: "a" } }).seleccion).toBeNull();
    expect(leerCambiosAristas([{ id: "c1", type: "select", selected: true }, { id: "c2", type: "remove" }], { seleccion: null }))
      .toEqual({ seleccion: { tipo: "conexion", id: "c1" }, quitar: ["c2"] });
  });

  it("marcas de comparación y posición para un nodo nuevo", () => {
    expect(marcasDiff({ nodos: { agregados: ["x"], modificados: [{ id: "y", campos: ["nombre"] }] } })).toEqual({ x: "agregado", y: "modificado" });
    expect(posicionNueva({ a: { x: 0, y: 100 }, b: { x: 0, y: 300 } })).toEqual({ x: 0, y: 440 });
    expect(posicionNueva({ a: { x: 10, y: 100 } }, "a")).toEqual({ x: 290, y: 100 });
    expect(posicionNueva({})).toEqual({ x: 0, y: 0 });
  });
});

describe("layout con ELK", () => {
  const grafo = {
    nodos: [{ id: "i" }, { id: "a" }, { id: "b" }, { id: "f" }],
    conexiones: [{ id: "c1", de: "i", a: "a" }, { id: "c2", de: "a", a: "b" }, { id: "c3", de: "b", a: "f" }, { id: "c4", de: "b", a: "i" }],
  };

  it("arma el grafo de ELK con las medidas reales o las por defecto", () => {
    const elk = grafoAElk(grafo, { a: { width: 300, height: 90 } });
    expect(elk.children[1]).toEqual({ id: "a", width: 300, height: 90 });
    expect(elk.children[0]).toEqual({ id: "i", width: 220, height: 72 });
    expect(elk.edges[3]).toEqual({ id: "c4", sources: ["b"], targets: ["i"] });
    expect(layoutDeElk({ children: [{ id: "a", x: 1.6, y: 2.2 }] })).toEqual({ a: { x: 2, y: 2 } });
  });

  it("ordena de arriba hacia abajo (ELK real, cargado bajo demanda)", async () => {
    const lay = await ordenar(grafo, {});
    expect(Object.keys(lay).sort()).toEqual(["a", "b", "f", "i"]);
    expect(lay.i.y).toBeLessThan(lay.a.y);
    expect(lay.a.y).toBeLessThan(lay.b.y);
    expect(lay.b.y).toBeLessThan(lay.f.y);
  });
});

describe("exportar", () => {
  it("nombre de archivo y caja que encierra los nodos", () => {
    expect(nombreArchivo({ modulo: "tesoreria", objeto: "LOTE_PAGO" }, { numero: 3 })).toBe("workflow-tesoreria-LOTE_PAGO-v3.png");
    expect(cajaDeNodos([{ position: { x: 0, y: 0 }, measured: { width: 100, height: 50 } }, { position: { x: 200, y: 300 } }], 10))
      .toEqual({ x: -10, y: -10, width: 440, height: 392 });
    expect(cajaDeNodos([])).toEqual({ x: 0, y: 0, width: 1, height: 1 });
  });
});
