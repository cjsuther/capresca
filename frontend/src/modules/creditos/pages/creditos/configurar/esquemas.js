// Configurar Créditos — esquemas, defaults y validaciones del product builder (estilo Temenos AA).
// Es la parte sin UI: la comparten el catálogo, el editor de componentes y la prueba en vivo.

export const ICONOS = {
  TERM_AMOUNT: "📐", INTEREST: "％", REPAYMENT_SCHEDULE: "📅", PAYMENT_RULES: "⇄", CHARGE: "＄",
  TAX: "🧾", OVERDUE: "⏰", PAYOFF: "✔", SETTLEMENT: "🧭", ACCOUNTING: "📚", AVAILABILITY: "🎯",
  ACTIVITY_RESTRICTION: "🔒", PERIODIC: "🔁", REQUIREMENTS: "📎", COLLECTION: "💳",
};

/** Campos tipados por componente (editor genérico). t: num | text | bool | date | select | impuesto */
export const SCHEMA = {
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
  // Forma de cobro: con código de descuento, la solicitud avisa cómo viene la cuota en el recibo de sueldo.
  COLLECTION: [
    { k: "modalidad", l: "Modalidad", t: "select", o: ["CODIGO_DESCUENTO", "VENTANILLA", "DEBITO_AUTOMATICO"],
      etq: { CODIGO_DESCUENTO: "Código de descuento (recibo de sueldo)", VENTANILLA: "Pago en ventanilla",
             DEBITO_AUTOMATICO: "Débito automático" } },
    { k: "codigoDescuento", l: "Código de descuento", t: "text" },
    { k: "conceptoRecibo", l: "Cómo figura en el recibo", t: "text" },
    { k: "detalle", l: "Aclaración para el solicitante (opcional)", t: "text" },
  ],
  OVERDUE: [
    { k: "diasGracia", l: "Días de gracia", t: "num" },
    { k: "base", l: "Base punitorio", t: "select", o: ["CUOTA_VENCIDA", "SALDO"] },
    { k: "capitaliza", l: "Capitaliza mora", t: "bool" },
  ],
};

/** Componentes con múltiples instancias (varios cargos / impuestos). */
export const ITEM_SCHEMA = {
  INTEREST: [{ k: "etiqueta", l: "Nombre", t: "text" },
             { k: "tipo", l: "Tipo", t: "select", o: ["COMPENSATORIO", "PROMOCIONAL", "COMISION"] },
             { k: "tna", l: "TNA %", t: "num" }],
  CHARGE: [{ k: "etiqueta", l: "Etiqueta", t: "text" }, { k: "porcentaje", l: "%", t: "num" },
           { k: "momento", l: "Momento", t: "select", o: ["DESEMBOLSO", "PRORRATEADO"] }],
  TAX: [{ k: "codigo", l: "Impuesto (maestro)", t: "impuesto" }, { k: "etiqueta", l: "Etiqueta", t: "text" },
        { k: "base", l: "Base", t: "select", o: ["INTERES", "CARGOS", "CUOTA", "CAPITAL"] },
        { k: "porcentaje", l: "%", t: "num" }],
};
export const ITEM_NUEVO = {
  INTEREST: { etiqueta: "Nueva propiedad", tipo: "COMPENSATORIO", tna: 0 },
  CHARGE: { etiqueta: "Nuevo cargo", porcentaje: 0, momento: "PRORRATEADO" },
  TAX: { etiqueta: "Nuevo impuesto", base: "INTERES", porcentaje: 0 },
};
export const ITEM_TITULO = { INTEREST: "Propiedades de interés adicionales", CHARGE: "Cargos adicionales", TAX: "Impuestos" };
export const ITEM_SINGULAR = { INTEREST: "propiedad", CHARGE: "cargo", TAX: "impuesto" };

export const CFG_DEFAULT = {
  sistema: "FRANCES", modalidad: "FIJA", tna: 52, baseDias: "ACT/365", frecuencia: "MENSUAL",
  montoMin: 100000, montoMax: 5000000, plazoMin: 6, plazoMax: 60, graciaCapital: 0,
  cargoOtorg: 2, moraTNA: 120, indice: "", margen: 0, tnaNegociable: false, tnaMin: 0, tnaMax: 0,
  vigenciaDesde: "", vigenciaHasta: "",
};

