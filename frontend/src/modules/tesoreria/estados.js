// Etiquetas, tonos y formato del módulo Tesorería.
export const ESTADO_LOTE = {
  PENDIENTE_APROBACION: ["Pendiente de aprobación", "warn"],
  APROBADO: ["Aprobado · listo para enviar", "brand"],
  ENVIADO: ["Enviado al banco", "brand"],
  CONFIRMADO: ["Acreditado", "ok"],
  CON_ERRORES: ["Con errores", "crit"],
  RECHAZADO: ["Rechazado", "neutral"],
};

export const ESTADO_PAGO = {
  PENDIENTE: ["Pendiente", "warn"],
  EXCLUIDO: ["Excluido", "neutral"],
  RECHAZADO: ["Rechazado", "neutral"],
  ENVIANDO: ["Enviando…", "brand"],
  ENVIADO: ["Enviado", "brand"],
  CONFIRMADO: ["Acreditado", "ok"],
  FALLIDO: ["Fallido", "crit"],
  INCIERTO: ["Incierto", "crit"],
};

export const ORIGENES = { CREDITOS: "Créditos", CONCILIACION: "Conciliación", MANUAL: "Carga manual" };

export const money = (v) =>
  v == null || v === "" ? "—" : Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

export const fechaHora = (v) => {
  if (!v) return "—";
  const d = new Date(v);
  return isNaN(d) ? String(v) : d.toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" });
};

/** "011/99900011122/CC · Cuenta de pagos" */
export const cuentaLegible = (c) =>
  (!c ? "—" : [`${c.bank_number || "011"}/${c.account_number}/${c.account_type || "CC"}`, c.nombre].filter(Boolean).join(" · "));

/** CBU con separadores para leerlo (banco-sucursal · cuenta). */
export const cbuLegible = (c) => (c && c.length === 22 ? `${c.slice(0, 8)} ${c.slice(8)}` : c || "—");
