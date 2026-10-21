import { useEffect, useState } from "react";
import { X } from "lucide-react";

import { getLote } from "../../../api/despacho";

const money = (n) => `$ ${Number(n || 0).toLocaleString("es-AR", { minimumFractionDigits: 2 })}`;
const fecha = (f) => (f ? new Date(`${String(f).slice(0, 10)}T00:00:00`).toLocaleDateString("es-AR") : "—");
const fechaHora = (v) => (v ? new Date(v).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" }) : "");

const ESTADO_LOTE = {
  ABIERTO: "Abierto", CERRADO: "Cerrado", CON_RESOLUCION: "Con resolución",
  PARA_LIQUIDAR: "Para liquidar", LIQUIDADO: "Liquidado",
};

const textoRes = (r) => (r ? (r.numero_real || r.numeroOficial
  ? `N° ${r.numero_real || r.numeroOficial}/${r.anio}` : `Correlativo ${r.numero}/${r.anio}`) : "Sin resolución");

/**
 * El lote completo, tal como lo tiene Créditos: sus datos y cada solicitud que lo compone (quién la
 * pidió, cuánto, a qué plazo y en qué estado está). Se consulta en vivo al abrirlo.
 */
export default function DetalleLote({ loteId, onCerrar }) {
  const [lote, setLote] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setLote(null); setError("");
    getLote(loteId).then(setLote)
      .catch((e) => setError(e?.response?.data?.detail || "No se pudo traer el detalle del lote"));
  }, [loteId]);

  const filas = lote?.contratos || [];

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-[60]"
         role="dialog" aria-modal="true" aria-label="Detalle del lote">
      <div className="bg-surface rounded-xl w-full max-w-5xl max-h-[90vh] overflow-auto">
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 sticky top-0 bg-surface">
          <h2 className="font-semibold text-gray-800">Lote {lote?.codigo || ""}</h2>
          <button type="button" aria-label="Cerrar detalle del lote" onClick={onCerrar}
                  className="p-1 text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>
        <div className="p-5">
          {error && <div className="rounded-lg bg-red-50 text-red-700 text-sm px-4 py-3">{error}</div>}
          {!lote && !error && <p className="text-sm text-gray-400 py-6 text-center">Cargando…</p>}
          {lote && (
            <>
              <dl className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-2 text-sm mb-4">
                <Dato label="Tipo de crédito">{lote.producto || "—"}</Dato>
                <Dato label="Fecha">{fecha(lote.fecha)}</Dato>
                <Dato label="Estado">{ESTADO_LOTE[lote.estado] || lote.estado}</Dato>
                <Dato label="Resolución">{textoRes(lote.resolucion_despacho || lote.resolucion)}</Dato>
                <Dato label="Solicitudes"><span className="tabular-nums">{lote.cantidad}</span></Dato>
                <Dato label="Importe total"><span className="tabular-nums">{money(lote.montoTotal)}</span></Dato>
                <Dato label="Cerrado por">
                  {lote.cerradoPor ? `${lote.cerradoPor} · ${fechaHora(lote.cerradoEn)}` : "—"}
                </Dato>
                <Dato label="Orden de pago">{lote.ordenPago?.codigo || "—"}</Dato>
              </dl>

              <div className="border border-gray-200 rounded-lg overflow-x-auto">
                <table className="w-full text-sm min-w-[760px]">
                  <thead className="bg-gray-50 text-gray-600">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium">Solicitud</th>
                      <th className="text-left px-3 py-2 font-medium">Solicitante</th>
                      <th className="text-left px-3 py-2 font-medium">CUIL</th>
                      <th className="text-right px-3 py-2 font-medium">Monto</th>
                      <th className="text-right px-3 py-2 font-medium">Plazo</th>
                      <th className="text-left px-3 py-2 font-medium">Contrato</th>
                      <th className="text-left px-3 py-2 font-medium">Estado</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {filas.length === 0 && (
                      <tr><td colSpan={7} className="px-3 py-6 text-center text-gray-400">El lote no tiene solicitudes.</td></tr>
                    )}
                    {filas.map((f) => (
                      <tr key={`${f.tipo}-${f.id}`}>
                        <td className="px-3 py-2 tabular-nums">{f.solicitud || "—"}</td>
                        <td className="px-3 py-2 text-gray-800">
                          {f.cliente || "—"}
                          {f.dni && <div className="text-xs text-gray-400">DNI {f.dni}</div>}
                        </td>
                        <td className="px-3 py-2 tabular-nums text-gray-600">{f.cuil || "—"}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{money(f.monto)}</td>
                        <td className="px-3 py-2 text-right tabular-nums">{f.plazo || "—"}</td>
                        <td className="px-3 py-2 tabular-nums text-gray-600">{f.numero || "—"}</td>
                        <td className="px-3 py-2 text-gray-700">
                          {f.estadoContrato || f.estadoSolicitud || "—"}
                          {f.pendienteAprobacion && <div className="text-xs text-amber-700">Desembolso pendiente de aprobación</div>}
                          {f.desembolso?.estado && (
                            <div className="text-xs text-gray-500">
                              Desembolso: {f.desembolso.estado}{f.desembolso.motivo ? ` · ${f.desembolso.motivo}` : ""}
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  {filas.length > 0 && (
                    <tfoot className="bg-gray-50 text-gray-700 font-medium">
                      <tr>
                        <td colSpan={3} className="px-3 py-2 text-right">{filas.length} solicitud(es)</td>
                        <td className="px-3 py-2 text-right tabular-nums">{money(lote.montoTotal)}</td>
                        <td colSpan={3} />
                      </tr>
                    </tfoot>
                  )}
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Dato({ label, children }) {
  return (
    <div>
      <dt className="text-xs text-gray-500">{label}</dt>
      <dd className="text-gray-800">{children}</dd>
    </div>
  );
}
