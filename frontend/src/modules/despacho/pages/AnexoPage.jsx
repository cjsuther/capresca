import { useCallback, useEffect, useState } from "react";
import { Download, FileCheck2 } from "lucide-react";

import {
  asignarAnexo, descargarAnexoWord, getResoluciones, getSolicitudesAnexo, getTiposAnexo,
  quitarDelAnexo,
} from "../../../api/despacho";
import { useHasPermission } from "../../../context/usePermissions";

const money = (n) => `$ ${Number(n || 0).toLocaleString("es-AR", { minimumFractionDigits: 2 })}`;
const fecha = (f) => (f ? new Date(`${f}T00:00:00`).toLocaleDateString("es-AR") : "—");

/**
 * El anexo de una resolución: las solicitudes que el acto otorga.
 *
 * "Armar" lista las aprobadas y cubicadas que todavía no están en ninguna resolución; "Ver"
 * muestra las de una resolución ya armada, para reimprimirla o corregirla mientras siga en borrador.
 */
export default function AnexoPage() {
  const puedeEscribir = useHasPermission("despacho", "resoluciones:write");

  const [vista, setVista] = useState("armar");       // armar | ver
  const [tipos, setTipos] = useState([]);
  const [tipo, setTipo] = useState(6);
  const [datos, setDatos] = useState({ items: [], cantidad: 0, total: 0 });
  const [elegidas, setElegidas] = useState(() => new Set());
  const [borradores, setBorradores] = useState([]);
  const [resolucionId, setResolucionId] = useState("");
  const [lote, setLote] = useState("");
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");

  useEffect(() => { getTiposAnexo().then(setTipos).catch(() => {}); }, []);

  // Sólo se puede armar el anexo de un acto todavía en borrador.
  useEffect(() => {
    getResoluciones({ estado: "B", por_pagina: 100 })
      .then((d) => setBorradores(d.items))
      .catch(() => {});
  }, []);

  const buscar = useCallback(() => {
    setCargando(true); setError(""); setElegidas(new Set());
    const params = vista === "ver" ? { lote: Number(lote) || 0 } : { tipo };
    if (vista === "ver" && !params.lote) { setCargando(false); return; }
    getSolicitudesAnexo(params)
      .then(setDatos)
      .catch((e) => setError(e?.response?.data?.detail || "No se pudieron traer las solicitudes"))
      .finally(() => setCargando(false));
  }, [vista, tipo, lote]);

  useEffect(() => { if (vista === "armar") buscar(); }, [vista, tipo]);  // eslint-disable-line react-hooks/exhaustive-deps

  const marcar = (id) => setElegidas((s) => {
    const n = new Set(s);
    n.has(id) ? n.delete(id) : n.add(id);
    return n;
  });

  const marcarTodas = (e) =>
    setElegidas(e.target.checked ? new Set(datos.items.map((i) => i.id)) : new Set());

  const totalElegido = datos.items
    .filter((i) => elegidas.has(i.id))
    .reduce((a, i) => a + Number(i.monto || 0), 0);

  const asignar = async () => {
    setError(""); setAviso("");
    try {
      const r = await asignarAnexo({ tipo, resolucion_id: Number(resolucionId),
                                     solicitud_ids: [...elegidas] });
      setAviso(`${r.asignadas} solicitud(es) por ${money(r.total)} en la resolución N° ${r.numero}/${r.anio}.`);
      buscar();
    } catch (e) {
      setError(e?.response?.data?.detail || "No se pudieron asignar");
    }
  };

  const quitar = async () => {
    setError(""); setAviso("");
    try {
      const r = await quitarDelAnexo([...elegidas], Number(lote) || undefined);
      setAviso(`${r.quitadas} solicitud(es) quitadas del anexo.`);
      buscar();
    } catch (e) {
      setError(e?.response?.data?.detail || "No se pudieron quitar");
    }
  };

  const bajarWord = async () => {
    const res = borradores.find((b) => String(b.numero) === String(lote));
    const id = res?.id || Number(resolucionId);
    if (!id) { setError("Elegí la resolución del anexo para poder imprimirlo."); return; }
    const blob = await descargarAnexoWord(id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `anexo_${lote || id}.docx`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Anexo de resolución</h1>
        <p className="text-sm text-gray-500 mt-1 max-w-3xl">
          Las solicitudes aprobadas se otorgan <strong>en lote</strong>: se eligen acá y se asignan a
          una resolución en borrador. El número de lote es el correlativo de esa resolución. Las
          solicitudes son del módulo Créditos y se consultan en vivo: no hay copia de este lado.
        </p>
      </div>

      <div className="flex gap-1 border-b border-gray-200">
        {[["armar", "Armar anexo"], ["ver", "Ver anexo armado"]].map(([v, l]) => (
          <button key={v} type="button" onClick={() => { setVista(v); setDatos({ items: [], cantidad: 0, total: 0 }); }}
                  className={`px-4 py-2 text-sm -mb-px border-b-2 ${
                    vista === v ? "border-blue-600 text-blue-700 font-medium"
                                : "border-transparent text-gray-500 hover:text-gray-700"}`}>
            {l}
          </button>
        ))}
      </div>

      {error && <div className="rounded-lg bg-red-50 text-red-700 text-sm px-4 py-3">{error}</div>}
      {aviso && <div className="rounded-lg bg-green-50 text-green-700 text-sm px-4 py-3">{aviso}</div>}

      <div className="flex flex-wrap items-end gap-3">
        {vista === "armar" ? (
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-gray-500">Tipo de anexo</span>
            <select className="input w-56" value={tipo} aria-label="Tipo de anexo"
                    onChange={(e) => setTipo(Number(e.target.value))}>
              {tipos.map((t) => <option key={t.tipo} value={t.tipo}>{t.nombre}</option>)}
            </select>
          </label>
        ) : (
          <>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-gray-500">N° de resolución (lote)</span>
              <input className="input w-40" value={lote} inputMode="numeric" aria-label="Lote"
                     onChange={(e) => setLote(e.target.value.replace(/\D/g, ""))} />
            </label>
            <button type="button" onClick={buscar}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
              Ver
            </button>
            <button type="button" onClick={bajarWord}
                    className="inline-flex items-center gap-2 px-3 py-2 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
              <Download size={15} /> Anexo en Word
            </button>
          </>
        )}
      </div>

      <div className="bg-surface border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[720px]">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="px-3 py-3 w-10">
                <input type="checkbox" aria-label="Elegir todas" disabled={!datos.items.length}
                       checked={!!datos.items.length && elegidas.size === datos.items.length}
                       onChange={marcarTodas} />
              </th>
              <th className="text-left px-4 py-3 font-medium">Solicitante</th>
              <th className="text-left px-4 py-3 font-medium">CUIL</th>
              <th className="text-left px-4 py-3 font-medium">Línea</th>
              <th className="text-left px-4 py-3 font-medium">Fecha</th>
              <th className="text-right px-4 py-3 font-medium">Monto</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {cargando && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Cargando…</td></tr>
            )}
            {!cargando && datos.items.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                {vista === "armar" ? "No hay solicitudes pendientes de resolución para este tipo."
                                   : "Indicá el número de resolución para ver su anexo."}
              </td></tr>
            )}
            {datos.items.map((s) => (
              <tr key={s.id} className="hover:bg-blue-50/40">
                <td className="px-3 py-3">
                  <input type="checkbox" aria-label={`Elegir ${s.apellido_nombre}`}
                         checked={elegidas.has(s.id)} onChange={() => marcar(s.id)} />
                </td>
                <td className="px-4 py-3 text-gray-800">{s.apellido_nombre}</td>
                <td className="px-4 py-3 text-gray-600 tabular-nums">{s.cuil}</td>
                <td className="px-4 py-3 text-gray-600">{s.linea_nombre || s.linea}</td>
                <td className="px-4 py-3 text-gray-600">{fecha(s.fecha_solicitud)}</td>
                <td className="px-4 py-3 text-right tabular-nums">{money(s.monto)}</td>
              </tr>
            ))}
          </tbody>
          {datos.items.length > 0 && (
            <tfoot className="bg-gray-50 text-gray-700 font-medium">
              <tr>
                <td colSpan={5} className="px-4 py-3 text-right">
                  {elegidas.size > 0 ? `${elegidas.size} elegida(s)` : `${datos.cantidad} solicitud(es)`}
                </td>
                <td className="px-4 py-3 text-right tabular-nums">
                  {money(elegidas.size > 0 ? totalElegido : datos.total)}
                </td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {puedeEscribir && elegidas.size > 0 && (
        <div className="flex flex-wrap items-end justify-end gap-3">
          {vista === "armar" ? (
            <>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-gray-500">Resolución en borrador</span>
                <select className="input w-72" value={resolucionId} aria-label="Resolución en borrador"
                        onChange={(e) => setResolucionId(e.target.value)}>
                  <option value="">Elegí una…</option>
                  {borradores.map((b) => (
                    <option key={b.id} value={b.id}>
                      N° {b.numero}/{b.anio} · {b.motivo || b.asunto}
                    </option>
                  ))}
                </select>
              </label>
              <button type="button" onClick={asignar} disabled={!resolucionId}
                      className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50">
                <FileCheck2 size={16} /> Asignar al anexo
              </button>
            </>
          ) : (
            <button type="button" onClick={quitar}
                    className="px-4 py-2 text-sm border border-red-300 text-red-600 rounded-lg hover:bg-red-50">
              Quitar del anexo
            </button>
          )}
        </div>
      )}
    </div>
  );
}
