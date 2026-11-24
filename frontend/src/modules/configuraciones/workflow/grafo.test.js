import { describe, expect, it } from "vitest";
import {
  actualizarConexion, actualizarNodo, agregarNodo, cantidadAprobaciones, conectar, crearNodo, errores,
  motivosIncompatible, nuevoId, problemaRegla, problemasPorElemento, quitarConexion, quitarNodo, validar,
} from "./grafo";

const VARS = {
  monto: { nombre: "Monto", tipo: "numero" },
  origen: { nombre: "Origen", tipo: "opcion", opciones: ["PORTAL", "SUCURSAL"] },
  linea: { nombre: "Línea", tipo: "texto" },
  urgente: { nombre: "Urgente", tipo: "booleano" },
};
const ap = (id, nombre = "Aprobación", rol = "APROBAR", extra = {}) =>
  ({ id, tipo: "aprobacion", nombre, asignar: { tipo: "rol", valor: rol }, cuatroOjos: true, ...extra });

/** Lo mismo que genera la migración de una regla en serie (wf_grafo.grafo_desde_niveles). */
const serie = (...nombres) => {
  const nodos = [{ id: "inicio", tipo: "inicio", nombre: "Inicio" }];
  const conexiones = [];
  let previo = "inicio";
  nombres.forEach((nm, i) => {
    const id = `ap${i + 1}`;
    nodos.push(ap(id, nm));
    conexiones.push({ id: `c${conexiones.length + 1}`, de: previo, a: id, ...(previo !== "inicio" ? { salida: "aprobado" } : {}) });
    conexiones.push({ id: `c${conexiones.length + 1}`, de: id, a: "inicio", salida: "rechazado" });
    previo = id;
  });
  nodos.push({ id: "fin", tipo: "fin", nombre: "Aprobado", resultado: "APROBADO" });
  conexiones.push({ id: `c${conexiones.length + 1}`, de: previo, a: "fin", ...(previo !== "inicio" ? { salida: "aprobado" } : {}) });
  return { schema: 1, nodos, conexiones };
};

const conDecision = () => ({
  schema: 1,
  nodos: [{ id: "i", tipo: "inicio" }, ap("a1"), { id: "d", tipo: "decision", nombre: "¿Monto alto?" },
    ap("a2", "Gerencia", "SUPERVISAR"),
    { id: "n", tipo: "notificacion", nombre: "Avisar", destinatarios: [{ tipo: "iniciador" }] },
    { id: "ok", tipo: "fin", resultado: "APROBADO" }, { id: "no", tipo: "fin", resultado: "RECHAZADO" }],
  conexiones: [
    { id: "c1", de: "i", a: "a1" },
    { id: "c2", de: "a1", a: "d", salida: "aprobado" },
    { id: "c3", de: "a1", a: "i", salida: "rechazado" },
    { id: "c4", de: "d", a: "a2", condicion: { modo: "todas", reglas: [{ variable: "monto", op: ">", valor: 5000000 }] } },
    { id: "c5", de: "d", a: "n", defecto: true },
    { id: "c6", de: "a2", a: "n", salida: "aprobado" },
    { id: "c7", de: "a2", a: "no", salida: "rechazado" },
    { id: "c8", de: "n", a: "ok" }],
});

const codigos = (g) => [...new Set(errores(validar(g, VARS)).map((x) => x.codigo))].sort();

