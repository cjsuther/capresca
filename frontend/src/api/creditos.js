import api from "./client";

// Cliente del módulo Créditos (CCyPP). La API corre en su propio contenedor y se publica detrás del
// gateway en /api/creditos: la sesión, el token y el 401 → /login los maneja `client.js`, igual que
// en el resto de los módulos.
export const API = "/api/creditos";

// FastAPI devuelve `detail` como string (HTTPException) o como ARRAY de errores de validación
// (Pydantic 422). Sin normalizar, el error se renderiza como "[object Object]" en pantalla (H-200).
function mensajeDeError(data, status) {
  const d = data?.detail;
  // 403 del gateway: indica qué permiso de Portezuelo falta.
  if (typeof d === "string" && data?.required) return `${d}: falta el permiso ${data.required} (Seguridad).`;
  if (typeof d === "string" && d.trim()) return d;
  if (Array.isArray(d) && d.length) {
    const partes = d.map((e) => {
      const loc = Array.isArray(e?.loc) ? e.loc.filter((x) => x !== "body") : [];
      const campo = loc.length ? String(loc[loc.length - 1]) : "";
      const ctx = e?.ctx || {};
      let msg;
      switch (e?.type) {
        case "greater_than_equal": msg = `debe ser ≥ ${ctx.ge}`; break;
        case "less_than_equal": msg = `debe ser ≤ ${ctx.le}`; break;
        case "greater_than": msg = `debe ser > ${ctx.gt}`; break;
        case "less_than": msg = `debe ser < ${ctx.lt}`; break;
        case "missing": msg = "es obligatorio"; break;
        case "string_too_short": msg = `mínimo ${ctx.min_length} caracteres`; break;
        case "string_too_long": msg = `máximo ${ctx.max_length} caracteres`; break;
        default: msg = e?.msg || "valor inválido";
      }
      return campo ? `${campo}: ${msg}` : msg;
    }).filter(Boolean);
    if (partes.length) return partes.join(" · ");
  }
  return `Error ${status}`;
}

async function req(path, options = {}) {
  const { method = "GET", body, headers } = options;
  try {
    const res = await api.request({
      url: `/creditos${path}`,
      method,
      data: body,
      headers: { "Content-Type": "application/json", ...headers },
    });
    return res.status === 204 ? null : res.data;
  } catch (e) {
    if (!e.response) throw e;                       // red caída / timeout: se propaga tal cual
    throw new Error(mensajeDeError(e.response.data, e.response.status));
  }
}

// POST idempotente: manda una Idempotency-Key para que el backend deduplique reintentos y, además,
// dedup-lica en el cliente los envíos idénticos EN VUELO (doble clic) reusando la misma promesa.
// Sólo mientras está en vuelo: una segunda acción deliberada e idéntica sí tiene que salir.
const _idemInflight = new Map();

function postIdem(path, body) {
  const bodyStr = JSON.stringify(body ?? {});
  const sig = path + "|" + bodyStr;
  const enVuelo = _idemInflight.get(sig);
  if (enVuelo) return enVuelo;
  const key = globalThis.crypto?.randomUUID?.() || String(Date.now() + Math.random());
  const p = req(path, { method: "POST", body: bodyStr, headers: { "Idempotency-Key": key } })
    .finally(() => { if (_idemInflight.get(sig) === p) _idemInflight.delete(sig); });
  _idemInflight.set(sig, p);
  return p;
}

// Descarga/abre un archivo protegido (PDF/Excel). `path` ya viene absoluto (incluye API).
/** Trae un archivo del backend como Blob (con la sesión del usuario), para mostrarlo en la página. */
async function traerArchivo(path) {
  try {
    const res = await api.request({ url: path, baseURL: "", responseType: "blob" });
    return res.data;
  } catch (e) {
    throw new Error(e.response ? "No se pudo abrir el archivo" : e.message);
  }
}

async function abrirArchivo(path, downloadName) {
  let res;
  try {
    res = await api.request({ url: path, baseURL: "", responseType: "blob" });
  } catch (e) {
    throw new Error(e.response ? "No se pudo generar el archivo" : e.message);
  }
  const url = URL.createObjectURL(res.data);
  if (downloadName) {
    const a = document.createElement("a");
    a.href = url;
    a.download = downloadName;
    a.click();
  } else {
    window.open(url, "_blank");
  }
}

