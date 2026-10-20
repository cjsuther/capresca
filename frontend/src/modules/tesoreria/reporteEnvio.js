// Reporte de envío de un lote: qué transferencias se hicieron, cuáles no y qué hay que hacer con cada una.
// Interbanking sólo deja transferir a cuentas que el operador de API tiene habilitadas (error 1078): las
// que faltan se listan para darlas de alta y habilitarlas, y después se reintentan los fallidos.

const REALIZADAS = ["ENVIADO", "CONFIRMADO"];
const NO_REALIZADAS = ["FALLIDO", "INCIERTO"];

/** Qué hay que hacer con un pago que no salió. */
export function accionPendiente(p, operador = "") {
  const op = operador ? `el operador ${operador}` : "el operador de API";
  if (p.estado === "INCIERTO") return "Verificar en Interbanking si salió antes de resolverlo (no reintentar)";
  if (p.cuenta_sin_habilitar === "DESTINO") return `Dar de alta el CBU en Interbanking y habilitarlo para ${op}`;
  if (p.cuenta_sin_habilitar === "ORIGEN") return `Habilitar la cuenta de origen para ${op}`;
  return "Revisar el motivo y reintentar";
}

export function reporteEnvio(lote) {
  const pagos = lote?.pagos || [];
  const realizadas = pagos.filter((p) => REALIZADAS.includes(p.estado));
  const noRealizadas = pagos.filter((p) => NO_REALIZADAS.includes(p.estado));
  const suma = (ps) => ps.reduce((t, p) => t + Number(p.monto || 0), 0);
  // Una cuenta por CBU aunque cobre varios créditos: se habilita una sola vez.
  const porCbu = new Map();
  noRealizadas.filter((p) => p.cuenta_sin_habilitar === "DESTINO").forEach((p) => {
    if (!porCbu.has(p.cbu)) porCbu.set(p.cbu, { cbu: p.cbu, beneficiario: p.beneficiario, documento: p.documento });
  });
  return {
    realizadas, noRealizadas,
    totalRealizadas: suma(realizadas), totalNoRealizadas: suma(noRealizadas),
    cuentasAHabilitar: [...porCbu.values()],
    origenSinHabilitar: noRealizadas.some((p) => p.cuenta_sin_habilitar === "ORIGEN"),
    fallidos: noRealizadas.filter((p) => p.estado === "FALLIDO").length,
  };
}

// Fórmula de texto: Excel no pasa el CBU a notación científica ni le come ceros.
const texto = (v) => ({ formula: `="${v ?? ""}"` });
const celda = (v) => {
  if (v && typeof v === "object") return v.formula;
  const s = String(v ?? "");
  return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};
const importe = (v) => Number(v || 0).toLocaleString("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fecha = (v) => (v ? new Date(v).toLocaleString("es-AR") : "");

/** CSV separado por `;` (lo abre Excel en es-AR). */
export function csvReporte(lote, operador = "") {
  const r = reporteEnvio(lote);
  const origen = lote.cuenta_origen
    ? `${lote.cuenta_origen.bank_number}/${lote.cuenta_origen.account_number}/${lote.cuenta_origen.account_type}` : "";
  const filas = [
    ["Reporte de envío del lote", lote.codigo],
    ["Descripción", lote.descripcion || lote.referencia_origen],
    ["Cuenta de origen", origen],
    ["Enviado por", lote.enviado_por, "el", fecha(lote.enviado_en)],
    ["Operador de API de Interbanking", operador],
    ["Realizadas", r.realizadas.length, "por", importe(r.totalRealizadas)],
    ["No realizadas", r.noRealizadas.length, "por", importe(r.totalNoRealizadas)],
    [],
    ["Resultado", "Beneficiario", "Documento", "CBU", "Banco", "Monto", "Concepto", "Estado", "Motivo",
     "Acción a realizar", "Operación Interbanking", "Enviado por", "Fecha de envío"],
    ...[...r.realizadas, ...r.noRealizadas].map((p) => {
      const ok = REALIZADAS.includes(p.estado);
      return [ok ? "Realizada" : "No realizada", p.beneficiario, texto(p.documento), texto(p.cbu), (p.cbu || "").slice(0, 3),
              importe(p.monto), p.concepto, p.estado, p.motivo, ok ? "" : accionPendiente(p, operador),
              p.id_operacion_ib, p.enviado_por, fecha(p.enviado_en)];
    }),
  ];
  return filas.map((f) => f.map(celda).join(";")).join("\r\n");
}

export function descargarReporte(lote, operador = "") {
  // BOM para que Excel lea bien los acentos.
  const blob = new Blob(["﻿" + csvReporte(lote, operador)], { type: "text/csv;charset=utf-8" });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `reporte-envio-${lote.codigo}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