export const CONFIG_DEFAULT = {
  REPAYMENT_SCHEDULE: { diaPago: 5, primerVencimientoDias: 30, ajusteFinDeSemana: "SIGUIENTE_HABIL", tipoCuota: "VENCIDA" },
  PAYMENT_RULES: { ordenImputacion: "MORA,INTERES,CAPITAL", toleranciaDias: 3, permitePagoParcial: false, permiteAdelanto: true },
  CHARGE: { momento: "DESEMBOLSO", financiable: false, items: [{ etiqueta: "Cargo administrativo", porcentaje: 1.5, momento: "PRORRATEADO" }] },
  TAX: { items: [{ etiqueta: "IVA sobre interés", base: "INTERES", porcentaje: 21 },
                 { etiqueta: "IVA sobre cargos", base: "CARGOS", porcentaje: 21 },
                 { etiqueta: "Sellado", base: "CUOTA", porcentaje: 1.2 }] },
  OVERDUE: { diasGracia: 5, base: "CUOTA_VENCIDA", capitaliza: false },
  PAYOFF: { permite: true, penalidadPct: 0, minCuotasPagadas: 3, condonaInteresNoDevengado: true },
  SETTLEMENT: { generaLiquidacion: true, remitirA: "TESORERIA" },
  ACCOUNTING: { cuentaCapital: "1.1.05.01", cuentaInteres: "4.1.01", cuentaComision: "4.1.04",
                cuentaIva: "2.1.07", cuentaMora: "4.1.02", centroCosto: "CRED" },
  AVAILABILITY: { canales: ["SUCURSAL", "WEB"], segmentos: ["AGENTE_PUBLICO"], edadMin: 18, edadMax: 75,
                  antiguedadMinMeses: 0, afectacionMaxPct: 30, requiereGarante: false,
                  vigenteDesde: "", vigenteHasta: "" },
  ACTIVITY_RESTRICTION: { permitePrepago: true, permiteRenegociacion: true, permiteVacacionPago: false },
  PERIODIC: { repricingFrecuencia: "NINGUNA", capitalizaInteres: false, diaAplicacion: 1 },
  REQUIREMENTS: { documentos: [], campos: [] },
  COLLECTION: { modalidad: "CODIGO_DESCUENTO", codigoDescuento: "", conceptoRecibo: "", detalle: "" },
};

/** La documentación general del portal, para agregarla de un clic a una línea (mismos códigos). */
export const DOCUMENTOS_ESTANDAR = [
  { codigo: "DNI_FRENTE", titulo: "DNI (frente)", ayuda: "" },
  { codigo: "DNI_DORSO", titulo: "DNI (dorso)", ayuda: "" },
  { codigo: "SELFIE_DNI", titulo: "Selfie con el DNI en la mano", ayuda: "Una foto tuya sosteniendo el DNI, que se lean los datos." },
  { codigo: "RECIBO", titulo: "Recibo de sueldo", ayuda: "" },
  { codigo: "CERTIFICADO_SERVICIOS", titulo: "Certificado de servicios", ayuda: "El que emite tu empleador con tu antigüedad y situación de revista." },
  { codigo: "CONSTANCIA_CBU", titulo: "Constancia de CBU", ayuda: "La que baja tu banco o Home Banking con el CBU a tu nombre." },
];

/** Código de un documento o dato a partir de su título: "Orden médica" → ORDEN_MEDICA (hasta 20, único). */
export function codigoDesde(texto, usados = []) {
  const base = String(texto || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 20).replace(/_+$/, "");
  if (!base) return "";
  let cod = base;
  for (let n = 2; usados.includes(cod); n++) cod = `${base.slice(0, 20 - String(n).length - 1)}_${n}`;
  return cod;
}

// Catálogos de segmentación: el backend los puede sobreescribir (Parámetros de créditos, H-185).
export const SEGMENTOS = ["AGENTE_PUBLICO", "JUBILADO", "PENSIONADO", "DOCENTE", "MUNICIPAL", "CONTRATADO", "LIBRE"];
export const CANALES = ["SUCURSAL", "WEB", "APP", "CONVENIO"];