export const creditos = {
  // Configurar Créditos (catálogo de líneas de producto)
  ppCatalogo: () => req(`/productos`),
  ppCrear: (d = {}) => postIdem(`/productos`, d),
  ppPreview: (payload) => req(`/productos/preview`, { method: "POST", body: JSON.stringify(payload) }),
  ppSimGuardar: (id, d) => req(`/productos/${id}/simulaciones`, { method: "POST", body: JSON.stringify(d) }),
  ppSimPreview: (id, d) => req(`/productos/${id}/simular-preview`, { method: "POST", body: JSON.stringify(d) }),
  ppSimListar: (id) => req(`/productos/${id}/simulaciones`),
  ppSimBorrar: (id, simId) => req(`/productos/${id}/simulaciones/${simId}`, { method: "DELETE" }),
  ppFamilias: () => req(`/productos/_familias`),
  ppModelo: () => req(`/productos/_modelo`),
  ppRaw: (id) => req(`/productos/${id}/raw`),
  ppVersiones: (id) => req(`/productos/${id}/versiones`),
  // Maestro de impuestos (Contabilidad)
  impuestos: (estado) => req(`/impuestos${estado ? `?estado=${estado}` : ""}`),
  indices: (estado) => req(`/indices${estado ? `?estado=${estado}` : ""}`),
  ppGuardarConfig: (id, cfg) => req(`/productos/${id}/config`, { method: "PUT", body: JSON.stringify(cfg) }),
  ppNuevaVersion: (id) => req(`/productos/${id}/nueva-version`, { method: "POST" }),
  ppPublicarDirecto: (id) => req(`/productos/${id}/publicar-directo`, { method: "POST" }),
  ppEstado: (id, accion) => req(`/productos/${id}/estado`, { method: "POST", body: JSON.stringify({ accion }) }),
  ppBorrar: (id) => req(`/productos/${id}`, { method: "DELETE" }),
  // Originación (Fase 5) y servicing (Fase 6)
  ppOferta: (ctx = {}) => {
    const q = new URLSearchParams();
    if (ctx.segmento)
      q.set("segmento", ctx.segmento);
    if (ctx.canal)
      q.set("canal", ctx.canal);
    if (ctx.edad != null)
      q.set("edad", String(ctx.edad));
    if (ctx.antiguedad_meses != null)
      q.set("antiguedad_meses", String(ctx.antiguedad_meses));
    if (ctx.solo_elegibles)
      q.set("solo_elegibles", "true");
    const s = q.toString();
    return req(`/contratos/oferta${s ? `?${s}` : ""}`);
  },
  ctoSegmentos: () => req(`/contratos/segmentos`),
  ctoTablero: () => req(`/contratos/tablero`),
  ctoSolicitudes: (q = "") => req(`/contratos/solicitudes${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  ctoOriginar: (d) => postIdem(`/contratos/originar`, d),
  ctoDesembolsar: (id) => postIdem(`/contratos/${id}/desembolsar`, {}),
  ctoLotesLiquidacion: () => req(`/contratos/lotes-liquidacion`),
  ctoLiquidarLote: (fecha) => postIdem(`/contratos/liquidar-lote`, { fecha }),
  ctoRefinanciar: (id, tasa, plazo) => postIdem(`/contratos/${id}/refinanciar`, { tasa, plazo }),
  ctoActividadCaja: (id, tipo, importe, medio_pago, modo, cuotas) => postIdem(`/contratos/${id}/actividad`, { tipo, importe, medio_pago, ...(modo ? { modo } : {}), ...(cuotas ? { cuotas } : {}) }),
  // Solicitudes de crédito (línea nueva / product builder)
  ppSolicitudes: (p = {}) => {
    const s = new URLSearchParams();
    if (p.estado)
      s.set("estado", p.estado);
    if (p.q)
      s.set("q", p.q);
    const qs = s.toString();
    return req(`/solicitudes${qs ? `?${qs}` : ""}`);
  },
  ppSolicitudCrear: (d) => postIdem(`/solicitudes`, d),
  ppSolicitud: (id) => req(`/solicitudes/${id}`),
  ppSolicitudEditar: (id, d) => req(`/solicitudes/${id}`, { method: "PUT", body: JSON.stringify(d) }),
  ppSolicitudEstado: (id, accion, motivo = "", observacion = "") => req(`/solicitudes/${id}/estado`, { method: "POST", body: JSON.stringify({ accion, motivo, observacion }) }),
  ppSolicitudPromover: (id, d = {}) => req(`/solicitudes/${id}/promover-cliente`, { method: "POST", body: JSON.stringify(d) }),
  ppSolicitudDocs: (sid) => req(`/solicitudes/${sid}/documentos`),
  ppSolicitudDocAbrir: (sid, docId) => abrirArchivo(`${API}/solicitudes/${sid}/documentos/${docId}`),
  ppSolicitudDocArchivo: (sid, docId) => traerArchivo(`${API}/solicitudes/${sid}/documentos/${docId}`),
  ctoDevengar: (id) => req(`/contratos/${id}/devengar`, { method: "POST" }),
  ctoPdf: (id, numero) => abrirArchivo(`${API}/contratos/${id}/pdf`, `${numero}.pdf`),
  ctoCarteraExcel: () => abrirArchivo(`${API}/contratos/export.xlsx`, "cartera_creditos.xlsx"),
  ctoListar: () => req(`/contratos`),
  ctoSituacion: (q = "") => req(`/contratos/situacion${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  ctoObtener: (id) => req(`/contratos/${id}`),
  ctoActividad: (id, tipo, importe = 0, detalle = "", fecha, modo) => postIdem(`/contratos/${id}/actividad`, { tipo, importe, detalle, fecha, ...(modo ? { modo } : {}) }),
  ctoReversar: (id, actividadId) => req(`/contratos/${id}/actividad/${actividadId}/reversar`, { method: "POST" }),
  clientes: (p = {}) => {
    const s = new URLSearchParams();
    if (p.q)
      s.set("q", p.q);
    if (p.estado)
      s.set("estado", p.estado);
    if (p.organismo_id)
      s.set("organismo_id", String(p.organismo_id));
    if (p.limit != null)
      s.set("limit", String(p.limit));
    if (p.offset != null)
      s.set("offset", String(p.offset));
    if (p.sort)
      s.set("sort", p.sort);
    if (p.order)
      s.set("order", p.order);
    const qs = s.toString();
    return req(`/clientes${qs ? `?${qs}` : ""}`);
  },
  obtenerCliente: (id) => req(`/clientes/${id}`),
  lineas: () => req(`/creditos/lineas`),
  simular: (payload) => req(`/creditos/simular`, { method: "POST", body: JSON.stringify(payload) }),
  // Solicitudes
  solicitudes: (estado = "") => req(`/creditos/solicitudes${estado ? `?estado=${estado}` : ""}`),
  solicitud: (id) => req(`/creditos/solicitudes/${id}`),
  crearSolicitud: (payload) => req(`/creditos/solicitudes`, { method: "POST", body: JSON.stringify(payload) }),
  otorgar: (id, forzar = false) => req(`/creditos/solicitudes/${id}/otorgar${forzar ? "?forzar=true" : ""}`, {
    method: "POST",
  }),
  credito: (id) => req(`/creditos/${id}`),
  simularCancelacion: (id, fecha) => req(`/creditos/${id}/cancelacion?fecha=${fecha}`),
  cancelarCredito: (id, payload) => postIdem(`/creditos/${id}/cancelar`, payload), // dinero: dedup doble-click + Idempotency-Key
  bajaCredito: (id, motivo) => req(`/creditos/${id}/baja`, { method: "POST", body: JSON.stringify({ motivo }) }),
  recalculoPreview: (id, q) => {
    const s = new URLSearchParams({ modo: q.modo });
    if (q.primer_vto)
      s.set("primer_vto", q.primer_vto);
    if (q.haber)
      s.set("haber", q.haber);
    return req(`/creditos/${id}/recalculo?${s.toString()}`);
  },
  recalculoAplicar: (id, payload) => req(`/creditos/${id}/recalculo`, { method: "POST", body: JSON.stringify(payload) }),
  turnosPreview: (periodo, cantidad, grupo = "TODO") => req(`/creditos/turnos/generar/preview?periodo=${periodo}&cantidad=${cantidad}&grupo=${grupo}`),
  turnosGenerar: (payload) => req(`/creditos/turnos/generar`, { method: "POST", body: JSON.stringify(payload) }),
  turnoAsignar: (payload) => req(`/creditos/turnos/asignar`, { method: "POST", body: JSON.stringify(payload) }),
  verReciboPdf: (id) => abrirArchivo(`${API}/caja/recibos/${id}/pdf`),
  editarDisponibilidad: (id, body) => req(`/productos/${id}/disponibilidad`, { method: "PUT", body: JSON.stringify(body) }),
  pendientesCobro: (fecha) => req(`/caja/pendientes-cobro?fecha_corte=${fecha}`),
  verPendientesPdf: (fecha) => abrirArchivo(`${API}/caja/pendientes-cobro/pdf?fecha_corte=${fecha}`),
  verCarteraPdf: () => abrirArchivo(`${API}/creditos/consultas/estadisticas/pdf`),
  descargarEnviosExcel: (desde, hasta) => abrirArchivo(`${API}/creditos/consultas/envios/excel?desde=${desde}&hasta=${hasta}`, `padron_debito_${desde}_${hasta}.xlsx`),
  // Consultas de créditos
  jubiladosResumen: () => req(`/creditos/consultas/jubilados/resumen`),
  jubiladosPorDepto: () => req(`/creditos/consultas/jubilados/por-departamento`),
  listadoCreditos: (p = {}) => {
    const s = new URLSearchParams();
    if (p.estado)
      s.set("estado", p.estado);
    if (p.q)
      s.set("q", p.q);
    if (p.limit != null)
      s.set("limit", String(p.limit));
    if (p.offset != null)
      s.set("offset", String(p.offset));
    if (p.sort)
      s.set("sort", p.sort);
    if (p.order)
      s.set("order", p.order);
    const qs = s.toString();
    return req(`/creditos/consultas/creditos${qs ? `?${qs}` : ""}`);
  },
  cuotasMora: (fecha) => req(`/creditos/consultas/cuotas-mora?fecha_corte=${fecha}`),
  resumenCobros: (p = {}) => {
    const s = new URLSearchParams();
    if (p.desde)
      s.set("desde", p.desde);
    if (p.hasta)
      s.set("hasta", p.hasta);
    const qs = s.toString();
    return req(`/creditos/consultas/resumen-cobros${qs ? `?${qs}` : ""}`);
  },
  pagosEnCaja: (p = {}) => {
    const s = new URLSearchParams();
    if (p.desde)
      s.set("desde", p.desde);
    if (p.hasta)
      s.set("hasta", p.hasta);
    if (p.credito_id != null)
      s.set("credito_id", String(p.credito_id));
    if (p.via)
      s.set("via", p.via);
    if (p.limit != null)
      s.set("limit", String(p.limit));
    if (p.offset != null)
      s.set("offset", String(p.offset));
    const qs = s.toString();
    return req(`/creditos/consultas/pagos-caja${qs ? `?${qs}` : ""}`);
  },
  descargarPagosEnCajaExcel: (p = {}) => {
    const s = new URLSearchParams();
    if (p.desde)
      s.set("desde", p.desde);
    if (p.hasta)
      s.set("hasta", p.hasta);
    if (p.credito_id != null)
      s.set("credito_id", String(p.credito_id));
    const qs = s.toString();
    return abrirArchivo(`${API}/creditos/consultas/pagos-caja/excel${qs ? `?${qs}` : ""}`, "pagos_en_caja.xlsx");
  },
  creditosSinDebito: (p = {}) => {
    const s = new URLSearchParams();
    if (p.q)
      s.set("q", p.q);
    if (p.linea_id != null)
      s.set("linea_id", String(p.linea_id));
    if (p.limit != null)
      s.set("limit", String(p.limit));
    if (p.offset != null)
      s.set("offset", String(p.offset));
    const qs = s.toString();
    return req(`/creditos/consultas/sin-debito${qs ? `?${qs}` : ""}`);
  },
  situacionCliente: (id) => req(`/creditos/consultas/cliente/${id}/situacion`),
  cuentaCorriente: (creditoId) => req(`/creditos/consultas/cuenta-corriente/${creditoId}`),
  estadisticas: () => req(`/creditos/consultas/estadisticas`),
  situacionPorCartera: () => req(`/creditos/consultas/por-cartera`),
  verPorCarteraPdf: () => abrirArchivo(`${API}/creditos/consultas/por-cartera/pdf`),
  descargarListadoCreditosExcel: (p = {}) => {
    const s = new URLSearchParams();
    if (p.estado)
      s.set("estado", p.estado);
    if (p.q)
      s.set("q", p.q);
    if (p.sort)
      s.set("sort", p.sort);
    if (p.order)
      s.set("order", p.order);
    const qs = s.toString();
    return abrirArchivo(`${API}/creditos/consultas/creditos/excel${qs ? `?${qs}` : ""}`, "listado_creditos.xlsx");
  },
  // Generador de informes de créditos (filtros combinables)
  informeCreditos: (p = {}) => {
    const s = new URLSearchParams();
    Object.entries(p).forEach(([k, v]) => { if (v !== undefined && v !== "" && v !== null)
      s.set(k, String(v)); });
    const qs = s.toString();
    return req(`/creditos/consultas/creditos${qs ? `?${qs}` : ""}`);
  },
  descargarInformeCreditosExcel: (p = {}) => {
    const s = new URLSearchParams();
    Object.entries(p).forEach(([k, v]) => { if (v !== undefined && v !== "" && v !== null)
      s.set(k, String(v)); });
    const qs = s.toString();
    return abrirArchivo(`${API}/creditos/consultas/creditos/excel${qs ? `?${qs}` : ""}`, "informe_creditos.xlsx");
  },
  turnosOtorgados: (p = {}) => {
    const s = new URLSearchParams();
    if (p.periodo)
      s.set("periodo", p.periodo);
    if (p.tipo)
      s.set("tipo", p.tipo);
    if (p.usado != null)
      s.set("usado", String(p.usado));
    if (p.q)
      s.set("q", p.q);
    if (p.limit != null)
      s.set("limit", String(p.limit));
    if (p.offset != null)
      s.set("offset", String(p.offset));
    const qs = s.toString();
    return req(`/creditos/consultas/turnos${qs ? `?${qs}` : ""}`);
  },
  descargarTurnosExcel: (p = {}) => {
    const s = new URLSearchParams();
    if (p.periodo)
      s.set("periodo", p.periodo);
    if (p.tipo)
      s.set("tipo", p.tipo);
    if (p.usado != null)
      s.set("usado", String(p.usado));
    if (p.q)
      s.set("q", p.q);
    const qs = s.toString();
    return abrirArchivo(`${API}/creditos/consultas/turnos/excel${qs ? `?${qs}` : ""}`, "turnos_otorgados.xlsx");
  },
  envios: (desde, hasta) => req(`/creditos/consultas/envios?desde=${desde}&hasta=${hasta}`),
  // Utilidades / Tablas (ABM)
  adminLineas: () => req(`/admin/lineas`),
  crearLinea: (payload) => req(`/admin/lineas`, { method: "POST", body: JSON.stringify(payload) }),
  editarLinea: (id, payload) => req(`/admin/lineas/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  adminOrganismos: () => req(`/admin/organismos`),
  adminParametros: (ambito) => req(`/admin/parametros${ambito ? `?ambito=${encodeURIComponent(ambito)}` : ""}`),
  upsertParametro: (payload) => req(`/admin/parametros`, { method: "POST", body: JSON.stringify(payload) }),
  inboxAprobaciones: () => req(`/aprobaciones/inbox`),
  inboxAprobarPendiente: (pid) => req(`/aprobaciones/pendientes/${pid}/aprobar`, { method: "POST" }),
  inboxRechazarPendiente: (pid, motivo = "") => req(`/aprobaciones/pendientes/${pid}/rechazar`, { method: "POST", body: JSON.stringify({ motivo }) }),
  sistemaCalculos: () => req(`/sistema-calculos`),
  sistemaCalculosDebug: (d) => req(`/sistema-calculos/debug`, { method: "POST", body: JSON.stringify(d) }),
};
