import { useEffect, useMemo, useState } from "react";
import { useTema, Tema } from "./tema";
import { PasoVideos, guardarVistos, leerVistos, olvidarVistos } from "./videos";
import { api, nuevoId, token, Video, Ciudadano, Producto, Simulacion, Solicitud, SolicitudDetalle, Credito, CreditoDetalle, Notificacion, PreAprobado } from "./api";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 2 });

/** Lo tecleado ("1.234,56", "1234.56") al número que viaja al backend ("1234.56"). */
const aNumero = (texto: string) => {
  const limpio = texto.replace(/[^\d,.-]/g, "").replace(/\.(?=\d{3}\b)/g, "").replace(",", ".");
  const n = Number(limpio);
  return limpio === "" || isNaN(n) ? "" : String(n);
};

/** El sueldo ya cargado, con separador de miles y dos decimales. */
const formatoMoneda = (v: string | number) =>
  v === "" || v == null || isNaN(Number(v)) ? "" :
    Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS",
                                        minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Antigüedad: hasta dos dígitos de años (con medio año, por eso el decimal). */
const acotarAnios = (texto: string) => {
  const n = texto.replace(/[^\d.,]/g, "").replace(",", ".");
  const entero = n.split(".")[0];
  return entero.length > 2 ? entero.slice(0, 2) + (n.includes(".") ? "." + n.split(".")[1] : "") : n;
};

// Isotipo institucional — vector oficial (navy #1a3258 + verde #81bc26).
function PortalLogo({ size = 40 }: { size?: number }) {
  const h = Math.round(size * 325 / 540);
  return (
    <svg width={size} height={h} viewBox="0 0 540 325" role="img" aria-label="Caja de Crédito y Prestaciones de Catamarca">
      <g transform="translate(0,325) scale(0.1,-0.1)" stroke="none">
        <path fill="#1a3258" d="M1795 3145 c-27 -7 -93 -22 -145 -34 -52 -12 -171 -39 -265 -60 -93 -22 -255 -58 -360 -81 -104 -23 -212 -48 -240 -55 -27 -8 -84 -21 -127 -30 -72 -15 -77 -18 -94 -53 -19 -40 -142 -295 -274 -567 -45 -93 -104 -215 -130 -270 -26 -55 -70 -148 -99 -207 -28 -58 -51 -111 -51 -116 0 -5 47 -106 104 -223 57 -118 128 -266 159 -329 30 -63 101 -209 157 -324 55 -115 112 -233 126 -261 29 -62 -10 -48 399 -140 160 -36 339 -77 400 -91 326 -76 509 -114 526 -109 10 4 51 33 91 67 97 80 102 83 338 270 113 89 304 241 425 337 121 97 269 214 329 261 60 47 120 94 133 105 13 11 54 45 92 75 86 68 114 120 115 205 1 159 -156 274 -305 223 -28 -9 -174 -115 -303 -220 -16 -12 -67 -54 -115 -91 -47 -38 -106 -85 -131 -105 -24 -20 -85 -69 -135 -107 -85 -66 -276 -217 -320 -253 -11 -10 -92 -73 -179 -141 l-159 -124 -61 12 c-34 7 -140 30 -236 53 -96 22 -213 49 -260 59 -171 37 -290 66 -294 70 -5 4 -121 244 -198 409 -22 47 -61 128 -88 180 -26 53 -57 118 -69 146 l-22 50 82 170 c45 93 96 201 114 239 108 233 179 367 199 376 20 8 271 67 531 124 66 14 158 35 204 46 97 23 113 21 163 -23 63 -57 196 -158 206 -158 6 0 12 3 14 8 2 4 28 28 58 52 30 25 68 57 85 72 16 16 35 28 42 28 6 0 13 4 15 8 2 4 35 35 73 67 39 32 70 62 70 66 0 5 -180 152 -311 254 -21 17 -52 42 -69 56 -119 101 -129 105 -210 84z" />
        <path fill="#81bc26" d="M3140 2928 c-102 -88 -308 -262 -459 -386 -150 -124 -275 -232 -278 -239 -3 -7 -10 -13 -15 -13 -8 0 -212 -161 -228 -180 -3 -4 -57 -48 -120 -100 -213 -173 -237 -196 -254 -247 -67 -197 136 -392 315 -300 32 16 1227 999 1259 1036 3 3 29 26 58 50 65 53 21 56 535 -40 289 -54 384 -75 392 -88 6 -9 38 -69 72 -133 34 -65 100 -189 146 -275 197 -368 181 -333 170 -373 -11 -36 -21 -59 -168 -395 -48 -109 -88 -204 -90 -210 -7 -33 -80 -175 -90 -175 -6 0 -103 -25 -215 -56 -219 -59 -420 -114 -538 -145 l-73 -20 -77 55 c-42 31 -107 78 -144 105 l-67 50 -43 -32 c-24 -18 -99 -75 -168 -127 -69 -52 -137 -104 -152 -116 l-27 -22 127 -95 c302 -224 446 -327 457 -327 7 0 95 22 196 49 375 100 644 173 659 178 8 3 22 7 31 9 55 11 384 105 391 112 12 12 199 442 211 487 7 22 15 42 18 45 9 6 37 68 132 290 41 96 94 218 118 270 49 112 50 120 5 202 -18 35 -90 169 -158 298 -69 129 -177 332 -240 450 -64 118 -129 243 -146 276 l-31 61 -163 31 c-340 64 -706 132 -783 146 -44 8 -129 24 -190 35 -186 35 -162 44 -375 -141z" />
      </g>
    </svg>
  );
}
// Selector de tema (claro / oscuro / dispositivo). Mismo criterio que el backoffice: la
// preferencia es del navegador, así que también está disponible antes de iniciar sesión.
const TEMAS: { id: Tema; label: string; icono: JSX.Element }[] = [
  { id: "light", label: "Claro", icono: (
    <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>
  ) },
  { id: "dark", label: "Oscuro", icono: <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z" /> },
  { id: "system", label: "Dispositivo", icono: (
    <><rect x="2" y="4" width="20" height="13" rx="2" /><path d="M8 21h8M12 17v4" /></>
  ) },
];

function SelectorTema() {
  const [tema, setTema] = useTema();
  return (
    <div className="p-tema" role="radiogroup" aria-label="Tema de la interfaz">
      {TEMAS.map((t) => (
        <button key={t.id} type="button" role="radio" aria-checked={tema === t.id} aria-label={t.label}
                title={t.label} className={tema === t.id ? "on" : ""} onClick={() => setTema(t.id)}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            {t.icono}
          </svg>
        </button>
      ))}
    </div>
  );
}

const SISTEMA: Record<string, string> = { FRANCES: "Francés", ALEMAN: "Alemán", DIRECTO: "Directo", CUOTA_FIJA: "Cuota fija" };

// Captura el token del fragmento tras el callback OIDC (<base>/ingreso#token=...) y limpia la URL.
// La base es /portal-creditos/ (vite.config.ts): Portezuelo publica el portal ahí.
/** Vuelta de Mi Catamarca: con el token entra; con error, se avisa en el login. */
function capturarTokenDeCallback(): string {
  const base = import.meta.env.BASE_URL;
  if (window.location.pathname !== `${base}ingreso`) return "";
  const h = new URLSearchParams(window.location.hash.slice(1));
  const t = h.get("token");
  if (t) token.set(t);
  window.history.replaceState({}, "", base);
  return !t && h.get("error")
    ? "No se pudo completar el ingreso con Mi Catamarca. Probá de nuevo."
    : "";
}

export default function App() {
  const [sesion, setSesion] = useState<Ciudadano | null>(null);
  const [cargando, setCargando] = useState(true);
  const [errSso, setErrSso] = useState("");

  useEffect(() => {
    setErrSso(capturarTokenDeCallback());
    if (!token.get()) { setCargando(false); return; }
    api.me().then(setSesion).catch(() => token.clear()).finally(() => setCargando(false));
  }, []);

  // H-159: si el token vence a mitad de sesión (un 401 en cualquier request), volver a Login sin recargar.
  useEffect(() => {
    const alExpirar = () => setSesion(null);
    window.addEventListener("portal:sesion-expirada", alExpirar);
    return () => window.removeEventListener("portal:sesion-expirada", alExpirar);
  }, []);

  if (cargando) return <Marco><p className="p-muted">Cargando…</p></Marco>;
  if (!sesion) return <Login aviso={errSso} />;
  return <Simulador sesion={sesion} onSalir={() => { token.clear(); setSesion(null); }} />;
}

function Marco({ children }: { children: React.ReactNode }) {
  return (
    <div className="p-app">
      <div className="p-center">{children}</div>
      <Estilos />
    </div>
  );
}

function Login({ aviso = "" }: { aviso?: string }) {
  const [err, setErr] = useState(aviso);
  const [yendo, setYendo] = useState(false);
  async function ingresar() {
    setYendo(true); setErr("");
    try { window.location.href = (await api.loginUrl()).authorize_url; }
    catch (e) { setErr(String(e)); setYendo(false); }
  }
  return (
    <Marco>
      <div className="p-card p-login">
        <div className="p-login-top">
          <div className="p-brand"><PortalLogo size={64} /><div><b>Caja de Crédito y Prestaciones</b><span>Ca.Pre.S.Ca. · Provincia de Catamarca</span></div></div>
          <SelectorTema />
        </div>
        <h1>Solicitá tu crédito online</h1>
        <p className="p-muted">Ingresá con tu cuenta de <b>Mi Catamarca</b> para simular tu crédito y enviar tu solicitud sin trámites presenciales.</p>
        <button className="p-btn p-btn-mc" onClick={ingresar} disabled={yendo}>
          {yendo ? "Redirigiendo…" : "Ingresar con Mi Catamarca"}
        </button>
        {err && <div className="p-alert">{err}</div>}
        <p className="p-fine">Tu identidad la valida el gobierno provincial. No guardamos tu contraseña de Mi Catamarca.</p>
      </div>
    </Marco>
  );
}

const ESTADO_SOL: Record<string, { label: string; cls: string }> = {
  EN_EVALUACION: { label: "En evaluación", cls: "warn" },
  APROBADA: { label: "Aprobada", cls: "ok" },
  ORIGINADA: { label: "Otorgada", cls: "ok" },
  RECHAZADA: { label: "Rechazada", cls: "crit" },
  ANULADA: { label: "Anulada", cls: "" },
  BORRADOR: { label: "Borrador", cls: "" },
};

// Seguimiento del expediente: etapas del trámite derivadas del estado de la solicitud.
// "done" = etapa superada · "current" = etapa actual · "todo" = pendiente · "fail" = rechazo.
type PasoEstado = "done" | "current" | "todo" | "fail";
function pasosExpediente(estado: string): { label: string; estado: PasoEstado }[] {
  const orden = ["EN_EVALUACION", "APROBADA", "ORIGINADA"];
  if (estado === "RECHAZADA")
    return [
      { label: "Enviada", estado: "done" },
      { label: "En evaluación", estado: "done" },
      { label: "Rechazada", estado: "fail" },
    ];
  const i = orden.indexOf(estado);
  const etapa = (n: number): PasoEstado => (i < 0 ? "todo" : i > n ? "done" : i === n ? "current" : "todo");
  const otorgada: PasoEstado = estado === "ORIGINADA" ? "done" : "todo";
  return [
    { label: "Enviada", estado: "done" },
    { label: "En evaluación", estado: etapa(0) },
    { label: "Aprobada", estado: etapa(1) },
    { label: "Otorgada", estado: otorgada },
  ];
}

const ESTADO_CR: Record<string, { label: string; cls: string }> = {
  ACTIVO: { label: "Activo", cls: "ok" },
  A_LIQUIDAR: { label: "En proceso", cls: "warn" },
  CERRADO: { label: "Cancelado", cls: "" },
  CANCELADO: { label: "Cancelado", cls: "" },
  REFINANCIADO: { label: "Refinanciado", cls: "" },
};

const SEGMENTOS: [string, string][] = [
  ["", "Elegí tu situación…"],
  ["AGENTE_PUBLICO", "Empleado público provincial"],
  ["MUNICIPAL", "Empleado municipal"],
  ["DOCENTE", "Docente"],
  ["JUBILADO", "Jubilado"],
  ["PENSIONADO", "Pensionado"],
  ["CONTRATADO", "Contratado / monotributo"],
  ["LIBRE", "Otro / independiente"],
];
const SEG_LABEL = Object.fromEntries(SEGMENTOS);

const TIPO_DOC: Record<string, string> = {
  DNI_FRENTE: "DNI (frente)", DNI_DORSO: "DNI (dorso)",
  SELFIE_DNI: "Selfie con el DNI en la mano", RECIBO: "Recibo de sueldo",
  CERTIFICADO_SERVICIOS: "Certificado de servicios", CONSTANCIA_CBU: "Constancia de CBU",
};
const TIPO_DOC_AYUDA: Record<string, string> = {
  SELFIE_DNI: "Una foto tuya sosteniendo el DNI, que se lean los datos.",
  CERTIFICADO_SERVICIOS: "El que emite tu empleador con tu antigüedad y situación de revista.",
  CONSTANCIA_CBU: "La que baja tu banco o Home Banking con el CBU a tu nombre.",
};
// Documentación del paso 3: exactamente un archivo por cada uno de estos (ni más, ni otros).
const DOCS_REQUERIDOS = ["DNI_FRENTE", "DNI_DORSO", "SELFIE_DNI", "RECIBO",
                         "CERTIFICADO_SERVICIOS", "CONSTANCIA_CBU"];

/** Años cumplidos a hoy (el backend calcula lo mismo con la fecha declarada). */
function edadDe(nacimiento: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(nacimiento)) return null;
  const n = new Date(`${nacimiento}T00:00:00`);
  if (isNaN(n.getTime())) return null;
  const hoy = new Date();
  let e = hoy.getFullYear() - n.getFullYear();
  const m = hoy.getMonth() - n.getMonth();
  if (m < 0 || (m === 0 && hoy.getDate() < n.getDate())) e--;
  return e;
}
const emailValido = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim());
const PASOS = ["Tus datos", "Simulación", "Documentación", "Videos", "Confirmación"];
/** Cuando el paso de videos está omitido (no hay videos configurados), no se muestra en la guía. */
const pasosVisibles = (conVideos: boolean) =>
  PASOS.map((t, i) => ({ titulo: t, numero: (i + 1) as Paso }))
       .filter((p) => conVideos || p.numero !== 4);