export const FORMULA = {
  FRANCES: "cuota = P · i / (1 − (1 + i)⁻ⁿ)",
  ALEMAN: "capitalₜ = P / n  ·  interésₜ = saldoₜ · i",
  AMERICANO: "interésₜ = P · i  ·  capitalₙ = P",
  BULLET: "pago único = P · (1 + i)ⁿ",
};

export const LIFECYCLE = ["BORRADOR", "EN_REVISION", "APROBADO", "PUBLICADO", "RETIRADO"];
export const ESTADO_LABEL = {
  BORRADOR: "Borrador", EN_REVISION: "En revisión", APROBADO: "Aprobado",
  PUBLICADO: "Publicado", RETIRADO: "Retirado",
};
export const ESTADO_TONO = {
  BORRADOR: "neutral", EN_REVISION: "warn", APROBADO: "brand", PUBLICADO: "ok", RETIRADO: "neutral",
};

/** Errores de configuración de un componente (los mismos que valida el backend). */
export function valida(codigo, config, cfg) {
  const e = [];
  const items = config.items || [];
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
      if (cfg.modalidad === "FIJA" && !(cfg.tnaMin <= cfg.tna && cfg.tna <= cfg.tnaMax))
        e.push("La TNA base debe estar dentro de la banda negociable");
    }
    items.forEach((it, i) => {
      if (!it.etiqueta) e.push(`Propiedad de interés #${i + 1}: falta nombre`);
      if (it.tna < 0 || it.tna > 500) e.push(`Propiedad de interés #${i + 1}: TNA 0–500%`);
    });
  }
  if (codigo === "CHARGE") {
    if (cfg.cargoOtorg < 0 || cfg.cargoOtorg > 100) e.push("Cargo de otorgamiento 0–100%");
    items.forEach((it, i) => {
      if (!it.etiqueta) e.push(`Cargo #${i + 1}: falta etiqueta`);
      if (it.porcentaje < 0 || it.porcentaje > 100) e.push(`Cargo #${i + 1}: % debe ser 0–100`);
    });
  }
  if (codigo === "TAX") items.forEach((it, i) => {
    if (!it.etiqueta) e.push(`Impuesto #${i + 1}: falta etiqueta`);
    if (it.porcentaje < 0 || it.porcentaje > 100) e.push(`Impuesto #${i + 1}: % debe ser 0–100`);
  });
  if (codigo === "OVERDUE") {
    if (cfg.moraTNA < 0) e.push("TNA punitoria ≥ 0");
    if ((config.diasGracia ?? 0) < 0) e.push("Días de gracia ≥ 0");
  }
  if (codigo === "REPAYMENT_SCHEDULE") {
    const d = config.diaPago;
    if (d < 1 || d > 28) e.push("Día de pago debe ser 1–28");
    if ((config.primerVencimientoDias ?? 0) < 0) e.push("1er vencimiento ≥ 0");
  }
  if (codigo === "PAYOFF") {
    const p = config.penalidadPct ?? 0;
    if (p < 0 || p > 100) e.push("Penalidad 0–100%");
  }
  if (codigo === "COLLECTION" && config.modalidad === "CODIGO_DESCUENTO") {
    if (!String(config.codigoDescuento || "").trim()) e.push("Falta el código de descuento");
    if (!String(config.conceptoRecibo || "").trim()) e.push("Falta cómo figura en el recibo de sueldo");
  }
  if (codigo === "REQUIREMENTS") {
    (config.documentos || []).forEach((d, i) => {
      if (!String(d.titulo || "").trim()) e.push(`Documento #${i + 1}: falta el título`);
    });
    (config.campos || []).forEach((c, i) => {
      const nombre = String(c.etiqueta || "").trim() || `#${i + 1}`;
      if (!String(c.etiqueta || "").trim()) e.push(`Dato #${i + 1}: falta la pregunta`);
      const op = c.opciones || [];
      if (op.length < 2) e.push(`Dato ${nombre}: necesita al menos dos opciones`);
      if (new Set(op).size !== op.length) e.push(`Dato ${nombre}: hay opciones repetidas`);
    });
  }
  return e;
}

