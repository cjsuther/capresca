/**
 * Grafo del workflow de aprobaciones: funciones PURAS (sin React ni red).
 *
 * `validar` es el espejo de `modules/configuraciones/app/services/wf_grafo.py` con los MISMOS códigos de
 * problema: sirve para marcar errores en vivo mientras se edita. La validación que manda al publicar
 * es la del backend.
 */

export const TIPOS = ["inicio", "aprobacion", "decision", "notificacion", "fin"];
export const ROLES = { APROBAR: "Aprobador", SUPERVISAR: "Supervisor" };
export const RESULTADOS = { APROBADO: "Aprobado", RECHAZADO: "Rechazado" };
export const TIPOS_DESTINATARIO = { rol: "Rol", grupo: "Grupo", usuario: "Usuario", iniciador: "Quien inició" };
export const OPERADORES = {
  numero: ["=", "!=", ">", ">=", "<", "<="],
  texto: ["=", "!=", "contiene"],
  opcion: ["=", "!=", "en"],
  booleano: ["="],
};
export const ETIQUETA_TIPO = {
  inicio: "Inicio", aprobacion: "Aprobación", decision: "Decisión", notificacion: "Notificación", fin: "Fin",
};
const MAX_NODOS = 200;

const p = (codigo, mensaje, { nodo = null, conexion = null, nivel = "error" } = {}) =>
  ({ codigo, nivel, mensaje, nodo, conexion });

export const nombreDe = (n) => (n?.nombre || "").trim() || ETIQUETA_TIPO[n?.tipo] || n?.tipo || "nodo";

// ── Validación ──────────────────────────────────────────────────────────────────────────────────
export function validar(grafo, variables = {}) {
  const probs = [];
  const nodos = grafo?.nodos || [];
  const conexiones = grafo?.conexiones || [];
  if (nodos.length > MAX_NODOS) return [p("DEMASIADOS_NODOS", `El workflow no puede tener más de ${MAX_NODOS} nodos.`)];

  const porId = new Map();
  for (const n of nodos) {
    if (!n?.id || typeof n.id !== "string") { probs.push(p("NODO_SIN_ID", "Hay un nodo sin identificador.")); continue; }
    if (porId.has(n.id)) { probs.push(p("ID_DUPLICADO", `Hay dos nodos con el id «${n.id}».`, { nodo: n.id })); continue; }
    if (!TIPOS.includes(n.tipo)) { probs.push(p("TIPO_INVALIDO", `Tipo de nodo desconocido: ${n.tipo}.`, { nodo: n.id })); continue; }
    porId.set(n.id, n);
  }

  const salen = new Map(); const entran = new Map(); const idsCon = new Set();
  for (const c0 of conexiones) {
    const cid = c0.id || `${c0.de}->${c0.a}`;
    if (idsCon.has(cid)) { probs.push(p("ID_DUPLICADO", `Hay dos conexiones con el id «${cid}».`, { conexion: cid })); continue; }
    idsCon.add(cid);
    if (!porId.has(c0.de) || !porId.has(c0.a)) {
      probs.push(p("CONEXION_ROTA", "Una conexión apunta a un nodo que no existe.", { conexion: cid })); continue;
    }
    if (c0.de === c0.a) {
      probs.push(p("CONEXION_A_SI_MISMO", "Un nodo no puede conectarse consigo mismo.", { conexion: cid, nodo: c0.de })); continue;
    }
    const c = { ...c0, id: cid };
    if (!salen.has(c.de)) salen.set(c.de, []);
    if (!entran.has(c.a)) entran.set(c.a, []);
    salen.get(c.de).push(c); entran.get(c.a).push(c);
  }

  const lista = [...porId.values()];
  const inicios = lista.filter((n) => n.tipo === "inicio");
  const fines = lista.filter((n) => n.tipo === "fin");
  if (inicios.length !== 1) probs.push(p("INICIO_UNICO", `Tiene que haber exactamente un nodo Inicio (hay ${inicios.length}).`));
  if (!fines.length) probs.push(p("FIN_REQUERIDO", "Tiene que haber al menos un nodo Fin."));

  for (const n of lista) {
    const out = salen.get(n.id) || [];
    if ((n.nombre || "").length > 80) probs.push(p("NOMBRE_LARGO", "El nombre no puede pasar de 80 caracteres.", { nodo: n.id }));
    if (n.tipo === "inicio" && out.length !== 1) {
      probs.push(p("SALIDAS_INICIO", "El Inicio tiene que tener exactamente una salida.", { nodo: n.id }));
    } else if (n.tipo === "fin") {
      if (out.length) probs.push(p("FIN_CON_SALIDA", "Un Fin no puede tener salidas.", { nodo: n.id }));
      if (!RESULTADOS[n.resultado]) probs.push(p("FIN_SIN_RESULTADO", `«${nombreDe(n)}»: elegí si termina Aprobado o Rechazado.`, { nodo: n.id }));
    } else if (n.tipo === "notificacion") {
      if (out.length !== 1) probs.push(p("SALIDAS_NOTIFICACION", `«${nombreDe(n)}»: una notificación tiene una sola salida.`, { nodo: n.id }));
      const dest = n.destinatarios || [];
      if (!dest.length) probs.push(p("NOTIFICACION_SIN_DESTINO", `«${nombreDe(n)}»: elegí a quién se avisa.`, { nodo: n.id }));
      if (dest.some((d) => !TIPOS_DESTINATARIO[d?.tipo] || (d.tipo !== "iniciador" && !String(d.valor || "").trim()))) {
        probs.push(p("DESTINATARIO_INVALIDO", `«${nombreDe(n)}»: hay un destinatario incompleto.`, { nodo: n.id }));
      }
    } else if (n.tipo === "aprobacion") {
      probs.push(...validarAprobacion(n, out));
    } else if (n.tipo === "decision") {
      probs.push(...validarDecision(n, out, variables));
    }
    for (const c of out) {
      if (c.salida && n.tipo !== "aprobacion") {
        probs.push(p("SALIDA_FUERA_DE_APROBACION", "Sólo una aprobación tiene salidas aprobado/rechazado.", { conexion: c.id, nodo: n.id }));
      }
      if ((c.condicion || c.defecto) && n.tipo !== "decision") {
        probs.push(p("CONDICION_FUERA_DE_DECISION", "Sólo una decisión lleva condiciones.", { conexion: c.id, nodo: n.id }));
      }
    }
  }

  if (inicios.length === 1) {
    const alc = bfs([inicios[0].id], (x) => (salen.get(x) || []).map((c) => c.a));
    for (const n of lista) if (!alc.has(n.id)) probs.push(p("HUERFANO", `«${nombreDe(n)}» no se alcanza desde el Inicio.`, { nodo: n.id }));
  }
  if (fines.length) {
    const llega = bfs(fines.map((f) => f.id), (x) => (entran.get(x) || []).map((c) => c.de));
    for (const n of lista) if (!llega.has(n.id)) probs.push(p("SIN_CAMINO_A_FIN", `Desde «${nombreDe(n)}» no se llega a ningún Fin.`, { nodo: n.id }));
  }

  const automaticos = new Set(lista.filter((n) => n.tipo !== "aprobacion").map((n) => n.id));
  for (const comp of componentesConCiclo(automaticos, salen)) {
    const nombres = [...comp].map((x) => nombreDe(porId.get(x))).sort();
    probs.push(p("CICLO_SIN_APROBACION", `Hay un ciclo que no pasa por ninguna aprobación: ${nombres.join(", ")}.`, { nodo: [...comp].sort()[0] }));
  }
  return probs;
}

