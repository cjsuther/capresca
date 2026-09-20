import { useEffect, useMemo, useState } from "react";
import RowMenu from "../../components/RowMenu";
import DataTable, { Col } from "../../components/DataTable";
import { api } from "../../api";
import { useNivelActual } from "../../permisos";
import { confirmar, avisar, pedirTexto } from "../../ui/dialog";

// Configurar Créditos — Product Builder estilo Temenos AA. Diseño guiado por componentes
// (Property Classes) con editores por componente, agregar/quitar, prueba en vivo opcional
// e inspector de datos. Persiste contra el backend (pp_*).

const money = (n: number) => isFinite(n) ? new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 }).format(n) : "—";
const money2 = (n: number) => isFinite(n) ? new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 2 }).format(n) : "—";

type Sistema = "FRANCES" | "ALEMAN" | "AMERICANO" | "BULLET";
type Estado = "BORRADOR" | "EN_REVISION" | "APROBADO" | "PUBLICADO" | "RETIRADO";
type Cfg = {
  sistema: Sistema; modalidad: string; tna: number; baseDias: string; frecuencia: string;
  montoMin: number; montoMax: number; plazoMin: number; plazoMax: number;
  graciaCapital: number; cargoOtorg: number; moraTNA: number;
  indice?: string; margen?: number; tnaVigente?: number;
  tnaNegociable?: boolean; tnaMin?: number; tnaMax?: number;
  vigenciaDesde?: string; vigenciaHasta?: string;
};
type Comp = { codigo: string; nombre: string; categoria: string; multiple: boolean; requerido: boolean; orden: number; activo: boolean; config: Record<string, any>; heredado?: boolean };
type Producto = {
  id: string; nombre: string; codigo: string; grupo: string; familia: string;
  version: number; estado: Estado; derivadaDe?: number | null; publicadas: number[]; cfg: Cfg;
  vigentePortal?: number | null;   // versión publicada y vigente HOY que se ofrece en el portal (o null)
  componentes: Comp[]; enviadoPor?: string | null; aprobadoPor?: string | null; publicadoPor?: string | null;
  padre?: { id: string; codigo: string; nombre: string } | null; cfgHeredada?: boolean;
  copiadoDe?: { id: string; codigo: string; nombre: string; publicado: boolean } | null;   // H-190: origen de la copia
};
type Permisos = { edita: boolean; aprueba: boolean };

const ICONS: Record<string, string> = {
  TERM_AMOUNT: "📐", INTEREST: "％", REPAYMENT_SCHEDULE: "📅", PAYMENT_RULES: "⇄", CHARGE: "＄",
  TAX: "🧾", OVERDUE: "⏰", PAYOFF: "✔", SETTLEMENT: "🧭", ACCOUNTING: "📚", AVAILABILITY: "🎯", ACTIVITY_RESTRICTION: "🔒", PERIODIC: "🔁",
};

type Field = { k: string; l: string; t: "num" | "text" | "bool" | "date" | "select" | "impuesto"; o?: string[] };
const SCHEMA: Record<string, Field[]> = {
  REPAYMENT_SCHEDULE: [
    { k: "diaPago", l: "Día de pago", t: "num" },
    { k: "primerVencimientoDias", l: "1er vencimiento (días)", t: "num" },
    { k: "ajusteFinDeSemana", l: "Ajuste fin de semana", t: "select", o: ["SIGUIENTE_HABIL", "ANTERIOR_HABIL", "SIN_AJUSTE"] },
    { k: "tipoCuota", l: "Tipo de cuota", t: "select", o: ["VENCIDA", "ADELANTADA"] },
  ],
  PAYMENT_RULES: [
    { k: "ordenImputacion", l: "Orden de imputación", t: "text" },
    { k: "toleranciaDias", l: "Tolerancia (días)", t: "num" },
    { k: "permitePagoParcial", l: "Permite pago parcial", t: "bool" },
    { k: "permiteAdelanto", l: "Permite adelanto de cuotas", t: "bool" },
  ],
  PAYOFF: [
    { k: "permite", l: "Permite cancelación anticipada", t: "bool" },
    { k: "penalidadPct", l: "Penalidad (%)", t: "num" },
    { k: "minCuotasPagadas", l: "Mín. cuotas pagadas", t: "num" },
    { k: "condonaInteresNoDevengado", l: "Condona interés no devengado", t: "bool" },
  ],
  SETTLEMENT: [
    { k: "generaLiquidacion", l: "Genera liquidación", t: "bool" },
    { k: "remitirA", l: "Remitir a", t: "select", o: ["TESORERIA", "CONTADURIA"] },
  ],
  ACCOUNTING: [
    { k: "cuentaCapital", l: "Cuenta capital", t: "text" },
    { k: "cuentaInteres", l: "Cuenta interés", t: "text" },
    { k: "cuentaComision", l: "Cuenta comisiones", t: "text" },
    { k: "cuentaIva", l: "Cuenta IVA", t: "text" },
    { k: "cuentaMora", l: "Cuenta mora", t: "text" },
    { k: "centroCosto", l: "Centro de costo", t: "text" },
  ],
  ACTIVITY_RESTRICTION: [
    { k: "permitePrepago", l: "Permite prepago", t: "bool" },
    { k: "permiteRenegociacion", l: "Permite renegociación", t: "bool" },
    { k: "permiteVacacionPago", l: "Permite vacación de pago", t: "bool" },
  ],
  PERIODIC: [
    { k: "repricingFrecuencia", l: "Repricing (tasa variable)", t: "select", o: ["NINGUNA", "MENSUAL", "TRIMESTRAL", "SEMESTRAL"] },
    { k: "capitalizaInteres", l: "Capitaliza interés", t: "bool" },
    { k: "diaAplicacion", l: "Día de aplicación", t: "num" },
  ],
  CHARGE: [
    { k: "momento", l: "Momento de aplicación", t: "select", o: ["DESEMBOLSO", "PRORRATEADO"] },
    { k: "financiable", l: "Financiable", t: "bool" },
  ],
  OVERDUE: [
    { k: "diasGracia", l: "Días de gracia", t: "num" },
    { k: "base", l: "Base punitorio", t: "select", o: ["CUOTA_VENCIDA", "SALDO"] },
    { k: "capitaliza", l: "Capitaliza mora", t: "bool" },
  ],
};

// Componentes con múltiples instancias (varios cargos / impuestos) — editor de lista.
const ITEM_SCHEMA: Record<string, Field[]> = {
  INTEREST: [{ k: "etiqueta", l: "Nombre", t: "text" }, { k: "tipo", l: "Tipo", t: "select", o: ["COMPENSATORIO", "PROMOCIONAL", "COMISION"] },
             { k: "tna", l: "TNA %", t: "num" }],
  CHARGE: [{ k: "etiqueta", l: "Etiqueta", t: "text" }, { k: "porcentaje", l: "%", t: "num" },
           { k: "momento", l: "Momento", t: "select", o: ["DESEMBOLSO", "PRORRATEADO"] }],
  TAX: [{ k: "codigo", l: "Impuesto (maestro)", t: "impuesto" }, { k: "etiqueta", l: "Etiqueta", t: "text" },
        { k: "base", l: "Base", t: "select", o: ["INTERES", "CARGOS", "CUOTA", "CAPITAL"] }, { k: "porcentaje", l: "%", t: "num" }],
};
const ITEM_NUEVO: Record<string, any> = {
  INTEREST: { etiqueta: "Nueva propiedad", tipo: "COMPENSATORIO", tna: 0 },
  CHARGE: { etiqueta: "Nuevo cargo", porcentaje: 0, momento: "PRORRATEADO" },
  TAX: { etiqueta: "Nuevo impuesto", base: "INTERES", porcentaje: 0 },
};
const ITEM_TITULO: Record<string, string> = { INTEREST: "Propiedades de interés adicionales", CHARGE: "Cargos adicionales", TAX: "Impuestos" };
const ITEM_SINGULAR: Record<string, string> = { INTEREST: "propiedad", CHARGE: "cargo", TAX: "impuesto" };

const CFG_DEFAULT: Cfg = { sistema: "FRANCES", modalidad: "FIJA", tna: 52, baseDias: "ACT/365", frecuencia: "MENSUAL", montoMin: 100000, montoMax: 5000000, plazoMin: 6, plazoMax: 60, graciaCapital: 0, cargoOtorg: 2, moraTNA: 120, indice: "", margen: 0, tnaNegociable: false, tnaMin: 0, tnaMax: 0, vigenciaDesde: "", vigenciaHasta: "" };
const CONFIG_DEFAULT: Record<string, any> = {
  REPAYMENT_SCHEDULE: { diaPago: 5, primerVencimientoDias: 30, ajusteFinDeSemana: "SIGUIENTE_HABIL", tipoCuota: "VENCIDA" },
  PAYMENT_RULES: { ordenImputacion: "MORA,INTERES,CAPITAL", toleranciaDias: 3, permitePagoParcial: false, permiteAdelanto: true },
  CHARGE: { momento: "DESEMBOLSO", financiable: false, items: [{ etiqueta: "Cargo administrativo", porcentaje: 1.5, momento: "PRORRATEADO" }] },
  TAX: { items: [{ etiqueta: "IVA sobre interés", base: "INTERES", porcentaje: 21 }, { etiqueta: "IVA sobre cargos", base: "CARGOS", porcentaje: 21 }, { etiqueta: "Sellado", base: "CUOTA", porcentaje: 1.2 }] },
  OVERDUE: { diasGracia: 5, base: "CUOTA_VENCIDA", capitaliza: false },
  PAYOFF: { permite: true, penalidadPct: 0, minCuotasPagadas: 3, condonaInteresNoDevengado: true },
  SETTLEMENT: { generaLiquidacion: true, remitirA: "TESORERIA" },
  ACCOUNTING: { cuentaCapital: "1.1.05.01", cuentaInteres: "4.1.01", cuentaComision: "4.1.04", cuentaIva: "2.1.07", cuentaMora: "4.1.02", centroCosto: "CRED" },
  AVAILABILITY: { canales: ["SUCURSAL", "WEB"], segmentos: ["AGENTE_PUBLICO"], edadMin: 18, edadMax: 75, antiguedadMinMeses: 0, requiereGarante: false, vigenteDesde: "", vigenteHasta: "" },
  ACTIVITY_RESTRICTION: { permitePrepago: true, permiteRenegociacion: true, permiteVacacionPago: false },
  PERIODIC: { repricingFrecuencia: "NINGUNA", capitalizaInteres: false, diaAplicacion: 1 },
};
// Catálogos de segmentación (Fase E) — deben coincidir con el backend (productos.py).
const SEGMENTOS = ["AGENTE_PUBLICO", "JUBILADO", "PENSIONADO", "DOCENTE", "MUNICIPAL", "CONTRATADO", "LIBRE"];
const CANALES = ["SUCURSAL", "WEB", "APP", "CONVENIO"];