type Paso = 1 | 2 | 3 | 4 | 5;
type DocElegido = { file: File; tipo: string };
const fmtBytes = (n: number) => (n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1048576).toFixed(1)} MB`);

// Documentos del paso 3: un casillero por documento pedido, con un único archivo cada uno (adjuntar de
// nuevo lo reemplaza). Se eligen en el cliente y se suben al ENVIAR la solicitud (todavía no existe el
// número). Valida formato/tamaño localmente; el backend exige lo mismo. H-162.
const DOC_MAX = 5 * 1024 * 1024;
const DOC_TYPES = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
function DocsPicker({ docs, onChange }: { docs: DocElegido[]; onChange: (d: DocElegido[]) => void }) {
  const [err, setErr] = useState("");
  const elegir = (tipo: string, file?: File, input?: HTMLInputElement) => {
    if (input) input.value = "";          // permite volver a elegir el mismo archivo
    if (!file) return;
    setErr("");
    if (!DOC_TYPES.includes(file.type)) { setErr(`${TIPO_DOC[tipo]}: formato no permitido (JPG, PNG o PDF).`); return; }
    if (file.size > DOC_MAX) { setErr(`${TIPO_DOC[tipo]}: el archivo supera los 5 MB.`); return; }
    onChange([...docs.filter((d) => d.tipo !== tipo), { file, tipo }]);
  };
  const quitar = (tipo: string) => onChange(docs.filter((d) => d.tipo !== tipo));
  return (
    <div className="p-docs">
      <ul className="p-docs-slots" aria-label="Documentación requerida">
        {DOCS_REQUERIDOS.map((t) => {
          const d = docs.find((x) => x.tipo === t);
          const esPdf = d?.file.type === "application/pdf";
          return (
            <li key={t} className={`p-doc-slot${d ? " ok" : ""}`}>
              <span className={"p-doc-ic" + (esPdf ? " pdf" : "")} aria-hidden>{d ? (esPdf ? "PDF" : "IMG") : "○"}</span>
              <div className="p-doc-meta">
                <b>{TIPO_DOC[t]}</b>
                <span>{d ? `${d.file.name} · ${fmtBytes(d.file.size)}` : (TIPO_DOC_AYUDA[t] || "Falta adjuntar")}</span>
              </div>
              <label className={`p-btn-file${d ? " sec" : ""}`}>{d ? "Cambiar" : "＋ Adjuntar"}
                <input type="file" accept={DOC_TYPES.join(",")} hidden aria-label={`Adjuntar ${TIPO_DOC[t]}`}
                       onChange={(e) => elegir(t, e.target.files?.[0], e.target)} />
              </label>
              {d && <button type="button" className="p-doc-del" onClick={() => quitar(t)} aria-label={`Quitar ${TIPO_DOC[t]}`}>✕</button>}
            </li>
          );
        })}
      </ul>
      <p className="p-fine" style={{ margin: "8px 0 0" }}>Un archivo por documento · JPG, PNG o PDF · máx 5 MB</p>
      {err && <div className="p-alert" style={{ marginTop: 8 }}>{err}</div>}
    </div>
  );
}

function Simulador({ sesion, onSalir }: { sesion: Ciudadano; onSalir: () => void }) {
  const [tab, setTab] = useState<"simular" | "solicitudes" | "creditos">("simular");
  const [creditos, setCreditos] = useState<Credito[]>([]);
  const [creditoDet, setCreditoDet] = useState<CreditoDetalle | null>(null);
  const [notis, setNotis] = useState<Notificacion[]>([]);
  const [notisOpen, setNotisOpen] = useState(false);
  const [paso, setPaso] = useState<Paso>(1);   // 1 Datos · 2 Simulación · 3 Documentación · 4 Videos · 5 Confirmación
  const [datosErr, setDatosErr] = useState("");
  const [productos, setProductos] = useState<Producto[]>([]);
  const [prodId, setProdId] = useState<string>("");
  const [monto, setMonto] = useState("500000");
  const [plazo, setPlazo] = useState("12");
  const [sim, setSim] = useState<Simulacion | null>(null);
  const [preap, setPreap] = useState<PreAprobado | null>(null);
  const [err, setErr] = useState("");
  const [calc, setCalc] = useState(false);
  const [idem, setIdem] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [okMsg, setOkMsg] = useState("");
  const [solicitudes, setSolicitudes] = useState<Solicitud[]>([]);
  const [detalle, setDetalle] = useState<SolicitudDetalle | null>(null);
  // Datos del solicitante (Fase 3). Mi Catamarca sólo confirma que la persona existe: la identidad la
  // CARGA el ciudadano (H-162).
  const [apellido, setApellido] = useState("");
  const [nombre, setNombre] = useState("");
  const [dni, setDni] = useState("");
  const [segmento, setSegmento] = useState("");
  const [nacimiento, setNacimiento] = useState("");     // fecha; la edad se calcula (antes se pedía la edad)
  const [email, setEmail] = useState("");
  const [telefono, setTelefono] = useState("");
  const [antiguedad, setAntiguedad] = useState("");
  const [sueldo, setSueldo] = useState("");
  // El sueldo se guarda como número y se muestra con formato de moneda (se saca al editarlo).
  const [sueldoTexto, setSueldoTexto] = useState("");
  const [pendingDocs, setPendingDocs] = useState<DocElegido[]>([]);   // adjuntos elegidos (se suben al enviar)
  const [docsErr, setDocsErr] = useState("");
  const docsFaltantes = DOCS_REQUERIDOS.filter((t) => !pendingDocs.some((d) => d.tipo === t));
  // Paso 4: videos obligatorios (la lista la da el backend) y los que ya vio completos.
  const [videos, setVideos] = useState<Video[]>([]);
  const [videosErr, setVideosErr] = useState("");
  const [videosListos, setVideosListos] = useState(false);   // hasta que llega la lista no se puede avanzar
  const [vistos, setVistos] = useState<string[]>(() => leerVistos(sesion.sub));
  const videosOk = videosListos && videos.every((v) => vistos.includes(v.id));
  // El paso se saltea SÓLO cuando la lista llegó bien y vino vacía (omitido por configuración).
  // Si los videos no se pudieron cargar, el paso se muestra igual con su error: no se deja pasar
  // de largo un requisito por una falla de red.
  const pasoVideosOmitido = videosListos && !videosErr && videos.length === 0;
  const marcarVisto = (id: string) => setVistos((vs) => {
    const nuevos = vs.includes(id) ? vs : [...vs, id];
    guardarVistos(sesion.sub, nuevos);
    return nuevos;
  });
  const [cbu, setCbu] = useState("");
  const [aceptaTerminos, setAceptaTerminos] = useState(false);
  const [aceptaDatos, setAceptaDatos] = useState(false);
  const cbuDigits = cbu.replace(/\D/g, "");
  const dniDigits = dni.replace(/\D/g, "");
  const edad = edadDe(nacimiento);
  const telDigits = telefono.replace(/[^\d+]/g, "");
  const contactoOk = emailValido(email) && telDigits.replace("+", "").length >= 8;
  const identidadOk = apellido.trim().length > 0 && nombre.trim().length > 0 && (dniDigits.length === 7 || dniDigits.length === 8)
    && edad !== null && edad >= 18 && edad <= 99 && contactoOk;
  const puedeEnviar = identidadOk && cbuDigits.length === 22 && aceptaTerminos && aceptaDatos;

  // Borrador del portal: el ciudadano guarda la solicitud a medias y la retoma después (por dispositivo).
  const BORRADOR_KEY = `portal_borrador_${sesion.sub}`;
  const [borrador, setBorrador] = useState<any>(null);   // draft encontrado al entrar (para retomar)
  const [borradorMsg, setBorradorMsg] = useState("");
  useEffect(() => {
    try { const raw = localStorage.getItem(BORRADOR_KEY); if (raw) setBorrador(JSON.parse(raw)); } catch { /* ignore */ }
  }, []);
  function guardarBorrador() {
    const d = { paso, apellido, nombre, dni, segmento, nacimiento, email, telefono, antiguedad, sueldo,
                prodId, monto, plazo, cbu, aceptaTerminos, aceptaDatos, savedAt: new Date().toISOString() };
    try { localStorage.setItem(BORRADOR_KEY, JSON.stringify(d)); } catch { /* ignore */ }
    setBorrador(null); setBorradorMsg("Borrador guardado. Podés retomarlo más tarde desde este dispositivo.");
    setTimeout(() => setBorradorMsg(""), 4000);
  }
  function retomarBorrador() {
    const d = borrador; if (!d) return;
    setApellido(d.apellido || ""); setNombre(d.nombre || ""); setDni(d.dni || "");
    setSegmento(d.segmento || ""); setNacimiento(d.nacimiento || "");
    setEmail(d.email || ""); setTelefono(d.telefono || ""); setAntiguedad(d.antiguedad || "");
    setSueldo(d.sueldo || ""); setSueldoTexto(d.sueldo ? formatoMoneda(d.sueldo) : "");
    if (d.prodId) setProdId(d.prodId);
    setMonto(d.monto || "500000"); setPlazo(d.plazo || "12"); setCbu(d.cbu || "");
    setAceptaTerminos(!!d.aceptaTerminos); setAceptaDatos(!!d.aceptaDatos);
    // Los archivos no se guardan en el borrador: se retoma, como mucho, en Documentación.
    setPaso(Math.min(d.paso || 1, 3) as Paso); setTab("simular"); setBorrador(null);
  }
  function limpiarBorrador() { try { localStorage.removeItem(BORRADOR_KEY); } catch { /* ignore */ } }
  function descartarBorrador() { limpiarBorrador(); setBorrador(null); }

  const datos = () => ({
    apellido: apellido.trim(), nombre: nombre.trim(), dni: dniDigits,
    segmento: segmento || undefined,
    fecha_nacimiento: nacimiento || undefined,
    email: email.trim(),
    telefono: telDigits,
    antiguedad_meses: antiguedad ? Math.round(Number(antiguedad) * 12) : undefined,   // se declara en años
    sueldo: sueldo ? Number(sueldo) : undefined,
  });

  useEffect(() => {
    api.productos().then((ps) => { setProductos(ps); if (ps[0]) setProdId(ps[0].id); }).catch((e) => setErr(String(e)));
  }, []);

  function cargarSolicitudes() { api.misSolicitudes().then(setSolicitudes).catch((e) => setErr(String(e))); }
  useEffect(() => { if (tab === "solicitudes") cargarSolicitudes(); }, [tab]);
  useEffect(() => { if (tab === "creditos") api.misCreditos().then(setCreditos).catch((e) => setErr(String(e))); }, [tab]);
  useEffect(() => { api.notificaciones().then(setNotis).catch(() => {}); }, []);
  useEffect(() => {
    api.videos().then((vs) => { setVideos(vs); setVideosListos(true); }).catch(() => setVideosErr("No se pudieron cargar los videos. Reintentá en unos minutos."));
  }, []);

  // Paso 2: la cuota se recalcula EN VIVO al mover el monto/plazo (debounce), sin apretar "Simular".
  useEffect(() => {
    if (paso !== 2 || !prodId) return;
    const t = setTimeout(() => { correrSimulacion(); }, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line
  }, [prodId, monto, plazo, paso]);

  // Pre-aprobado ("¿cuánto puedo pedir?"): con el sueldo declarado, el monto máximo que califica.
  useEffect(() => {
    const s = Number(sueldo);
    if (paso !== 2 || !prodId || !s) { setPreap(null); return; }
    api.preAprobado({ producto_id: prodId, plazo: Number(plazo), sueldo: s })
      .then(setPreap).catch(() => setPreap(null));
  }, [paso, prodId, plazo, sueldo]);

  async function correrSimulacion() {
    if (!prodId) return;
    setCalc(true); setErr("");
    try {
      setSim(await api.simular({ producto_id: prodId, monto: Number(monto), plazo: Number(plazo), ...datos() }));
      setIdem(nuevoId());
    } catch (e) {
      // Sin simulación no hay "Continuar": se avisa en vez de dejar al ciudadano trabado sin explicación.
      setSim(null);
      setErr(`No pudimos calcular tu crédito: ${String(e).replace(/^Error:\s*/, "")}. Probá de nuevo en unos segundos.`);
    }
    finally { setCalc(false); }
  }

  const prod = useMemo(() => productos.find((p) => p.id === prodId) || null, [productos, prodId]);

  function irASimulacion() {
    if (!apellido.trim() || !nombre.trim()) { setDatosErr("Cargá tu apellido y nombre."); return; }
    if (dniDigits.length !== 7 && dniDigits.length !== 8) { setDatosErr("El DNI debe tener 7 u 8 dígitos."); return; }
    if (!segmento) { setDatosErr("Elegí tu situación laboral para continuar."); return; }
    if (edad === null) { setDatosErr("Cargá tu fecha de nacimiento."); return; }
    if (edad < 18 || edad > 99) { setDatosErr("Revisá tu fecha de nacimiento: la edad tiene que estar entre 18 y 99 años."); return; }
    if (!emailValido(email)) { setDatosErr("Cargá un email válido para que podamos contactarte."); return; }
    if (telDigits.replace("+", "").length < 8) { setDatosErr("Cargá un teléfono de contacto."); return; }
    setDatosErr(""); setPaso(2);
  }
  function reiniciarWizard() { setPaso(1); setSim(null); }
  function irAVideos() {
    if (docsFaltantes.length) { setDocsErr(`Falta adjuntar: ${docsFaltantes.map((t) => TIPO_DOC[t]).join(", ")}.`); return; }
    // Sin videos configurados (paso omitido), de la documentación se pasa derecho a confirmar.
    setDocsErr(""); setPaso(pasoVideosOmitido ? 5 : 4);
  }

  async function enviarSolicitud() {
    if (!prodId || !idem) return;
    setEnviando(true); setErr("");
    try {
      const s = await api.enviarSolicitud({ producto_id: prodId, monto: Number(monto), plazo: Number(plazo), cbu: cbuDigits, acepta_terminos: aceptaTerminos, acepta_datos: aceptaDatos, videos_vistos: vistos, ...datos() }, idem);
      // Subir los documentos del paso 3 (best-effort: si alguno falla, avisamos sin frenar).
      let fallos = 0;
      for (const d of pendingDocs) {
        try { await api.docSubir(s.numero, d.file, d.tipo); } catch { fallos++; }
      }
      setOkMsg(`Solicitud ${s.numero} enviada. Un asesor la va a evaluar.`
        + (fallos ? ` (No se pudieron adjuntar ${fallos} archivo/s; un asesor te los va a pedir si hacen falta.)` : ""));
      setPendingDocs([]);
      limpiarBorrador();   // enviada → el borrador ya no aplica
      olvidarVistos(sesion.sub); setVistos([]);   // la próxima solicitud vuelve a pedir los videos
      reiniciarWizard();
      setTab("solicitudes");
    } catch (e) { setErr(String(e)); }
    finally { setEnviando(false); }
  }

  return (
    <div className="p-app">
      <header className="p-header">
        <div className="p-brand"><PortalLogo size={44} /><b>Créditos CCyPP</b></div>
        <nav className="p-nav">
          <button className={tab === "simular" ? "on" : ""} onClick={() => setTab("simular")}>Solicitar</button>
          <button className={tab === "solicitudes" ? "on" : ""} onClick={() => setTab("solicitudes")}>Mis solicitudes</button>
          <button className={tab === "creditos" ? "on" : ""} onClick={() => setTab("creditos")}>Mis créditos</button>
        </nav>
        <div className="p-user">
          <SelectorTema />
          <div className="p-bell">
            <button className="p-bell-btn" onClick={() => setNotisOpen((o) => !o)} aria-label="Notificaciones">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M10.268 21a2 2 0 0 0 3.464 0" />
                <path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.674C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326" />
              </svg>
              {notis.length > 0 && <span className="p-bell-dot">{notis.length}</span>}
            </button>
            {notisOpen && (
              <div className="p-notis" onClick={(e) => e.stopPropagation()}>
                <div className="p-notis-head">Notificaciones</div>
                {notis.length === 0 && <div className="p-notis-empty">No tenés notificaciones.</div>}
                {notis.map((n, i) => (
                  <div className={`p-noti p-noti-${n.tipo}`} key={i}>
                    <b>{n.titulo}</b><span>{n.detalle}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <span>{sesion.nombre || sesion.email}</span><button className="p-btn-ghost" onClick={onSalir}>Salir</button>
        </div>
      </header>

      {tab === "solicitudes" ? (
        <main className="p-main">
          <h1>Mis solicitudes</h1>
          <p className="p-muted">El estado de los créditos que enviaste desde el portal.</p>
          {okMsg && <div className="p-ok">{okMsg}</div>}
          {err && <div className="p-alert">{err}</div>}
          {!solicitudes.length && <p className="p-muted">Todavía no enviaste ninguna solicitud.</p>}
          {solicitudes.length > 0 && (
            <div className="p-tablewrap">
              <table className="p-table">
                <thead><tr><th>N°</th><th>Producto</th><th className="r">Monto</th><th className="r">Cuotas</th><th className="r">Cuota est.</th><th>Fecha</th><th>Estado</th></tr></thead>
                <tbody>
                  {solicitudes.map((s) => (
                    <tr key={s.numero} className="p-rowlink" onClick={() => api.solicitudDetalle(s.numero).then(setDetalle).catch((e) => setErr(String(e)))}>
                      <td>{s.numero}</td><td>{s.producto}</td>
                      <td className="r">{money(s.monto)}</td><td className="r">{s.plazo}</td>
                      <td className="r">{money(s.cuota_estimada)}</td>
                      <td>{s.fecha ? new Date(s.fecha).toLocaleDateString("es-AR") : "—"}</td>
                      <td><span className={`p-pill ${ESTADO_SOL[s.estado]?.cls || ""}`}>{ESTADO_SOL[s.estado]?.label || s.estado}</span>
                        {s.estado === "RECHAZADA" && s.motivo_rechazo && <div className="p-fine">{s.motivo_rechazo}</div>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {detalle && (
            <div className="p-overlay" onClick={() => setDetalle(null)}>
              <div className="p-modal" onClick={(e) => e.stopPropagation()}>
                <div className="p-modal-head">
                  <b>{detalle.numero} · {detalle.producto}</b>
                  <span className={`p-pill ${ESTADO_SOL[detalle.estado]?.cls || ""}`}>{ESTADO_SOL[detalle.estado]?.label || detalle.estado}</span>
                  <button className="p-btn-ghost" onClick={() => setDetalle(null)}>✕</button>
                </div>
                <div className="p-modal-body">
                  <ol className="p-track" aria-label="Estado del trámite">
                    {pasosExpediente(detalle.estado).map((p, idx) => (
                      <li className={`p-track-step ${p.estado}`} key={idx}>
                        <span className="p-track-dot">{p.estado === "done" ? "✓" : p.estado === "fail" ? "✕" : idx + 1}</span>
                        <span className="p-track-label">{p.label}</span>
                      </li>
                    ))}
                  </ol>
                  {detalle.estado === "RECHAZADA" && detalle.motivo_rechazo && <div className="p-warnbox">Motivo del rechazo: {detalle.motivo_rechazo}</div>}
                  <div className="p-kpis">
                    <div className="p-kpi"><span>Monto</span><b>{money(detalle.monto)}</b></div>
                    <div className="p-kpi"><span>Cuota estimada</span><b>{money(detalle.cuota_estimada)}</b></div>
                    <div className="p-kpi"><span>Cuotas</span><b>{detalle.plazo}</b></div>
                    <div className="p-kpi"><span>Total a pagar</span><b>{money(detalle.total_a_pagar)}</b></div>
                  </div>
                  <p className="p-fine">Sistema {SISTEMA[detalle.sistema] || detalle.sistema} · TNA {detalle.tna}%{detalle.segmento ? ` · ${SEG_LABEL[detalle.segmento] || detalle.segmento}` : ""}{detalle.afectacion != null ? ` · afectación ${detalle.afectacion}%` : ""}</p>
                  {detalle.cuotas.length > 0 && (
                    <div className="p-tablewrap">
                      <table className="p-table">
                        <thead><tr><th>#</th><th>Vencimiento</th><th className="r">Capital</th><th className="r">Interés</th><th className="r">Cuota</th></tr></thead>
                        <tbody>
                          {detalle.cuotas.map((c) => (
                            <tr key={c.numero}><td>{c.numero}</td><td>{new Date(c.vencimiento).toLocaleDateString("es-AR")}</td>
                              <td className="r">{money(c.capital)}</td><td className="r">{money(c.interes)}</td><td className="r"><b>{money(c.total)}</b></td></tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </main>
      ) : tab === "creditos" ? (
        <main className="p-main">
          <h1>Mis créditos</h1>
          <p className="p-muted">Los préstamos que te otorgamos y cómo vienen tus cuotas.</p>
          {err && <div className="p-alert">{err}</div>}
          {!creditos.length && <p className="p-muted">Todavía no tenés créditos otorgados. Cuando aprobemos una solicitud, aparece acá.</p>}
          <div className="p-cred-list">
            {creditos.map((cr) => {
              const est = cr.en_mora ? { label: "En mora", cls: "crit" } : (ESTADO_CR[cr.estado] || { label: cr.estado, cls: "" });
              return (
                <div className="p-cred p-rowlink" key={cr.contrato} onClick={() => api.creditoDetalle(cr.contrato).then(setCreditoDet).catch((e) => setErr(String(e)))}>
                  <div className="p-cred-top">
                    <div><b>{cr.producto || "Crédito"}</b><span className="p-fine">{cr.contrato}</span></div>
                    <span className={`p-pill ${est.cls}`}>{est.label}</span>
                  </div>
                  <div className="p-cred-bar"><div className="p-cred-fill" style={{ width: `${cr.progreso}%` }} /></div>
                  <div className="p-cred-facts">
                    <div><span>Pagadas</span>{cr.cuotas_pagadas}/{cr.cuotas_total}</div>
                    <div><span>Saldo</span>{money(cr.saldo)}</div>
                    <div><span>Próxima cuota</span>{cr.proxima ? `${money(cr.proxima.total)} · ${new Date(cr.proxima.vencimiento).toLocaleDateString("es-AR")}${cr.proxima.vencida ? " (vencida)" : ""}` : "—"}</div>
                  </div>
                </div>
              );
            })}
          </div>
          {creditoDet && (
            <div className="p-overlay" onClick={() => setCreditoDet(null)}>
              <div className="p-modal" onClick={(e) => e.stopPropagation()}>
                <div className="p-modal-head">
                  <b>{creditoDet.contrato} · {creditoDet.producto || "Crédito"}</b>
                  <span className={`p-pill ${creditoDet.en_mora ? "crit" : (ESTADO_CR[creditoDet.estado]?.cls || "")}`}>{creditoDet.en_mora ? "En mora" : (ESTADO_CR[creditoDet.estado]?.label || creditoDet.estado)}</span>
                  <button className="p-btn-ghost" onClick={() => setCreditoDet(null)}>✕</button>
                </div>
                <div className="p-modal-body">
                  <div className="p-kpis">
                    <div className="p-kpi"><span>Monto otorgado</span><b>{money(creditoDet.monto)}</b></div>
                    <div className="p-kpi"><span>Saldo</span><b>{money(creditoDet.saldo)}</b></div>
                    <div className="p-kpi"><span>Cuotas pagadas</span><b>{creditoDet.cuotas_pagadas}/{creditoDet.cuotas_total}</b></div>
                    <div className="p-kpi"><span>TNA</span><b>{creditoDet.tna}%</b></div>
                  </div>
                  <p className="p-fine">Alta {creditoDet.fecha_alta ? new Date(creditoDet.fecha_alta).toLocaleDateString("es-AR") : "—"} · {creditoDet.plazo} cuotas</p>
                  <div className="p-tablewrap">
                    <table className="p-table">
                      <thead><tr><th>#</th><th>Vencimiento</th><th className="r">Cuota</th><th className="r">Pagado</th><th>Estado</th></tr></thead>
                      <tbody>
                        {creditoDet.cuotas.map((q) => (
                          <tr key={q.numero}>
                            <td>{q.numero}</td><td>{new Date(q.vencimiento).toLocaleDateString("es-AR")}</td>
                            <td className="r">{money(q.total)}</td><td className="r">{money(q.pagado)}</td>
                            <td><span className={`p-pill ${q.estado === "PAGADA" ? "ok" : q.vencida ? "crit" : "warn"}`}>{q.estado === "PAGADA" ? "Pagada" : q.vencida ? "Vencida" : "Pendiente"}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      ) : (
      <main className="p-main">
        <h1>Solicitá tu crédito</h1>
        <ol className="p-steps">
          {pasosVisibles(!pasoVideosOmitido).map(({ titulo, numero: n }, i) => {
            const estado = paso === n ? "on" : paso > n ? "done" : "";
            const ir = () => { if (n < paso) setPaso(n); };
            return <li key={titulo} className={`p-step ${estado}`} onClick={ir}>
              <span className="p-step-n">{paso > n ? "✓" : i + 1}</span>{titulo}</li>;
          })}
        </ol>
        {borrador && (
          <div className="p-borrador">
            <span>Tenés una solicitud sin terminar (guardada {new Date(borrador.savedAt).toLocaleString("es-AR")}).</span>
            <div className="p-borrador-acc">
              <button className="p-btn-ghost" onClick={retomarBorrador}>Retomar</button>
              <button className="p-btn-ghost" onClick={descartarBorrador}>Descartar</button>
            </div>
          </div>
        )}
        {borradorMsg && <div className="p-ok" style={{ marginBottom: 14 }}>{borradorMsg}</div>}
        <div className="p-borrador-save"><button className="p-btn-ghost" onClick={guardarBorrador}>Guardar borrador</button></div>

        {err && <div className="p-alert">{err}</div>}

        {paso === 1 && (
          <div className="p-card p-form">
            <div className="p-col2 p-subtitle">Tus datos <span>(nos dicen si calificás y tu afectación)</span></div>
            <p className="p-col2 p-fine" style={{ margin: "-4px 0 2px" }}>Ingresaste con Mi Catamarca (identidad verificada). Completá tus datos para simular y solicitar.</p>
            <label className="p-fld"><span>Apellido <b className="p-req">*</b></span>
              <input value={apellido} maxLength={40} onChange={(e) => setApellido(e.target.value)} placeholder="—" /></label>
            <label className="p-fld"><span>Nombre <b className="p-req">*</b></span>
              <input value={nombre} maxLength={40} onChange={(e) => setNombre(e.target.value)} placeholder="—" /></label>
            <label className="p-fld"><span>DNI <b className="p-req">*</b></span>
              <input inputMode="numeric" value={dni} maxLength={8} onChange={(e) => setDni(e.target.value.replace(/\D/g, "").slice(0, 8))} placeholder="—" /></label>
            <label className="p-fld"><span>Situación laboral <b className="p-req">*</b></span>
              <select value={segmento} onChange={(e) => setSegmento(e.target.value)}>
                {SEGMENTOS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select></label>
            <label className="p-fld"><span>Fecha de nacimiento <b className="p-req">*</b></span>
              <input type="date" value={nacimiento} max={new Date().toISOString().slice(0, 10)}
                     onChange={(e) => setNacimiento(e.target.value)} />
              {edad !== null && <span className="p-fine">{edad} años</span>}</label>
            <label className="p-fld"><span>Email <b className="p-req">*</b></span>
              <input type="email" value={email} maxLength={80} onChange={(e) => setEmail(e.target.value)} placeholder="nombre@correo.com" /></label>
            <label className="p-fld"><span>Teléfono <b className="p-req">*</b></span>
              <input type="tel" inputMode="tel" value={telefono} maxLength={20}
                     onChange={(e) => setTelefono(e.target.value)} /></label>
            <label className="p-fld"><span>Antigüedad laboral (años)</span>
              <input type="number" min="0" max="99" step="0.5" value={antiguedad}
                     onChange={(e) => setAntiguedad(acotarAnios(e.target.value))} placeholder="—" /></label>
            <label className="p-fld"><span>Sueldo neto</span>
              <input inputMode="decimal" value={sueldoTexto}
                     onChange={(e) => { setSueldoTexto(e.target.value); setSueldo(aNumero(e.target.value)); }}
                     onBlur={() => setSueldoTexto(sueldo ? formatoMoneda(sueldo) : "")}
                     onFocus={() => setSueldoTexto(sueldo)}
                     placeholder="$ 0,00" /></label>
            {datosErr && <div className="p-col2 p-alert">{datosErr}</div>}
            <div className="p-col2 p-actions"><button className="p-btn" onClick={irASimulacion}>Continuar →</button></div>
          </div>
        )}

        {paso === 2 && (
          <>
            <div className="p-card p-form">
              <div className="p-col2 p-subtitle">Elegí el crédito</div>
              <label className="p-fld p-col2"><span>Producto de crédito</span>
                <select value={prodId} onChange={(e) => setProdId(e.target.value)}>
                  {productos.map((p) => <option key={p.id} value={p.id}>{p.nombre} · {SISTEMA[p.sistema] || p.sistema} · TNA {p.tna}%</option>)}
                </select></label>

              {preap && (
                <div className="p-col2 p-preap">
                  {preap.monto_maximo > 0 ? (
                    <>
                      <div><b>Podés pedir hasta {money(preap.monto_maximo)}</b><span> · cuota {money(preap.cuota)} ({preap.afectacion}% de tu sueldo)</span></div>
                      <button type="button" className="p-preap-btn" onClick={() => setMonto(String(preap.monto_maximo))}>Usar el máximo</button>
                    </>
                  ) : <span>Con este sueldo y plazo la cuota se pasa del {preap.afectacion_max}% de tu sueldo, que es el máximo de este crédito; probá un plazo más largo.</span>}
                </div>
              )}

              <div className="p-fld p-col2">
                <span>Monto: <b className="p-slider-val">{money(Number(monto))}</b>{prod ? <em className="p-fine"> ({money(prod.monto_min)}–{money(prod.monto_max)})</em> : null}</span>
                <input type="range" min={prod?.monto_min || 0} max={prod?.monto_max || 1000000} step="10000" value={monto} onChange={(e) => setMonto(e.target.value)} /></div>
              <div className="p-fld p-col2">
                <span>Cuotas: <b className="p-slider-val">{plazo}</b>{prod ? <em className="p-fine"> ({prod.plazo_min}–{prod.plazo_max})</em> : null}</span>
                <input type="range" min={prod?.plazo_min || 1} max={prod?.plazo_max || 60} step="1" value={plazo} onChange={(e) => setPlazo(e.target.value)} /></div>

              <div className="p-col2 p-actions">
                <button type="button" className="p-btn-ghost" onClick={() => setPaso(1)}>← Volver</button>
                {calc && <span className="p-fine">Calculando…</span>}
              </div>
            </div>

            {sim && (
              <section className="p-result">
                <div className="p-kpis">
                  <div className="p-kpi"><span>Cuota promedio</span><b>{money(sim.cuota_promedio)}</b></div>
                  <div className="p-kpi"><span>Total a pagar</span><b>{money(sim.total_a_pagar)}</b></div>
                  <div className="p-kpi"><span>Total intereses</span><b>{money(sim.total_interes)}</b></div>
                  <div className="p-kpi"><span>CFT anual</span><b>{sim.cft}%</b></div>
                </div>
                <p className="p-fine" style={{ marginTop: 10 }}>{sim.producto} · sistema {SISTEMA[sim.sistema] || sim.sistema} · TNA {sim.tna}% · TEA {sim.tea}% · {sim.cantidad_cuotas} cuotas</p>
                {sim.elegible === true && <div className="p-ok" style={{ marginTop: 10 }}>✓ Con tus datos calificás para este crédito{sim.afectacion != null ? ` · la cuota es el ${sim.afectacion}% de tu sueldo` : ""}.</div>}
                {sim.elegible === false && (
                  <div className="p-warnbox">No calificás con estos datos:<ul>{sim.motivos.map((m2, i) => <li key={i}>{m2}</li>)}</ul>No podés enviar la solicitud hasta cumplir las condiciones. Ajustá los datos o elegí otro crédito.</div>
                )}
                {sim.elegible == null && sim.afectacion != null && <div className="p-ok" style={{ marginTop: 10 }}>La cuota es el {sim.afectacion}% de tu sueldo declarado.</div>}

                <details className="p-cronograma">
                  <summary>Ver el detalle de las {sim.cantidad_cuotas} cuotas</summary>
                  <div className="p-tablewrap">
                    <table className="p-table">
                      <thead><tr><th>#</th><th>Vencimiento</th><th className="r">Capital</th><th className="r">Interés</th><th className="r">Cargos</th><th className="r">Impuestos</th><th className="r">Cuota</th></tr></thead>
                      <tbody>
                        {sim.cuotas.map((c) => (
                          <tr key={c.numero}><td>{c.numero}</td><td>{new Date(c.vencimiento).toLocaleDateString("es-AR")}</td>
                            <td className="r">{money(c.capital)}</td><td className="r">{money(c.interes)}</td>
                            <td className="r">{money(c.cargos)}</td><td className="r">{money(c.impuestos)}</td><td className="r"><b>{money(c.total)}</b></td></tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>

                <div className="p-sticky-cta">
                  <div><span className="p-fine">Cuota</span><b>{money(sim.cuota_promedio)}</b></div>
                  <button className="p-btn p-btn-mc" onClick={() => setPaso(3)}>Continuar →</button>
                </div>
              </section>
            )}
          </>
        )}

        {paso === 3 && (
          <section className="p-result">
            <div className="p-card" style={{ padding: "18px 20px" }}>
              <div className="p-subtitle" style={{ borderTop: "none", paddingTop: 0 }}>Documentación <span>(obligatoria para continuar)</span></div>
              <p className="p-fine" style={{ margin: "6px 0 12px" }}>Adjuntá una imagen o PDF de cada uno: DNI frente, DNI dorso y tu último recibo de sueldo.</p>
              <DocsPicker docs={pendingDocs} onChange={(d) => { setPendingDocs(d); setDocsErr(""); }} />
              {docsErr && <div className="p-alert">{docsErr}</div>}
            </div>
            <div className="p-cta">
              <button type="button" className="p-btn-ghost" onClick={() => setPaso(2)}>← Volver</button>
              <button className="p-btn p-btn-mc" onClick={irAVideos}>Continuar →</button>
              {docsFaltantes.length > 0 && <span className="p-fine">Te falta{docsFaltantes.length === 1 ? "" : "n"} {docsFaltantes.length} documento{docsFaltantes.length === 1 ? "" : "s"}.</span>}
            </div>
          </section>
        )}

        {paso === 4 && (
          <section className="p-result">
            <PasoVideos videos={videos} vistos={vistos} onVisto={marcarVisto} error={videosErr} />
            <div className="p-cta">
              <button type="button" className="p-btn-ghost" onClick={() => setPaso(3)}>← Volver</button>
              <button className="p-btn p-btn-mc" onClick={() => setPaso(5)} disabled={!videosOk || !!videosErr}>Continuar →</button>
              {!videosOk && <span className="p-fine">Terminá de ver los videos para continuar.</span>}
            </div>
          </section>
        )}

        {paso === 5 && sim && (
          <section className="p-result">
            <div className="p-card" style={{ padding: "18px 20px" }}>
              <div className="p-subtitle" style={{ borderTop: "none", paddingTop: 0 }}>Revisá y confirmá tu solicitud</div>
              <div className="p-resumen">
                <div><span>Producto</span>{sim.producto}</div>
                <div><span>Monto</span>{money(sim.monto)}</div>
                <div><span>Cuotas</span>{sim.cantidad_cuotas}</div>
                <div><span>Cuota estimada</span>{money(sim.cuota_promedio)}</div>
                <div><span>Total a pagar</span>{money(sim.total_a_pagar)}</div>
                <div><span>TNA / CFT</span>{sim.tna}% / {sim.cft}%</div>
                <div><span>Solicitante</span>{apellido || nombre ? `${apellido}, ${nombre}` : "—"}</div>
                <div><span>DNI</span>{dniDigits || "—"}</div>
                <div><span>Situación</span>{SEG_LABEL[segmento] || segmento || "—"}</div>
                {edad !== null && <div><span>Edad</span>{edad} años</div>}
                <div><span>Email</span>{email || "—"}</div>
                <div><span>Teléfono</span>{telefono || "—"}</div>
                {sueldo && <div><span>Sueldo declarado</span>{money(sueldo)}</div>}
                {sim.afectacion != null && <div><span>Afectación</span>{sim.afectacion}%</div>}
              </div>
              {sim.elegible === true && <div className="p-ok" style={{ marginTop: 4 }}>✓ Con tus datos calificás para este crédito.</div>}
              {sim.elegible === false && <div className="p-warnbox">Con estos datos no cumplís las condiciones de este crédito, así que no se puede enviar. Volvé atrás para ajustar los datos o elegir otro crédito.</div>}

              <label className="p-fld" style={{ marginTop: 14 }}><span>CBU para acreditar el crédito (22 dígitos)</span>
                <input inputMode="numeric" maxLength={22} value={cbu}
                       onChange={(e) => setCbu(e.target.value.replace(/\D/g, "").slice(0, 22))}
                       placeholder="0000000000000000000000" />
                {cbu && cbuDigits.length !== 22 && <span className="p-fine" style={{ color: "var(--p-warn)" }}>Faltan {22 - cbuDigits.length} dígito(s).</span>}
              </label>
              <label className="p-check"><input type="checkbox" checked={aceptaTerminos} onChange={(e) => setAceptaTerminos(e.target.checked)} /> Acepto los <b>términos y condiciones</b> del crédito.</label>
              <label className="p-check"><input type="checkbox" checked={aceptaDatos} onChange={(e) => setAceptaDatos(e.target.checked)} /> Autorizo el <b>tratamiento de mis datos personales</b> para evaluar la solicitud.</label>
            </div>
            <div className="p-cta">
              <button type="button" className="p-btn-ghost" onClick={() => setPaso(pasoVideosOmitido ? 3 : 4)}>← Volver</button>
              <button className="p-btn p-btn-mc" onClick={enviarSolicitud} disabled={enviando || !puedeEnviar || !videosOk || sim?.elegible === false}>{enviando ? "Enviando…" : "Confirmar y enviar solicitud"}</button>
              {sim?.elegible === false
                ? <span className="p-fine">No cumplís las condiciones de este crédito: no se puede enviar.</span>
                : !puedeEnviar && <span className="p-fine">Completá el CBU y aceptá los términos para enviar.</span>}
            </div>
          </section>
        )}
      </main>
      )}
      <Estilos />
    </div>
  );
}

// Reglas del tema oscuro, parametrizadas por el selector raíz: se emiten dos veces (elección
// explícita y preferencia del dispositivo) para no duplicar los valores a mano.
const OSCURO = (raiz: string) => `
      ${raiz} {
        --p-bg:#0e1622; --p-surface:#172230; --p-ink:#e7eef7; --p-muted:#95a3b8;
        --p-border:#2a3a4e; --p-brand:#5b8fc7; --p-brand-2:#7aa6d6; --p-green:#81bc26; --p-brand-ink:#0b1220;
        --p-ok:#43c88a; --p-warn:#e0a44a; --p-warn-soft:#3a2f16; --p-crit:#f0777a; --p-crit-soft:#3a1e20;
      }
      ${raiz} .p-alert { background:#3a1e20; color:#f0777a; border-color:#5b2a2c; }
      ${raiz} .p-ok, ${raiz} .p-preap { background:rgba(129,188,38,.12); border-color:rgba(129,188,38,.35); color:var(--p-ink); }
      ${raiz} .p-pill.ok { background:rgba(67,200,138,.16); color:var(--p-ok); }
      ${raiz} .p-track-step.done .p-track-dot, ${raiz} .p-track-step.fail .p-track-dot { color:#0b1220; }
`;

function Estilos() {
  return <style>{`
    :root {
      /* Identidad Caja de Crédito y Prestaciones de Catamarca: navy + verde */
      --p-bg:#eef2f6; --p-surface:#ffffff; --p-ink:#17202e; --p-muted:#55617a;
      --p-border:#dbe1ee; --p-brand:#1a3258; --p-brand-2:#294d76; --p-green:#81bc26; --p-brand-ink:#ffffff;
      --p-ok:#1a7f4b; --p-warn:#b45309; --p-warn-soft:#fef3c7; --p-crit:#b91c1c; --p-crit-soft:#fef2f2;
    }
    /* Modo oscuro: misma identidad (navy más claro para contraste + verde). Se aplica cuando el
       ciudadano lo elige (<html data-tema="dark">) o, si eligió "dispositivo", cuando el sistema
       operativo lo pide — salvo que haya elegido claro explícitamente. */
    ${OSCURO(':root[data-tema="dark"]')}
    @media (prefers-color-scheme: dark) {
      ${OSCURO(':root:not([data-tema="light"])')}
    }
    * { box-sizing:border-box; }
    html, body { margin:0; overflow-x:hidden; max-width:100%; }
    .p-app { min-height:100vh; width:100%; background:var(--p-bg); color:var(--p-ink);
      font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; }
    .p-center { min-height:100vh; display:flex; align-items:center; justify-content:center; padding:24px; }
    .p-card { background:var(--p-surface); border:1px solid var(--p-border); border-radius:16px;
      box-shadow:0 10px 30px rgba(15,23,42,.06); }
    .p-brand { display:flex; align-items:center; gap:10px; }
    .p-logo { width:38px; height:38px; border-radius:10px; background:linear-gradient(135deg,var(--p-brand),var(--p-brand-2));
      color:var(--p-brand-ink); font-weight:800; display:grid; place-items:center; letter-spacing:.5px; }
    .p-brand div { display:flex; flex-direction:column; line-height:1.2; }
    .p-brand div span { font-size:.72rem; color:var(--p-muted); }
    .p-login { max-width:420px; padding:30px; text-align:left; }
    .p-login h1 { font-size:1.5rem; margin:20px 0 6px; }
    .p-muted { color:var(--p-muted); line-height:1.5; margin:0 0 18px; }
    .p-btn { background:var(--p-brand); color:var(--p-brand-ink); border:none; border-radius:10px;
      padding:12px 18px; font-size:.95rem; font-weight:700; cursor:pointer; width:100%; }
    .p-btn:hover { background:var(--p-brand-2); }
    .p-btn:disabled { opacity:.6; cursor:default; }
    .p-btn-mc { background:linear-gradient(135deg,var(--p-brand),var(--p-brand-2)); }
    .p-btn-ghost { background:transparent; border:1px solid var(--p-border); border-radius:8px;
      padding:6px 12px; cursor:pointer; color:var(--p-ink); }
    .p-fine { font-size:.75rem; color:var(--p-muted); margin-top:14px; }
    .p-alert { margin-top:12px; background:#fef2f2; color:#b91c1c; border:1px solid #fecaca;
      border-radius:8px; padding:8px 12px; font-size:.85rem; }
    .p-header { display:flex; align-items:center; gap:16px; flex-wrap:wrap; padding:14px 20px;
      background:var(--p-surface); border-bottom:1px solid var(--p-border); }
    .p-header .p-logo { width:32px; height:32px; }
    .p-nav { display:flex; gap:4px; }
    .p-nav button { background:transparent; border:none; padding:8px 14px; border-radius:8px; cursor:pointer;
      font-size:.9rem; font-weight:600; color:var(--p-muted); }
    .p-nav button.on { background:var(--p-bg); color:var(--p-brand); }
    .p-user { display:flex; align-items:center; gap:12px; font-size:.9rem; margin-left:auto; }
    .p-login-top { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; }
    .p-tema { display:inline-flex; align-items:center; gap:2px; padding:2px; border-radius:10px; background:var(--p-bg); border:1px solid var(--p-border); }
    .p-tema button { display:inline-flex; padding:5px; border:none; border-radius:8px; background:transparent; color:var(--p-muted); cursor:pointer; transition:background .15s, color .15s; }
    .p-tema button:hover { color:var(--p-ink); }
    .p-tema button.on { background:var(--p-surface); color:var(--p-brand); box-shadow:0 1px 2px rgba(15,23,42,.12); }
    .p-bell { position:relative; }
    .p-bell-btn { background:transparent; border:none; cursor:pointer; position:relative; padding:5px; color:var(--p-muted); display:inline-flex; border-radius:10px; transition:color .15s, background .15s; }
    .p-bell-btn:hover { color:var(--p-ink); background:var(--p-surface-2, rgba(120,140,170,.12)); }
    .p-bell-btn svg { display:block; transition:transform .18s ease; }
    .p-bell-btn:hover svg { transform:rotate(-8deg); transform-origin:50% 20%; }
    .p-bell-dot { position:absolute; top:-1px; right:-2px; background:var(--p-crit, #dc2626); color:#fff; border-radius:999px; font-size:.6rem; font-weight:800; line-height:1; min-width:16px; height:16px; display:inline-flex; align-items:center; justify-content:center; padding:0 3px; box-shadow:0 0 0 2px var(--p-bg, #fff); }
    .p-bell-dot::after { content:""; position:absolute; inset:0; border-radius:inherit; box-shadow:0 0 0 0 color-mix(in srgb, var(--p-crit, #dc2626) 55%, transparent); animation:p-bell-pulse 2s ease-out infinite; }
    @keyframes p-bell-pulse { 0%{box-shadow:0 0 0 0 color-mix(in srgb, var(--p-crit,#dc2626) 55%, transparent);} 70%{box-shadow:0 0 0 6px transparent;} 100%{box-shadow:0 0 0 0 transparent;} }
    @media (prefers-reduced-motion: reduce) { .p-bell-dot::after { animation:none; } .p-bell-btn:hover svg { transform:none; } }
    .p-notis { position:absolute; right:0; top:34px; width:min(340px,90vw); background:var(--p-surface); border:1px solid var(--p-border); border-radius:12px; box-shadow:0 14px 40px rgba(15,23,42,.18); z-index:1100; overflow:hidden; }
    .p-notis-head { padding:12px 14px; font-weight:600; border-bottom:1px solid var(--p-border); }
    .p-notis-empty { padding:16px 14px; color:var(--p-muted); font-size:.88rem; }
    .p-noti { padding:10px 14px; border-bottom:1px solid var(--p-border); display:flex; flex-direction:column; gap:2px; border-left:3px solid var(--p-border); }
    .p-noti b { font-size:.86rem; } .p-noti span { font-size:.8rem; color:var(--p-muted); }
    .p-noti-otorgado { border-left-color:var(--p-ok); } .p-noti-vencimiento { border-left-color:var(--p-warn); } .p-noti-mora { border-left-color:#b91c1c; }
    .p-cred-list { display:flex; flex-direction:column; gap:14px; margin-top:16px; }
    .p-cred { background:var(--p-surface); border:1px solid var(--p-border); border-radius:14px; padding:16px 18px; }
    .p-cred-top { display:flex; align-items:center; justify-content:space-between; }
    .p-cred-top span { display:block; }
    .p-cred-bar { height:8px; background:var(--p-bg); border-radius:999px; overflow:hidden; margin:12px 0; }
    .p-cred-fill { height:100%; background:var(--p-green); border-radius:999px; }
    .p-cred-facts { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
    .p-cred-facts > div { display:flex; flex-direction:column; font-size:.92rem; font-weight:600; }
    .p-cred-facts span { font-size:.66rem; font-weight:600; text-transform:uppercase; letter-spacing:.02em; color:var(--p-muted); }
    .p-ok { background:#ecfdf5; color:var(--p-ok); border:1px solid #a7f3d0; border-radius:10px;
      padding:10px 14px; font-size:.9rem; margin-bottom:14px; font-weight:600; }
    .p-pill { display:inline-block; font-size:.72rem; font-weight:700; padding:3px 10px; border-radius:999px;
      background:var(--p-bg); color:var(--p-muted); }
    .p-pill.ok { background:#ecfdf5; color:var(--p-ok); }
    .p-pill.warn { background:var(--p-warn-soft); color:var(--p-warn); }
    .p-pill.crit { background:var(--p-crit-soft); color:var(--p-crit); }

    /* Seguimiento del expediente (stepper) */
    .p-track { list-style:none; display:flex; gap:0; margin:0 0 18px; padding:0; }
    .p-track-step { flex:1; display:flex; flex-direction:column; align-items:center; gap:6px; position:relative; text-align:center; }
    .p-track-step::before { content:""; position:absolute; top:13px; left:-50%; width:100%; height:2px; background:var(--p-border); z-index:0; }
    .p-track-step:first-child::before { display:none; }
    .p-track-dot { position:relative; z-index:1; width:28px; height:28px; border-radius:999px; display:grid; place-items:center;
      font-size:.8rem; font-weight:800; background:var(--p-surface); border:2px solid var(--p-border); color:var(--p-muted); }
    .p-track-label { font-size:.72rem; font-weight:600; color:var(--p-muted); line-height:1.2; }
    .p-track-step.done .p-track-dot { background:var(--p-ok); border-color:var(--p-ok); color:#fff; }
    .p-track-step.done::before { background:var(--p-ok); }
    .p-track-step.done .p-track-label { color:var(--p-ink); }
    .p-track-step.current .p-track-dot { background:var(--p-brand); border-color:var(--p-brand); color:var(--p-brand-ink); box-shadow:0 0 0 4px rgba(26,50,88,.12); }
    .p-track-step.current .p-track-label { color:var(--p-brand); font-weight:800; }
    .p-track-step.fail .p-track-dot { background:var(--p-crit); border-color:var(--p-crit); color:#fff; }
    .p-track-step.fail .p-track-label { color:var(--p-crit); font-weight:800; }
    @media (max-width:400px) { .p-track-label { font-size:.66rem; } }
    .p-borrador { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;
      background:var(--p-warn-soft); border:1px solid var(--p-warn); border-radius:10px; padding:10px 14px; margin-bottom:14px; font-size:.9rem; color:var(--p-ink); }
    .p-borrador-acc { display:flex; gap:8px; }
    .p-borrador-save { display:flex; justify-content:flex-end; margin-bottom:10px; }
    .p-cta { display:flex; align-items:center; gap:14px; margin-top:18px; flex-wrap:wrap; }
    .p-cta .p-btn { width:auto; padding:12px 26px; }
    .p-cronograma { margin-top:14px; }
    .p-cronograma > summary { cursor:pointer; color:var(--p-brand); font-weight:600; font-size:.9rem; padding:6px 0; list-style:revert; }
    .p-sticky-cta { position:sticky; bottom:0; margin-top:16px; display:flex; align-items:center; justify-content:space-between; gap:14px;
      background:var(--p-surface); border:1px solid var(--p-border); border-radius:12px; padding:12px 16px; box-shadow:0 -6px 20px rgba(15,23,42,.08); }
    .p-sticky-cta > div { display:flex; flex-direction:column; line-height:1.1; }
    .p-sticky-cta b { font-size:1.15rem; }
    .p-sticky-cta .p-btn { width:auto; padding:12px 28px; }
    .p-preap { background:#ecfdf5; border:1px solid #a7f3d0; border-radius:10px; padding:10px 14px; display:flex; align-items:center; gap:12px; flex-wrap:wrap; font-size:.9rem; }
    .p-preap b { color:var(--p-ok); } .p-preap span { color:var(--p-muted); }
    .p-preap-btn { margin-left:auto; background:var(--p-green); color:#fff; border:none; border-radius:8px; padding:6px 14px; font-weight:600; cursor:pointer; font-size:.85rem; }
    .p-slider-val { color:var(--p-brand); font-size:1.05rem; }
    .p-check { display:flex; align-items:flex-start; gap:9px; font-size:.88rem; color:var(--p-ink); margin-top:10px; cursor:pointer; line-height:1.4; }
    .p-check input { margin-top:2px; accent-color:var(--p-green); width:16px; height:16px; }
    .p-form input[type=range] { width:100%; accent-color:var(--p-green); margin-top:6px; height:6px; }
    .p-haberes { display:flex; align-items:center; gap:12px; flex-wrap:wrap; margin-bottom:2px; }
    .p-verif { color:var(--p-ok); font-size:.85rem; font-weight:600; }
    .p-subtitle { font-size:.82rem; font-weight:600; color:var(--p-brand); border-top:1px solid var(--p-border); padding-top:14px; margin-top:4px; }
    .p-subtitle span { color:var(--p-muted); font-weight:400; }
    .p-warnbox { background:var(--p-warn-soft); color:var(--p-warn); border-radius:10px; padding:10px 14px; font-size:.85rem; margin-top:10px; }
    .p-warnbox ul { margin:6px 0 4px; padding-left:18px; }
    .p-rowlink { cursor:pointer; }
    .p-rowlink:hover td { background:var(--p-bg); }
    .p-overlay { position:fixed; inset:0; background:rgba(15,23,42,.5); display:flex; align-items:center; justify-content:center; z-index:1000; padding:20px; }
    .p-modal { background:var(--p-surface); border-radius:14px; width:min(760px,96vw); max-height:88vh; overflow:auto; box-shadow:0 20px 50px rgba(0,0,0,.3); }
    .p-modal-head { display:flex; align-items:center; gap:12px; padding:16px 20px; border-bottom:1px solid var(--p-border); position:sticky; top:0; background:var(--p-surface); }
    .p-modal-head .p-btn-ghost { margin-left:auto; }
    .p-modal-body { padding:16px 20px; }
    .p-main { max-width:900px; margin:0 auto; padding:28px 24px 60px; }
    .p-main h1 { margin:0 0 4px; }
    .p-form { display:grid; grid-template-columns:1fr 1fr; gap:16px; padding:20px; margin-top:16px; }
    /* min-width:0 + width:100%: sin esto el ancho propio del <input> (y el del date en iOS) no deja
       achicar la columna y los campos se salen de la pantalla en el celular. */
    .p-fld { display:flex; flex-direction:column; gap:6px; font-size:.85rem; min-width:0; }
    .p-fld span { color:var(--p-muted); font-weight:600; }
    .p-fld select, .p-fld input { padding:10px 12px; border:1px solid var(--p-border); border-radius:9px;
      font-size:.95rem; width:100%; min-width:0; max-width:100%; }
    .p-col2 { grid-column:1 / -1; }
    .p-actions { display:flex; justify-content:flex-end; gap:10px; align-items:center; }
    .p-steps { display:flex; gap:10px; list-style:none; padding:0; margin:0 0 20px; flex-wrap:wrap; }
    .p-step { display:flex; align-items:center; gap:8px; font-size:.9rem; font-weight:600; color:var(--p-muted); background:var(--p-surface); border:1px solid var(--p-border); border-radius:999px; padding:7px 16px 7px 8px; }
    .p-step.done { cursor:pointer; color:var(--p-brand); }
    .p-step.on { color:var(--p-brand); border-color:var(--p-brand); box-shadow:0 0 0 3px rgba(30,58,92,.08); }
    .p-step-n { width:24px; height:24px; border-radius:999px; background:var(--p-bg); color:var(--p-muted); display:grid; place-items:center; font-size:.8rem; font-weight:800; }
    .p-step.on .p-step-n { background:var(--p-brand); color:#fff; }
    .p-step.done .p-step-n { background:var(--p-green); color:#fff; }
    .p-resumen { display:grid; grid-template-columns:1fr 1fr; gap:10px 24px; margin:12px 0; }
    .p-resumen > div { display:flex; flex-direction:column; font-size:.95rem; font-weight:600; color:var(--p-ink);
      min-width:0; overflow-wrap:anywhere; }
    .p-resumen span { font-size:.7rem; font-weight:600; text-transform:uppercase; letter-spacing:.02em; color:var(--p-muted); }
    .p-actions .p-btn { width:auto; padding:11px 24px; }
    .p-result { margin-top:24px; }
    .p-kpis { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; }
    .p-kpi { background:var(--p-surface); border:1px solid var(--p-border); border-radius:12px; padding:14px 16px;
      min-width:0; overflow-wrap:anywhere; }
    .p-kpi span { display:block; font-size:.72rem; color:var(--p-muted); text-transform:uppercase; letter-spacing:.03em; }
    .p-kpi b { font-size:1.25rem; }
    .p-warn { background:var(--p-warn-soft); color:var(--p-warn); border-radius:10px; padding:10px 16px 10px 30px; margin:16px 0 0; font-size:.85rem; }
    .p-tablewrap { overflow-x:auto; margin-top:18px; background:var(--p-surface); border:1px solid var(--p-border); border-radius:12px; }
    .p-table { width:100%; border-collapse:collapse; font-size:.86rem; font-variant-numeric:tabular-nums; }
    .p-table th, .p-table td { padding:9px 14px; border-bottom:1px solid var(--p-border); text-align:left; }
    .p-table th { color:var(--p-muted); font-weight:700; font-size:.72rem; text-transform:uppercase; }
    .p-table td.r, .p-table th.r { text-align:right; }
    .p-table tr:last-child td { border-bottom:none; }
    /* Documentación adjunta (H-160) */
    .p-docs { margin-top:4px; }
    .p-docs-req { list-style:none; margin:0 0 12px; padding:0; display:flex; flex-wrap:wrap; gap:8px; }
    .p-docs-req li { display:flex; align-items:center; gap:6px; font-size:.82rem; font-weight:600; padding:5px 12px; border-radius:999px; border:1px dashed var(--p-border); color:var(--p-muted); }
    .p-docs-req li.ok { border-style:solid; border-color:var(--p-ok); color:var(--p-ok); }

    /* Paso 4: videos obligatorios */
    .p-videos { padding:18px 20px; }
    .p-video { border:1px solid var(--p-border); border-radius:14px; padding:12px; margin-bottom:12px; background:var(--p-surface); }
    .p-video.off { opacity:.65; }
    .p-video.ok { border-color:var(--p-ok); }
    .p-video-head { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:10px; }
    .p-video-head .p-fine { margin:0 0 0 auto; }
    .p-video-n { width:26px; height:26px; border-radius:999px; display:grid; place-items:center; font-size:.8rem; font-weight:800; background:var(--p-bg); color:var(--p-muted); }
    .p-video.on .p-video-n { background:var(--p-brand); color:var(--p-brand-ink); }
    .p-video.ok .p-video-n { background:var(--p-ok); color:#fff; }
    .p-video video { width:100%; max-height:62vh; border-radius:10px; background:#000; display:block; }
    /* Controles propios: sin la barra nativa no se puede arrastrar para adelantar (en el celular sí se podía). */
    .p-video-ctrl { display:flex; align-items:center; gap:10px; margin-top:8px; }
    .p-video-play { width:44px; height:44px; border-radius:999px; border:none; cursor:pointer; font-size:1rem;
                    background:var(--p-brand); color:var(--p-brand-ink); display:grid; place-items:center; }
    .p-video-play:active { transform:scale(.96); }
    .p-video-bar { height:6px; border-radius:999px; background:var(--p-bg); overflow:hidden; margin-top:8px; }
    .p-video-bar span { display:block; height:100%; background:var(--p-green); transition:width .3s; }
    .p-video-aviso { margin:8px 0 0; font-size:.8rem; color:var(--p-warn); font-weight:600; }
    .p-video-lock { height:140px; border-radius:10px; background:var(--p-bg); display:grid; place-items:center; font-size:1.6rem; }
    .p-docs-head { font-size:.78rem; font-weight:800; text-transform:uppercase; letter-spacing:.04em; color:var(--p-muted); margin-bottom:10px; display:flex; align-items:center; gap:8px; }
    .p-docs-count { font-weight:700; color:var(--p-ink); background:var(--p-surface-2, rgba(120,140,170,.14)); border-radius:999px; padding:1px 8px; font-size:.72rem; letter-spacing:0; }
    .p-docs-opt { font-weight:400; text-transform:none; letter-spacing:0; color:var(--p-muted); font-size:.72rem; }
    .p-req { color:var(--p-crit, #dc2626); font-weight:700; }
    .p-docs-list { list-style:none; margin:0 0 10px; padding:0; display:flex; flex-direction:column; gap:8px; }
    .p-doc { display:flex; align-items:center; gap:10px; background:var(--p-surface); border:1px solid var(--p-border); border-radius:10px; padding:8px 10px; }
    .p-doc-ic { flex:none; width:34px; height:34px; border-radius:8px; display:grid; place-items:center; font-size:.6rem; font-weight:800; letter-spacing:.02em; background:color-mix(in srgb, var(--p-brand,#2f6df6) 14%, transparent); color:var(--p-brand,#2f6df6); }
    .p-doc-ic.pdf { background:color-mix(in srgb, var(--p-crit,#dc2626) 14%, transparent); color:var(--p-crit,#dc2626); }
    .p-doc-meta { min-width:0; flex:1; display:flex; flex-direction:column; line-height:1.25; }
    .p-doc-meta b { font-size:.86rem; }
    .p-doc-meta span { font-size:.72rem; color:var(--p-muted); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .p-doc-link { flex:none; background:transparent; border:1px solid var(--p-border); border-radius:8px; padding:5px 12px; font-size:.78rem; font-weight:600; color:var(--p-ink); cursor:pointer; }
    .p-doc-link:hover { border-color:var(--p-brand,#2f6df6); color:var(--p-brand,#2f6df6); }
    .p-doc-del { flex:none; background:transparent; border:none; color:var(--p-muted); cursor:pointer; font-size:1rem; padding:4px 6px; border-radius:8px; line-height:1; }
    .p-doc-del:hover { color:var(--p-crit,#dc2626); background:color-mix(in srgb, var(--p-crit,#dc2626) 12%, transparent); }
    .p-doc-del.on { font-size:.74rem; font-weight:700; color:#fff; background:var(--p-crit,#dc2626); padding:5px 9px; }
    .p-docs-up { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
    .p-docs-up select { padding:8px 10px; border:1px solid var(--p-border); border-radius:9px; background:var(--p-surface); color:var(--p-ink); font-size:.82rem; }
    .p-btn-file { display:inline-flex; align-items:center; gap:6px; background:var(--p-brand,#2f6df6); color:#fff; border-radius:9px; padding:8px 14px; font-size:.82rem; font-weight:700; cursor:pointer; }
    .p-btn-file.off { opacity:.6; cursor:default; }
    .p-btn-file.sec { background:transparent; color:var(--p-brand); border:1px solid var(--p-border); }
    .p-docs-slots { list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:8px; }
    .p-doc-slot { display:flex; align-items:center; gap:10px; padding:10px 12px; border:1px dashed var(--p-border); border-radius:12px; }
    .p-doc-slot.ok { border-style:solid; border-color:var(--p-ok); }
    .p-doc-slot .p-doc-meta { flex:1; min-width:0; }
    .p-doc-slot .p-doc-meta span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; display:block; }
    @media (max-width:680px){
      .p-header{ padding:12px 14px; gap:10px 14px; }
      .p-nav{ order:3; width:100%; overflow-x:auto; }
      .p-nav button{ padding:7px 12px; white-space:nowrap; }
      .p-user{ font-size:.85rem; }
      .p-user > span{ max-width:120px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .p-main{ padding:20px 14px 70px; }
      .p-center{ padding:16px; }
      .p-form{ grid-template-columns:1fr 1fr; padding:16px; }
      .p-kpis{ grid-template-columns:1fr 1fr; }
      .p-card{ border-radius:14px; }
      .p-videos{ padding:14px; }
      .p-doc-slot{ flex-wrap:wrap; }
      .p-resumen,.p-cred-facts{ grid-template-columns:1fr; gap:8px; }
      .p-preap{ flex-direction:column; align-items:flex-start; }
      .p-preap-btn{ margin-left:0; }
      .p-notis{ position:fixed; left:8px; right:8px; top:64px; width:auto; }
    }
    /* En celular, el formulario va a una sola columna: con dos, los campos no entraban y se salían
       de la pantalla (pasaba en cualquier teléfono de 401 a 560px, que son casi todos). */
    @media (max-width:560px){
      .p-form{ grid-template-columns:1fr; }
      .p-steps{ gap:6px; }
      .p-step{ padding:5px 10px 5px 5px; font-size:.78rem; }
      .p-step:not(.on){ font-size:0; gap:0; padding:4px; }
      .p-step:not(.on) .p-step-n{ font-size:.75rem; }
    }
  `}</style>;
}