function validarAprobacion(n, out) {
  const probs = [];
  const a = n.asignar || {};
  if (a.tipo === "rol") {
    if (!ROLES[a.valor]) probs.push(p("ROL_INVALIDO", `«${nombreDe(n)}»: rol inválido (${a.valor}).`, { nodo: n.id }));
  } else if (a.tipo === "grupo") {
    if (!String(a.valor || "").trim()) probs.push(p("GRUPO_VACIO", `«${nombreDe(n)}»: elegí el grupo que aprueba.`, { nodo: n.id }));
  } else {
    probs.push(p("SIN_ASIGNACION", `«${nombreDe(n)}»: elegí quién aprueba (rol o grupo).`, { nodo: n.id }));
  }
  const inc = new Set(n.incluir || []);
  const ambos = (n.excluir || []).filter((u) => inc.has(u));
  if (ambos.length) {
    probs.push(p("USUARIO_INCLUIDO_Y_EXCLUIDO", `«${nombreDe(n)}»: ${ambos.sort().join(", ")} figura como incluido y excluido a la vez.`, { nodo: n.id }));
  }
  const salidas = out.map((c) => c.salida);
  for (const s of ["aprobado", "rechazado"]) {
    if (salidas.filter((x) => x === s).length !== 1) {
      probs.push(p("SALIDAS_APROBACION", `«${nombreDe(n)}»: tiene que tener una salida «${s}».`, { nodo: n.id }));
    }
  }
  if (salidas.some((s) => s !== "aprobado" && s !== "rechazado")) {
    probs.push(p("SALIDAS_APROBACION", `«${nombreDe(n)}»: cada salida tiene que ser «aprobado» o «rechazado».`, { nodo: n.id }));
  }
  if (n.cuatroOjos === false) {
    probs.push(p("SIN_CUATRO_OJOS", `«${nombreDe(n)}»: sin cuatro-ojos, quien envió puede aprobar.`, { nodo: n.id, nivel: "aviso" }));
  }
  return probs;
}

