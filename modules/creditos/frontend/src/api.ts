// Cliente HTTP mínimo para la API CCyPP.
//
// Créditos corre dentro de Portezuelo: no tiene login propio. La sesión es la del sistema (mismo origen):
// el login de Portezuelo guarda el JWT en sessionStorage ("auth-storage", zustand persist) y el gateway
// publica esta API bajo /api/creditos.
const SESION_KEY = "auth-storage";
const EMPRESA_KEY = "ccypp_empresa";   // empresa contable activa (multi-plan, H-188)
export const API = "/api/creditos";

function sesion(): any {
  try { return JSON.parse(sessionStorage.getItem(SESION_KEY) || "null")?.state ?? null; } catch { return null; }
}
export function getToken(): string | null {
  return sesion()?.token || null;
}
/** Usuario logueado en Portezuelo (para mostrar en la topbar). */
export function usuarioSesion(): { username: string; nombre: string } {
  const u = sesion()?.user;
  return { username: u?.username || "", nombre: u?.full_name || u?.username || "" };
}
export function logout() {
  try { sessionStorage.removeItem(SESION_KEY); } catch { /* ignore */ }
}
/** Login de Portezuelo; al ingresar vuelve a la pantalla actual de Créditos. */
export function irAlLogin() {
  const aca = window.location.pathname + window.location.search;
  window.location.assign(`/login?next=${encodeURIComponent(aca)}`);
}
/** Cierra la sesión de Portezuelo (revoca el token) y vuelve a su login. */
export async function salir() {
  const token = getToken();
  if (token) await fetch("/api/auth/logout", { method: "POST", headers: { Authorization: `Bearer ${token}` } }).catch(() => {});
  logout();
  window.location.assign("/login");
}

// Empresa contable activa: la eligen las pantallas de Contabilidad; se agrega como empresa_id a TODA
// llamada /contabilidad/* (los endpoints que no la usan la ignoran). Cambia en un solo lugar.
export function getEmpresaActiva(): number | undefined {
  const v = localStorage.getItem(EMPRESA_KEY);
  return v ? Number(v) : undefined;
}
export function setEmpresaActiva(id: number | undefined) {
  if (id) localStorage.setItem(EMPRESA_KEY, String(id)); else localStorage.removeItem(EMPRESA_KEY);
  window.dispatchEvent(new CustomEvent("empresa-cambiada", { detail: id }));
}

async function req(path: string, options: RequestInit = {}) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  // Inyecta la empresa activa en las llamadas contables (si no viene ya en la URL).
  const emp = getEmpresaActiva();
  if (emp && path.startsWith("/contabilidad/") && !/[?&]empresa_id=/.test(path)) {
    path += (path.includes("?") ? "&" : "?") + `empresa_id=${emp}`;
  }
  const res = await fetch(`${API}${path}`, { ...options, headers });
  if (res.status === 401) {
    // Token ausente o vencido: limpiar la sesión y volver al login de Portezuelo (evita pantallas
    // vacías silenciosas).
    logout();
    irAlLogin();
    throw new Error("Sesión expirada. Volvé a iniciar sesión.");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({} as any));
    throw new Error(mensajeDeError(data, res.status));
  }
  return res.status === 204 ? null : res.json();
}