describe("validar (espejo de wf_grafo.py, mismos códigos)", () => {
  it("una serie y un grafo con decisión son válidos", () => {
    expect(codigos(serie("Aprobación"))).toEqual([]);
    expect(codigos(conDecision())).toEqual([]);
  });

  it("un Inicio exacto y al menos un Fin", () => {
    const g = serie("A");
    g.nodos.push({ id: "i2", tipo: "inicio" });
    g.conexiones.push({ id: "x", de: "i2", a: "fin" });
    expect(codigos(g)).toContain("INICIO_UNICO");
    const h = serie("A");
    h.nodos = h.nodos.filter((n) => n.tipo !== "fin");
    h.conexiones = h.conexiones.filter((c) => c.a !== "fin");
    expect(codigos(h)).toContain("FIN_REQUERIDO");
  });

  it("marca huérfanos y nodos sin camino a un Fin sobre el nodo", () => {
    const g = serie("A");
    g.nodos.push(ap("suelto"));
    expect(codigos(g)).toEqual(expect.arrayContaining(["HUERFANO", "SIN_CAMINO_A_FIN", "SALIDAS_APROBACION"]));
    expect(problemasPorElemento(validar(g, VARS)).nodos.suelto.map((x) => x.codigo)).toContain("HUERFANO");
  });

  it("aprobación: quién aprueba, sus dos salidas y usuarios en conflicto", () => {
    const g = serie("A");
    g.nodos[1].asignar = {};
    expect(codigos(g)).toContain("SIN_ASIGNACION");
    g.nodos[1].asignar = { tipo: "rol", valor: "ADMG" };
    expect(codigos(g)).toContain("ROL_INVALIDO");
    g.nodos[1].asignar = { tipo: "grupo", valor: " " };
    expect(codigos(g)).toContain("GRUPO_VACIO");
    const h = serie("A");
    h.conexiones = h.conexiones.filter((c) => c.salida !== "rechazado");
    expect(codigos(h)).toContain("SALIDAS_APROBACION");
    const k = serie("A");
    Object.assign(k.nodos[1], { incluir: ["ana"], excluir: ["ana"] });
    expect(codigos(k)).toContain("USUARIO_INCLUIDO_Y_EXCLUIDO");
  });

  it("sin cuatro-ojos es sólo un aviso", () => {
    const g = serie("A");
    g.nodos[1].cuatroOjos = false;
    expect(codigos(g)).toEqual([]);
    expect(validar(g, VARS).filter((x) => x.nivel === "aviso").map((x) => x.codigo)).toEqual(["SIN_CUATRO_OJOS"]);
  });

  it("decisión: un «si no» y condiciones bien tipadas", () => {
    const g = conDecision();
    delete g.conexiones[4].defecto;
    g.conexiones[4].condicion = { reglas: [{ variable: "origen", op: "=", valor: "PORTAL" }] };
    expect(codigos(g)).toContain("DECISION_SIN_DEFECTO");
    const casos = [
      [{ variable: "monto", op: ">", valor: "mucho" }, false],
      [{ variable: "monto", op: "contiene", valor: 3 }, false],
      [{ variable: "nada", op: "=", valor: 1 }, false],
      [{ variable: "origen", op: "=", valor: "OTRO" }, false],
      [{ variable: "origen", op: "en", valor: ["PORTAL", "SUCURSAL"] }, true],
      [{ variable: "linea", op: "contiene", valor: "Emprend" }, true],
      [{ variable: "urgente", op: "=", valor: true }, true],
      [{ variable: "urgente", op: "=", valor: 1 }, false],
      [{ variable: "monto", op: ">", valor: true }, false],
    ];
    for (const [regla, ok] of casos) {
      const h = conDecision();
      h.conexiones[3].condicion.reglas = [regla];
      expect(codigos(h).length === 0).toBe(ok);
    }
    const sinSalida = conDecision();
    sinSalida.conexiones = sinSalida.conexiones.filter((c) => c.id !== "c4");
    expect(codigos(sinSalida)).toContain("SALIDAS_DECISION");
  });

  it("notificación con destinatarios completos y fin con resultado y sin salidas", () => {
    const g = conDecision();
    g.nodos[4].destinatarios = [];
    expect(codigos(g)).toContain("NOTIFICACION_SIN_DESTINO");
    g.nodos[4].destinatarios = [{ tipo: "grupo", valor: "" }];
    expect(codigos(g)).toContain("DESTINATARIO_INVALIDO");
    const h = serie("A");
    h.nodos.at(-1).resultado = "";
    h.conexiones.push({ id: "x", de: "fin", a: "inicio" });
    expect(codigos(h)).toEqual(expect.arrayContaining(["FIN_SIN_RESULTADO", "FIN_CON_SALIDA"]));
  });

  it("un ciclo tiene que pasar por una aprobación", () => {
    const g = conDecision();
    g.conexiones[7] = { id: "c8", de: "n", a: "d" };
    expect(codigos(g)).toContain("CICLO_SIN_APROBACION");
  });

  it("conexiones rotas, ids duplicados, tipos desconocidos y salidas fuera de lugar", () => {
    const g = serie("A");
    g.conexiones.push({ id: "x", de: "ap1", a: "fantasma" });
    g.nodos.push({ id: "ap1", tipo: "aprobacion" }, { id: "z", tipo: "subflujo" });
    expect(codigos(g)).toEqual(expect.arrayContaining(["CONEXION_ROTA", "ID_DUPLICADO", "TIPO_INVALIDO"]));
    const h = conDecision();
    h.conexiones[0].salida = "aprobado";
    h.conexiones[7].condicion = { reglas: [{ variable: "monto", op: ">", valor: 1 }] };
    expect(codigos(h)).toEqual(expect.arrayContaining(["SALIDA_FUERA_DE_APROBACION", "CONDICION_FUERA_DE_DECISION"]));
  });

  it("problemaRegla explica qué falla", () => {
    expect(problemaRegla({ variable: "monto", op: ">", valor: 3 }, VARS)).toBeNull();
    expect(problemaRegla({ variable: "monto", op: ">", valor: NaN }, VARS)).toMatch(/número/);
  });
});