function validarDecision(n, out, variables) {
  const probs = [];
  if (out.length < 2) probs.push(p("SALIDAS_DECISION", `«${nombreDe(n)}»: una decisión necesita al menos dos salidas.`, { nodo: n.id }));
  if (out.filter((c) => c.defecto).length !== 1) {
    probs.push(p("DECISION_SIN_DEFECTO", `«${nombreDe(n)}»: tiene que haber exactamente una salida «si no» (por defecto).`, { nodo: n.id }));
  }
  for (const c of out) {
    if (c.defecto) continue;
    const cond = c.condicion || {};
    const reglas = cond.reglas || [];
    if (!reglas.length) {
      probs.push(p("CONDICION_VACIA", `«${nombreDe(n)}»: una salida no tiene condición.`, { nodo: n.id, conexion: c.id }));
      continue;
    }
    if (!["todas", "alguna"].includes(cond.modo || "todas")) {
      probs.push(p("CONDICION_INVALIDA", "Modo de condición inválido.", { nodo: n.id, conexion: c.id }));
    }
    for (const r of reglas) {
      const msg = problemaRegla(r, variables);
      if (msg) probs.push(p("CONDICION_INVALIDA", `«${nombreDe(n)}»: ${msg}`, { nodo: n.id, conexion: c.id }));
    }
  }
  return probs;
}

/** Qué está mal en una regla de condición, o null. */
export function problemaRegla(r, variables) {
  const v = variables?.[r?.variable];
  if (!v) return `la variable «${r?.variable ?? ""}» no existe en este proceso.`;
  if (!(OPERADORES[v.tipo] || []).includes(r.op)) return `el operador «${r.op}» no sirve para «${v.nombre || r.variable}».`;
  const val = r.valor;
  if (v.tipo === "numero" && (typeof val !== "number" || Number.isNaN(val))) return `«${v.nombre}» se compara con un número.`;
  if (v.tipo === "booleano" && typeof val !== "boolean") return `«${v.nombre}» se compara con sí/no.`;
  if (v.tipo === "opcion") {
    const vals = r.op === "en" ? val : [val];
    if (!Array.isArray(vals) || !vals.length || vals.some((x) => !(v.opciones || []).includes(x))) {
      return `valor fuera de las opciones de «${v.nombre}».`;
    }
  }
  if (v.tipo === "texto" && !String(val ?? "").trim()) return `falta el texto a comparar en «${v.nombre}».`;
  return null;
}

function bfs(inicio, vecinos) {
  const vistos = new Set(inicio); const cola = [...inicio];
  while (cola.length) {
    for (const x of vecinos(cola.pop())) if (!vistos.has(x)) { vistos.add(x); cola.push(x); }
  }
  return vistos;
}

/** Componentes fuertemente conexas con ciclo (Tarjan) del subgrafo inducido por `nodos`. */
function componentesConCiclo(nodos, salen) {
  const indice = new Map(); const bajo = new Map(); const pila = []; const enPila = new Set(); const res = [];
  let i = 0;
  const vec = (v) => (salen.get(v) || []).map((c) => c.a).filter((w) => nodos.has(w));
  const visitar = (v) => {
    indice.set(v, i); bajo.set(v, i); i += 1; pila.push(v); enPila.add(v);
    for (const w of vec(v)) {
      if (!indice.has(w)) { visitar(w); bajo.set(v, Math.min(bajo.get(v), bajo.get(w))); }
      else if (enPila.has(w)) bajo.set(v, Math.min(bajo.get(v), indice.get(w)));
    }
    if (bajo.get(v) === indice.get(v)) {
      const comp = new Set();
      let w;
      do { w = pila.pop(); enPila.delete(w); comp.add(w); } while (w !== v);
      if (comp.size > 1) res.push(comp);
    }
  };
  for (const v of [...nodos].sort()) if (!indice.has(v)) visitar(v);
  return res;
}

export const errores = (probs) => probs.filter((x) => x.nivel === "error");

/** Problemas agrupados por nodo y por conexión (para pintarlos sobre el diagrama). */
export function problemasPorElemento(probs) {
  const nodos = {}; const conexiones = {};
  for (const x of probs) {
    if (x.nodo) (nodos[x.nodo] ||= []).push(x);
    if (x.conexion) (conexiones[x.conexion] ||= []).push(x);
  }
  return { nodos, conexiones };
}

