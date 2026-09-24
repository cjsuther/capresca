import { useCallback, useEffect, useState } from "react";
import { FileText, Pencil, Plus, Search, X } from "lucide-react";

import { crearModelo, editarModelo, getModelos, getSeries } from "../../../api/despacho";
import { PermissionGate } from "../../../components/PrivateRoute";
import { useHasPermission } from "../../../context/usePermissions";
import { EditorTexto } from "../components/EditorTexto";

const TIPOS = [["RES", "Resolución"], ["DIS", "Disposición"]];
const nombreTipo = (t) => TIPOS.find(([v]) => v === t)?.[1] || t;

const VACIO = { descripcion: "", tipo: "RES", serie: 1, es_seguros: false, plantilla: "",
                activo: true };

export default function ModelosPage() {
  const puedeEditar = useHasPermission("despacho", "modelos:write");
  const [items, setItems] = useState([]);
  const [series, setSeries] = useState([]);
  const [serie, setSerie] = useState("");
  const [tipo, setTipo] = useState("");
  const [buscar, setBuscar] = useState("");
  const [incluirInactivos, setIncluirInactivos] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [editando, setEditando] = useState(null);   // null = modal cerrado
  const [form, setForm] = useState(VACIO);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(() => {
    setCargando(true);
    getModelos({ tipo: tipo || undefined, buscar: buscar || undefined,
                 serie: serie || undefined, incluir_inactivos: incluirInactivos })
      .then(setItems)
      .catch((e) => setError(e?.response?.data?.detail || "No se pudieron cargar los modelos"))
      .finally(() => setCargando(false));
  }, [tipo, serie, incluirInactivos]);   // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(cargar, [cargar]);
  useEffect(() => { getSeries().then(setSeries).catch(() => {}); }, []);

  const abrir = (m) => {
    setEditando(m || { nuevo: true });
    setForm(m ? { ...m } : { ...VACIO });
    setError("");
  };

  const guardar = async () => {
    setError(""); setGuardando(true);
    try {
      const datos = { descripcion: form.descripcion, tipo: form.tipo, serie: Number(form.serie),
                      es_seguros: form.es_seguros, plantilla: form.plantilla, activo: form.activo };
      if (editando.nuevo) await crearModelo(datos);
      else await editarModelo(editando.id, datos);
      setEditando(null);
      cargar();
    } catch (e) {
      setError(e?.response?.data?.detail || "No se pudo guardar el modelo");
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Modelo de resoluciones</h1>
          <p className="text-sm text-gray-500 mt-1 max-w-3xl">
            Las plantillas con las que se redactan las resoluciones y disposiciones. Al elegir un
            modelo, su descripción pasa a ser el <strong>motivo</strong> del acto y su texto, el
            cuerpo inicial que después se edita. Cada <strong>serie</strong> tiene su propio juego
            de modelos: el mismo código significa una cosa distinta en cada una.
          </p>
        </div>
        <PermissionGate moduleCode="despacho" action="modelos:write">
          <button type="button" onClick={() => abrir(null)}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
            <Plus size={16} /> Nuevo modelo
          </button>
        </PermissionGate>
      </div>

      {error && !editando && (
        <div className="rounded-lg bg-red-50 text-red-700 text-sm px-4 py-3">{error}</div>
      )}

      <form onSubmit={(e) => { e.preventDefault(); cargar(); }} className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input className="input w-full pl-9" placeholder="Buscar por descripción…"
                 value={buscar} onChange={(e) => setBuscar(e.target.value)} />
        </div>
        <select className="input w-full sm:w-56" value={serie} aria-label="Serie"
                onChange={(e) => setSerie(e.target.value)}>
          <option value="">Todas las series</option>
          {series.map((s) => <option key={s.serie} value={s.serie}>{s.nombre}</option>)}
        </select>
        <select className="input w-full sm:w-44" value={tipo} aria-label="Tipo"
                onChange={(e) => setTipo(e.target.value)}>
          <option value="">Todos los tipos</option>
          {TIPOS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input type="checkbox" checked={incluirInactivos}
                 onChange={(e) => setIncluirInactivos(e.target.checked)} />
          Ver inactivos
        </label>
        <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
          Buscar
        </button>
      </form>

      <div className="bg-surface border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[560px]">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Código</th>
              <th className="text-left px-4 py-3 font-medium">Serie</th>
              <th className="text-left px-4 py-3 font-medium">Descripción (motivo)</th>
              <th className="text-left px-4 py-3 font-medium">Tipo</th>
              <th className="text-left px-4 py-3 font-medium">Texto</th>
              <th className="text-left px-4 py-3 font-medium">Estado</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {cargando && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Cargando…</td></tr>
            )}
            {!cargando && items.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                No hay modelos cargados.
              </td></tr>
            )}
            {items.map((m) => (
              <tr key={m.id} className="hover:bg-blue-50/40">
                <td className="px-4 py-3 font-mono text-xs text-gray-500">{m.codigo}</td>
                <td className="px-4 py-3 text-gray-600">{m.serie_nombre}</td>
                <td className="px-4 py-3 font-medium text-gray-800">
                  {m.descripcion}
                  {m.es_seguros && (
                    <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700">
                      seguros
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-600">{nombreTipo(m.tipo)}</td>
                <td className="px-4 py-3">
                  {m.tiene_plantilla
                    ? <span className="inline-flex items-center gap-1 text-xs text-green-700">
                        <FileText size={13} /> con texto
                      </span>
                    : <span className="text-xs text-gray-400">sin texto</span>}
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${m.activo ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                    {m.activo ? "Activo" : "Inactivo"}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  {puedeEditar && (
                    <button type="button" aria-label={`Editar ${m.descripcion}`} onClick={() => abrir(m)}
                            className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg">
                      <Pencil size={14} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editando && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
          <div className="bg-surface rounded-xl w-full max-w-3xl max-h-[90vh] overflow-auto">
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200">
              <h2 className="font-semibold text-gray-800">
                {editando.nuevo ? "Nuevo modelo" : `Modelo ${editando.codigo}`}
              </h2>
              <button type="button" aria-label="Cerrar" onClick={() => setEditando(null)}
                      className="p-1 text-gray-400 hover:text-gray-600">
                <X size={18} />
              </button>
            </div>

            <div className="p-5 space-y-4">
              {error && <div className="rounded-lg bg-red-50 text-red-700 text-sm px-4 py-3">{error}</div>}

              <div className="grid gap-4 sm:grid-cols-2">
                <label className="flex flex-col gap-1 text-sm">
                  <span className="text-gray-500">Descripción (será el motivo) <span className="text-red-500">*</span></span>
                  <input className="input" value={form.descripcion} maxLength={120}
                         aria-label="Descripción"
                         onChange={(e) => setForm({ ...form, descripcion: e.target.value })} />
                </label>
                <label className="flex flex-col gap-1 text-sm">
                  <span className="text-gray-500">Tipo</span>
                  <select className="input" value={form.tipo} aria-label="Tipo del modelo"
                          onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
                    {TIPOS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </label>
                <label className="flex flex-col gap-1 text-sm">
                  <span className="text-gray-500">Serie</span>
                  <select className="input" value={form.serie} aria-label="Serie del modelo"
                          onChange={(e) => setForm({ ...form, serie: Number(e.target.value) })}>
                    {series.map((s) => <option key={s.serie} value={s.serie}>{s.nombre}</option>)}
                  </select>
                </label>
              </div>

              <div className="flex flex-wrap gap-5">
                <label className="flex items-center gap-2 text-sm text-gray-600">
                  <input type="checkbox" checked={!!form.es_seguros}
                         onChange={(e) => setForm({ ...form, es_seguros: e.target.checked })} />
                  Es de seguros
                </label>
                <label className="flex items-center gap-2 text-sm text-gray-600">
                  <input type="checkbox" checked={form.activo !== false}
                         onChange={(e) => setForm({ ...form, activo: e.target.checked })} />
                  Activo
                </label>
              </div>

              <div>
                <p className="text-sm text-gray-500 mb-1">Texto de la plantilla</p>
                <EditorTexto value={form.plantilla} label="Texto de la plantilla"
                             onChange={(html) => setForm({ ...form, plantilla: html })} />
              </div>
            </div>

            <div className="flex justify-end gap-2 px-5 py-3 border-t border-gray-200">
              <button type="button" onClick={() => setEditando(null)}
                      className="px-4 py-2 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
                Cancelar
              </button>
              <button type="button" onClick={guardar} disabled={guardando}
                      className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
                {guardando ? "Guardando…" : "Guardar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