describe("compatibilidad con el motor actual", () => {
  it("decisiones, notificaciones y grupos no se pueden publicar todavía", () => {
    expect(motivosIncompatible(serie("A", "B"))).toEqual([]);
    const m = motivosIncompatible(conDecision());
    expect(m.some((x) => /decisión/.test(x)) && m.some((x) => /notificación/.test(x))).toBe(true);
    const g = serie("A");
    g.nodos[1].asignar = { tipo: "grupo", valor: "Gerencia" };
    expect(motivosIncompatible(g)[0]).toMatch(/grupo/);
    expect(cantidadAprobaciones(conDecision())).toBe(2);
  });
});

describe("edición", () => {
  it("crea nodos con ids libres y valores por defecto", () => {
    const g = serie("A");
    expect(nuevoId(g, "ap")).toBe("ap2");
    const n = crearNodo(g, "aprobacion");
    expect(n).toMatchObject({ id: "ap2", asignar: { tipo: "rol", valor: "APROBAR" }, cuatroOjos: true });
    expect(crearNodo(g, "fin")).toMatchObject({ id: "fin1", resultado: "APROBADO" });
    expect(crearNodo(g, "notificacion").destinatarios).toEqual([{ tipo: "iniciador", valor: "" }]);
    expect(agregarNodo(g, n).nodos).toHaveLength(4);
  });

  it("quitar un nodo se lleva sus conexiones", () => {
    const g = quitarNodo(serie("A", "B"), "ap1");
    expect(g.nodos.map((n) => n.id)).toEqual(["inicio", "ap2", "fin"]);
    expect(g.conexiones.every((c) => c.de !== "ap1" && c.a !== "ap1")).toBe(true);
  });

  it("actualiza nodos y conexiones; «si no» borra la condición", () => {
    let g = actualizarNodo(serie("A"), "ap1", { nombre: "Tesorero" });
    expect(g.nodos[1].nombre).toBe("Tesorero");
    g = conDecision();
    g = actualizarConexion(g, "c4", { defecto: true });
    expect(g.conexiones[3]).toEqual({ id: "c4", de: "d", a: "a2", defecto: true });
    g = actualizarConexion(g, "c4", { defecto: false, condicion: { modo: "todas", reglas: [] } });
    expect(g.conexiones[3]).toEqual({ id: "c4", de: "d", a: "a2", condicion: { modo: "todas", reglas: [] } });
    expect(quitarConexion(g, "c4").conexiones).toHaveLength(7);
  });

  it("conectar elige la salida que falta y avisa lo que no se puede", () => {
    let g = { schema: 1, nodos: [{ id: "i", tipo: "inicio" }, ap("a"), { id: "f", tipo: "fin", resultado: "APROBADO" },
      { id: "d", tipo: "decision" }], conexiones: [] };
    ({ grafo: g } = conectar(g, "i", "a"));
    ({ grafo: g } = conectar(g, "a", "f"));
    ({ grafo: g } = conectar(g, "a", "i"));
    expect(g.conexiones.map((c) => [c.de, c.a, c.salida])).toEqual([["i", "a", undefined], ["a", "f", "aprobado"], ["a", "i", "rechazado"]]);
    expect(conectar(g, "a", "d").error).toMatch(/dos salidas/);
    expect(conectar(g, "i", "f").error).toMatch(/una sola salida/);
    expect(conectar(g, "f", "a").error).toMatch(/Fin/);
    expect(conectar(g, "a", "a").error).toMatch(/consigo mismo/);
    expect(conectar(g, "a", "f").error).toMatch(/ya están conectados/);
    // Arrastrar desde el punto lateral (rojo) de una aprobación arma el «rechazado» aunque falte el «aprobado».
    const h = { ...g, conexiones: [] };
    expect(conectar(h, "a", "i", "rechazado").grafo.conexiones[0].salida).toBe("rechazado");
    ({ grafo: g } = conectar(g, "d", "f"));
    ({ grafo: g } = conectar(g, "d", "a"));
    expect(g.conexiones.slice(-2).map((c) => [c.defecto, c.condicion])).toEqual([[true, undefined], [undefined, { modo: "todas", reglas: [] }]]);
  });
});