function valida(codigo: string, config: any, cfg: Cfg): string[] {
  const e: string[] = []; const items = config.items || [];
  if (codigo === "TERM_AMOUNT") {
    if (cfg.montoMin <= 0) e.push("Monto mínimo debe ser > 0");
    if (cfg.montoMin > cfg.montoMax) e.push("Monto mínimo > máximo");
    if (cfg.plazoMin < 1) e.push("Plazo mínimo ≥ 1");
    if (cfg.plazoMin > cfg.plazoMax) e.push("Plazo mínimo > máximo");
  }
  if (codigo === "INTEREST") {
    if (cfg.tna < 0 || cfg.tna > 500) e.push("TNA fuera de 0–500%");
    if (cfg.tnaNegociable) {
      if ((cfg.tnaMin || 0) > (cfg.tnaMax || 0)) e.push("TNA mínima > máxima");
      if (cfg.modalidad === "FIJA" && !(cfg.tnaMin! <= cfg.tna && cfg.tna <= cfg.tnaMax!)) e.push("La TNA base debe estar dentro de la banda negociable");
    }
    items.forEach((it: any, i: number) => { if (!it.etiqueta) e.push(`Propiedad de interés #${i + 1}: falta nombre`); if (it.tna < 0 || it.tna > 500) e.push(`Propiedad de interés #${i + 1}: TNA 0–500%`); });
  }
  if (codigo === "CHARGE") {
    if (cfg.cargoOtorg < 0 || cfg.cargoOtorg > 100) e.push("Cargo de otorgamiento 0–100%");
    items.forEach((it: any, i: number) => { if (!it.etiqueta) e.push(`Cargo #${i + 1}: falta etiqueta`); if (it.porcentaje < 0 || it.porcentaje > 100) e.push(`Cargo #${i + 1}: % debe ser 0–100`); });
  }
  if (codigo === "TAX") items.forEach((it: any, i: number) => { if (!it.etiqueta) e.push(`Impuesto #${i + 1}: falta etiqueta`); if (it.porcentaje < 0 || it.porcentaje > 100) e.push(`Impuesto #${i + 1}: % debe ser 0–100`); });
  if (codigo === "OVERDUE") { if (cfg.moraTNA < 0) e.push("TNA punitoria ≥ 0"); if ((config.diasGracia ?? 0) < 0) e.push("Días de gracia ≥ 0"); }
  if (codigo === "REPAYMENT_SCHEDULE") { const d = config.diaPago; if (d < 1 || d > 28) e.push("Día de pago debe ser 1–28"); if ((config.primerVencimientoDias ?? 0) < 0) e.push("1er vencimiento ≥ 0"); }
  if (codigo === "PAYOFF") { const p = config.penalidadPct ?? 0; if (p < 0 || p > 100) e.push("Penalidad 0–100%"); }
  return e;
}

function esDefault(codigo: string, config: any, cfg: Cfg): boolean {
  const eq = (a: any, b: any) => JSON.stringify(a) === JSON.stringify(b);
  if (codigo === "TERM_AMOUNT") return ["montoMin", "montoMax", "plazoMin", "plazoMax", "frecuencia", "graciaCapital"].every((k) => (cfg as any)[k] === (CFG_DEFAULT as any)[k]);
  if (codigo === "INTEREST") return ["sistema", "modalidad", "tna", "baseDias"].every((k) => (cfg as any)[k] === (CFG_DEFAULT as any)[k]) && (cfg.indice || "") === "" && (cfg.margen || 0) === 0 && !cfg.tnaNegociable && (cfg.tnaMin || 0) === 0 && (cfg.tnaMax || 0) === 0 && !((config.items || []).length);
  if (codigo === "CHARGE") return cfg.cargoOtorg === CFG_DEFAULT.cargoOtorg && eq(config, CONFIG_DEFAULT.CHARGE);
  if (codigo === "OVERDUE") return cfg.moraTNA === CFG_DEFAULT.moraTNA && eq(config, CONFIG_DEFAULT.OVERDUE);
  return eq(config, CONFIG_DEFAULT[codigo] ?? {});
}

const CMP_CAMPOS: [keyof Cfg, string][] = [["sistema", "Sistema"], ["modalidad", "Modalidad"], ["tna", "TNA %"], ["baseDias", "Base de días"], ["frecuencia", "Frecuencia"], ["montoMin", "Monto mín."], ["montoMax", "Monto máx."], ["plazoMin", "Plazo mín."], ["plazoMax", "Plazo máx."], ["graciaCapital", "Gracia capital"], ["cargoOtorg", "Cargo otorg. %"], ["moraTNA", "Mora TNA %"]];
function diffVersiones(A: any, B: any): { grupo: string; campo: string; a: any; b: any }[] {
  const rows: { grupo: string; campo: string; a: any; b: any }[] = [];
  for (const [k, l] of CMP_CAMPOS) if (String(A.cfg[k]) !== String(B.cfg[k])) rows.push({ grupo: "Condiciones", campo: l, a: A.cfg[k], b: B.cfg[k] });
  const cA: Record<string, any> = Object.fromEntries(A.componentes.map((c: any) => [c.codigo, c]));
  for (const b of B.componentes) {
    const a = cA[b.codigo]; if (!a) continue;
    if (a.activo !== b.activo) rows.push({ grupo: "Componentes", campo: `${b.nombre} · activo`, a: a.activo ? "Sí" : "No", b: b.activo ? "Sí" : "No" });
    else if (b.activo && JSON.stringify(a.config) !== JSON.stringify(b.config)) rows.push({ grupo: "Componentes", campo: `${b.nombre} · config`, a: JSON.stringify(a.config), b: JSON.stringify(b.config) });
  }
  return rows;
}

type Fila = { k: number; date: Date; opening: number; capital: number; interes: number; cargos: number; total: number; closing: number };
// Arma el payload para el cronograma del backend (ÚNICA FUENTE DE VERDAD).
function previewPayload(cfg: Cfg, comps: Comp[], tnaEff: number, monto: number, plazo: number) {
  const conf = (cod: string) => (comps.find((c) => c.codigo === cod && c.activo)?.config || {}) as any;
  const ch = conf("CHARGE"), tx = conf("TAX"), rs = conf("REPAYMENT_SCHEDULE");
  return {
    sistema: cfg.sistema, monto, plazo, tna: tnaEff, cargoOtorg: cfg.cargoOtorg,
    gracia: cfg.graciaCapital || 0, frecuencia: cfg.frecuencia,
    cargos: (ch.items || []).map((it: any) => ({ porcentaje: it.porcentaje, momento: it.momento })),
    impuestos: (tx.items || []).map((it: any) => ({ base: it.base, porcentaje: it.porcentaje })),
    diaPago: rs.diaPago ?? 5, primerVencimientoDias: rs.primerVencimientoDias ?? 30,
    ajusteFinDeSemana: rs.ajusteFinDeSemana ?? "SIN_AJUSTE", tipoCuota: rs.tipoCuota ?? "VENCIDA",
    financiable: !!ch.financiable, cargoMomento: ch.momento ?? "PRORRATEADO",
  };
}
// Convierte las filas del backend al tipo Fila del simulador.
function toFilas(serverRows: any[]): Fila[] {
  return (serverRows || []).map((r) => ({
    k: r.numero_cuota, date: new Date(r.fecha_vencimiento + "T00:00:00"),
    opening: r.saldo_inicial, capital: r.capital, interes: r.interes,
    cargos: r.cargos, total: r.total, closing: r.saldo_final,
  }));
}

const FORMULA: Record<Sistema, string> = {
  FRANCES: "cuota = P · i / (1 − (1 + i)⁻ⁿ)", ALEMAN: "capitalₜ = P / n ·   interésₜ = saldoₜ · i",
  AMERICANO: "interésₜ = P · i ·   capitalₙ = P", BULLET: "pago único = P · (1 + i)ⁿ",
};
const LIFECYCLE: Estado[] = ["BORRADOR", "EN_REVISION", "APROBADO", "PUBLICADO", "RETIRADO"];
const ESTADO_LABEL: Record<Estado, string> = { BORRADOR: "Borrador", EN_REVISION: "En revisión", APROBADO: "Aprobado", PUBLICADO: "Publicado", RETIRADO: "Retirado" };
const ESTADO_CLS: Record<Estado, string> = { BORRADOR: "draft", EN_REVISION: "rev", APROBADO: "apr", PUBLICADO: "pub", RETIRADO: "ret" };

function Cond({ k, v, eff, neg }: { k: string; v: string; eff?: string; neg?: boolean }) {
  return (<div className="cfgc-cond"><span className="k">{k}</span><span className="v">{v}</span>
    <span className="meta">{eff && <span className="eff">▲ desde {eff}</span>}<span className={`neg ${neg ? "" : "no"}`}>{neg ? "◈ negociable" : "◇ no negociable"}</span></span></div>);
}

