/**
 * Cómo se cobra la cuota de la línea (componente "Forma de cobro"). Con código de descuento, le avisa al
 * solicitante cómo le va a venir detallada en el recibo de sueldo. `cuota` es opcional (la primera).
 */
export function textoCobro(cobro, cuota, money) {
  if (!cobro) return "";
  const monto = cuota ? `de ${money(cuota)} ` : "";
  if (cobro.modalidad === "CODIGO_DESCUENTO") {
    return `La cuota ${monto}se descuenta directamente del sueldo. En el recibo de haberes figura como «${cobro.conceptoRecibo}», código de descuento ${cobro.codigoDescuento}.`;
  }
  if (cobro.modalidad === "DEBITO_AUTOMATICO") return `La cuota ${monto}se debita automáticamente de la cuenta.`;
  return `La cuota ${monto}se paga en ventanilla.`;
}

export function AvisoCobro({ cobro, cuota, money, titulo = "Cómo se cobra" }) {
  if (!cobro) return null;
  return (
    <div className="border border-blue-200 bg-blue-50 rounded-lg px-3 py-2 text-sm text-blue-900" role="note" aria-label={titulo}>
      <p className="font-medium">{titulo}</p>
      <p>{textoCobro(cobro, cuota, money)}</p>
      {cobro.detalle && <p className="text-blue-800 mt-1">{cobro.detalle}</p>}
    </div>
  );
}