/** ¿El componente quedó con los valores por defecto (nadie lo tocó)? */
export function esDefault(codigo, config, cfg) {
  const eq = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  if (codigo === "TERM_AMOUNT")
    return ["montoMin", "montoMax", "plazoMin", "plazoMax", "frecuencia", "graciaCapital"]
      .every((k) => cfg[k] === CFG_DEFAULT[k]);
  if (codigo === "INTEREST")
    return ["sistema", "modalidad", "tna", "baseDias"].every((k) => cfg[k] === CFG_DEFAULT[k])
      && (cfg.indice || "") === "" && (cfg.margen || 0) === 0 && !cfg.tnaNegociable
      && (cfg.tnaMin || 0) === 0 && (cfg.tnaMax || 0) === 0 && !(config.items || []).length;
  if (codigo === "CHARGE") return cfg.cargoOtorg === CFG_DEFAULT.cargoOtorg && eq(config, CONFIG_DEFAULT.CHARGE);
  if (codigo === "OVERDUE") return cfg.moraTNA === CFG_DEFAULT.moraTNA && eq(config, CONFIG_DEFAULT.OVERDUE);
  return eq(config, CONFIG_DEFAULT[codigo] ?? {});
}

export const CMP_CAMPOS = [
  ["sistema", "Sistema"], ["modalidad", "Modalidad"], ["tna", "TNA %"], ["baseDias", "Base de días"],
  ["frecuencia", "Frecuencia"], ["montoMin", "Monto mín."], ["montoMax", "Monto máx."],
  ["plazoMin", "Plazo mín."], ["plazoMax", "Plazo máx."], ["graciaCapital", "Gracia capital"],
  ["cargoOtorg", "Cargo otorg. %"], ["moraTNA", "Mora TNA %"],
];

/** Diferencias entre dos versiones de una línea (comparador). */
export function diffVersiones(A, B) {
  const filas = [];
  for (const [k, l] of CMP_CAMPOS)
    if (String(A.cfg[k]) !== String(B.cfg[k])) filas.push({ grupo: "Condiciones", campo: l, a: A.cfg[k], b: B.cfg[k] });
  const cA = Object.fromEntries(A.componentes.map((c) => [c.codigo, c]));
  for (const b of B.componentes) {
    const a = cA[b.codigo];
    if (!a) continue;
    if (a.activo !== b.activo)
      filas.push({ grupo: "Componentes", campo: `${b.nombre} · activo`, a: a.activo ? "Sí" : "No", b: b.activo ? "Sí" : "No" });
    else if (b.activo && JSON.stringify(a.config) !== JSON.stringify(b.config))
      filas.push({ grupo: "Componentes", campo: `${b.nombre} · config`, a: JSON.stringify(a.config), b: JSON.stringify(b.config) });
  }
  return filas;
}

/** Payload del cronograma para el backend: el cálculo es SIEMPRE del servidor (fuente única). */
export function previewPayload(cfg, comps, tnaEfectiva, monto, plazo) {
  const conf = (cod) => comps.find((c) => c.codigo === cod && c.activo)?.config || {};
  const ch = conf("CHARGE"), tx = conf("TAX"), rs = conf("REPAYMENT_SCHEDULE");
  return {
    sistema: cfg.sistema, monto, plazo, tna: tnaEfectiva, cargoOtorg: cfg.cargoOtorg,
    gracia: cfg.graciaCapital || 0, frecuencia: cfg.frecuencia,
    cargos: (ch.items || []).map((it) => ({ porcentaje: it.porcentaje, momento: it.momento })),
    impuestos: (tx.items || []).map((it) => ({ base: it.base, porcentaje: it.porcentaje })),
    diaPago: rs.diaPago ?? 5, primerVencimientoDias: rs.primerVencimientoDias ?? 30,
    ajusteFinDeSemana: rs.ajusteFinDeSemana ?? "SIN_AJUSTE", tipoCuota: rs.tipoCuota ?? "VENCIDA",
    financiable: !!ch.financiable, cargoMomento: ch.momento ?? "PRORRATEADO",
  };
}

/** Filas del cronograma que devuelve el backend, normalizadas para la tabla. */
export const toFilas = (filas) => (filas || []).map((r) => ({
  k: r.numero_cuota, fecha: r.fecha_vencimiento, apertura: r.saldo_inicial, capital: r.capital,
  interes: r.interes, cargos: r.cargos, total: r.total, cierre: r.saldo_final,
}));
