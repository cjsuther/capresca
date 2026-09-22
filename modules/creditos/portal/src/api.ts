// Cliente mínimo del portal. El token de sesión (scope=portal) vive en localStorage.
const KEY = "portal_token";
// Portezuelo publica la API del portal bajo /api/creditos/portal (nginx → módulo créditos, sin gateway).
const API = "/api/creditos";

export const token = {
  get: () => { try { return localStorage.getItem(KEY) || ""; } catch { return ""; } },
  set: (t: string) => { try { localStorage.setItem(KEY, t); } catch { /* ignore */ } },
  clear: () => { try { localStorage.removeItem(KEY); } catch { /* ignore */ } },
};

// H-159: un 401 a mitad de sesión (token vencido) debe expulsar a Login, no dejar la UI rota hasta recargar.
// Se limpia el token y se avisa a la app con un evento global; App lo escucha y vuelve a <Login/>.
function sesionExpirada() {
  token.clear();
  try { window.dispatchEvent(new Event("portal:sesion-expirada")); } catch { /* SSR/no-DOM */ }
  return new Error("Tu sesión expiró. Volvé a ingresar.");
}

async function req(path: string, options: RequestInit = {}) {
  const t = token.get();
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(t ? { Authorization: `Bearer ${t}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) { throw sesionExpirada(); }
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Error ${res.status}`);
  return res.json();
}

// Subida multipart (sin Content-Type manual: el navegador pone el boundary).
async function upload(path: string, form: FormData) {
  const t = token.get();
  const res = await fetch(`${API}${path}`, { method: "POST", body: form, headers: t ? { Authorization: `Bearer ${t}` } : {} });
  if (res.status === 401) { throw sesionExpirada(); }
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Error ${res.status}`);
  return res.json();
}

// Descarga autenticada → abre el archivo en una pestaña nueva (preview de imagen/PDF).
async function abrirArchivo(path: string) {
  const t = token.get();
  const res = await fetch(`${API}${path}`, { headers: t ? { Authorization: `Bearer ${t}` } : {} });
  if (res.status === 401) { throw sesionExpirada(); }
  if (!res.ok) throw new Error(`Error ${res.status}`);
  const url = URL.createObjectURL(await res.blob());
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

export type Ciudadano = { sub: string; email: string; nombre: string };
export type Haberes = { disponible: boolean; sueldo: number | null; antiguedad_meses: number | null; segmento: string; empleador: string; fuente: string };
// Producto del product builder nuevo (pp_*), no la línea legacy.
export type Producto = { id: string; nombre: string; codigo: string; sistema: string; tna: number; monto_min: number; monto_max: number; plazo_min: number; plazo_max: number };
export type Cuota = { numero: number; vencimiento: string; capital: number; interes: number; cargos: number; impuestos: number; total: number };
export type Datos = { segmento?: string; edad?: number; antiguedad_meses?: number; sueldo?: number };
export type PreAprobado = { monto_maximo: number; monto_min: number; cuota: number; afectacion: number; plazo: number };
export type Simulacion = {
  producto: string; sistema: string; tna: number; monto: number; cantidad_cuotas: number;
  total_a_pagar: number; total_interes: number; cuota_promedio: number; tea: number; cft: number;
  elegible: boolean | null; motivos: string[]; afectacion: number | null; cuotas: Cuota[];
};
export type SolicitudDetalle = Solicitud & {
  sistema: string; destino: string; segmento: string; edad: number | null; antiguedad_meses: number | null;
  sueldo: number | null; afectacion: number | null; total_a_pagar: number; cuotas: Cuota[];
};

// Video obligatorio del paso 4: se ve completo (sin adelantar) antes de confirmar la solicitud.
export type Video = { id: string; titulo: string; url: string };

export type Solicitud = {
  numero: string; estado: string; producto: string; monto: number; plazo: number;
  cuota_estimada: number; tna: number; fecha: string; motivo_rechazo: string;
};

export const api = {
  loginUrl: () => req("/portal/auth/login"),
  me: (): Promise<Ciudadano> => req("/portal/me"),
  haberes: (): Promise<Haberes> => req("/portal/haberes"),
  productos: (): Promise<Producto[]> => req("/portal/productos"),
  simular: (b: { producto_id: string; monto: number; plazo: number } & Datos): Promise<Simulacion> =>
    req("/portal/simular", { method: "POST", body: JSON.stringify(b) }),
  preAprobado: (b: { producto_id: string; plazo: number; sueldo: number; afectacion_max?: number }): Promise<PreAprobado> =>
    req("/portal/pre-aprobado", { method: "POST", body: JSON.stringify(b) }),
  // Idempotency-Key: un doble-clic en "Enviar" no crea dos solicitudes.
  enviarSolicitud: (b: { producto_id: string; monto: number; plazo: number; apellido?: string; nombre?: string; dni?: string; destino?: string; cbu?: string; acepta_terminos?: boolean; acepta_datos?: boolean; videos_vistos?: string[] } & Datos, idemKey: string): Promise<Solicitud> =>
    req("/portal/solicitudes", { method: "POST", body: JSON.stringify(b), headers: { "Idempotency-Key": idemKey } }),
  videos: (): Promise<Video[]> => req("/portal/videos"),
  misSolicitudes: (): Promise<Solicitud[]> => req("/portal/solicitudes"),
  solicitudDetalle: (numero: string): Promise<SolicitudDetalle> => req(`/portal/solicitudes/${numero}`),
  // Documentación adjunta
  docsListar: (numero: string): Promise<{ items: Documento[]; puede_subir: boolean }> => req(`/portal/solicitudes/${numero}/documentos`),
  docSubir: (numero: string, file: File, tipo: string) => {
    const f = new FormData(); f.append("archivo", file); f.append("tipo", tipo);
    return upload(`/portal/solicitudes/${numero}/documentos`, f) as Promise<Documento>;
  },
  docAbrir: (numero: string, docId: string) => abrirArchivo(`/portal/solicitudes/${numero}/documentos/${docId}`),
  docBorrar: (numero: string, docId: string) => req(`/portal/solicitudes/${numero}/documentos/${docId}`, { method: "DELETE" }),
  // Mis créditos (préstamo otorgado + cuotas + notificaciones)
  misCreditos: (): Promise<Credito[]> => req("/portal/creditos"),
  creditoDetalle: (contrato: string): Promise<CreditoDetalle> => req(`/portal/creditos/${contrato}`),
  notificaciones: (): Promise<Notificacion[]> => req("/portal/notificaciones"),
};

export type Documento = { id: string; tipo: string; nombre: string; content_type: string; tamano: number; subido_en: string; subido_por: string };
export type ProximaCuota = { numero: number; vencimiento: string; total: number; vencida: boolean };
export type Credito = { contrato: string; producto: string; monto: number; saldo: number; estado: string; tna: number; plazo: number; cuotas_pagadas: number; cuotas_total: number; progreso: number; en_mora: boolean; proxima: ProximaCuota | null };
export type CuotaEstado = { numero: number; vencimiento: string; total: number; pagado: number; estado: string; vencida: boolean };
export type CreditoDetalle = Credito & { fecha_alta: string; cuotas: CuotaEstado[] };
export type Notificacion = { tipo: string; titulo: string; detalle: string; fecha: string; contrato: string };
