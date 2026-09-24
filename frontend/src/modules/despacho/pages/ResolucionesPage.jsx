import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Download, FileSignature, Plus, Search, X } from "lucide-react";

import {
  anularResolucion, cargarNumeroReal, crearResolucion, descargarWord, editarResolucion,
  firmarResolucion, getModelos, getResolucion, getResoluciones, getSeries,
} from "../../../api/despacho";
import { PermissionGate } from "../../../components/PrivateRoute";
import { useHasPermission } from "../../../context/usePermissions";
import { EditorTexto } from "../components/EditorTexto";

const TIPOS = [["RES", "Resolución"], ["DIS", "Disposición"]];
const nombreTipo = (t) => TIPOS.find(([v]) => v === t)?.[1] || t;
const money = (n) => `$ ${Number(n || 0).toLocaleString("es-AR", { minimumFractionDigits: 2 })}`;
const fecha = (f) => (f ? new Date(`${f}T00:00:00`).toLocaleDateString("es-AR") : "—");
const num = (n) => Number(n || 0).toLocaleString("es-AR");

/** Un acto puede estar en borrador, emitido (firmado o con N° real) o anulado. */
function Estado({ r }) {
  const [texto, clase] = r.anulada ? ["Anulada", "bg-red-100 text-red-700"]
    : r.numero_real ? ["Oficial", "bg-green-100 text-green-700"]
    : r.estado === "F" ? ["Firmada", "bg-blue-100 text-blue-700"]
    : ["Borrador", "bg-gray-100 text-gray-600"];
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${clase}`}>{texto}</span>;
}

const VACIO = { tipo: "RES", serie: 1, asunto: "", organo: "", modelo_id: "", importe: "",
                origen: "", texto: "" };

export default function ResolucionesPage() {
  const puedeEscribir = useHasPermission("despacho", "resoluciones:write");
  const puedeFirmar = useHasPermission("despacho", "resoluciones:firmar");

  const [datos, setDatos] = useState({ items: [], total: 0 });
  const [modelos, setModelos] = useState([]);
  const [series, setSeries] = useState([]);
  const [filtros, setFiltros] = useState({ tipo: "", estado: "", anio: "", serie: "" });
  const [buscar, setBuscar] = useState("");
  const [buscado, setBuscado] = useState(0);
  const [pagina, setPagina] = useState(1);
  const porPagina = 20;
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [detalle, setDetalle] = useState(null);     // resolución abierta
  const [form, setForm] = useState(null);           // alta/edición
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(() => {
    setCargando(true);
    getResoluciones({ tipo: filtros.tipo || undefined, estado: filtros.estado || undefined,
                      anio: filtros.anio || undefined, serie: filtros.serie || undefined,
                      buscar: buscar || undefined, pagina, por_pagina: porPagina })
      .then(setDatos)
      .catch((e) => setError(e?.response?.data?.detail || "No se pudieron cargar las resoluciones"))
      .finally(() => setCargando(false));
  }, [filtros, pagina, buscado]);   // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(cargar, [cargar]);
  useEffect(() => {
    getModelos().then(setModelos).catch(() => {});
    getSeries().then(setSeries).catch(() => {});
  }, []);

  const paginas = Math.max(1, Math.ceil(datos.total / porPagina));

  const abrirNueva = () => { setForm({ ...VACIO, nueva: true }); setError(""); };

  const abrirDetalle = async (id) => {
    try { setDetalle(await getResolucion(id)); }
    catch (e) { setError(e?.response?.data?.detail || "No se pudo abrir"); }
  };

  const editar = (r) => {
    setForm({
      ...r, nueva: false, modelo_id: r.modelo_id || "",
      importe: r.importe ? String(r.importe) : "",
    });
    setDetalle(null);
  };

  const guardar = async () => {
    setError(""); setGuardando(true);
    try {
      const datosEnvio = {
        tipo: form.tipo, serie: Number(form.serie), asunto: form.asunto || null,
        organo: form.organo || null,
        modelo_id: form.modelo_id ? Number(form.modelo_id) : null,
        importe: form.importe === "" ? null : Number(form.importe),
        origen: form.origen || null, texto: form.texto || null,
      };
      const r = form.nueva ? await crearResolucion(datosEnvio)
                           : await editarResolucion(form.id, datosEnvio);
      setForm(null);
      cargar();
      setDetalle(r);
    } catch (e) {
      setError(e?.response?.data?.detail || "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  };

  const accion = async (fn, ...args) => {
    setError("");
    try {
      const r = await fn(...args);
      setDetalle(r);
      cargar();
    } catch (e) {
      setError(e?.response?.data?.detail || "No se pudo completar la acción");
    }
  };

  const bajarWord = async (r) => {
    const blob = await descargarWord(r.id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${r.tipo}_${r.numero_real || r.numero}_${r.anio}.docx`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Resoluciones y disposiciones</h1>
          <p className="text-sm text-gray-500 mt-1 max-w-3xl">
            Los actos administrativos de la Caja. Nacen en borrador con un <strong>número
            correlativo</strong> —que corre por <strong>serie</strong>, o sea por el área que
            emite— y, cuando vuelven firmados, se les carga el <strong>número oficial</strong>. Un
            acto ya emitido no se modifica.
          </p>
        </div>
        <PermissionGate moduleCode="despacho" action="resoluciones:write">
          <button type="button" onClick={abrirNueva}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
            <Plus size={16} /> Nueva
          </button>
        </PermissionGate>
      </div>

      {error && !form && !detalle && (
        <div className="rounded-lg bg-red-50 text-red-700 text-sm px-4 py-3">{error}</div>
      )}

      <form onSubmit={(e) => { e.preventDefault(); setPagina(1); setBuscado((n) => n + 1); }}
            className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input className="input w-full pl-9" placeholder="Buscar por asunto, motivo u origen…"
                 value={buscar} onChange={(e) => setBuscar(e.target.value)} />
        </div>
        <select className="input w-full sm:w-40" value={filtros.tipo} aria-label="Tipo"
                onChange={(e) => { setPagina(1); setFiltros({ ...filtros, tipo: e.target.value }); }}>
          <option value="">Todos</option>
          {TIPOS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <select className="input w-full sm:w-56" value={filtros.serie} aria-label="Serie"
                onChange={(e) => { setPagina(1); setFiltros({ ...filtros, serie: e.target.value }); }}>
          <option value="">Todas las series</option>
          {series.map((s) => <option key={s.serie} value={s.serie}>{s.nombre}</option>)}
        </select>
        <select className="input w-full sm:w-40" value={filtros.estado} aria-label="Estado"
                onChange={(e) => { setPagina(1); setFiltros({ ...filtros, estado: e.target.value }); }}>
          <option value="">Cualquier estado</option>
          <option value="B">Borradores</option>
          <option value="F">Firmadas</option>
          <option value="ANULADA">Anuladas</option>
        </select>
        <input className="input w-full sm:w-28" placeholder="Año" value={filtros.anio}
               aria-label="Año"
               onChange={(e) => { setPagina(1); setFiltros({ ...filtros, anio: e.target.value.replace(/\D/g, "") }); }} />
        <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
          Buscar
        </button>
      </form>

      <div className="bg-surface border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[720px]">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">N°</th>
              <th className="text-left px-4 py-3 font-medium">N° oficial</th>
              <th className="text-left px-4 py-3 font-medium">Tipo</th>
              <th className="text-left px-4 py-3 font-medium">Serie</th>
              <th className="text-left px-4 py-3 font-medium">Fecha</th>
              <th className="text-left px-4 py-3 font-medium">Motivo / asunto</th>
              <th className="text-right px-4 py-3 font-medium">Importe</th>
              <th className="text-left px-4 py-3 font-medium">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {cargando && (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">Cargando…</td></tr>
            )}
            {!cargando && datos.items.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">
                No hay resoluciones con este filtro.
              </td></tr>
            )}
            {datos.items.map((r) => (
              <tr key={r.id} onClick={() => abrirDetalle(r.id)}
                  className="hover:bg-blue-50 cursor-pointer">
                <td className="px-4 py-3 font-medium text-gray-800 tabular-nums">{r.numero}/{r.anio}</td>
                <td className="px-4 py-3 tabular-nums text-gray-600">
                  {r.numero_real ? `${r.numero_real}/${r.anio}` : "—"}
                </td>
                <td className="px-4 py-3 text-gray-600">{nombreTipo(r.tipo)}</td>
                <td className="px-4 py-3 text-gray-600">{r.serie_nombre}</td>
                <td className="px-4 py-3 text-gray-600">{fecha(r.fecha)}</td>
                <td className="px-4 py-3 text-gray-700">{r.motivo || r.asunto}</td>
                <td className="px-4 py-3 text-right tabular-nums">{money(r.importe)}</td>
                <td className="px-4 py-3"><Estado r={r} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-gray-500 tabular-nums">{num(datos.total)} resolución(es)</p>
        <div className="flex items-center gap-1">
          <button type="button" aria-label="Página anterior" disabled={pagina <= 1 || cargando}
                  onClick={() => setPagina((p) => Math.max(1, p - 1))}
                  className="p-2 rounded-lg border border-gray-300 text-gray-600 enabled:hover:bg-gray-50 disabled:opacity-40">
            <ChevronLeft size={16} />
          </button>
          <span className="text-sm text-gray-600 tabular-nums px-2">{pagina} de {num(paginas)}</span>
          <button type="button" aria-label="Página siguiente" disabled={pagina >= paginas || cargando}
                  onClick={() => setPagina((p) => Math.min(paginas, p + 1))}
                  className="p-2 rounded-lg border border-gray-300 text-gray-600 enabled:hover:bg-gray-50 disabled:opacity-40">
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {/* ── Detalle ── */}
      {detalle && (
        <Modal titulo={`${nombreTipo(detalle.tipo)} N° ${detalle.numero}/${detalle.anio}`}
               onCerrar={() => setDetalle(null)}>
          {error && <div className="rounded-lg bg-red-50 text-red-700 text-sm px-4 py-3 mb-3">{error}</div>}

          <dl className="grid grid-cols-1 sm:grid-cols-3 gap-x-6 gap-y-2 text-sm mb-4">
            <Dato label="Estado"><Estado r={detalle} /></Dato>
            <Dato label="N° oficial">
              {detalle.numero_real ? `${detalle.numero_real}/${detalle.anio} (${fecha(detalle.fecha_real)})` : "sin cargar"}
            </Dato>
            <Dato label="Fecha">{fecha(detalle.fecha)}</Dato>
            <Dato label="Serie">{detalle.serie_nombre}</Dato>
            <Dato label="Motivo">{detalle.motivo || "—"}</Dato>
            <Dato label="Órgano">{detalle.organo || "—"}</Dato>
            <Dato label="Importe">{money(detalle.importe)}</Dato>
            <Dato label="Origen">{detalle.origen || "—"}</Dato>
            <Dato label="Creada por">{detalle.creado_por || "—"}</Dato>
          </dl>

          {detalle.anulada && (
            <div className="rounded-lg bg-red-50 text-red-700 text-sm px-4 py-3 mb-3">
              Anulada: {detalle.motivo_anulacion}
            </div>
          )}

          <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 mb-4 max-h-72 overflow-auto"
               dangerouslySetInnerHTML={{ __html: detalle.texto || "<p class='text-gray-400'>Sin texto</p>" }} />

          {detalle.beneficiarios?.length > 0 && (
            <div className="mb-4">
              <p className="text-sm font-medium text-gray-700 mb-1">
                Beneficiarios ({detalle.beneficiarios.length})
              </p>
              <ul className="text-sm text-gray-600 divide-y divide-gray-100 border border-gray-200 rounded-lg">
                {detalle.beneficiarios.map((b) => (
                  <li key={b.id} className="flex justify-between px-3 py-1.5">
                    <span>{b.nombre} <span className="text-gray-400 text-xs">{b.nro_doc}</span></span>
                    <span className="tabular-nums">{money(b.importe)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-wrap gap-2 justify-end">
            <button type="button" onClick={() => bajarWord(detalle)}
                    className="inline-flex items-center gap-2 px-3 py-2 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
              <Download size={15} /> Word
            </button>
            {!detalle.anulada && detalle.estado === "B" && puedeEscribir && (
              <button type="button" onClick={() => editar(detalle)}
                      className="px-3 py-2 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
                Editar
              </button>
            )}
            {!detalle.anulada && detalle.estado === "B" && puedeFirmar && (
              <button type="button" onClick={() => accion(firmarResolucion, detalle.id)}
                      className="inline-flex items-center gap-2 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                <FileSignature size={15} /> Firmar
              </button>
            )}
            {!detalle.anulada && !detalle.numero_real && puedeFirmar && (
              <button type="button" onClick={() => accion(cargarNumeroReal, detalle.id, null)}
                      className="px-3 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700">
                Cargar N° oficial
              </button>
            )}
            {!detalle.anulada && puedeFirmar && (
              <button type="button"
                      onClick={() => {
                        const motivo = window.prompt("Motivo de la anulación:");
                        if (motivo) accion(anularResolucion, detalle.id, motivo);
                      }}
                      className="px-3 py-2 text-sm border border-red-300 text-red-600 rounded-lg hover:bg-red-50">
                Anular
              </button>
            )}
          </div>
        </Modal>
      )}

      {/* ── Alta / edición ── */}
      {form && (
        <Modal titulo={form.nueva ? "Nueva resolución o disposición"
                                  : `Editar N° ${form.numero}/${form.anio}`}
               onCerrar={() => setForm(null)}>
          {error && <div className="rounded-lg bg-red-50 text-red-700 text-sm px-4 py-3 mb-3">{error}</div>}

          <div className="grid gap-4 sm:grid-cols-2 mb-4">
            {form.nueva && (
              <>
                <label className="flex flex-col gap-1 text-sm">
                  <span className="text-gray-500">Tipo</span>
                  <select className="input" value={form.tipo} aria-label="Tipo del acto"
                          onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
                    {TIPOS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </label>
                <label className="flex flex-col gap-1 text-sm">
                  <span className="text-gray-500">Serie (numeración)</span>
                  <select className="input" value={form.serie} aria-label="Serie del acto"
                          onChange={(e) => setForm({ ...form, serie: Number(e.target.value),
                                                     modelo_id: "" })}>
                    {series.map((s) => <option key={s.serie} value={s.serie}>{s.nombre}</option>)}
                  </select>
                </label>
              </>
            )}
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-gray-500">Modelo a utilizar</span>
              <select className="input" value={form.modelo_id} aria-label="Modelo a utilizar"
                      onChange={(e) => {
                        const m = modelos.find((x) => String(x.id) === e.target.value);
                        setForm({ ...form, modelo_id: e.target.value,
                                  // Al elegir modelo se ofrece su plantilla, si todavía no se escribió nada.
                                  texto: form.texto?.trim() ? form.texto : (m?.plantilla || "") });
                      }}>
                <option value="">(sin modelo)</option>
                {modelos.filter((m) => m.tipo === form.tipo && m.serie === Number(form.serie)).map((m) => (
                  <option key={m.id} value={m.id}>{m.codigo} · {m.descripcion}</option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-gray-500">Asunto</span>
              <input className="input" value={form.asunto || ""} maxLength={200} aria-label="Asunto"
                     onChange={(e) => setForm({ ...form, asunto: e.target.value })} />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-gray-500">Órgano</span>
              <input className="input" value={form.organo || ""} maxLength={60} aria-label="Órgano"
                     onChange={(e) => setForm({ ...form, organo: e.target.value })} />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-gray-500">Importe</span>
              <input className="input" inputMode="decimal" value={form.importe} aria-label="Importe"
                     onChange={(e) => setForm({ ...form, importe: e.target.value.replace(/[^\d.,]/g, "").replace(",", ".") })} />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-gray-500">Expediente / nota de origen</span>
              <input className="input" value={form.origen || ""} maxLength={40} aria-label="Origen"
                     onChange={(e) => setForm({ ...form, origen: e.target.value })} />
            </label>
          </div>

          <p className="text-sm text-gray-500 mb-1">Texto del instrumento</p>
          <EditorTexto value={form.texto} label="Texto del instrumento"
                       onChange={(html) => setForm({ ...form, texto: html })} />

          <div className="flex justify-end gap-2 mt-4">
            <button type="button" onClick={() => setForm(null)}
                    className="px-4 py-2 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
              Cancelar
            </button>
            <button type="button" onClick={guardar} disabled={guardando}
                    className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
              {guardando ? "Guardando…" : "Guardar"}
            </button>
          </div>
        </Modal>
      )}
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

function Modal({ titulo, onCerrar, children }) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
      <div className="bg-surface rounded-xl w-full max-w-3xl max-h-[90vh] overflow-auto">
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 sticky top-0 bg-surface">
          <h2 className="font-semibold text-gray-800">{titulo}</h2>
          <button type="button" aria-label="Cerrar" onClick={onCerrar}
                  className="p-1 text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}