// FastAPI devuelve `detail` como string (HTTPException) o como ARRAY de errores de validación
// (Pydantic 422). Sin normalizar, `new Error(array)` se renderiza como "[object Object]" en pantalla.
// Acá lo convertimos a un mensaje legible por campo (H-200).
function mensajeDeError(data: any, status: number): string {
  const d = data?.detail;
  // 403 del gateway: indica qué permiso de Portezuelo falta.
  if (typeof d === "string" && data?.required) return `${d}: falta el permiso ${data.required} (Seguridad de Portezuelo).`;
  if (typeof d === "string" && d.trim()) return d;
  if (Array.isArray(d) && d.length) {
    const partes = d.map((e: any) => {
      const loc = Array.isArray(e?.loc) ? e.loc.filter((x: any) => x !== "body") : [];
      const campo = loc.length ? String(loc[loc.length - 1]) : "";
      const ctx = e?.ctx || {};
      let msg: string;
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

// POST idempotente: manda una Idempotency-Key para que el backend deduplique reintentos, y ademas
// dedup-lica en el cliente los envíos idénticos en vuelo (doble clic) reusando la misma promesa+clave.
const _idemInflight = new Map<string, Promise<any>>();
function postIdem(path: string, body: any) {
  // Dedup SÓLO mientras la request está EN VUELO: evita el doble-submit concurrente (doble-clic antes de que
  // responda) sin tragar acciones deliberadas repetidas. Antes se retenía 4 s tras responder, lo que hacía
  // que una 2ª acción idéntica (p.ej. "Pagar próxima cuota" de la cuota siguiente, o "Diferir" otra cuota)
  // devolviera el resultado viejo y se perdiera. El árbitro real de idempotencia es la Idempotency-Key + backend.
  const bodyStr = JSON.stringify(body ?? {});
  const sig = path + "|" + bodyStr;
  const enVuelo = _idemInflight.get(sig);
  if (enVuelo) return enVuelo;
  const key = (globalThis.crypto?.randomUUID?.() || String(Date.now() + Math.random()));
  const p = req(path, { method: "POST", body: bodyStr, headers: { "Idempotency-Key": key } })
    .finally(() => { if (_idemInflight.get(sig) === p) _idemInflight.delete(sig); });
  _idemInflight.set(sig, p);
  return p;
}

// Descarga/abre un archivo protegido (PDF/Excel) usando el token.
async function abrirArchivo(path: string, downloadName?: string) {
  const res = await fetch(path, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (res.status === 401) { logout(); irAlLogin(); throw new Error("Sesión expirada. Volvé a iniciar sesión."); }
  if (!res.ok) throw new Error("No se pudo generar el archivo");
  const url = URL.createObjectURL(await res.blob());
  if (downloadName) {
    const a = document.createElement("a");
    a.href = url;
    a.download = downloadName;
    a.click();
  } else {
    window.open(url, "_blank");
  }
}

export const api = {
  // Configurar Créditos (catálogo de líneas de producto)
  ppCatalogo: () => req(`/productos`),
  ppCrear: (d: { nombre?: string; familia_id?: string; copiar_de?: string; padre_id?: string } = {}) => postIdem(`/productos`, d),
  ppPreview: (payload: any) => req(`/productos/preview`, { method: "POST", body: JSON.stringify(payload) }),
  ppSimGuardar: (id: string, d: { monto: number; plazo: number; tna?: number; etiqueta?: string }) => req(`/productos/${id}/simulaciones`, { method: "POST", body: JSON.stringify(d) }),
  ppSimPreview: (id: string, d: { monto: number; plazo: number; segmento?: string; canal?: string; edad?: number; antiguedad_meses?: number }) => req(`/productos/${id}/simular-preview`, { method: "POST", body: JSON.stringify(d) }),
  ppSimListar: (id: string) => req(`/productos/${id}/simulaciones`),
  ppSimBorrar: (id: string, simId: string) => req(`/productos/${id}/simulaciones/${simId}`, { method: "DELETE" }),
  ppFamilias: () => req(`/productos/_familias`),
  ppModelo: () => req(`/productos/_modelo`),
  ppRaw: (id: string) => req(`/productos/${id}/raw`),
  ppVersiones: (id: string) => req(`/productos/${id}/versiones`),
  // Maestro de impuestos (Contabilidad)
  impuestos: (estado?: string) => req(`/impuestos${estado ? `?estado=${estado}` : ""}`),
  impuestoCrear: (d: any) => req(`/impuestos`, { method: "POST", body: JSON.stringify(d) }),
  impuestoEditar: (id: number, d: any) => req(`/impuestos/${id}`, { method: "PUT", body: JSON.stringify(d) }),
  impuestoBaja: (id: number) => req(`/impuestos/${id}/baja`, { method: "POST" }),
  impuestoReactivar: (id: number) => req(`/impuestos/${id}/reactivar`, { method: "POST" }),
  indices: (estado?: string) => req(`/indices${estado ? `?estado=${estado}` : ""}`),
  indiceCrear: (d: any) => req(`/indices`, { method: "POST", body: JSON.stringify(d) }),
  indiceEditar: (id: number, d: any) => req(`/indices/${id}`, { method: "PUT", body: JSON.stringify(d) }),
  indiceBaja: (id: number) => req(`/indices/${id}/baja`, { method: "POST" }),
  indiceReactivar: (id: number) => req(`/indices/${id}/reactivar`, { method: "POST" }),
  ppGuardarConfig: (id: string, cfg: any) => req(`/productos/${id}/config`, { method: "PUT", body: JSON.stringify(cfg) }),
  ppNuevaVersion: (id: string) => req(`/productos/${id}/nueva-version`, { method: "POST" }),
  ppPublicarDirecto: (id: string) => req(`/productos/${id}/publicar-directo`, { method: "POST" }),
  ppEstado: (id: string, accion: string) => req(`/productos/${id}/estado`, { method: "POST", body: JSON.stringify({ accion }) }),
  ppBorrar: (id: string) => req(`/productos/${id}`, { method: "DELETE" }),
  // Originación (Fase 5) y servicing (Fase 6)
  ppOferta: (ctx: { segmento?: string; canal?: string; edad?: number; antiguedad_meses?: number; solo_elegibles?: boolean } = {}) => {
    const q = new URLSearchParams();
    if (ctx.segmento) q.set("segmento", ctx.segmento);
    if (ctx.canal) q.set("canal", ctx.canal);
    if (ctx.edad != null) q.set("edad", String(ctx.edad));
    if (ctx.antiguedad_meses != null) q.set("antiguedad_meses", String(ctx.antiguedad_meses));
    if (ctx.solo_elegibles) q.set("solo_elegibles", "true");
    const s = q.toString();
    return req(`/contratos/oferta${s ? `?${s}` : ""}`);
  },
  ctoSegmentos: () => req(`/contratos/segmentos`),
  ctoBundles: () => req(`/contratos/bundles`),
  ctoTablero: () => req(`/contratos/tablero`),
  ctoSolicitudes: (q = "") => req(`/contratos/solicitudes${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  ctoOriginar: (d: { producto_id: string; cliente_nombre: string; monto: number; plazo: number; tasa?: number; segmento?: string; canal?: string; edad?: number; antiguedad_meses?: number; relacion?: string; solicitud_id?: number; solicitud_pp_id?: string; datos_adicionales?: any; desembolsar?: boolean }) => postIdem(`/contratos/originar`, d),
  ctoDesembolsar: (id: string) => postIdem(`/contratos/${id}/desembolsar`, {}),
  ctoLotesLiquidacion: () => req(`/contratos/lotes-liquidacion`),
  ctoLiquidarLote: (fecha: string) => postIdem(`/contratos/liquidar-lote`, { fecha }),
  ctoRefinanciar: (id: string, tasa: number, plazo: number) => postIdem(`/contratos/${id}/refinanciar`, { tasa, plazo }),
  ctoActividadCaja: (id: string, tipo: string, importe: number, medio_pago: string, modo?: string, cuotas?: number) => postIdem(`/contratos/${id}/actividad`, { tipo, importe, medio_pago, ...(modo ? { modo } : {}), ...(cuotas ? { cuotas } : {}) }),
  // Solicitudes de crédito (línea nueva / product builder)
  ppSolicitudes: (p: { estado?: string; q?: string } = {}) => {
    const s = new URLSearchParams();
    if (p.estado) s.set("estado", p.estado);
    if (p.q) s.set("q", p.q);
    const qs = s.toString();
    return req(`/solicitudes${qs ? `?${qs}` : ""}`);
  },
  ppSolicitudCrear: (d: any) => postIdem(`/solicitudes`, d),
  ppSolicitud: (id: string) => req(`/solicitudes/${id}`),
  ppSolicitudEditar: (id: string, d: any) => req(`/solicitudes/${id}`, { method: "PUT", body: JSON.stringify(d) }),
  ppSolicitudEstado: (id: string, accion: string, motivo = "", observacion = "") => req(`/solicitudes/${id}/estado`, { method: "POST", body: JSON.stringify({ accion, motivo, observacion }) }),
  ppSolicitudPromover: (id: string, d: { cliente_id?: number; cuil?: string; dni?: string; apellido_nombre?: string } = {}) => req(`/solicitudes/${id}/promover-cliente`, { method: "POST", body: JSON.stringify(d) }),
  ppSolicitudDocs: (sid: string) => req(`/solicitudes/${sid}/documentos`),
  ppSolicitudDocAbrir: (sid: string, docId: string) => abrirArchivo(`${API}/solicitudes/${sid}/documentos/${docId}`),
  ctoDevengar: (id: string) => req(`/contratos/${id}/devengar`, { method: "POST" }),
  ctoPdf: (id: string, numero: string) => abrirArchivo(`${API}/contratos/${id}/pdf`, `${numero}.pdf`),
  ctoCarteraExcel: () => abrirArchivo(`${API}/contratos/export.xlsx`, "cartera_creditos.xlsx"),
  ctoListar: () => req(`/contratos`),
  ctoSituacion: (q = "") => req(`/contratos/situacion${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  ctoObtener: (id: string) => req(`/contratos/${id}`),
  ctoActividad: (id: string, tipo: string, importe = 0, detalle = "", fecha?: string, modo?: string) => postIdem(`/contratos/${id}/actividad`, { tipo, importe, detalle, fecha, ...(modo ? { modo } : {}) }),
  ctoReversar: (id: string, actividadId: string) => req(`/contratos/${id}/actividad/${actividadId}/reversar`, { method: "POST" }),

  clientes: (p: { q?: string; estado?: string; organismo_id?: number; limit?: number; offset?: number; sort?: string; order?: string } = {}) => {
    const s = new URLSearchParams();
    if (p.q) s.set("q", p.q);
    if (p.estado) s.set("estado", p.estado);
    if (p.organismo_id) s.set("organismo_id", String(p.organismo_id));
    if (p.limit != null) s.set("limit", String(p.limit));
    if (p.offset != null) s.set("offset", String(p.offset));
    if (p.sort) s.set("sort", p.sort);
    if (p.order) s.set("order", p.order);
    const qs = s.toString();
    return req(`/clientes${qs ? `?${qs}` : ""}`);
  },
  obtenerCliente: (id: number) => req(`/clientes/${id}`),
  crearCliente: (data: any) => postIdem(`/clientes`, data),
  editarCliente: (id: number, data: any) => req(`/clientes/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  bajaCliente: (id: number, motivo: string) => req(`/clientes/${id}/baja`, { method: "POST", body: JSON.stringify({ motivo }) }),
  reactivarCliente: (id: number) => req(`/clientes/${id}/reactivar`, { method: "POST" }),
  lineas: () => req(`/creditos/lineas`),
  simular: (payload: any) =>
    req(`/creditos/simular`, { method: "POST", body: JSON.stringify(payload) }),
  // Solicitudes
  solicitudes: (estado = "") =>
    req(`/creditos/solicitudes${estado ? `?estado=${estado}` : ""}`),
  solicitud: (id: number) => req(`/creditos/solicitudes/${id}`),
  crearSolicitud: (payload: any) =>
    req(`/creditos/solicitudes`, { method: "POST", body: JSON.stringify(payload) }),
  otorgar: (id: number, forzar = false) =>
    req(`/creditos/solicitudes/${id}/otorgar${forzar ? "?forzar=true" : ""}`, {
      method: "POST",
    }),
  credito: (id: number) => req(`/creditos/${id}`),
  simularCancelacion: (id: number, fecha: string) =>
    req(`/creditos/${id}/cancelacion?fecha=${fecha}`),
  cancelarCredito: (id: number, payload: any) =>
    postIdem(`/creditos/${id}/cancelar`, payload),   // dinero: dedup doble-click + Idempotency-Key
  bajaCredito: (id: number, motivo: string) =>
    req(`/creditos/${id}/baja`, { method: "POST", body: JSON.stringify({ motivo }) }),
  recalculoPreview: (id: number, q: { modo: string; primer_vto?: string; haber?: string }) => {
    const s = new URLSearchParams({ modo: q.modo });
    if (q.primer_vto) s.set("primer_vto", q.primer_vto);
    if (q.haber) s.set("haber", q.haber);
    return req(`/creditos/${id}/recalculo?${s.toString()}`);
  },
  recalculoAplicar: (id: number, payload: any) =>
    req(`/creditos/${id}/recalculo`, { method: "POST", body: JSON.stringify(payload) }),
  turnosPreview: (periodo: string, cantidad: number, grupo = "TODO") =>
    req(`/creditos/turnos/generar/preview?periodo=${periodo}&cantidad=${cantidad}&grupo=${grupo}`),
  turnosGenerar: (payload: any) =>
    req(`/creditos/turnos/generar`, { method: "POST", body: JSON.stringify(payload) }),
  turnoAsignar: (payload: any) =>
    req(`/creditos/turnos/asignar`, { method: "POST", body: JSON.stringify(payload) }),
  // Caja / cobranza
  pendientes: (creditoId: number, fecha: string) =>
    req(`/caja/creditos/${creditoId}/pendientes?fecha_pago=${fecha}`),
  cobrar: (payload: any) => postIdem(`/caja/cobrar`, payload),   // dinero: dedup doble-click + Idempotency-Key
  cola: (q: { cuil?: string; dni?: string; nombre?: string; fecha: string }) => {
    const s = new URLSearchParams();
    if (q.cuil) s.set("cuil", q.cuil);
    if (q.dni) s.set("dni", q.dni);
    if (q.nombre) s.set("nombre", q.nombre);
    s.set("fecha", q.fecha);
    return req(`/caja/cola?${s.toString()}`);
  },
  cobrarCola: (payload: any) => postIdem(`/caja/cola/cobrar`, payload),   // dinero: dedup doble-click
  recibo: (id: number) => req(`/caja/recibos/${id}`),
  cierre: (fecha: string) => req(`/caja/cierre?fecha=${fecha}`),
  cobranzasPeriodo: (desde: string, hasta: string, origen = "") =>
    req(`/caja/cobranzas-periodo?desde=${desde}&hasta=${hasta}${origen ? `&origen=${origen}` : ""}`),
  recaudacionAnual: (anio: number) => req(`/caja/recaudacion-anual?anio=${anio}`),
  recibosDelDia: (fecha: string) => req(`/caja/recibos-del-dia?fecha=${fecha}`),
  reimprimirRecibo: (noRecibo: number, origen: string, fecha: string) =>
    abrirArchivo(`${API}/caja/recibos-del-dia/reimprimir?no_recibo=${noRecibo}&origen=${origen}&fecha=${fecha}`),
  interesesIvaMensual: (mes: number, anio: number) =>
    req(`/caja/intereses-iva-mensual?mes=${mes}&anio=${anio}`),
  planillaContableCreditos: (fecha: string) =>
    req(`/caja/planilla-contable-creditos?fecha=${fecha}`),
  pagosRealizados: (desde: string, hasta: string, coding = "", texto = "") => {
    const s = new URLSearchParams({ desde, hasta });
    if (coding) s.set("coding", coding);
    if (texto) s.set("texto", texto);
    return req(`/caja/pagos-realizados?${s.toString()}`);
  },
  verReciboPdf: (id: number) => abrirArchivo(`${API}/caja/recibos/${id}/pdf`),
  comprobanteEgresoPdf: (id: number) => abrirArchivo(`${API}/egresos/${id}/comprobante-pdf`),
  verLibroDiarioPdf: () => abrirArchivo(`${API}/contabilidad/libro-diario/pdf`),
  planCuentas: (q = "", emp?: number) => { const s = new URLSearchParams(); if (q) s.set("q", q); if (emp) s.set("empresa_id", String(emp)); const qs = s.toString(); return req(`/contabilidad/plan-cuentas${qs ? `?${qs}` : ""}`); },
  crearCuenta: (data: any, emp?: number) => postIdem(`/contabilidad/plan-cuentas${emp ? `?empresa_id=${emp}` : ""}`, data),
  editarCuenta: (id: number, data: any) => req(`/contabilidad/plan-cuentas/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  borrarCuenta: (id: number) => req(`/contabilidad/plan-cuentas/${id}`, { method: "DELETE" }),
  editarDisponibilidad: (id: string, body: any) => req(`/productos/${id}/disponibilidad`, { method: "PUT", body: JSON.stringify(body) }),
  // Empresas / entes contables (multi-plan — H-188)
  empresas: () => req(`/contabilidad/empresas`),
  crearEmpresa: (data: any) => req(`/contabilidad/empresas`, { method: "POST", body: JSON.stringify(data) }),
  setEmpresaPredeterminada: (id: number) => req(`/contabilidad/empresas/${id}/predeterminada`, { method: "POST" }),
  restaurarPlanCuentas: () => req(`/contabilidad/plan-cuentas/restaurar-plantilla`, { method: "POST" }),
  cargarPlanEstandar: () => req(`/contabilidad/plan-cuentas/cargar-estandar`, { method: "POST" }),
  asientosManuales: () => req(`/contabilidad/asientos-manuales`),
  crearAsientoManual: (payload: any) => postIdem(`/contabilidad/asientos-manuales`, payload),
  reversarAsiento: (id: number) => req(`/contabilidad/asientos-manuales/${id}/reversar`, { method: "POST" }),
  editarAsientoManual: (id: number, payload: any) => req(`/contabilidad/asientos-manuales/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  publicarAsiento: (id: number) => req(`/contabilidad/asientos-manuales/${id}/publicar`, { method: "POST" }),
  eliminarAsientoManual: (id: number) => req(`/contabilidad/asientos-manuales/${id}`, { method: "DELETE" }),
  diariosContables: () => req(`/contabilidad/diarios`),
  centrosCosto: () => req(`/contabilidad/centros-costo`),
  crearCentro: (payload: any) => req(`/contabilidad/centros-costo`, { method: "POST", body: JSON.stringify(payload) }),
  editarCentro: (id: number, payload: any) => req(`/contabilidad/centros-costo/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  porCentro: (desde = "", hasta = "") => { const s = new URLSearchParams(); if (desde) s.set("desde", desde); if (hasta) s.set("hasta", hasta); const q = s.toString(); return req(`/contabilidad/por-centro${q ? `?${q}` : ""}`); },
  ejercicios: () => req(`/contabilidad/ejercicios`),
  crearEjercicio: (payload: any) => req(`/contabilidad/ejercicios`, { method: "POST", body: JSON.stringify(payload) }),
  cerrarEjercicio: (id: number) => req(`/contabilidad/ejercicios/${id}/cerrar`, { method: "POST" }),
  reabrirEjercicio: (id: number) => req(`/contabilidad/ejercicios/${id}/reabrir`, { method: "POST" }),
  aperturaEjercicio: (id: number) => req(`/contabilidad/ejercicios/${id}/apertura`, { method: "POST" }),
  sumasYSaldos: (desde = "", hasta = "") => { const s = new URLSearchParams(); if (desde) s.set("desde", desde); if (hasta) s.set("hasta", hasta); const q = s.toString(); return req(`/contabilidad/sumas-y-saldos${q ? `?${q}` : ""}`); },
  estadosContables: (desde = "", hasta = "") => { const s = new URLSearchParams(); if (desde) s.set("desde", desde); if (hasta) s.set("hasta", hasta); const q = s.toString(); return req(`/contabilidad/estados-contables${q ? `?${q}` : ""}`); },
  flujoEfectivo: (desde = "", hasta = "") => { const s = new URLSearchParams(); if (desde) s.set("desde", desde); if (hasta) s.set("hasta", hasta); const q = s.toString(); return req(`/contabilidad/flujo-efectivo${q ? `?${q}` : ""}`); },
  conciliacion: (cuenta = "1.1.02", desde = "", hasta = "") => { const s = new URLSearchParams(); s.set("cuenta", cuenta); if (desde) s.set("desde", desde); if (hasta) s.set("hasta", hasta); return req(`/contabilidad/conciliacion?${s.toString()}`); },
  crearExtracto: (body: any) => req(`/contabilidad/conciliacion/extracto`, { method: "POST", body: JSON.stringify(body) }),
  borrarExtracto: (id: number) => req(`/contabilidad/conciliacion/extracto/${id}`, { method: "DELETE" }),
  conciliar: (extracto_id: number, asiento_linea_id: number) => req(`/contabilidad/conciliacion/conciliar`, { method: "POST", body: JSON.stringify({ extracto_id, asiento_linea_id }) }),
  desconciliar: (id: number) => req(`/contabilidad/conciliacion/desconciliar/${id}`, { method: "POST" }),
  conciliarAutomatica: (cuenta = "1.1.02") => req(`/contabilidad/conciliacion/automatica?cuenta=${encodeURIComponent(cuenta)}`, { method: "POST" }),
  sumasYSaldosExcel: (desde = "", hasta = "") => { const s = new URLSearchParams(); if (desde) s.set("desde", desde); if (hasta) s.set("hasta", hasta); const q = s.toString(); return abrirArchivo(`${API}/contabilidad/sumas-y-saldos/excel${q ? `?${q}` : ""}`, "sumas_y_saldos.xlsx"); },
  estadosContablesExcel: (desde = "", hasta = "") => { const s = new URLSearchParams(); if (desde) s.set("desde", desde); if (hasta) s.set("hasta", hasta); const q = s.toString(); return abrirArchivo(`${API}/contabilidad/estados-contables/excel${q ? `?${q}` : ""}`, "estados_contables.xlsx"); },
  libroDiarioExcel: (desde = "", hasta = "") => { const s = new URLSearchParams(); if (desde) s.set("desde", desde); if (hasta) s.set("hasta", hasta); const q = s.toString(); return abrirArchivo(`${API}/contabilidad/libro-diario/excel${q ? `?${q}` : ""}`, "libro_diario.xlsx"); },
  imputaciones: () => req(`/contabilidad/imputaciones`),
  editarImputacion: (id: number, cuenta_codigo: string) => req(`/contabilidad/imputaciones/${id}`, { method: "PUT", body: JSON.stringify({ cuenta_codigo }) }),
  balance: (desde = "", hasta = "") => {
    const s = new URLSearchParams();
    if (desde) s.set("desde", desde);
    if (hasta) s.set("hasta", hasta);
    const qs = s.toString();
    return req(`/contabilidad/balance${qs ? `?${qs}` : ""}`);
  },
  verBalancePdf: (desde = "", hasta = "") => {
    const s = new URLSearchParams();
    if (desde) s.set("desde", desde);
    if (hasta) s.set("hasta", hasta);
    const qs = s.toString();
    return abrirArchivo(`${API}/contabilidad/balance/pdf${qs ? `?${qs}` : ""}`);
  },
  verCierrePdf: (fecha: string) => abrirArchivo(`${API}/caja/cierre/pdf?fecha=${fecha}`),
  ivaPeriodo: (desde: string, hasta: string) =>
    req(`/contabilidad/iva-periodo?desde=${desde}&hasta=${hasta}`),
  verIvaPdf: (desde: string, hasta: string) =>
    abrirArchivo(`${API}/contabilidad/iva-periodo/pdf?desde=${desde}&hasta=${hasta}`),
  pendientesCobro: (fecha: string) =>
    req(`/caja/pendientes-cobro?fecha_corte=${fecha}`),
  verPendientesPdf: (fecha: string) =>
    abrirArchivo(`${API}/caja/pendientes-cobro/pdf?fecha_corte=${fecha}`),
  controlCaja: (fecha: string, cajero = "") =>
    req(`/caja/control?fecha=${fecha}${cajero ? `&cajero=${encodeURIComponent(cajero)}` : ""}`),
  verControlPdf: (fecha: string, cajero = "") =>
    abrirArchivo(`${API}/caja/control/pdf?fecha=${fecha}${cajero ? `&cajero=${encodeURIComponent(cajero)}` : ""}`),
  verCarteraPdf: () => abrirArchivo(`${API}/creditos/consultas/estadisticas/pdf`),
  descargarEnviosExcel: (desde: string, hasta: string) =>
    abrirArchivo(`${API}/creditos/consultas/envios/excel?desde=${desde}&hasta=${hasta}`,
      `padron_debito_${desde}_${hasta}.xlsx`),
  // Contabilidad
  ivaCuotas: (desde = "", hasta = "") => {
    const s = new URLSearchParams();
    if (desde) s.set("desde", desde);
    if (hasta) s.set("hasta", hasta);
    const qs = s.toString();
    return req(`/contabilidad/iva-cuotas${qs ? `?${qs}` : ""}`);
  },
  balanceMayor: (desde = "", hasta = "", periodo = "") => {
    const s = new URLSearchParams();
    if (desde) s.set("desde", desde);
    if (hasta) s.set("hasta", hasta);
    if (periodo) s.set("periodo", periodo);
    const qs = s.toString();
    return req(`/contabilidad/mayor/balance${qs ? `?${qs}` : ""}`);
  },
  ctacteContableCredito: (noCredito: number) =>
    req(`/contabilidad/ctacte-credito?no_credito=${noCredito}`),
  contabilidadGeneral: (p: { desde?: string; hasta?: string; tipo?: string; limit?: number; offset?: number } = {}) => {
    const s = new URLSearchParams();
    if (p.desde) s.set("desde", p.desde);
    if (p.hasta) s.set("hasta", p.hasta);
    if (p.tipo) s.set("tipo", p.tipo);
    if (p.limit) s.set("limit", String(p.limit));
    if (p.offset) s.set("offset", String(p.offset));
    const qs = s.toString();
    return req(`/contabilidad/general${qs ? `?${qs}` : ""}`);
  },
  agenciaHistorico: (noAgencia: number, desde = "", hasta = "") => {
    const s = new URLSearchParams({ no_agencia: String(noAgencia) });
    if (desde) s.set("desde", desde);
    if (hasta) s.set("hasta", hasta);
    return req(`/juegos/agencia-historico?${s.toString()}`);
  },
  mayorCuenta: (cuenta: string, desde = "", hasta = "", offset = 0) => {
    const s = new URLSearchParams({ cuenta, limit: "200", offset: String(offset) });
    if (desde) s.set("desde", desde);
    if (hasta) s.set("hasta", hasta);
    return req(`/contabilidad/mayor/cuenta?${s.toString()}`);
  },
  libroDiario: (desde = "", hasta = "") => {
    const p = new URLSearchParams();
    if (desde) p.set("desde", desde);
    if (hasta) p.set("hasta", hasta);
    const qs = p.toString();
    return req(`/contabilidad/libro-diario${qs ? `?${qs}` : ""}`);
  },
  // Seguros
  polizas: () => req(`/seguros/polizas`),
  polizasAgente: (p: { q?: string; codigo?: number; solo_vigentes?: boolean; limit?: number; offset?: number } = {}) => {
    const qs = new URLSearchParams();
    if (p.q) qs.set("q", p.q);
    if (p.codigo) qs.set("codigo", String(p.codigo));
    if (p.solo_vigentes === false) qs.set("solo_vigentes", "false");
    if (p.limit) qs.set("limit", String(p.limit));
    if (p.offset) qs.set("offset", String(p.offset));
    const s = qs.toString();
    return req(`/seguros/polizas-agente${s ? `?${s}` : ""}`);
  },
  liquidacionSeguros: (desde: string, hasta: string) =>
    req(`/seguros/liquidacion?desde=${desde}&hasta=${hasta}`),
  regimenes: () => req(`/seguros/regimenes`),
  beneficiarios: (regimenId: number) =>
    req(`/seguros/regimenes/${regimenId}/beneficiarios`),
  crearBeneficiario: (regimenId: number, payload: any) =>
    req(`/seguros/regimenes/${regimenId}/beneficiarios`, { method: "POST", body: JSON.stringify(payload) }),
  generarCuotasRegimen: (regimenId: number, periodo: string) =>
    req(`/seguros/regimenes/${regimenId}/generar-cuotas?periodo=${periodo}`, { method: "POST" }),
  segurosCobrados: (desde: string, hasta: string) =>
    req(`/seguros/cobrados?desde=${desde}&hasta=${hasta}`),
  titularesSeguro: (p: { q?: string; tipo?: string; limit?: number; offset?: number } = {}) => {
    const s = new URLSearchParams();
    if (p.q) s.set("q", p.q);
    if (p.tipo) s.set("tipo", p.tipo);
    if (p.limit != null) s.set("limit", String(p.limit));
    if (p.offset != null) s.set("offset", String(p.offset));
    const qs = s.toString();
    return req(`/seguros/titulares${qs ? `?${qs}` : ""}`);
  },
  resumenSeguroAdicional: (periodo = "") =>
    req(`/seguros/adicional/resumen${periodo ? `?periodo=${periodo}` : ""}`),
  agentesSeguroAdicional: (p: { con_adicional?: boolean; periodo?: string; q?: string; limit?: number; offset?: number } = {}) => {
    const s = new URLSearchParams();
    if (p.con_adicional != null) s.set("con_adicional", String(p.con_adicional));
    if (p.periodo) s.set("periodo", p.periodo);
    if (p.q) s.set("q", p.q);
    if (p.limit != null) s.set("limit", String(p.limit));
    if (p.offset != null) s.set("offset", String(p.offset));
    const qs = s.toString();
    return req(`/seguros/adicional/agentes${qs ? `?${qs}` : ""}`);
  },
  // Juegos / Quiniela
  agenciasJuego: () => req(`/juegos/agencias`),
  maestroJuegos: () => req(`/juegos/maestro`),
  sorteos: (p: { cod_juego?: number; limit?: number; offset?: number; sort?: string; order?: string } = {}) => {
    const s = new URLSearchParams();
    if (p.cod_juego != null) s.set("cod_juego", String(p.cod_juego));
    if (p.limit != null) s.set("limit", String(p.limit));
    if (p.offset != null) s.set("offset", String(p.offset));
    if (p.sort) s.set("sort", p.sort);
    if (p.order) s.set("order", p.order);
    const qs = s.toString();
    return req(`/juegos/sorteos${qs ? `?${qs}` : ""}`);
  },
  liquidacionesJuego: (p: { pagado?: boolean; limit?: number; offset?: number; sort?: string; order?: string } = {}) => {
    const s = new URLSearchParams();
    if (p.pagado != null) s.set("pagado", String(p.pagado));
    if (p.limit != null) s.set("limit", String(p.limit));
    if (p.offset != null) s.set("offset", String(p.offset));
    if (p.sort) s.set("sort", p.sort);
    if (p.order) s.set("order", p.order);
    const qs = s.toString();
    return req(`/juegos/liquidaciones${qs ? `?${qs}` : ""}`);
  },
  resumenJuegos: () => req(`/juegos/resumen`),
  ingresosPorJuego: (desde = "", hasta = "") => {
    const s = new URLSearchParams();
    if (desde) s.set("desde", desde);
    if (hasta) s.set("hasta", hasta);
    const qs = s.toString();
    return req(`/juegos/ingresos-por-juego${qs ? `?${qs}` : ""}`);
  },
  cobrarLiquidacion: (id: number, recibo: number) =>
    postIdem(`/juegos/liquidaciones/${id}/cobrar?no_recibo=${recibo}`, {}),   // dinero: dedup doble-click
  deudaAgencia: (cod: number) => req(`/juegos/agencias/${cod}/deuda`),
  ingresosBrutos: (mes: number, anio: number) =>
    req(`/juegos/ingresos-brutos?mes=${mes}&anio=${anio}`),
  buscarEgresos: (p: { modo?: string; valor?: string; limit?: number; offset?: number } = {}) => {
    const s = new URLSearchParams();
    s.set("modo", p.modo || "apellido");
    if (p.valor) s.set("valor", p.valor);
    if (p.limit) s.set("limit", String(p.limit));
    if (p.offset) s.set("offset", String(p.offset));
    return req(`/egresos/buscar?${s.toString()}`);
  },
  chequesEmitidos: (p: { desde?: string; hasta?: string; cuenta?: string; banco?: string; incluir_anulados?: boolean; limit?: number; offset?: number } = {}) => {
    const s = new URLSearchParams();
    if (p.desde) s.set("desde", p.desde);
    if (p.hasta) s.set("hasta", p.hasta);
    if (p.cuenta) s.set("cuenta", p.cuenta);
    if (p.banco) s.set("banco", p.banco);
    if (p.incluir_anulados) s.set("incluir_anulados", "true");
    if (p.limit) s.set("limit", String(p.limit));
    if (p.offset) s.set("offset", String(p.offset));
    const qs = s.toString();
    return req(`/egresos/cheques${qs ? `?${qs}` : ""}`);
  },
  fondoGarantia: (p: { no_agencia?: string; desde?: string; hasta?: string } = {}) => {
    const s = new URLSearchParams();
    if (p.no_agencia) s.set("no_agencia", p.no_agencia);
    if (p.desde) s.set("desde", p.desde);
    if (p.hasta) s.set("hasta", p.hasta);
    const qs = s.toString();
    return req(`/juegos/fondo-garantia${qs ? `?${qs}` : ""}`);
  },
  liquidacionesCobradas: (fecha: string) =>
    req(`/juegos/liquidaciones-cobradas?fecha=${fecha}`),
  premiosQuiniela: (fecha: string, modo = "cobradas") =>
    req(`/juegos/premios?fecha=${fecha}&modo=${modo}`),
  chequesAgencias: (fechaVto: string) =>
    req(`/juegos/cheques-agencias?fecha_vto=${fechaVto}`),
  premiosCompensados: (fechaVto: string) =>
    req(`/juegos/premios-compensados?fecha_vto=${fechaVto}`),
  deudaAgenciaInforme: (q: { cod?: string; desde?: string; hasta?: string } = {}) => {
    const s = new URLSearchParams();
    if (q.cod) s.set("cod_agencia", q.cod);
    if (q.desde) s.set("desde", q.desde);
    if (q.hasta) s.set("hasta", q.hasta);
    const qs = s.toString();
    return req(`/juegos/agencias/deuda-informe${qs ? `?${qs}` : ""}`);
  },
  cobrarAgencia: (payload: any) => postIdem(`/juegos/agencias/cobrar`, payload),   // dinero: dedup doble-click
  primasDevengadas: (desde: string, hasta: string) =>
    req(`/seguros/primas-devengadas?desde=${desde}&hasta=${hasta}`),
  // Consultas de créditos
  jubiladosResumen: () => req(`/creditos/consultas/jubilados/resumen`),
  jubiladosPorDepto: () => req(`/creditos/consultas/jubilados/por-departamento`),
  listadoCreditos: (p: { estado?: string; q?: string; limit?: number; offset?: number; sort?: string; order?: string } = {}) => {
    const s = new URLSearchParams();
    if (p.estado) s.set("estado", p.estado);
    if (p.q) s.set("q", p.q);
    if (p.limit != null) s.set("limit", String(p.limit));
    if (p.offset != null) s.set("offset", String(p.offset));
    if (p.sort) s.set("sort", p.sort);
    if (p.order) s.set("order", p.order);
    const qs = s.toString();
    return req(`/creditos/consultas/creditos${qs ? `?${qs}` : ""}`);
  },
  cuotasMora: (fecha: string) => req(`/creditos/consultas/cuotas-mora?fecha_corte=${fecha}`),
  resumenCobros: (p: { desde?: string; hasta?: string } = {}) => {
    const s = new URLSearchParams();
    if (p.desde) s.set("desde", p.desde);
    if (p.hasta) s.set("hasta", p.hasta);
    const qs = s.toString();
    return req(`/creditos/consultas/resumen-cobros${qs ? `?${qs}` : ""}`);
  },
  pagosEnCaja: (p: { desde?: string; hasta?: string; credito_id?: number; via?: string; limit?: number; offset?: number } = {}) => {
    const s = new URLSearchParams();
    if (p.desde) s.set("desde", p.desde);
    if (p.hasta) s.set("hasta", p.hasta);
    if (p.credito_id != null) s.set("credito_id", String(p.credito_id));
    if (p.via) s.set("via", p.via);
    if (p.limit != null) s.set("limit", String(p.limit));
    if (p.offset != null) s.set("offset", String(p.offset));
    const qs = s.toString();
    return req(`/creditos/consultas/pagos-caja${qs ? `?${qs}` : ""}`);
  },
  descargarPagosEnCajaExcel: (p: { desde?: string; hasta?: string; credito_id?: number } = {}) => {
    const s = new URLSearchParams();
    if (p.desde) s.set("desde", p.desde);
    if (p.hasta) s.set("hasta", p.hasta);
    if (p.credito_id != null) s.set("credito_id", String(p.credito_id));
    const qs = s.toString();
    return abrirArchivo(`${API}/creditos/consultas/pagos-caja/excel${qs ? `?${qs}` : ""}`, "pagos_en_caja.xlsx");
  },
  creditosSinDebito: (p: { q?: string; linea_id?: number; limit?: number; offset?: number } = {}) => {
    const s = new URLSearchParams();
    if (p.q) s.set("q", p.q);
    if (p.linea_id != null) s.set("linea_id", String(p.linea_id));
    if (p.limit != null) s.set("limit", String(p.limit));
    if (p.offset != null) s.set("offset", String(p.offset));
    const qs = s.toString();
    return req(`/creditos/consultas/sin-debito${qs ? `?${qs}` : ""}`);
  },
  situacionCliente: (id: number) => req(`/creditos/consultas/cliente/${id}/situacion`),
  vision360: (id: number) => req(`/creditos/consultas/cliente/${id}/vision-360`),
  cuentaCorriente: (creditoId: number) => req(`/creditos/consultas/cuenta-corriente/${creditoId}`),
  estadisticas: () => req(`/creditos/consultas/estadisticas`),
  situacionPorCartera: () => req(`/creditos/consultas/por-cartera`),
  verPorCarteraPdf: () => abrirArchivo(`${API}/creditos/consultas/por-cartera/pdf`),
  descargarListadoCreditosExcel: (p: { estado?: string; q?: string; sort?: string; order?: string } = {}) => {
    const s = new URLSearchParams();
    if (p.estado) s.set("estado", p.estado);
    if (p.q) s.set("q", p.q);
    if (p.sort) s.set("sort", p.sort);
    if (p.order) s.set("order", p.order);
    const qs = s.toString();
    return abrirArchivo(`${API}/creditos/consultas/creditos/excel${qs ? `?${qs}` : ""}`, "listado_creditos.xlsx");
  },
  // Generador de informes de créditos (filtros combinables)
  informeCreditos: (p: any = {}) => {
    const s = new URLSearchParams();
    Object.entries(p).forEach(([k, v]) => { if (v !== undefined && v !== "" && v !== null) s.set(k, String(v)); });
    const qs = s.toString();
    return req(`/creditos/consultas/creditos${qs ? `?${qs}` : ""}`);
  },
  descargarInformeCreditosExcel: (p: any = {}) => {
    const s = new URLSearchParams();
    Object.entries(p).forEach(([k, v]) => { if (v !== undefined && v !== "" && v !== null) s.set(k, String(v)); });
    const qs = s.toString();
    return abrirArchivo(`${API}/creditos/consultas/creditos/excel${qs ? `?${qs}` : ""}`, "informe_creditos.xlsx");
  },
  turnosOtorgados: (p: { periodo?: string; tipo?: string; usado?: boolean; q?: string; limit?: number; offset?: number } = {}) => {
    const s = new URLSearchParams();
    if (p.periodo) s.set("periodo", p.periodo);
    if (p.tipo) s.set("tipo", p.tipo);
    if (p.usado != null) s.set("usado", String(p.usado));
    if (p.q) s.set("q", p.q);
    if (p.limit != null) s.set("limit", String(p.limit));
    if (p.offset != null) s.set("offset", String(p.offset));
    const qs = s.toString();
    return req(`/creditos/consultas/turnos${qs ? `?${qs}` : ""}`);
  },
  descargarTurnosExcel: (p: { periodo?: string; tipo?: string; usado?: boolean; q?: string } = {}) => {
    const s = new URLSearchParams();
    if (p.periodo) s.set("periodo", p.periodo);
    if (p.tipo) s.set("tipo", p.tipo);
    if (p.usado != null) s.set("usado", String(p.usado));
    if (p.q) s.set("q", p.q);
    const qs = s.toString();
    return abrirArchivo(`${API}/creditos/consultas/turnos/excel${qs ? `?${qs}` : ""}`, "turnos_otorgados.xlsx");
  },
  envios: (desde: string, hasta: string) =>
    req(`/creditos/consultas/envios?desde=${desde}&hasta=${hasta}`),
  // Tesorería / Egresos
  ordenesPago: (p: { estado?: string; limit?: number; offset?: number; sort?: string; order?: string } = {}) => {
    const s = new URLSearchParams();
    if (p.estado) s.set("estado", p.estado);
    if (p.limit != null) s.set("limit", String(p.limit));
    if (p.offset != null) s.set("offset", String(p.offset));
    if (p.sort) s.set("sort", p.sort);
    if (p.order) s.set("order", p.order);
    const qs = s.toString();
    return req(`/egresos/ordenes${qs ? `?${qs}` : ""}`);
  },
  totalesEgresos: () => req(`/egresos/totales`),
  autorizacionesOP: (p: { habilitada?: boolean; con_saldo?: boolean; q?: string; limit?: number; offset?: number } = {}) => {
    const s = new URLSearchParams();
    if (p.habilitada !== undefined) s.set("habilitada", String(p.habilitada));
    if (p.con_saldo) s.set("con_saldo", "true");
    if (p.q) s.set("q", p.q);
    s.set("limit", String(p.limit ?? 25)); s.set("offset", String(p.offset ?? 0));
    return req(`/egresos/autorizaciones?${s.toString()}`);
  },
  autorizacionesOPTotales: (habilitada?: boolean) =>
    req(`/egresos/autorizaciones/totales${habilitada !== undefined ? `?habilitada=${habilitada}` : ""}`),
  informeOP: (p: any = {}) => {
    const s = new URLSearchParams();
    Object.entries(p).forEach(([k, v]) => { if (v !== undefined && v !== "" && v !== null) s.set(k, String(v)); });
    const qs = s.toString();
    return req(`/egresos/ordenes${qs ? `?${qs}` : ""}`);
  },
  descargarInformeOPExcel: (p: any = {}) => {
    const s = new URLSearchParams();
    Object.entries(p).forEach(([k, v]) => { if (v !== undefined && v !== "" && v !== null) s.set(k, String(v)); });
    const qs = s.toString();
    return abrirArchivo(`${API}/egresos/ordenes/excel${qs ? `?${qs}` : ""}`, "informe_op.xlsx");
  },
  reporteOP: (desde = "", hasta = "") => {
    const s = new URLSearchParams();
    if (desde) s.set("desde", desde);
    if (hasta) s.set("hasta", hasta);
    const qs = s.toString();
    return req(`/egresos/reporte${qs ? `?${qs}` : ""}`);
  },
  crearOP: (payload: any) =>
    req(`/egresos/ordenes`, { method: "POST", body: JSON.stringify(payload) }),
  pagarOP: (id: number, payload: any) => postIdem(`/egresos/ordenes/${id}/pagar`, payload),   // dinero: dedup doble-click
  chequeras: () => req(`/egresos/chequeras`),
  crearChequera: (payload: any) =>
    req(`/egresos/chequeras`, { method: "POST", body: JSON.stringify(payload) }),
  revisionEgresos: () => req(`/egresos/revision`),
  // Utilidades / Tablas (ABM)
  adminLineas: () => req(`/admin/lineas`),
  crearLinea: (payload: any) =>
    req(`/admin/lineas`, { method: "POST", body: JSON.stringify(payload) }),
  editarLinea: (id: number, payload: any) =>
    req(`/admin/lineas/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  adminOrganismos: () => req(`/admin/organismos`),
  crearOrganismo: (payload: any) =>
    req(`/admin/organismos`, { method: "POST", body: JSON.stringify(payload) }),
  adminCompanias: () => req(`/admin/companias`),
  crearCompania: (payload: any) =>
    req(`/admin/companias`, { method: "POST", body: JSON.stringify(payload) }),
  adminProveedores: (q = "") => req(`/admin/proveedores${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  crearProveedor: (payload: any) =>
    req(`/admin/proveedores`, { method: "POST", body: JSON.stringify(payload) }),
  adminParametros: (ambito?: string) => req(`/admin/parametros${ambito ? `?ambito=${encodeURIComponent(ambito)}` : ""}`),
  upsertParametro: (payload: any) =>
    req(`/admin/parametros`, { method: "POST", body: JSON.stringify(payload) }),
  // Usuarios, roles y permisos: los administra Seguridad de Portezuelo (ver permisos.tsx).
  misPermisos: () => req(`/auth/mis-permisos`),
  auditoria: (p: { usuario?: string; limit?: number; offset?: number } = {}) => {
    const s = new URLSearchParams();
    if (p.usuario) s.set("usuario", p.usuario);
    if (p.limit != null) s.set("limit", String(p.limit));
    if (p.offset != null) s.set("offset", String(p.offset));
    const qs = s.toString();
    return req(`/admin/auditoria${qs ? `?${qs}` : ""}`);
  },
  auditoriaResumen: (por: "usuario" | "maquina" = "usuario") =>
    req(`/admin/auditoria/resumen?por=${por}`),
  // Auditoría de cambios (sistema nuevo: antes/después + IP)
  auditoriaCambios: (p: { texto?: string; entidad?: string; operacion?: string;
                          resultado?: string; limit?: number; offset?: number } = {}) => {
    const s = new URLSearchParams();
    if (p.texto) s.set("texto", p.texto);
    if (p.entidad) s.set("entidad", p.entidad);
    if (p.operacion) s.set("operacion", p.operacion);
    if (p.resultado) s.set("resultado", p.resultado);
    if (p.limit != null) s.set("limit", String(p.limit));
    if (p.offset != null) s.set("offset", String(p.offset));
    const qs = s.toString();
    return req(`/admin/auditoria-cambios${qs ? `?${qs}` : ""}`);
  },
  auditoriaCambioDetalle: (id: number) => req(`/admin/auditoria-cambios/${id}`),
  // Migradores DBF → modelo
  migradores: () => req(`/migradores`),
  ejecutarMigrador: (clave: string, reset: boolean) =>
    req(`/migradores/${clave}/ejecutar?reset=${reset}`, { method: "POST" }),
  ejecutarMigradoresTodo: (reset: boolean) =>
    req(`/migradores/ejecutar-todo?reset=${reset}`, { method: "POST" }),
  esquemaDatos: () => req(`/migradores/esquema`),
  inventarioDbfs: () => req(`/migradores/inventario`),
  // Despacho
  modelosResolucion: (q = "") => req(`/despacho/modelos${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  resoluciones: (p: { tipo?: string; limit?: number; offset?: number; sort?: string; order?: string } = {}) => {
    const s = new URLSearchParams();
    if (p.tipo) s.set("tipo", p.tipo);
    if (p.limit != null) s.set("limit", String(p.limit));
    if (p.offset != null) s.set("offset", String(p.offset));
    if (p.sort) s.set("sort", p.sort);
    if (p.order) s.set("order", p.order);
    const qs = s.toString();
    return req(`/despacho/resoluciones${qs ? `?${qs}` : ""}`);
  },
  modeloResolucion: (id: number) => req(`/despacho/modelos/${id}`),
  crearModeloResolucion: (payload: any) => postIdem(`/despacho/modelos`, payload),
  editarModeloResolucion: (id: number, payload: any) =>
    req(`/despacho/modelos/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  resolucion: (id: number) => req(`/despacho/resoluciones/${id}`),
  crearResolucion: (payload: any) => postIdem(`/despacho/resoluciones`, payload),
  editarResolucion: (id: number, payload: any) =>
    req(`/despacho/resoluciones/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  cargarNumeroReal: (id: number, payload: any = {}) =>
    req(`/despacho/resoluciones/${id}/numero-real`, { method: "POST", body: JSON.stringify(payload) }),
  firmarResolucion: (id: number) =>
    req(`/despacho/resoluciones/${id}/firmar`, { method: "POST" }),
  // Anexo de Resolución (asignación de lote de solicitudes)
  anexoTipos: () => req(`/despacho/anexo/tipos`),
  anexoSolicitudes: (tipo: number, lote?: number) =>
    req(`/despacho/anexo/solicitudes?tipo=${tipo}${lote ? `&lote=${lote}` : ""}`),
  anexoAsignar: (payload: any) =>
    req(`/despacho/anexo/asignar`, { method: "POST", body: JSON.stringify(payload) }),
  descargarAnexoExcel: (tipo: number, lote: number) =>
    abrirArchivo(`${API}/despacho/anexo/excel?tipo=${tipo}&lote=${lote}`, `anexo_resolucion_${lote}.xlsx`),
  descargarResolucionWord: (id: number, nombre: string) =>
    abrirArchivo(`${API}/despacho/resoluciones/${id}/word`, nombre),
  expedientes: () => req(`/despacho/expedientes`),
  expediente: (id: number) => req(`/despacho/expedientes/${id}`),
  crearExpediente: (payload: any) =>
    req(`/despacho/expedientes`, { method: "POST", body: JSON.stringify(payload) }),
  pasarExpediente: (id: number, payload: any) =>
    req(`/despacho/expedientes/${id}/pase`, { method: "POST", body: JSON.stringify(payload) }),
  // Mesa de entradas
  tiposTramite: () => req(`/mesa/tipos-tramite`),
  tramiteTipos: () => req(`/mesa/tramites/tipos`),
  oficinas: () => req(`/mesa/oficinas`),
  tramites: (p: { tipo?: string; estado?: string; anio?: number; q?: string; solo_expedientes?: boolean; limit?: number; offset?: number } = {}) => {
    const s = new URLSearchParams();
    if (p.tipo) s.set("tipo", p.tipo);
    if (p.estado) s.set("estado", p.estado);
    if (p.anio != null) s.set("anio", String(p.anio));
    if (p.q) s.set("q", p.q);
    if (p.solo_expedientes) s.set("solo_expedientes", "true");
    if (p.limit != null) s.set("limit", String(p.limit));
    if (p.offset != null) s.set("offset", String(p.offset));
    const qs = s.toString();
    return req(`/mesa/tramites${qs ? `?${qs}` : ""}`);
  },
  tramitePases: (tramiteId: number) => req(`/mesa/tramites/${tramiteId}/pases`),
  tramitesIngresados: (desde = "", hasta = "") => {
    const s = new URLSearchParams();
    if (desde) s.set("desde", desde);
    if (hasta) s.set("hasta", hasta);
    const qs = s.toString();
    return req(`/mesa/tramites/ingresados${qs ? `?${qs}` : ""}`);
  },
  generarTurno: (payload: any) =>
    req(`/mesa/turnos`, { method: "POST", body: JSON.stringify(payload) }),
  tablero: (fecha: string) => req(`/mesa/tablero?fecha=${fecha}`),
  llamarSiguiente: (payload: any) =>
    req(`/mesa/llamar`, { method: "POST", body: JSON.stringify(payload) }),
  atenderTurno: (id: number) => req(`/mesa/turnos/${id}/atender`, { method: "POST" }),
  cancelarTurno: (id: number) => req(`/mesa/turnos/${id}/cancelar`, { method: "POST" }),
  controlesVersion: () => req(`/controles-version`),
  correrCasos: () => req(`/controles-version/casos/run`, { method: "POST" }),
  principiosArquitectura: () => req(`/controles-version/principios`),
  principiosDiseno: () => req(`/controles-version/principios-diseno`),
  procesos: () => req(`/controles-version/procesos`),
  inboxAprobaciones: () => req(`/aprobaciones/inbox`),
  inboxCount: () => req(`/aprobaciones/count`),
  inboxAprobarPendiente: (pid: string) => req(`/aprobaciones/pendientes/${pid}/aprobar`, { method: "POST" }),
  inboxRechazarPendiente: (pid: string, motivo = "") => req(`/aprobaciones/pendientes/${pid}/rechazar`, { method: "POST", body: JSON.stringify({ motivo }) }),
  // Workflow de aprobaciones (Seguridad)
  wfListar: () => req(`/workflow`),
  wfEditarRegla: (objeto: string, d: { activo?: boolean; nombre?: string; descripcion?: string }) => req(`/workflow/${objeto}`, { method: "PUT", body: JSON.stringify(d) }),
  wfAgregarNivel: (objeto: string, d: { nombre: string; rol: string; cuatroOjos: boolean }) => req(`/workflow/${objeto}/niveles`, { method: "POST", body: JSON.stringify(d) }),
  wfEditarNivel: (nivelId: string, d: { nombre: string; rol: string; cuatroOjos: boolean }) => req(`/workflow/niveles/${nivelId}`, { method: "PUT", body: JSON.stringify(d) }),
  wfBorrarNivel: (nivelId: string) => req(`/workflow/niveles/${nivelId}`, { method: "DELETE" }),
  wfAgregarUsuario: (nivelId: string, d: { username: string; modo: string }) => req(`/workflow/niveles/${nivelId}/usuarios`, { method: "POST", body: JSON.stringify(d) }),
  wfBorrarUsuario: (overrideId: string) => req(`/workflow/usuarios/${overrideId}`, { method: "DELETE" }),
  feriados: (pais = "AR", anio?: number) => req(`/feriados?pais=${pais}${anio ? `&anio=${anio}` : ""}`),
  feriadosPaises: () => req(`/feriados/paises`),
  feriadoCrear: (d: { pais: string; fecha: string; nombre: string; tipo?: string; activo?: boolean }) => req(`/feriados`, { method: "POST", body: JSON.stringify(d) }),
  feriadoEditar: (id: number, d: { pais: string; fecha: string; nombre: string; tipo?: string; activo?: boolean }) => req(`/feriados/${id}`, { method: "PUT", body: JSON.stringify(d) }),
  feriadoBorrar: (id: number) => req(`/feriados/${id}`, { method: "DELETE" }),
  feriadosImportar: (pais: string, anio: number) => req(`/feriados/importar`, { method: "POST", body: JSON.stringify({ pais, anio }) }),
  sistemaCalculos: () => req(`/sistema-calculos`),
  sistemaCalculosDebug: (d: { sistema: string; monto: number; plazo: number; tna: number; frecuencia?: string; gracia?: number; tipoCuota?: string; cargoPct?: number }) => req(`/sistema-calculos/debug`, { method: "POST", body: JSON.stringify(d) }),
};
