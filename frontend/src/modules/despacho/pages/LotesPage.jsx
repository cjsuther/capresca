import { useCallback, useEffect, useState } from "react";
import { Download, Eye, FileCheck2 } from "lucide-react";

import {
  asignarLotes, descargarAnexoWord, getLotes, getLotesDeResolucion, getResoluciones, getTiposLotes,
  quitarResolucionLote,
} from "../../../api/despacho";
import { useHasPermission } from "../../../context/usePermissions";
import DetalleLote from "../components/DetalleLote";

const money = (n) => `$ ${Number(n || 0).toLocaleString("es-AR", { minimumFractionDigits: 2 })}`;
const fecha = (f) => (f ? new Date(`${String(f).slice(0, 10)}T00:00:00`).toLocaleDateString("es-AR") : "—");

const ESTADOS = [["CERRADO", "Cerrados (para asignar)"], ["ABIERTO", "Abiertos"], ["CON_RESOLUCION", "Con resolución"],
                 ["PARA_LIQUIDAR", "Para liquidar (en orden de pago)"], ["LIQUIDADO", "Liquidados"], ["", "Todos"]];
const ESTADO = {
  ABIERTO: ["Abierto", "bg-amber-100 text-amber-800"],
  CERRADO: ["Cerrado", "bg-gray-100 text-gray-700"],
  CON_RESOLUCION: ["Con resolución", "bg-blue-100 text-blue-700"],
  PARA_LIQUIDAR: ["Para liquidar", "bg-blue-100 text-blue-700"],
  LIQUIDADO: ["Liquidado", "bg-green-100 text-green-700"],
};