export default function ConfigurarCreditos() {
  const [productos, setProductos] = useState<Producto[]>([]);
  const [permisos, setPermisos] = useState<Permisos>({ edita: false, aprueba: false });
  const { soloLectura } = useNivelActual();
  const [usuario, setUsuario] = useState("");
  const [cargando, setCargando] = useState(true);
  const [vista, setVista] = useState<"catalogo" | "builder">("catalogo");
  const [activoId, setActivoId] = useState<string | null>(null);
  const [nuevaVerDe, setNuevaVerDe] = useState<number | null>(null);
  const [filtro, setFiltro] = useState<Estado | "TODOS">("TODOS");
  const [catVista, setCatVista] = useState<"tarjetas" | "lista">(() => {
    try { return (localStorage.getItem("cfgc_vista") as any) || "tarjetas"; } catch { return "tarjetas"; }
  });
  const cambiarVista = (v: "tarjetas" | "lista") => { setCatVista(v); try { localStorage.setItem("cfgc_vista", v); } catch { /* ignore */ } };
  const [monto, setMonto] = useState(1200000);
  const [plazo, setPlazo] = useState(24);
  const [sel, setSel] = useState("TERM_AMOUNT");
  const [visitados, setVisitados] = useState<Set<string>>(new Set(["TERM_AMOUNT"]));
  const [probar, setProbar] = useState(false);
  // simulaciones guardadas (persistencia + trazabilidad)
  const [sims, setSims] = useState<any[]>([]);
  const [simEtiq, setSimEtiq] = useState("");
  // baseline (config al abrir) para el panel flotante de impacto + posición del panel
  const [baseline, setBaseline] = useState<{ cfg: Cfg; comps: Comp[] } | null>(null);
  const [simPos, setSimPos] = useState({ x: 0, y: 0 });
  const verComp = (cod: string) => { setSel(cod); setVisitados((s) => new Set(s).add(cod)); };
  // creación
  const [nuevoOpen, setNuevoOpen] = useState(false);
  const [familias, setFamilias] = useState<any[]>([]);
  const [nuevo, setNuevo] = useState({ nombre: "", familia_id: "", copiar_de: "", heredar: false });
  // inspector
  const [inspOpen, setInspOpen] = useState(false);
  const [inspTab, setInspTab] = useState<"datos" | "modelo">("datos");
  const [raw, setRaw] = useState<any>(null);
  const [modelo, setModelo] = useState<any>(null);
  // comparar versiones
  const [cmpOpen, setCmpOpen] = useState(false);
  const [versiones, setVersiones] = useState<any[]>([]);
  const [cmpA, setCmpA] = useState<number>(0);
  const [cmpB, setCmpB] = useState<number>(0);
  // maestros de referencia (biblioteca de condiciones)
  const [impuestos, setImpuestos] = useState<any[]>([]);
  const [indices, setIndices] = useState<any[]>([]);
  // catálogo de segmentos/canales (configurable en Parámetros — H-185); los const son sólo el fallback.
  const [catSegmentos, setCatSegmentos] = useState<string[]>(SEGMENTOS);
  const [catCanales, setCatCanales] = useState<string[]>(CANALES);

  useEffect(() => {
    api.ppCatalogo().then((d) => {
      setProductos(d.items); if (d.permisos) setPermisos(d.permisos); if (d.usuario) setUsuario(d.usuario);
      // Deep-link desde el Inbox de aprobaciones: abrir directo la línea a revisar.
      const abrirId = sessionStorage.getItem("configurar_abrir_producto");
      if (abrirId) { sessionStorage.removeItem("configurar_abrir_producto"); const p = d.items.find((x: Producto) => x.id === abrirId); if (p) abrir(p); }
    })
      .catch((e) => avisar({ tipo: "error", mensaje: e.message })).finally(() => setCargando(false));
    api.ppFamilias().then((d) => setFamilias(d.items)).catch(() => {});
    api.impuestos("activos").then((d) => setImpuestos(d.items)).catch(() => {});
    api.indices().then((d) => setIndices(d.items)).catch(() => {});
    api.ctoSegmentos().then((d: any) => { if (Array.isArray(d?.segmentos)) setCatSegmentos(d.segmentos); if (Array.isArray(d?.canales)) setCatCanales(d.canales); }).catch(() => {});
  }, []);

  const activo = productos.find((p) => p.id === activoId) || null;
  const upsert = (p: Producto) => setProductos((ps) => (ps.some((x) => x.id === p.id) ? ps.map((x) => (x.id === p.id ? p : x)) : [p, ...ps]));
  // editar una condición núcleo rompe su herencia (pasa a "propio")
  const setCfg = (patch: Partial<Cfg>) => activo && setProductos((ps) => ps.map((p) => (p.id === activoId ? { ...p, cfg: { ...p.cfg, ...patch }, cfgHeredada: false } : p)));
  const setCompCfg = (cod: string, patch: Record<string, any>) => setProductos((ps) => ps.map((p) => p.id === activoId
    ? { ...p, componentes: p.componentes.map((c) => c.codigo === cod ? { ...c, config: { ...c.config, ...patch }, heredado: false } : c) } : p));
  const toggleComp = (cod: string, on: boolean) => setProductos((ps) => ps.map((p) => p.id === activoId
    ? { ...p, componentes: p.componentes.map((c) => c.codigo === cod ? { ...c, activo: on, heredado: false } : c) } : p));
  const payload = (p: Producto) => ({ ...p.cfg, cfgHeredada: !!p.cfgHeredada, componentes: p.componentes.map((c) => ({ codigo: c.codigo, activo: c.activo, config: c.config, heredado: !!c.heredado })) });
  // volver a heredar del padre: guarda y re-resuelve los valores heredados
  async function reheredarCfg() { if (!activo) return; try { upsert(await api.ppGuardarConfig(activo.id, payload({ ...activo, cfgHeredada: true }))); } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); } }
  async function reheredarComp(cod: string) { if (!activo) return; try { upsert(await api.ppGuardarConfig(activo.id, payload({ ...activo, componentes: activo.componentes.map((c) => c.codigo === cod ? { ...c, heredado: true } : c) }))); } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); } }

  function abrir(p: Producto, verDe: number | null = null) { setActivoId(p.id); setNuevaVerDe(verDe); setSel("TERM_AMOUNT"); setVisitados(new Set(["TERM_AMOUNT"])); setProbar(false); setVista("builder"); setSims([]); setSimEtiq(""); setBaseline({ cfg: JSON.parse(JSON.stringify(p.cfg)), comps: JSON.parse(JSON.stringify(p.componentes)) }); setSimPos({ x: 0, y: 0 }); api.ppSimListar(p.id).then((d) => setSims(d.items)).catch(() => {}); }
  async function guardarSim() { if (!activo) return; try { const s = await api.ppSimGuardar(activo.id, { monto, plazo, tna: tnaEfectiva, etiqueta: simEtiq }); setSims((xs) => [s, ...xs]); setSimEtiq(""); } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); } }
  async function borrarSim(id: string) { if (!activo) return; try { await api.ppSimBorrar(activo.id, id); setSims((xs) => xs.filter((s) => s.id !== id)); } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); } }
  function cargarSim(s: any) { setMonto(s.monto); setPlazo(s.plazo); }
  function abrirNuevo() { setNuevo({ nombre: "", familia_id: familias[0]?.id || "", copiar_de: "", heredar: false }); setNuevoOpen(true); }
  async function confirmarCrear() {
    try {
      const base: any = { nombre: nuevo.nombre || undefined, familia_id: nuevo.familia_id || undefined };
      if (nuevo.copiar_de && nuevo.heredar) base.padre_id = nuevo.copiar_de;
      else if (nuevo.copiar_de) base.copiar_de = nuevo.copiar_de;
      const p = await api.ppCrear(base); setNuevoOpen(false); upsert(p); abrir(p);
    } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); }
  }
  async function retirar(p: Producto) { if (!(await confirmar({ titulo: "Retirar línea", danger: true, mensaje: `Retirar "${p.nombre}".\n\nDeja de ofrecerse a clientes nuevos. Los contratos ya originados NO se afectan (conservan su snapshot).\n\n¿Confirmás?` }))) return; try { upsert(await api.ppEstado(p.id, "retirar")); } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); } }
  async function reactivar(p: Producto) { try { upsert(await api.ppEstado(p.id, "reactivar")); } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); } }
  async function borrar(p: Producto) {
    const soloVersion = p.publicadas.length > 0;
    if (!(await confirmar({ titulo: "Borrar línea", danger: true, mensaje: soloVersion ? `Borrar la versión v${p.version} (borrador) de "${p.nombre}". La versión publicada anterior queda intacta.\n\n¿Confirmás?` : `Borrar definitivamente la línea "${p.nombre}" (nunca se publicó).\n\n¿Confirmás?` }))) return;
    try { await api.ppBorrar(p.id); const d = await api.ppCatalogo(); setProductos(d.items); if (activoId === p.id) { setActivoId(null); setVista("catalogo"); } }
    catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); }
  }
  async function guardarBorrador() { if (!activo) return; try { upsert(await api.ppGuardarConfig(activo.id, payload(activo))); avisar("Borrador guardado"); } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); } }
  async function publicar() { if (!activo) return; try { upsert(await api.ppEstado(activo.id, "publicar")); } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); } }
  async function aprobar() { if (!activo) return; try { upsert(await api.ppEstado(activo.id, "aprobar")); } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); } }
  // H-190: DUPLICAR = crear un préstamo NUEVO e independiente (copia de la config), con su propio código y ciclo.
  async function duplicar(p: Producto) {
    const nombre = await pedirTexto({ mensaje: "Nombre del préstamo nuevo (copia independiente):", valor: `${p.nombre} — copia`, requerido: true });
    if (!nombre) return;
    try {
      const np = await api.ppCrear({ copiar_de: p.id, nombre });
      upsert(np); abrir(np);
      avisar({ tipo: "ok", mensaje: `Se creó "${nombre}" como préstamo independiente. Editalo y publicalo.` });
    } catch (e: any) { avisar({ tipo: "error", mensaje: e.message || String(e) }); }
  }
  // PUBLICAR en un paso (revisar→aprobar→publicar si el cuatro-ojos está apagado). Una copia INDEPENDIENTE es
  // un préstamo NUEVO que coexiste con su origen: al publicarla NO se toca el original (H-201). Si querés dejar
  // de ofrecer el original, se retira a mano desde su propio menú ("Retirar línea").
  async function publicarCambios() {
    if (!activo) return;
    try {
      if (activo.estado === "BORRADOR") await api.ppGuardarConfig(activo.id, payload(activo));
      const r = await api.ppPublicarDirecto(activo.id);
      if (r.producto) upsert(r.producto);
      if (r.needs_approval) { avisar({ tipo: "ok", mensaje: "Enviado a revisión: requiere la aprobación de otra persona (cuatro-ojos)." }); return; }
      avisar({ tipo: "ok", mensaje: activo.copiadoDe ? "Préstamo publicado. El original queda intacto (son independientes)." : "Préstamo publicado." });
    } catch (e: any) { avisar({ tipo: "error", mensaje: e.message || String(e) }); }
  }
  async function rechazar() { if (!activo) return; try { upsert(await api.ppEstado(activo.id, "rechazar")); } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); } }

  async function abrirInspector() { setInspOpen(true); if (activo) api.ppRaw(activo.id).then(setRaw).catch(() => {}); if (!modelo) api.ppModelo().then(setModelo).catch(() => {}); }
  async function abrirComparar() {
    if (!activo) return;
    try {
      const d = await api.ppVersiones(activo.id);
      setVersiones(d.items);
      const nums = d.items.map((x: any) => x.version);
      setCmpB(nums[nums.length - 1]); setCmpA(nums.length > 1 ? nums[nums.length - 2] : nums[nums.length - 1]);
      setCmpOpen(true);
    } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); }
  }

  function accionesCard(p: Producto) {
    return [
      { label: "Editar", icon: "edit", onClick: () => abrir(p), hidden: !(permisos.edita && !soloLectura) || p.estado !== "BORRADOR" },
      { label: "Abrir", icon: "eye", onClick: () => abrir(p) },
      { label: "⧉ Duplicar (préstamo nuevo)", icon: "copy", onClick: () => duplicar(p), hidden: !(permisos.edita && !soloLectura) },
      { label: "Crear derivado (hereda)", icon: "git-branch", onClick: () => { setNuevo({ nombre: `${p.nombre} (derivado)`, familia_id: "", copiar_de: p.id, heredar: true }); setNuevoOpen(true); }, hidden: !(permisos.edita && !soloLectura) },
      { label: "Retirar línea", icon: "ban", danger: true, onClick: () => retirar(p), hidden: !permisos.aprueba || p.estado !== "PUBLICADO" },
      { label: "Reactivar línea", icon: "rotate-ccw", onClick: () => reactivar(p), hidden: !permisos.aprueba || p.estado !== "RETIRADO" },
      { label: p.publicadas.length ? "Borrar esta versión" : "Borrar línea", icon: "trash", danger: true, onClick: () => borrar(p), hidden: !(permisos.edita && !soloLectura) || !["BORRADOR", "EN_REVISION"].includes(p.estado) },
    ];
  }

  // ---- derivados del builder ----
  const cfg = activo?.cfg || { sistema: "FRANCES", modalidad: "FIJA", tna: 52, baseDias: "ACT/365", frecuencia: "MENSUAL", montoMin: 100000, montoMax: 5000000, plazoMin: 6, plazoMax: 60, graciaCapital: 0, cargoOtorg: 2, moraTNA: 120 } as Cfg;
  const comps = activo?.componentes || [];
  const indiceVal = indices.find((x) => x.codigo === cfg.indice)?.valor || 0;
  const tnaEfectiva = cfg.modalidad === "VARIABLE" ? indiceVal + (cfg.margen || 0) : cfg.tna;
  const compErrores: Record<string, string[]> = {};
  comps.forEach((c) => { if (c.activo) compErrores[c.codigo] = valida(c.codigo, c.config, cfg); });
  const totalCompErr = Object.values(compErrores).reduce((a, e) => a + e.length, 0);
  const updItem = (cod: string, idx: number, patch: any) => {
    const c = comps.find((x) => x.codigo === cod); if (!c) return;
    setCompCfg(cod, { items: (c.config.items || []).map((x: any, i: number) => (i === idx ? { ...x, ...patch } : x)) });
  };
  // Estado real por componente: pendiente (activo sin revisar), ok (revisado/personalizado), error, add (inactivo).
  const estadoComp = (c: Comp): "add" | "error" | "ok" | "pend" => {
    if (!c.activo) return "add";
    if ((compErrores[c.codigo] || []).length) return "error";
    if (visitados.has(c.codigo) || !esDefault(c.codigo, c.config, cfg)) return "ok";
    return "pend";
  };
  // El cronograma y las métricas vienen del BACKEND (única fuente de verdad): el mismo
  // cálculo que usa la originación. La prueba en vivo consulta /productos/preview (debounced).
  const [rows, setRows] = useState<Fila[]>([]);
  const [res, setRes] = useState({ totalCuotas: 0, totalInteres: 0, totalCargos: 0, primeraCuota: 0, tna: 0, tea: 0, cft: 0 });
  const [baseRows, setBaseRows] = useState<Fila[]>([]);
  useEffect(() => {
    if (!activo) return;
    const t = setTimeout(() => {
      api.ppPreview(previewPayload(cfg, comps, tnaEfectiva, monto, plazo))
        .then((d) => { setRows(toFilas(d.rows)); setRes(d.resumen); }).catch(() => {});
    }, 220);
    return () => clearTimeout(t);
  }, [cfg, comps, monto, plazo, tnaEfectiva, activoId]);
  useEffect(() => {
    if (!baseline) { setBaseRows([]); return; }
    const btna = baseline.cfg.modalidad === "VARIABLE" ? (indices.find((x) => x.codigo === baseline.cfg.indice)?.valor || 0) + (baseline.cfg.margen || 0) : baseline.cfg.tna;
    api.ppPreview(previewPayload(baseline.cfg, baseline.comps, btna, monto, plazo)).then((d) => setBaseRows(toFilas(d.rows))).catch(() => {});
  }, [baseline, monto, plazo]);
  const totInt = res.totalInteres, totCar = res.totalCargos;
  const totCap = rows.reduce((a, r) => a + r.capital, 0);
  const costo = res.totalCuotas || (monto + totInt + totCar);
  const cft = res.cft;
  const lastBal = rows.length ? rows[rows.length - 1].closing : 0;
  const baseCosto = baseRows.reduce((a, r) => a + r.total, 0) || costo;
  const impacto = useMemo(() => {
    if (!baseline) return [] as { campo: string; antes: string; ahora: string }[];
    const out: { campo: string; antes: string; ahora: string }[] = [];
    const fmtV = (v: any) => typeof v === "number" ? String(v) : String(v ?? "");
    for (const [k, l] of CMP_CAMPOS) if (String(baseline.cfg[k] ?? "") !== String((cfg as any)[k] ?? "")) out.push({ campo: l, antes: fmtV(baseline.cfg[k]), ahora: fmtV((cfg as any)[k]) });
    const bC: Record<string, Comp> = Object.fromEntries((baseline.comps as Comp[]).map((c) => [c.codigo, c]));
    for (const c of comps) {
      const b = bC[c.codigo];
      if (!b) continue;
      if (b.activo !== c.activo) out.push({ campo: `${c.nombre} · activo`, antes: b.activo ? "Sí" : "No", ahora: c.activo ? "Sí" : "No" });
      else if (c.activo && JSON.stringify(b.config) !== JSON.stringify(c.config)) out.push({ campo: `${c.nombre} · condiciones`, antes: "—", ahora: "modificado" });
    }
    return out;
  }, [baseline, cfg, comps]);
  const checks = [
    { ok: cfg.montoMin <= cfg.montoMax, t: "monto_minimo ≤ monto_maximo", s: `${money(cfg.montoMin)} ≤ ${money(cfg.montoMax)}` },
    { ok: cfg.plazoMin <= cfg.plazoMax, t: "plazo_minimo ≤ plazo_maximo", s: `${cfg.plazoMin} ≤ ${cfg.plazoMax}` },
    { ok: monto >= cfg.montoMin && monto <= cfg.montoMax, t: "Monto simulado en rango", s: `${money(monto)}` },
    { ok: plazo >= cfg.plazoMin && plazo <= cfg.plazoMax, t: "Plazo simulado en rango", s: `${plazo} cuotas` },
    { ok: Math.abs(totCap - monto) < 1, t: "Σ capital = monto", s: `${money(totCap)} vs ${money(monto)}` },
    { ok: Math.abs(lastBal) < 1, t: "Saldo final = 0", s: `${money2(lastBal)}` },
    { ok: comps.filter((c) => c.requerido).every((c) => c.activo), t: "Componentes requeridos activos", s: "TERM_AMOUNT · INTEREST · REPAYMENT_SCHEDULE" },
  ];
  const errs = checks.filter((c) => !c.ok).length + totalCompErr;

  const comp = comps.find((c) => c.codigo === sel);
  const activeComps = comps.filter((c) => c.activo).sort((a, b) => a.orden - b.orden);
  const guiaIdx = comp ? activeComps.findIndex((c) => c.codigo === sel) : -1;
  const siguiente = guiaIdx >= 0 && guiaIdx < activeComps.length - 1 ? activeComps[guiaIdx + 1].codigo : null;
  const editable = activo && activo.estado === "BORRADOR" && (permisos.edita && !soloLectura);
  // La DISPONIBILIDAD (canales/segmentos) es metadata de distribución, no términos financieros: se puede
  // editar aunque la versión esté publicada (H-189), sin crear versión nueva.
  const editableDisp = !!activo && permisos.edita && !soloLectura;
  async function guardarDisponibilidad() {
    if (!activo || !comp) return;
    try {
      upsert(await api.editarDisponibilidad(activo.id, { activo: true, ...comp.config }));
      avisar({ tipo: "ok", mensaje: "Disponibilidad guardada (canales/segmentos)." });
    } catch (e: any) { avisar({ tipo: "error", mensaje: e.message || String(e) }); }
  }

  // ============ CATÁLOGO ============
  if (vista === "catalogo" || !activo) {
    const lista = productos.filter((p) => filtro === "TODOS" || p.estado === filtro);
    const colsCat: Col[] = [
      { key: "nombre", label: "Línea", sortable: true, render: (p: any) => (
          <div><b>{p.nombre}</b><div className="code" style={{ fontSize: 11, color: "var(--ink-faint)", fontFamily: "var(--mono, monospace)" }}>{p.codigo}</div></div>) },
      { key: "estado", label: "Estado", sortable: true, render: (p: any) => (
          <span className="cfgc-liststate">
            <span className={`pill ${ESTADO_CLS[p.estado as Estado]}`}>{ESTADO_LABEL[p.estado as Estado].toUpperCase()}</span>
            {p.vigentePortal == null && p.estado !== "RETIRADO" && <span className="pill" title="No se ofrece en el portal">no ofrecido</span>}
          </span>) },
      { key: "sistema", label: "Sistema", sortable: true, render: (p: any) => p.cfg.sistema },
      { key: "tna", label: "TNA", align: "right", sortable: true, sortValue: (p: any) => p.cfg.tna, render: (p: any) => <span className="num">{p.cfg.tna}%</span> },
      { key: "monto", label: "Monto", align: "right", render: (p: any) => <span className="num">{money(p.cfg.montoMin)}–{money(p.cfg.montoMax)}</span> },
      { key: "plazo", label: "Plazo", align: "right", render: (p: any) => <span className="num">{p.cfg.plazoMin}–{p.cfg.plazoMax}</span> },
    ];
    return (
      <div className="cfgc">
        <div className="cfgc-cathead">
          <div><h1>Configurar Créditos — Catálogo de líneas</h1>
            <p>Diseñá, versioná y publicá líneas de crédito para ofrecer a los clientes. Línea <b>LENDING</b>.</p></div>
          <span className="sp" />
          {(permisos.edita && !soloLectura) && <button className="btn primary" onClick={abrirNuevo}>＋ Nueva línea</button>}
        </div>
        <div className="cfgc-catfilters">
          <span style={{ fontSize: 12.5, color: "var(--ink-soft)", fontWeight: 600 }}>Estado</span>
          <select value={filtro} onChange={(e) => setFiltro(e.target.value as any)}>
            <option value="TODOS">Todos</option><option value="BORRADOR">Borrador</option><option value="EN_REVISION">En revisión</option>
            <option value="APROBADO">Aprobado</option><option value="PUBLICADO">Publicado</option><option value="RETIRADO">Retirado</option>
          </select>
          <span style={{ marginLeft: "auto", fontSize: 12, color: "var(--ink-faint)" }}>{lista.length} de {productos.length} líneas</span>
          <div className="cfgc-vistas" role="group" aria-label="Vista">
            <button className={catVista === "tarjetas" ? "on" : ""} title="Vista en tarjetas" onClick={() => cambiarVista("tarjetas")}>▦ Tarjetas</button>
            <button className={catVista === "lista" ? "on" : ""} title="Vista en línea (lista)" onClick={() => cambiarVista("lista")}>≣ En línea</button>
          </div>
        </div>
        {cargando && <p className="muted">Cargando catálogo…</p>}
        {!cargando && !productos.length && <p className="muted">Sin líneas. Creá la primera con “＋ Nueva línea”.</p>}
        {catVista === "lista" && productos.length > 0 && (
          <div className="card" style={{ padding: "4px 14px 14px" }}>
            <DataTable columns={colsCat} rows={lista} rowKey={(p: any) => p.id} actions={accionesCard}
              clientSort pageSize={50} defaultSort="nombre" emptyText="Sin líneas en este filtro"
              rowStyle={(p: any) => p.estado === "RETIRADO" ? { opacity: .6 } : undefined} />
          </div>
        )}
        {catVista === "tarjetas" && (
        <div className="cfgc-cat">
          {lista.map((p) => (
            <div className={`cfgc-pcard ${p.estado === "RETIRADO" ? "ret" : ""}`} key={p.id}>
              <div className="top">
                <div style={{ flex: 1, minWidth: 0 }}><h3>{p.nombre}</h3><div className="code">{p.codigo} · v{p.version}</div></div>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
                  <span className={`pill ${ESTADO_CLS[p.estado]}`}>{ESTADO_LABEL[p.estado].toUpperCase()}</span>
                  {p.vigentePortal == null && p.estado !== "RETIRADO" && (
                    <span className="pill" title="Ninguna versión publicada y vigente: este producto NO se ofrece en el portal del ciudadano.">no ofrecido</span>
                  )}
                </div>
                <RowMenu actions={accionesCard(p)} />
              </div>
              <div className="crumbs">Grupo <b>{p.grupo}</b> · Familia <b>{p.familia}</b> · {p.componentes.filter((c) => c.activo).length} componentes</div>
              {p.padre && <div className="crumbs" style={{ color: "var(--brand-2)" }}>🧬 Deriva de <b>{p.padre.nombre}</b></div>}
              <div className="facts">
                <div><b>{p.cfg.sistema}</b>sistema</div><div><b>{p.cfg.tna}%</b>TNA</div>
                <div><b>{money(p.cfg.montoMin)}–{money(p.cfg.montoMax)}</b>monto</div><div><b>{p.cfg.plazoMin}–{p.cfg.plazoMax}</b>plazo</div>
              </div>
              <div className="foot"><span className="sp" />
                <button className="btn sm" onClick={() => abrir(p)}>Abrir</button>
                {p.estado === "BORRADOR" && (permisos.edita && !soloLectura) && <button className="btn sm primary" onClick={() => abrir(p)}>Continuar edición</button>}
                {p.estado === "PUBLICADO" && (permisos.edita && !soloLectura) && <button className="btn sm primary" title="Crear un préstamo nuevo e independiente, copia de éste" onClick={() => duplicar(p)}>⧉ Duplicar</button>}
                {p.estado === "RETIRADO" && permisos.aprueba && <button className="btn sm" onClick={() => reactivar(p)}>Reactivar</button>}
              </div>
            </div>
          ))}
        </div>
        )}

        {nuevoOpen && (
          <div className="cfgc-scrim" onClick={() => setNuevoOpen(false)}>
            <div className="cfgc-modal" onClick={(e) => e.stopPropagation()}>
              <h3>Nueva línea de crédito</h3>
              <p className="sub">Poné un nombre, elegí la familia y opcionalmente copiá la configuración de una línea existente.</p>
              <label className="f" style={{ display: "block", marginBottom: 12 }}><span className="lbl">Nombre</span>
                <input value={nuevo.nombre} onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })} placeholder="Ej.: Préstamo Personal 2026" /></label>
              <label className="f" style={{ display: "block", marginBottom: 12 }}><span className="lbl">Familia</span>
                <select value={nuevo.familia_id} onChange={(e) => setNuevo({ ...nuevo, familia_id: e.target.value })}>
                  {familias.map((f) => <option key={f.id} value={f.id}>{f.grupo} · {f.nombre}</option>)}</select></label>
              <label className="f" style={{ display: "block", marginBottom: 12 }}><span className="lbl">Basar en</span>
                <select value={nuevo.copiar_de} onChange={(e) => setNuevo({ ...nuevo, copiar_de: e.target.value, heredar: e.target.value ? nuevo.heredar : false })}>
                  <option value="">— En blanco (valores por defecto) —</option>
                  {productos.map((p) => <option key={p.id} value={p.id}>{p.nombre} (v{p.version})</option>)}</select></label>
              {nuevo.copiar_de && (
                <div className="cfgc-radio" style={{ marginBottom: 16 }}>
                  <label className="cfgc-opt"><input type="radio" checked={!nuevo.heredar} onChange={() => setNuevo({ ...nuevo, heredar: false })} />
                    <span><b>Copia independiente</b><small>Se copian los valores una vez. Después evoluciona sola; los cambios del original no la afectan.</small></span></label>
                  <label className="cfgc-opt"><input type="radio" checked={nuevo.heredar} onChange={() => setNuevo({ ...nuevo, heredar: true })} />
                    <span><b>Derivar (hereda del padre)</b><small>Solo guarda lo que cambies. Lo no tocado se hereda del padre y se actualiza cuando el padre cambia.</small></span></label>
                </div>
              )}
              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                <button className="btn ghost" onClick={() => setNuevoOpen(false)}>Cancelar</button>
                <button className="btn primary" onClick={confirmarCrear}>Crear y diseñar</button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ============ BUILDER ============
  const nowIdx = LIFECYCLE.indexOf(activo.estado);
  return (
    <div className="cfgc">
      <button className="cfgc-back" onClick={() => setVista("catalogo")}>← Volver al catálogo de líneas</button>
      <section className="cfgc-hero">
        <div className="top">
          <div>
            <h1>{activo.nombre}</h1>
            <div className="sub">
              <span className="cfgc-crumbs">{activo.codigo} · Grupo <b>{activo.grupo}</b> › Familia <b>{activo.familia}</b></span>
              <span style={{ fontSize: 12.5, color: "var(--ink-soft)" }}>Versión <b>v{activo.version}</b></span>
              <span className={`pill ${ESTADO_CLS[activo.estado]}`}>● {ESTADO_LABEL[activo.estado].toUpperCase()}</span>
              {(activo.enviadoPor || activo.aprobadoPor || activo.publicadoPor) && (
                <span style={{ fontSize: 11.5, color: "var(--ink-faint)" }}>
                  {activo.enviadoPor && `Enviada por ${activo.enviadoPor}`}{activo.aprobadoPor && ` · Aprobada por ${activo.aprobadoPor}`}{activo.publicadoPor && ` · Publicada por ${activo.publicadoPor}`}</span>
              )}
            </div>
          </div>
          <div className="actions">
            <button className="btn ghost" onClick={() => setProbar((v) => !v)}>{probar ? "Ocultar prueba" : "▶ Probar en vivo"}</button>
            <button className="btn ghost" onClick={abrirComparar}>⇄ Comparar</button>
            <button className="btn ghost" onClick={abrirInspector}>🔍 Datos</button>
            {activo.estado === "BORRADOR" && <>
              <button className="btn" disabled={!(permisos.edita && !soloLectura)} onClick={guardarBorrador}>Guardar y seguir después</button>
              <button className="btn" disabled={!(permisos.edita && !soloLectura)} onClick={() => borrar(activo)}>Descartar</button>
              <button className="btn primary" disabled={!(permisos.edita && !soloLectura) || errs > 0}
                title={errs ? "Resolvé las validaciones antes de publicar" : "Publicar el préstamo (queda vigente)"} onClick={publicarCambios}>Publicar</button>
            </>}
            {activo.estado === "EN_REVISION" && <>
              <button className="btn" disabled={!permisos.aprueba} onClick={rechazar}>Rechazar</button>
              <button className="btn primary" disabled={!permisos.aprueba || activo.enviadoPor === usuario}
                title={activo.enviadoPor === usuario ? "Separación de funciones: no podés aprobar lo que vos enviaste" : "Aprobar"} onClick={aprobar}>Aprobar</button>
            </>}
            {activo.estado === "APROBADO" && (
              <button className="btn primary" disabled={!permisos.aprueba || errs > 0}
                title={errs ? "Resolvé las validaciones" : "Publicar"} onClick={publicar}>Publicar</button>
            )}
            {activo.estado === "PUBLICADO" && (permisos.edita && !soloLectura) && (
              <button className="btn primary" title="Crear un préstamo nuevo e independiente, copia de éste" onClick={() => duplicar(activo)}>⧉ Duplicar</button>
            )}
          </div>
        </div>
        <div className="cfgc-lifecycle">
          {LIFECYCLE.map((s, i) => (<span key={s} style={{ display: "contents" }}>
            <span className={`cfgc-lc ${i < nowIdx ? "done" : i === nowIdx ? "now" : ""}`}><span className="n">{i < nowIdx ? "✓" : i + 1}</span>{ESTADO_LABEL[s]}</span>
            {i < LIFECYCLE.length - 1 && <span className="cfgc-lc-sep" />}</span>))}
        </div>
        {/* Tasas calculadas siempre visibles: se recalculan con cada cambio de la config */}
        <div className="cfgc-rates">
          <div className="r"><small>TNA</small><b className="num">{tnaEfectiva.toFixed(2)}%</b><span className="h">nominal anual {cfg.modalidad === "VARIABLE" ? `(${cfg.indice}+${cfg.margen})` : ""}</span></div>
          <div className="r"><small>TEA</small><b className="num">{(res.tea || 0).toFixed(2)}%</b><span className="h">efectiva anual</span></div>
          <div className="r hl"><small>CFT</small><b className="num">{(res.cft || 0).toFixed(2)}%</b><span className="h">costo financiero total (TIR)</span></div>
          <div className="r"><small>Cuota</small><b className="num">{money(rows[0]?.total || 0)}</b><span className="h">{money(monto)} · {plazo} cuotas</span></div>
          <span className="live-tag">● en vivo</span>
        </div>
        {/* Vigencia de ESTA versión (v1 vigente → al publicar v2 con su fecha, v1 se cierra) */}
        <div className="cfgc-vig">
          <span className="lb">📅 Vigencia de la versión v{activo.version}:</span>
          {editable ? (<>
            <label>Desde <input type="date" value={cfg.vigenciaDesde || ""} onChange={(e) => setCfg({ vigenciaDesde: e.target.value })} /></label>
            <label>Hasta <input type="date" value={cfg.vigenciaHasta || ""} onChange={(e) => setCfg({ vigenciaHasta: e.target.value })} /></label>
            <span className="muted" style={{ fontSize: 11 }}>si no fijás "Desde", entra en vigencia al publicar</span>
          </>) : (
            <b>{cfg.vigenciaDesde || "—"} → {cfg.vigenciaHasta || "sin límite"}</b>
          )}
        </div>
        {nuevaVerDe != null && <div className="cfgc-newver">🌱 <span>Versión nueva (v{activo.version}) derivada de la <b>v{nuevaVerDe}</b> publicada. La v{nuevaVerDe} sigue vigente hasta que publiques esta.</span></div>}
        {activo.padre && <div className="cfgc-newver hered">🧬 <span>Deriva de <b>{activo.padre.nombre}</b> ({activo.padre.codigo}). Lo que no personalices se <b>hereda del padre</b> y se actualiza cuando el padre cambia. Condiciones generales (sistema, tasa, plazo): <b>{activo.cfgHeredada ? "heredadas" : "propias"}</b>.</span>{activo.padre && !activo.cfgHeredada && editable && <button className="btn sm ghost" style={{ marginLeft: "auto" }} title="Descartar condiciones generales propias y volver a heredar del padre" onClick={reheredarCfg}>↩ Volver a heredar generales</button>}</div>}
      </section>

      <div className="cfgc-grid" style={{ gridTemplateColumns: "260px 1fr" }}>
        {/* Paleta con activos/agregables */}
        <div className="card">
          <div className="h"><h3>Componentes</h3><span className="tag">PROPERTY CLASSES</span></div>
          <div className="cfgc-palette">
            {[...comps].sort((a, b) => a.orden - b.orden).map((c) => {
              const st = estadoComp(c);
              const m = { ok: { cls: "ok", ch: "✓", t: "Revisado" }, pend: { cls: "pend", ch: "○", t: "Activo — falta revisar" }, error: { cls: "err", ch: "!", t: (compErrores[c.codigo] || []).join(" · ") }, add: { cls: "off", ch: "＋", t: "No agregado" } }[st];
              return (
                <button key={c.codigo} className={`cfgc-comp ${c.codigo === sel ? "on" : ""} ${!c.activo ? "off" : ""}`} onClick={() => verComp(c.codigo)}>
                  <span className="ic">{ICONS[c.codigo] || "▫"}</span>
                  <span className="nm"><b>{c.nombre}</b><small>{c.requerido ? "Requerido" : c.categoria}{c.multiple ? " · multi" : ""}</small></span>
                  {activo.padre && c.heredado && <span title="Heredado del padre" style={{ fontSize: 12, lineHeight: 1 }}>🧬</span>}
                  {c.activo && !esDefault(c.codigo, c.config, cfg) && st !== "error" && <span title={activo.padre ? "Propio (personalizado)" : "Personalizado"} style={{ color: "var(--brand-2)", fontSize: 16, lineHeight: 1 }}>•</span>}
                  <span className={`st ${m.cls}`} title={m.t}>{m.ch}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Editor del componente */}
        <div className="card">
          <div className="cfgc-editor">
            <div className="cfgc-ehead">
              <div><span className="eyebrow">COMPONENTE · {comp?.categoria.toUpperCase()}</span><h2>{comp?.nombre}</h2>
                <p>Condiciones tipadas del componente. La extensibilidad vive acá, no en columnas sueltas.</p></div>
              <div style={{ marginLeft: "auto", display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
                <span className="cfgc-badge">{comp?.codigo}</span>
                {activo.padre && comp && (comp.heredado
                  ? <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: ".04em", padding: "2px 8px", borderRadius: 999, background: "var(--surface-2)", color: "var(--ink-faint)" }}>🧬 HEREDADO</span>
                  : <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: ".04em", padding: "2px 8px", borderRadius: 999, background: "var(--accent-soft)", color: "var(--brand-2)" }}>PROPIO</span>)}
                {!activo.padre && comp?.activo && (esDefault(comp.codigo, comp.config, cfg)
                  ? <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: ".04em", padding: "2px 8px", borderRadius: 999, background: "var(--surface-2)", color: "var(--ink-faint)" }}>POR DEFECTO</span>
                  : <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: ".04em", padding: "2px 8px", borderRadius: 999, background: "var(--accent-soft)", color: "var(--brand-2)" }}>PERSONALIZADO</span>)}
                {activo.padre && comp && !comp.heredado && editable && <button className="btn sm ghost" title="Descartar cambios propios y volver a heredar del padre" onClick={() => reheredarComp(comp.codigo)}>↩ Volver a heredar</button>}
              </div>
            </div>

            {comp && !comp.activo ? (
              <div style={{ textAlign: "center", padding: "40px 10px" }}>
                <div style={{ fontSize: 34, marginBottom: 8 }}>{ICONS[comp.codigo]}</div>
                <p className="muted" style={{ marginBottom: 14 }}>Este componente no está agregado a la línea.</p>
                <button className="btn primary" disabled={comp.codigo === "AVAILABILITY" ? !editableDisp : !editable} onClick={() => toggleComp(comp.codigo, true)}>＋ Agregar “{comp.nombre}”</button>
              </div>
            ) : comp && (<>
              {compErrores[comp.codigo]?.length > 0 && (
                <div style={{ background: "var(--crit-soft)", border: "1px solid var(--crit)", borderRadius: 9, padding: "9px 12px", marginBottom: 14, fontSize: 12, color: "var(--crit)" }}>
                  <b>⚠ {compErrores[comp.codigo].length} problema(s) en este componente:</b>
                  <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{compErrores[comp.codigo].map((m, i) => <li key={i}>{m}</li>)}</ul>
                </div>
              )}
              {/* Editores core */}
              {comp.codigo === "INTEREST" && (<>
                <div className="cfgc-fgrid">
                  <label className="f"><span className="lbl">Sistema de cálculo</span>
                    <select disabled={!editable} value={cfg.sistema} onChange={(e) => setCfg({ sistema: e.target.value as Sistema })}>
                      <option value="FRANCES">Francés · cuota constante</option><option value="ALEMAN">Alemán · capital constante</option>
                      <option value="AMERICANO">Americano · sólo interés periódico, capital al final</option><option value="BULLET">A vencimiento · capital + interés capitalizado (pago único)</option></select></label>
                  <label className="f"><span className="lbl">Modalidad de tasa</span>
                    <select disabled={!editable} value={cfg.modalidad} onChange={(e) => setCfg({ modalidad: e.target.value })}><option value="FIJA">Tasa fija</option><option value="VARIABLE">Variable (índice + margen)</option></select></label>
                  {cfg.modalidad === "FIJA"
                    ? <label className="f"><span className="lbl">Tasa nominal anual (%)</span><input disabled={!editable} className="num" type="number" value={cfg.tna} onChange={(e) => setCfg({ tna: Number(e.target.value) || 0 })} /></label>
                    : <>
                        <label className="f"><span className="lbl">Índice de referencia <span className="imp">▲ maestro</span></span>
                          <select disabled={!editable} value={cfg.indice || ""} onChange={(e) => setCfg({ indice: e.target.value })}>
                            <option value="">— elegí un índice —</option>{indices.map((x) => <option key={x.codigo} value={x.codigo}>{x.codigo} · {x.nombre} ({x.valor}%)</option>)}</select></label>
                        <label className="f"><span className="lbl">Margen (%)</span><input disabled={!editable} className="num" type="number" value={cfg.margen || 0} onChange={(e) => setCfg({ margen: Number(e.target.value) || 0 })} /></label>
                      </>}
                  <label className="f"><span className="lbl">Base de días</span><select disabled={!editable} value={cfg.baseDias} onChange={(e) => setCfg({ baseDias: e.target.value })}><option>ACT/365</option><option>30/360</option><option>ACT/360</option></select></label>
                </div>
                {cfg.modalidad === "FIJA" && (
                  <div className="cfgc-fgrid" style={{ marginTop: 12 }}>
                    <label className="f"><span className="lbl">¿Tasa negociable? <span className="imp">▲ Fase B</span></span>
                      <select disabled={!editable} value={String(!!cfg.tnaNegociable)} onChange={(e) => setCfg({ tnaNegociable: e.target.value === "true" })}><option value="false">No — tasa fija</option><option value="true">Sí — banda negociable</option></select></label>
                    {cfg.tnaNegociable && <>
                      <label className="f"><span className="lbl">TNA mínima (%)</span><input disabled={!editable} className="num" type="number" value={cfg.tnaMin || 0} onChange={(e) => setCfg({ tnaMin: Number(e.target.value) || 0 })} /></label>
                      <label className="f"><span className="lbl">TNA máxima (%)</span><input disabled={!editable} className="num" type="number" value={cfg.tnaMax || 0} onChange={(e) => setCfg({ tnaMax: Number(e.target.value) || 0 })} /></label>
                    </>}
                  </div>
                )}
                <div className="cfgc-formula"><span className="lab">MOTOR CERTIFICADO</span><code>{FORMULA[cfg.sistema]}</code><small>Calculador <b>{cfg.sistema}</b> · versión 2 · redondeo HALF_UP</small></div>
                <div className="cfgc-condlist">
                  {cfg.modalidad === "VARIABLE"
                    ? <Cond k="Tasa efectiva (índice + margen)" v={`${indiceVal.toFixed(2)}% + ${(cfg.margen || 0).toFixed(2)}% = ${tnaEfectiva.toFixed(2)}%`} />
                    : <Cond k="TNA vigente" v={`${cfg.tna.toFixed(2)} %`} eff="01/09/2026" neg={!!cfg.tnaNegociable} />}
                  {cfg.modalidad === "FIJA" && (cfg.tnaNegociable
                    ? <Cond k="Negociación al originar" v={`entre ${(cfg.tnaMin || 0).toFixed(2)}% y ${(cfg.tnaMax || 0).toFixed(2)}%`} neg />
                    : <Cond k="Negociación al originar" v="Tasa fija (no negociable)" />)}
                  <Cond k="Base de días" v={cfg.baseDias} />
                </div>
              </>)}
              {comp.codigo === "TERM_AMOUNT" && (
                <div className="cfgc-fgrid">
                  <label className="f"><span className="lbl">Monto mínimo</span><input disabled={!editable} className="num" type="number" value={cfg.montoMin} onChange={(e) => setCfg({ montoMin: Number(e.target.value) || 0 })} /></label>
                  <label className="f"><span className="lbl">Monto máximo</span><input disabled={!editable} className="num" type="number" value={cfg.montoMax} onChange={(e) => setCfg({ montoMax: Number(e.target.value) || 0 })} /></label>
                  <label className="f"><span className="lbl">Plazo mínimo</span><input disabled={!editable} className="num" type="number" value={cfg.plazoMin} onChange={(e) => setCfg({ plazoMin: Number(e.target.value) || 0 })} /></label>
                  <label className="f"><span className="lbl">Plazo máximo</span><input disabled={!editable} className="num" type="number" value={cfg.plazoMax} onChange={(e) => setCfg({ plazoMax: Number(e.target.value) || 0 })} /></label>
                  <label className="f"><span className="lbl">Frecuencia de pago</span><select disabled={!editable} value={cfg.frecuencia} onChange={(e) => setCfg({ frecuencia: e.target.value })}><option>MENSUAL</option><option>TRIMESTRAL</option></select></label>
                  <label className="f"><span className="lbl">Gracia de capital (cuotas)</span><input disabled={!editable} className="num" type="number" value={cfg.graciaCapital} onChange={(e) => setCfg({ graciaCapital: Number(e.target.value) || 0 })} /></label>
                </div>
              )}
              {comp.codigo === "CHARGE" && <div className="cfgc-fgrid"><label className="f"><span className="lbl">Cargo de otorgamiento (%)</span><input disabled={!editable} className="num" type="number" value={cfg.cargoOtorg} onChange={(e) => setCfg({ cargoOtorg: Number(e.target.value) || 0 })} /></label></div>}
              {comp.codigo === "OVERDUE" && <div className="cfgc-fgrid"><label className="f"><span className="lbl">TNA punitoria (%)</span><input disabled={!editable} className="num" type="number" value={cfg.moraTNA} onChange={(e) => setCfg({ moraTNA: Number(e.target.value) || 0 })} /></label></div>}

              {/* Disponibilidad / segmentación (Fase E) — a quién y por qué canal se ofrece */}
              {comp.codigo === "AVAILABILITY" && (() => {
                const arr = (k: string): string[] => Array.isArray(comp.config[k]) ? comp.config[k] : String(comp.config[k] || "").split(",").map((s: string) => s.trim()).filter(Boolean);
                const toggle = (k: string, val: string) => { const cur = arr(k); setCompCfg(comp.codigo, { [k]: cur.includes(val) ? cur.filter((x) => x !== val) : [...cur, val] }); };
                return (<div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <div>
                    <span className="lbl" style={{ display: "block", marginBottom: 6 }}>Segmentos habilitados <small className="muted">(vacío = todos)</small></span>
                    <div className="cfgc-chips">{catSegmentos.map((s) => <button key={s} type="button" disabled={!editableDisp} className={`cfgc-chip ${arr("segmentos").includes(s) ? "on" : ""}`} onClick={() => toggle("segmentos", s)}>{s.replace(/_/g, " ")}</button>)}</div>
                  </div>
                  <div>
                    <span className="lbl" style={{ display: "block", marginBottom: 6 }}>Canales habilitados <small className="muted">(vacío = todos los canales; en el portal público sólo se ofrece si la Disponibilidad está activa)</small></span>
                    <div className="cfgc-chips">{catCanales.map((s) => <button key={s} type="button" disabled={!editableDisp} className={`cfgc-chip ${arr("canales").includes(s) ? "on" : ""}`} onClick={() => toggle("canales", s)}>{s}</button>)}</div>
                  </div>
                  <div className="cfgc-fgrid">
                    <label className="f"><span className="lbl">Edad mínima</span><input disabled={!editableDisp} className="num" type="number" value={comp.config.edadMin ?? ""} onChange={(e) => setCompCfg(comp.codigo, { edadMin: Number(e.target.value) || 0 })} /></label>
                    <label className="f"><span className="lbl">Edad máxima</span><input disabled={!editableDisp} className="num" type="number" value={comp.config.edadMax ?? ""} onChange={(e) => setCompCfg(comp.codigo, { edadMax: Number(e.target.value) || 0 })} /></label>
                    <label className="f"><span className="lbl">Antigüedad mín. (meses)</span><input disabled={!editableDisp} className="num" type="number" value={comp.config.antiguedadMinMeses ?? ""} onChange={(e) => setCompCfg(comp.codigo, { antiguedadMinMeses: Number(e.target.value) || 0 })} /></label>
                    <label className="f"><span className="lbl">Requiere garante</span><select disabled={!editableDisp} value={String(!!comp.config.requiereGarante)} onChange={(e) => setCompCfg(comp.codigo, { requiereGarante: e.target.value === "true" })}><option value="true">Sí</option><option value="false">No</option></select></label>
                    <label className="f"><span className="lbl">Vigente desde</span><input disabled={!editableDisp} type="date" value={comp.config.vigenteDesde || ""} onChange={(e) => setCompCfg(comp.codigo, { vigenteDesde: e.target.value })} /></label>
                    <label className="f"><span className="lbl">Vigente hasta</span><input disabled={!editableDisp} type="date" value={comp.config.vigenteHasta || ""} onChange={(e) => setCompCfg(comp.codigo, { vigenteHasta: e.target.value })} /></label>
                  </div>
                  {!editable && editableDisp && (
                    <div className="cfgc-disp-save">
                      <span className="muted">La disponibilidad (canales/segmentos) se puede modificar aunque la línea esté publicada — no crea versión nueva.</span>
                      <button className="btn primary sm" onClick={guardarDisponibilidad}>💾 Guardar disponibilidad</button>
                    </div>
                  )}
                </div>);
              })()}

              {/* Editor genérico por esquema del componente */}
              {SCHEMA[comp.codigo] && (
                <div className="cfgc-fgrid" style={{ marginTop: comp.codigo === "CHARGE" || comp.codigo === "OVERDUE" ? 12 : 0 }}>
                  {SCHEMA[comp.codigo].map((f) => (
                    <label className="f" key={f.k}><span className="lbl">{f.l}</span>
                      {f.t === "bool" ? (
                        <select disabled={!editable} value={String(!!comp.config[f.k])} onChange={(e) => setCompCfg(comp.codigo, { [f.k]: e.target.value === "true" })}><option value="true">Sí</option><option value="false">No</option></select>
                      ) : f.t === "select" ? (
                        <select disabled={!editable} value={comp.config[f.k] ?? ""} onChange={(e) => setCompCfg(comp.codigo, { [f.k]: e.target.value })}>{f.o!.map((o) => <option key={o} value={o}>{o}</option>)}</select>
                      ) : (
                        <input disabled={!editable} className={f.t === "num" ? "num" : undefined} type={f.t === "num" ? "number" : f.t === "date" ? "date" : "text"}
                          value={comp.config[f.k] ?? ""} onChange={(e) => setCompCfg(comp.codigo, { [f.k]: f.t === "num" ? (Number(e.target.value) || 0) : e.target.value })} />
                      )}
                    </label>
                  ))}
                </div>
              )}
              {/* Múltiples instancias: varios cargos / impuestos */}
              {ITEM_SCHEMA[comp.codigo] && (
                <div style={{ marginTop: 14 }}>
                  <div style={{ display: "flex", alignItems: "center", marginBottom: 8 }}>
                    <b style={{ fontSize: 13 }}>{ITEM_TITULO[comp.codigo]} ({(comp.config.items || []).length})</b>
                    <span style={{ flex: 1 }} />
                    {editable && <button className="btn sm primary" onClick={() => setCompCfg(comp.codigo, { items: [...(comp.config.items || []), { ...ITEM_NUEVO[comp.codigo] }] })}>＋ Agregar {ITEM_SINGULAR[comp.codigo]}</button>}
                  </div>
                  {(comp.config.items || []).map((it: any, idx: number) => (
                    <div key={idx} style={{ display: "grid", gridTemplateColumns: `${ITEM_SCHEMA[comp.codigo].map(() => "1fr").join(" ")} auto`, gap: 8, alignItems: "end", marginBottom: 8, padding: 8, background: "var(--surface-2)", borderRadius: 9 }}>
                      {ITEM_SCHEMA[comp.codigo].map((f) => (
                        <label className="f" key={f.k}><span className="lbl">{f.l}</span>
                          {f.t === "impuesto"
                            ? <select disabled={!editable} value={it.codigo ?? ""} onChange={(e) => { const imp = impuestos.find((x) => x.codigo === e.target.value); updItem(comp.codigo, idx, imp ? { codigo: imp.codigo, etiqueta: imp.nombre, base: imp.base, porcentaje: imp.alicuota } : { codigo: "" }); }}>
                                <option value="">— manual —</option>{impuestos.map((x) => <option key={x.codigo} value={x.codigo}>{x.codigo} · {x.nombre}</option>)}</select>
                            : f.t === "select"
                              ? <select disabled={!editable} value={it[f.k] ?? ""} onChange={(e) => updItem(comp.codigo, idx, { [f.k]: e.target.value })}>{f.o!.map((o) => <option key={o} value={o}>{o}</option>)}</select>
                              : <input disabled={!editable} className={f.t === "num" ? "num" : undefined} type={f.t === "num" ? "number" : "text"} value={it[f.k] ?? ""} onChange={(e) => updItem(comp.codigo, idx, { [f.k]: f.t === "num" ? (Number(e.target.value) || 0) : e.target.value })} />}
                        </label>
                      ))}
                      {editable && <button className="btn sm" style={{ color: "var(--crit)", borderColor: "var(--crit)" }} title="Quitar" onClick={() => setCompCfg(comp.codigo, { items: (comp.config.items || []).filter((_: any, i: number) => i !== idx) })}>✕</button>}
                    </div>
                  ))}
                  {!(comp.config.items || []).length && <p className="muted" style={{ fontSize: 12 }}>Sin ítems. Agregá una {ITEM_SINGULAR[comp.codigo]}.</p>}
                </div>
              )}
              {!SCHEMA[comp.codigo] && !ITEM_SCHEMA[comp.codigo] && !["INTEREST", "TERM_AMOUNT", "AVAILABILITY"].includes(comp.codigo) &&
                <div className="cfgc-condlist"><Cond k="Estado" v="ACTIVO" /><Cond k="Categoría" v={comp.categoria} /></div>}

              {/* Guía + quitar */}
              <div style={{ marginTop: 18, display: "flex", alignItems: "center", gap: 10, borderTop: "1px solid var(--border)", paddingTop: 14 }}>
                {!comp.requerido && editable && <button className="btn" onClick={() => toggleComp(comp.codigo, false)}>Quitar componente</button>}
                <div className="cfgc-guide">
                  {guiaIdx >= 0 && (() => { const rev = activeComps.filter((c) => estadoComp(c) === "ok").length; return <>Revisados {rev} de {activeComps.length}<div className="bar"><i style={{ width: `${(rev / activeComps.length) * 100}%` }} /></div></>; })()}
                </div>
                {siguiente && <button className="btn primary" onClick={() => verComp(siguiente)}>Siguiente componente →</button>}
              </div>
            </>)}
          </div>
        </div>

      </div>

      {/* Panel FLOTANTE de prueba en vivo: datos básicos + impacto de los cambios */}
      {probar && (() => {
        const dInt = (totInt + totCar) - baseRows.reduce((a, r) => a + r.interes + r.cargos, 0);
        const dCuota = (rows[0]?.total || 0) - (baseRows[0]?.total || 0);
        const dCosto = costo - baseCosto;
        const Delta = ({ v, pct }: { v: number; pct?: boolean }) => Math.abs(v) < 0.005 ? <span className="cfgc-delta zero">sin cambio</span>
          : <span className={`cfgc-delta ${v > 0 ? "up" : "down"}`}>{v > 0 ? "▲" : "▼"} {pct ? `${Math.abs(v).toFixed(2)} pts` : money(Math.abs(v))}</span>;
        const onDrag = (e: React.MouseEvent) => {
          const sx = e.clientX, sy = e.clientY, ox = simPos.x, oy = simPos.y;
          const mv = (ev: MouseEvent) => setSimPos({ x: ox + ev.clientX - sx, y: oy + ev.clientY - sy });
          const up = () => { window.removeEventListener("mousemove", mv); window.removeEventListener("mouseup", up); };
          window.addEventListener("mousemove", mv); window.addEventListener("mouseup", up);
        };
        return (
        <div className="cfgc-float" style={{ transform: `translate(${simPos.x}px, ${simPos.y}px)` }}>
          <div className="cfgc-float-head" onMouseDown={onDrag}>
            <span className="live" /><b>Prueba en vivo</b><span className="tag">NO MODIFICA EL PRODUCTO</span>
            <span style={{ flex: 1 }} />
            <button className="cfgc-float-x" onClick={() => setProbar(false)} title="Cerrar">✕</button>
          </div>
          <div className="cfgc-float-body">
            <div className="cfgc-fgrid" style={{ gridTemplateColumns: "1fr 1fr" }}>
              <label className="f"><span className="lbl">Monto</span><input className="num" type="number" value={monto} onChange={(e) => setMonto(Number(e.target.value) || 0)} /></label>
              <label className="f"><span className="lbl">Plazo (cuotas)</span><input className="num" type="number" value={plazo} onChange={(e) => setPlazo(Math.max(1, Number(e.target.value) || 1))} /></label>
            </div>
            <div className="cfgc-metrics" style={{ gridTemplateColumns: "1fr 1fr 1fr" }}>
              <div className="cfgc-metric"><small>TNA</small><strong className="num">{tnaEfectiva.toFixed(2)}%</strong></div>
              <div className="cfgc-metric"><small>TEA</small><strong className="num">{(res.tea || 0).toFixed(2)}%</strong></div>
              <div className="cfgc-metric hl"><small>CFT (TIR)</small><strong className="num">{(res.cft || 0).toFixed(2)}%</strong></div>
            </div>
            <div className="cfgc-metrics">
              <div className="cfgc-metric hl"><small>{cfg.sistema === "FRANCES" ? "Cuota" : "1ª cuota"}</small><strong className="num">{money(rows[0]?.total || 0)}</strong><Delta v={dCuota} /></div>
              <div className="cfgc-metric"><small>Costo total</small><strong className="num">{money(costo)}</strong><Delta v={dCosto} /></div>
              <div className="cfgc-metric"><small>Intereses+cargos</small><strong className="num">{money(totInt + totCar)}</strong><Delta v={dInt} /></div>
            </div>

            {/* Impacto: qué cambió respecto del estado al abrir la línea */}
            <div className="cfgc-impact">
              <div className="ttl">📍 Impacto de tus cambios {impacto.length > 0 && <span className="cnt">{impacto.length}</span>}</div>
              {impacto.length === 0
                ? <p className="muted" style={{ fontSize: 11.5, margin: "2px 0 0" }}>Sin cambios respecto del estado inicial. Editá una condición y vas a ver acá el impacto.</p>
                : <div className="rows">{impacto.map((d, i) => (
                    <div className="row" key={i}><b>{d.campo}</b><span className="ba">{d.antes} <span className="ar">→</span> <em>{d.ahora}</em></span></div>
                  ))}</div>}
            </div>

            {/* Validación */}
            <div className="cfgc-impact">
              <div className="ttl">Validación <span className="cnt" style={{ background: errs ? "var(--crit)" : "var(--ok)" }}>{errs ? `${errs}` : "OK"}</span></div>
              <div className="rows">{checks.map((c, i) => <div className="item" key={i}><span className={`cfgc-vi ${c.ok ? "ok" : "err"}`}>{c.ok ? "✓" : "✕"}</span><div style={{ fontSize: 11.5 }}>{c.t}<small style={{ display: "block", color: "var(--ink-faint)" }}>{c.s}</small></div></div>)}</div>
            </div>

            {/* Guardar + guardadas */}
            <div style={{ display: "flex", gap: 6 }}>
              <input style={{ flex: 1 }} value={simEtiq} placeholder="Etiqueta (opcional)" onChange={(e) => setSimEtiq(e.target.value)} />
              <button className="btn sm primary" onClick={guardarSim}>💾 Guardar</button>
            </div>
            {sims.length > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: 5, maxHeight: 120, overflowY: "auto" }}>
                {sims.map((s) => (
                  <div key={s.id} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, background: "var(--surface-2)", borderRadius: 8, padding: "5px 8px" }}>
                    <button className="cfgc-linkbtn" title="Cargar" style={{ flex: 1, textAlign: "left", background: "none", border: "none", cursor: "pointer", padding: 0 }} onClick={() => cargarSim(s)}>
                      <b>{s.etiqueta || `${money(s.monto)} · ${s.plazo}c`}</b> <span className="muted">· {money(s.monto)} · {s.plazo}c · {s.tna}% · cuota {money(s.primeraCuota)}</span>
                    </button>
                    <button className="btn sm" style={{ color: "var(--crit)", borderColor: "var(--crit)" }} title="Borrar" onClick={() => borrarSim(s.id)}>✕</button>
                  </div>
                ))}
              </div>
            )}

            {/* Cronograma proyectado (reacciona a toda la config) */}
            <details className="cfgc-float-sched" open>
              <summary>Cronograma proyectado · sistema {cfg.sistema.toLowerCase()}{cfg.graciaCapital ? ` · ${cfg.graciaCapital} en gracia` : ""} · {cfg.frecuencia?.toLowerCase()}</summary>
              <div className="cfgc-twrap" style={{ maxHeight: 220 }}>
                <table>
                  <thead><tr><th>#</th><th>Vto</th><th>Capital</th><th>Interés</th><th>Cargos</th><th>Cuota</th><th>Saldo</th></tr></thead>
                  <tbody>{rows.map((r) => { const b = baseRows[r.k - 1]; const chgMonto = !!b && Math.abs((b.total || 0) - r.total) > 0.005; const chgFecha = !!b && b.date && r.date && b.date.getTime() !== r.date.getTime(); const chg = chgMonto || chgFecha; return (
                    <tr key={r.k} className={chg ? "chg" : ""}>
                      <td><b>{r.k}</b></td><td style={chgFecha ? { fontWeight: 700, color: "var(--brand-2)" } : undefined}>{r.date.toLocaleDateString("es-AR")}</td>
                      <td className="num">{money(r.capital)}</td><td className="num">{money(r.interes)}</td>
                      <td className="num">{money(r.cargos)}</td><td className="num"><b>{money(r.total)}</b></td><td className="num">{money(r.closing)}</td>
                    </tr>); })}</tbody>
                </table>
              </div>
            </details>
          </div>
        </div>
        );
      })()}

      {/* Comparar versiones (historial / diff) */}
      {cmpOpen && (() => {
        const A = versiones.find((v) => v.version === cmpA), B = versiones.find((v) => v.version === cmpB);
        const diffs = A && B ? diffVersiones(A, B) : [];
        return (
          <div className="cfgc-scrim" onClick={() => setCmpOpen(false)}>
            <div className="cfgc-modal" style={{ width: "min(760px,95vw)" }} onClick={(e) => e.stopPropagation()}>
              <h3>Comparar versiones — {activo.nombre}</h3>
              <p className="sub">{versiones.length} versión(es) en la historia. Diferencias de condiciones y componentes entre dos.</p>
              <div style={{ display: "flex", gap: 12, marginBottom: 14 }}>
                <label className="f" style={{ flex: 1 }}><span className="lbl">Versión A</span>
                  <select value={cmpA} onChange={(e) => setCmpA(Number(e.target.value))}>{versiones.map((v) => <option key={v.version} value={v.version}>v{v.version} · {ESTADO_LABEL[v.estado as Estado]}</option>)}</select></label>
                <label className="f" style={{ flex: 1 }}><span className="lbl">Versión B</span>
                  <select value={cmpB} onChange={(e) => setCmpB(Number(e.target.value))}>{versiones.map((v) => <option key={v.version} value={v.version}>v{v.version} · {ESTADO_LABEL[v.estado as Estado]}</option>)}</select></label>
              </div>
              {cmpA === cmpB ? <p className="muted">Elegí dos versiones distintas.</p>
                : !diffs.length ? <p className="muted">Sin diferencias entre v{cmpA} y v{cmpB}.</p>
                  : <div style={{ maxHeight: "52vh", overflow: "auto", border: "1px solid var(--border)", borderRadius: 9 }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
                      <thead><tr>{["", "Campo", `v${cmpA}`, `v${cmpB}`].map((h, i) => <th key={i} style={{ position: "sticky", top: 0, textAlign: "left", padding: "8px 10px", background: "var(--surface-2)", borderBottom: "1px solid var(--border)", fontSize: 10.5, color: "var(--ink-soft)" }}>{h}</th>)}</tr></thead>
                      <tbody>{diffs.map((d, i) => (<tr key={i}>
                        <td style={{ padding: "7px 10px", borderBottom: "1px solid var(--border)", fontSize: 10, color: "var(--ink-faint)" }}>{d.grupo}</td>
                        <td style={{ padding: "7px 10px", borderBottom: "1px solid var(--border)", fontWeight: 600 }}>{d.campo}</td>
                        <td className="num" style={{ padding: "7px 10px", borderBottom: "1px solid var(--border)", color: "var(--crit)", wordBreak: "break-all", maxWidth: 240 }}>{String(d.a)}</td>
                        <td className="num" style={{ padding: "7px 10px", borderBottom: "1px solid var(--border)", color: "var(--ok)", wordBreak: "break-all", maxWidth: 240 }}>{String(d.b)}</td>
                      </tr>))}</tbody>
                    </table>
                  </div>}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 14 }}>
                <span style={{ fontSize: 11.5, color: "var(--ink-faint)" }}>{diffs.length} diferencia(s)</span>
                <button className="btn" onClick={() => setCmpOpen(false)}>Cerrar</button>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Inspector de datos (control) */}
      {inspOpen && (
        <>
          <div className="cfgc-scrim" style={{ background: "rgba(10,18,32,.25)" }} onClick={() => setInspOpen(false)} />
          <div className="cfgc-drawer">
            <div className="dh"><h3>🔍 Inspector de datos</h3><span style={{ fontSize: 11.5, color: "var(--ink-faint)" }}>{activo.codigo} · v{activo.version}</span><button className="x" onClick={() => setInspOpen(false)}>✕</button></div>
            <div className="tabs">
              <button className={inspTab === "datos" ? "on" : ""} onClick={() => setInspTab("datos")}>Datos guardados</button>
              <button className={inspTab === "modelo" ? "on" : ""} onClick={() => setInspTab("modelo")}>Modelo de datos</button>
            </div>
            <div className="body">
              {inspTab === "datos" && <>
                <p className="muted" style={{ marginTop: 0, fontSize: 12 }}>Filas realmente persistidas en la base para esta línea (endpoint <span className="num">/productos/{"{id}"}/raw</span>). Guardá el borrador para ver los cambios.</p>
                <div className="cfgc-json">{raw ? JSON.stringify(raw, null, 2) : "Cargando…"}</div>
              </>}
              {inspTab === "modelo" && <div className="cfgc-modelo">
                {modelo ? modelo.tablas.map((t: any) => (
                  <table key={t.tabla}><caption>{t.tabla}</caption><tbody>
                    {t.columnas.map((c: any) => (<tr key={c.nombre}><td className={`k ${c.pk ? "pk" : ""}`}>{c.pk ? <b>◆ {c.nombre}</b> : c.fk ? `◇ ${c.nombre}` : c.nombre}</td><td style={{ color: "var(--ink-faint)" }}>{c.tipo}{c.fk ? ` → ${c.fk}` : ""}</td></tr>))}
                  </tbody></table>
                )) : "Cargando…"}
              </div>}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