// ── ¿Lo ejecuta el motor actual? (espejo de wf_grafo.proyectar, sólo el sí/no y los motivos) ──
export function motivosIncompatible(grafo) {
  const motivos = [];
  for (const n of grafo?.nodos || []) {
    if (n.tipo === "decision") motivos.push(`«${nombreDe(n)}» es una decisión: el motor actual sólo ejecuta aprobaciones en serie.`);
    else if (n.tipo === "notificacion") motivos.push(`«${nombreDe(n)}» es una notificación: el motor actual todavía no manda avisos.`);
    else if (n.tipo === "aprobacion" && n.asignar?.tipo === "grupo") {
      motivos.push(`«${nombreDe(n)}» la aprueba un grupo: el motor actual sólo entiende los roles APROBAR y SUPERVISAR.`);
    }
  }
  return motivos;
}

/** Cantidad de aprobaciones (para avisar si una versión nueva tiene menos niveles que la vigente). */
export const cantidadAprobaciones = (grafo) => (grafo?.nodos || []).filter((n) => n.tipo === "aprobacion").length;

// ── Edición (todas devuelven un grafo nuevo) ────────────────────────────────────────────────────
export function nuevoId(grafo, prefijo) {
  const usados = new Set([...(grafo?.nodos || []), ...(grafo?.conexiones || [])].map((x) => x.id));
  let i = 1;
  while (usados.has(`${prefijo}${i}`)) i += 1;
  return `${prefijo}${i}`;
}

const PREFIJO = { inicio: "inicio", aprobacion: "ap", decision: "dec", notificacion: "not", fin: "fin" };

export function crearNodo(grafo, tipo) {
  const id = nuevoId(grafo, PREFIJO[tipo] || "n");
  const base = { id, tipo, nombre: ETIQUETA_TIPO[tipo] };
  if (tipo === "aprobacion") Object.assign(base, { asignar: { tipo: "rol", valor: "APROBAR" }, cuatroOjos: true, incluir: [], excluir: [] });
  if (tipo === "notificacion") Object.assign(base, { destinatarios: [{ tipo: "iniciador", valor: "" }], mensaje: "" });
  if (tipo === "fin") Object.assign(base, { nombre: "Aprobado", resultado: "APROBADO" });
  if (tipo === "decision") base.nombre = "¿…?";
  return base;
}

export function agregarNodo(grafo, nodo) {
  return { ...grafo, nodos: [...(grafo.nodos || []), nodo] };
}

export function actualizarNodo(grafo, id, cambios) {
  return { ...grafo, nodos: grafo.nodos.map((n) => (n.id === id ? { ...n, ...cambios } : n)) };
}

export function quitarNodo(grafo, id) {
  return { ...grafo, nodos: grafo.nodos.filter((n) => n.id !== id),
           conexiones: grafo.conexiones.filter((c) => c.de !== id && c.a !== id) };
}

export function actualizarConexion(grafo, id, cambios) {
  return { ...grafo, conexiones: grafo.conexiones.map((c) => {
    if (c.id !== id) return c;
    const nueva = { ...c, ...cambios };
    if (nueva.defecto) delete nueva.condicion;
    for (const k of Object.keys(nueva)) if (nueva[k] === undefined || nueva[k] === false) delete nueva[k];
    return nueva;
  }) };
}

export function quitarConexion(grafo, id) {
  return { ...grafo, conexiones: grafo.conexiones.filter((c) => c.id !== id) };
}

/**
 * Conexión nueva de `de` a `a` con valores por defecto según el nodo de origen:
 * una aprobación usa la salida que le falte (primero «aprobado», después «rechazado»); una decisión
 * marca «si no» la primera salida y deja condición vacía en las demás. Devuelve {grafo, error}.
 */
export function conectar(grafo, de, a, salidaPreferida = null) {
  const origen = grafo.nodos.find((n) => n.id === de);
  if (!origen || !grafo.nodos.some((n) => n.id === a)) return { grafo, error: "Nodo inexistente." };
  if (de === a) return { grafo, error: "Un nodo no puede conectarse consigo mismo." };
  if (origen.tipo === "fin") return { grafo, error: "Un Fin no tiene salidas." };
  const out = grafo.conexiones.filter((c) => c.de === de);
  if (out.some((c) => c.a === a)) return { grafo, error: "Esos nodos ya están conectados." };
  const c = { id: nuevoId(grafo, "c"), de, a };
  if (origen.tipo === "aprobacion") {
    const orden = salidaPreferida === "rechazado" ? ["rechazado", "aprobado"] : ["aprobado", "rechazado"];
    const libre = orden.find((s) => !out.some((x) => x.salida === s));
    if (!libre) return { grafo, error: "La aprobación ya tiene sus dos salidas (aprobado y rechazado)." };
    c.salida = libre;
  } else if (origen.tipo === "decision") {
    if (!out.some((x) => x.defecto)) c.defecto = true;
    else c.condicion = { modo: "todas", reglas: [] };
  } else if (out.length >= 1) {
    return { grafo, error: `${ETIQUETA_TIPO[origen.tipo]} tiene una sola salida.` };
  }
  return { grafo: { ...grafo, conexiones: [...grafo.conexiones, c] }, error: null };
}