/** "N° 120/2026" con el oficial si ya lo tiene; si no, el correlativo. */
const fechaHora = (v) => (v ? new Date(v).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" }) : "");

const textoRes = (r) => (r ? (r.numero_real || r.numeroOficial
  ? `N° ${r.numero_real || r.numeroOficial}/${r.anio}` : `Correlativo ${r.numero}/${r.anio}`) : "—");

/**
 * Lotes de créditos: Créditos junta solo las solicitudes aprobadas que se pueden liquidar, por tipo
 * de crédito y fecha; alguien verifica cada lote y lo cierra. Acá se les asigna a los lotes cerrados
 * la resolución que los otorga; una misma resolución puede alcanzar varios lotes, siempre que la suma
 * no pase su importe. Con la resolución asignada, el lote
 * queda congelado y Créditos lo puede liquidar.
 */
export default function LotesPage() {
  const puedeEscribir = useHasPermission("despacho", "resoluciones:write");

  const [tipos, setTipos] = useState([]);
  const [tipo, setTipo] = useState("");
  const [estado, setEstado] = useState("CERRADO");
  const [datos, setDatos] = useState({ items: [], cantidad: 0, total: 0 });
  const [elegidos, setElegidos] = useState(() => new Set());
  const [borradores, setBorradores] = useState([]);
  const [resolucionId, setResolucionId] = useState("");
  const [comprometido, setComprometido] = useState(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [verLote, setVerLote] = useState(null);        // id del lote abierto en detalle

  useEffect(() => { getTiposLotes().then(setTipos).catch(() => {}); }, []);

  // Sólo se asignan lotes a un acto todavía en borrador (uno emitido no se toca).
  const cargarBorradores = () => getResoluciones({ estado: "B", por_pagina: 100 })
    .then((d) => setBorradores(d.items.filter((r) => !r.anulada))).catch(() => {});
  useEffect(() => { cargarBorradores(); }, []);

  const buscar = useCallback(() => {
    setCargando(true); setError(""); setElegidos(new Set());
    getLotes({ estado, tipo })
      .then(setDatos)
      .catch((e) => setError(e?.response?.data?.detail || "No se pudieron traer los lotes"))
      .finally(() => setCargando(false));
  }, [estado, tipo]);
  useEffect(() => { buscar(); }, [buscar]);

  useEffect(() => {
    setComprometido(null);
    if (!resolucionId) return;
    getLotesDeResolucion(Number(resolucionId)).then(setComprometido).catch(() => {});
  }, [resolucionId]);

  const marcar = (id) => setElegidos((s) => {
    const n = new Set(s);
    n.has(id) ? n.delete(id) : n.add(id);
    return n;
  });
  const cerrados = datos.items.filter((l) => l.estado === "CERRADO");
  const marcarTodos = (e) => setElegidos(e.target.checked ? new Set(cerrados.map((l) => l.id)) : new Set());
  const totalElegido = datos.items.filter((l) => elegidos.has(l.id)).reduce((a, l) => a + Number(l.montoTotal || 0), 0);
  const res = borradores.find((b) => String(b.id) === String(resolucionId));
  const disponible = comprometido ? Number(comprometido.disponible) : res ? Number(res.importe || 0) : null;
  const excede = disponible !== null && totalElegido > disponible;

  const asignar = async () => {
    setError(""); setAviso("");
    try {
      const r = await asignarLotes({ resolucion_id: Number(resolucionId), lote_ids: [...elegidos] });
      setAviso(`Resolución N° ${r.numero}/${r.anio} asignada a ${r.asignados.length} lote(s): ${r.asignados.join(", ")}. `
               + `Quedan ${money(r.disponible)} de su importe.`);
      setResolucionId("");
      buscar();
    } catch (e) {
      setError(e?.response?.data?.detail || "No se pudo asignar la resolución");
    }
  };

  const quitar = async (lote) => {
    setError(""); setAviso("");
    try {
      await quitarResolucionLote(lote.id);
      setAviso(`Se le quitó la resolución al lote ${lote.codigo}.`);
      buscar();
    } catch (e) {
      setError(e?.response?.data?.detail || "No se pudo quitar la resolución");
    }
  };

  const bajarAnexo = async (r) => {
    try {
      const blob = await descargarAnexoWord(r.id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `anexo_${r.numero_real || r.numero}_${r.anio}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e?.response?.data?.detail || "No se pudo bajar el anexo");
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Lotes de créditos</h1>
        <p className="text-sm text-gray-500 mt-1 max-w-3xl">
          Créditos junta en lotes, por tipo de crédito y fecha, las solicitudes aprobadas que se pueden
          liquidar; cuando alguien verifica un lote, lo cierra. Acá se les asigna a los lotes <strong>cerrados</strong> la{" "}
          <strong>resolución</strong> que los otorga: una misma resolución puede ir a varios lotes, sin que la
          suma pase su importe. Con la resolución asignada, el lote
          queda congelado y Créditos lo liquida. Los lotes son del módulo Créditos y se consultan en vivo.
        </p>
      </div>

      {error && <div className="rounded-lg bg-red-50 text-red-700 text-sm px-4 py-3">{error}</div>}
      {aviso && <div className="rounded-lg bg-green-50 text-green-700 text-sm px-4 py-3">{aviso}</div>}

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-gray-500">Estado</span>
          <select className="input w-48" value={estado} aria-label="Estado" onChange={(e) => setEstado(e.target.value)}>
            {ESTADOS.map(([v, l]) => <option key={v || "todos"} value={v}>{l}</option>)}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-gray-500">Tipo de crédito</span>
          <select className="input w-56" value={tipo} aria-label="Tipo de crédito" onChange={(e) => setTipo(e.target.value)}>
            {tipos.map((t) => <option key={t.tipo || "todos"} value={t.tipo}>{t.nombre}</option>)}
          </select>
        </label>
      </div>

      <div className="bg-surface border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[820px]">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="px-3 py-3 w-10">
                <input type="checkbox" aria-label="Elegir todos" disabled={!cerrados.length}
                       checked={!!cerrados.length && elegidos.size === cerrados.length} onChange={marcarTodos} />
              </th>
              <th className="text-left px-4 py-3 font-medium">Lote</th>
              <th className="text-left px-4 py-3 font-medium">Tipo de crédito</th>
              <th className="text-left px-4 py-3 font-medium">Fecha</th>
              <th className="text-right px-4 py-3 font-medium">Solicitudes</th>
              <th className="text-right px-4 py-3 font-medium">Importe</th>
              <th className="text-left px-4 py-3 font-medium">Resolución</th>
              <th className="text-left px-4 py-3 font-medium">Estado</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {cargando && <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-400">Cargando…</td></tr>}
            {!cargando && datos.items.length === 0 && (
              <tr><td colSpan={9} className="px-4 py-8 text-center text-gray-400">No hay lotes.</td></tr>
            )}
            {datos.items.map((l) => {
              const [texto, clase] = ESTADO[l.estado] || [l.estado, "bg-gray-100 text-gray-600"];
              const r = l.resolucion_despacho;
              return (
                <tr key={l.id} className="hover:bg-blue-50/40">
                  <td className="px-3 py-3">
                    {l.estado === "CERRADO" && (
                      <input type="checkbox" aria-label={`Elegir ${l.codigo}`}
                             checked={elegidos.has(l.id)} onChange={() => marcar(l.id)} />
                    )}
                  </td>
                  <td className="px-4 py-3 font-medium tabular-nums">
                    <button type="button" onClick={() => setVerLote(l.id)} title="Ver el detalle del lote"
                            className="text-blue-600 hover:underline">{l.codigo}</button>
                  </td>
                  <td className="px-4 py-3 text-gray-700">{l.producto}</td>
                  <td className="px-4 py-3 text-gray-600">{fecha(l.fecha)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{l.cantidad}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{money(l.montoTotal)}</td>
                  <td className="px-4 py-3 text-gray-700">{textoRes(r || l.resolucion)}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${clase}`}>{texto}</span>
                    {l.ordenPago && <div className="text-xs text-gray-500 mt-1">Orden de pago {l.ordenPago.codigo}</div>}
                    {l.cerradoPor && (
                      <div className="text-xs text-gray-500 mt-1">Cerrado por {l.cerradoPor} · {fechaHora(l.cerradoEn)}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">
                    <button type="button" onClick={() => setVerLote(l.id)} aria-label={`Ver detalle de ${l.codigo}`}
                            className="mr-2 inline-flex items-center gap-1 px-2 py-1 text-xs border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
                      <Eye size={13} /> Detalle
                    </button>
                    {r && (
                      <button type="button" onClick={() => bajarAnexo(r)} title="Anexo de la resolución en Word"
                              className="inline-flex items-center gap-1 px-2 py-1 text-xs border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
                        <Download size={13} /> Anexo
                      </button>
                    )}
                    {puedeEscribir && l.estado === "CON_RESOLUCION" && (
                      <button type="button" onClick={() => quitar(l)}
                              className="ml-2 px-2 py-1 text-xs border border-red-300 text-red-600 rounded-lg hover:bg-red-50">
                        Quitar resolución
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
          {datos.items.length > 0 && (
            <tfoot className="bg-gray-50 text-gray-700 font-medium">
              <tr>
                <td colSpan={5} className="px-4 py-3 text-right">
                  {elegidos.size > 0 ? `${elegidos.size} lote(s) elegido(s)` : `${datos.cantidad} lote(s)`}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">{money(elegidos.size > 0 ? totalElegido : datos.total)}</td>
                <td colSpan={3} />
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {verLote && <DetalleLote loteId={verLote} onCerrar={() => setVerLote(null)} />}

      {puedeEscribir && elegidos.size > 0 && (
        <div className="flex flex-wrap items-end justify-end gap-3">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-gray-500">Resolución en borrador</span>
            <select className="input w-80" value={resolucionId} aria-label="Resolución en borrador"
                    onChange={(e) => setResolucionId(e.target.value)}>
              <option value="">Elegí una…</option>
              {borradores.map((b) => (
                <option key={b.id} value={b.id}>
                  N° {b.numero}/{b.anio} · {money(b.importe)} · {b.motivo || b.asunto}
                </option>
              ))}
            </select>
          </label>
          {res && disponible !== null && (
            <p className={`text-sm pb-2 ${excede ? "text-red-600" : "text-gray-600"}`}>
              Disponible de la resolución: <b className="tabular-nums">{money(disponible)}</b>
              {excede && " · lo elegido lo supera"}
            </p>
          )}
          <button type="button" onClick={asignar} disabled={!resolucionId || excede}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50">
            <FileCheck2 size={16} /> Asignar resolución
          </button>
        </div>
      )}
    </div>
  );
}
