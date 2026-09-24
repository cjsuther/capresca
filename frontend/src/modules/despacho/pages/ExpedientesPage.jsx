import { useCallback, useEffect, useState } from "react";
import { Archive, ArrowRight, Plus, Search, X } from "lucide-react";

import {
  archivarExpediente, crearExpediente, getExpediente, getExpedientes,
  getExpedientesPorOficina, pasarExpediente,
} from "../../../api/despacho";
import { PermissionGate } from "../../../components/PrivateRoute";
import { useHasPermission } from "../../../context/usePermissions";

const fecha = (f) => (f ? new Date(`${f}T00:00:00`).toLocaleDateString("es-AR") : "—");
const hoyISO = () => new Date().toISOString().slice(0, 10);

const VACIO = { numero: "", caratula: "", iniciador: "", fecha_inicio: hoyISO(), oficina: "" };

export default function ExpedientesPage() {
  const puedeEscribir = useHasPermission("despacho", "expedientes:write");

  const [items, setItems] = useState([]);
  const [tablero, setTablero] = useState([]);
  const [estado, setEstado] = useState("T");
  const [oficina, setOficina] = useState("");
  const [buscar, setBuscar] = useState("");
  const [buscado, setBuscado] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [detalle, setDetalle] = useState(null);
  const [alta, setAlta] = useState(null);
  const [pase, setPase] = useState(null);        // { oficina_destino, motivo, fecha }

  const cargar = useCallback(() => {
    setCargando(true);
    getExpedientes({ estado: estado || undefined, oficina: oficina || undefined,
                     buscar: buscar || undefined })
      .then(setItems)
      .catch((e) => setError(e?.response?.data?.detail || "No se pudieron cargar los expedientes"))
      .finally(() => setCargando(false));
  }, [estado, oficina, buscado]);   // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(cargar, [cargar]);
  useEffect(() => { getExpedientesPorOficina().then(setTablero).catch(() => {}); }, [items]);

  const abrir = async (id) => {
    setError("");
    try { setDetalle(await getExpediente(id)); }
    catch (e) { setError(e?.response?.data?.detail || "No se pudo abrir"); }
  };

  const guardarAlta = async () => {
    setError("");
    try {
      const e = await crearExpediente(alta);
      setAlta(null);
      cargar();
      setDetalle(e);
    } catch (e) {
      setError(e?.response?.data?.detail || "No se pudo crear el expediente");
    }
  };

  const guardarPase = async () => {
    setError("");
    try {
      setDetalle(await pasarExpediente(detalle.id, pase));
      setPase(null);
      cargar();
    } catch (e) {
      setError(e?.response?.data?.detail || "No se pudo registrar el pase");
    }
  };

  const archivar = async () => {
    setError("");
    try {
      setDetalle(await archivarExpediente(detalle.id));
      cargar();
    } catch (e) {
      setError(e?.response?.data?.detail || "No se pudo archivar");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Expedientes y pases</h1>
          <p className="text-sm text-gray-500 mt-1 max-w-3xl">
            El recorrido de cada trámite por las oficinas. Los pases quedan registrados: no se editan
            ni se borran.
          </p>
        </div>
        <PermissionGate moduleCode="despacho" action="expedientes:write">
          <button type="button" onClick={() => { setAlta({ ...VACIO }); setError(""); }}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
            <Plus size={16} /> Nuevo expediente
          </button>
        </PermissionGate>
      </div>

      {error && !detalle && !alta && (
        <div className="rounded-lg bg-red-50 text-red-700 text-sm px-4 py-3">{error}</div>
      )}

      {tablero.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {tablero.map((t) => (
            <button key={t.oficina} type="button"
                    onClick={() => setOficina(oficina === t.oficina ? "" : t.oficina)}
                    className={`px-3 py-1.5 rounded-lg text-sm border ${
                      oficina === t.oficina ? "border-blue-500 bg-blue-50 text-blue-700"
                                            : "border-gray-300 text-gray-600 hover:bg-gray-50"}`}>
              {t.oficina} <span className="tabular-nums text-gray-400">· {t.cantidad}</span>
            </button>
          ))}
        </div>
      )}

      <form onSubmit={(e) => { e.preventDefault(); setBuscado((n) => n + 1); }}
            className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input className="input w-full pl-9" placeholder="Buscar por número, carátula o iniciador…"
                 value={buscar} onChange={(e) => setBuscar(e.target.value)} />
        </div>
        <select className="input w-full sm:w-44" value={estado} aria-label="Estado"
                onChange={(e) => setEstado(e.target.value)}>
          <option value="T">En trámite</option>
          <option value="A">Archivados</option>
          <option value="">Todos</option>
        </select>
        <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
          Buscar
        </button>
      </form>

      <div className="bg-surface border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Número</th>
              <th className="text-left px-4 py-3 font-medium">Carátula</th>
              <th className="text-left px-4 py-3 font-medium">Iniciador</th>
              <th className="text-left px-4 py-3 font-medium">Inicio</th>
              <th className="text-left px-4 py-3 font-medium">Oficina</th>
              <th className="text-left px-4 py-3 font-medium">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {cargando && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Cargando…</td></tr>
            )}
            {!cargando && items.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                No hay expedientes con este filtro.
              </td></tr>
            )}
            {items.map((e) => (
              <tr key={e.id} onClick={() => abrir(e.id)} className="hover:bg-blue-50 cursor-pointer">
                <td className="px-4 py-3 font-medium text-gray-800">{e.numero}</td>
                <td className="px-4 py-3 text-gray-700">{e.caratula}</td>
                <td className="px-4 py-3 text-gray-600">{e.iniciador || "—"}</td>
                <td className="px-4 py-3 text-gray-600">{fecha(e.fecha_inicio)}</td>
                <td className="px-4 py-3 text-gray-600">{e.oficina_actual || "—"}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    e.estado === "A" ? "bg-gray-100 text-gray-600" : "bg-blue-100 text-blue-700"}`}>
                    {e.estado === "A" ? "Archivado" : "En trámite"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Detalle con la historia de pases ── */}
      {detalle && (
        <Modal titulo={`Expediente ${detalle.numero}`} onCerrar={() => { setDetalle(null); setPase(null); }}>
          {error && <div className="rounded-lg bg-red-50 text-red-700 text-sm px-4 py-3 mb-3">{error}</div>}

          <p className="text-gray-800 font-medium">{detalle.caratula}</p>
          <p className="text-sm text-gray-500 mb-4">
            Iniciador: {detalle.iniciador || "—"} · Inicio: {fecha(detalle.fecha_inicio)} ·
            Oficina actual: <strong>{detalle.oficina_actual || "—"}</strong>
          </p>

          <p className="text-sm font-medium text-gray-700 mb-1">Pases</p>
          <ol className="border border-gray-200 rounded-lg divide-y divide-gray-100 text-sm mb-4">
            {detalle.pases?.map((p) => (
              <li key={p.id} className="px-3 py-2 flex flex-wrap items-center gap-2">
                <span className="text-gray-500 tabular-nums w-24">{fecha(p.fecha)}</span>
                <span className="text-gray-600">{p.oficina_origen || "—"}</span>
                <ArrowRight size={14} className="text-gray-400" />
                <span className="text-gray-800 font-medium">{p.oficina_destino}</span>
                {p.motivo && <span className="text-gray-500">· {p.motivo}</span>}
                {p.usuario && <span className="text-xs text-gray-400 ml-auto">{p.usuario}</span>}
              </li>
            ))}
          </ol>

          {pase && (
            <div className="grid gap-3 sm:grid-cols-3 border border-gray-200 rounded-lg p-3 mb-4">
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-gray-500">Oficina destino</span>
                <input className="input" value={pase.oficina_destino} aria-label="Oficina destino"
                       onChange={(e) => setPase({ ...pase, oficina_destino: e.target.value })} />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-gray-500">Fecha</span>
                <input type="date" className="input" value={pase.fecha} aria-label="Fecha del pase"
                       onChange={(e) => setPase({ ...pase, fecha: e.target.value })} />
              </label>
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-gray-500">Motivo</span>
                <input className="input" value={pase.motivo} aria-label="Motivo del pase"
                       onChange={(e) => setPase({ ...pase, motivo: e.target.value })} />
              </label>
            </div>
          )}

          <div className="flex flex-wrap gap-2 justify-end">
            {puedeEscribir && detalle.estado !== "A" && (
              pase ? (
                <>
                  <button type="button" onClick={() => setPase(null)}
                          className="px-3 py-2 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
                    Cancelar
                  </button>
                  <button type="button" onClick={guardarPase} disabled={!pase.oficina_destino.trim()}
                          className="px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
                    Registrar pase
                  </button>
                </>
              ) : (
                <>
                  <button type="button"
                          onClick={() => setPase({ oficina_destino: "", motivo: "", fecha: hoyISO() })}
                          className="inline-flex items-center gap-2 px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                    <ArrowRight size={15} /> Pasar a otra oficina
                  </button>
                  <button type="button" onClick={archivar}
                          className="inline-flex items-center gap-2 px-3 py-2 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
                    <Archive size={15} /> Archivar
                  </button>
                </>
              )
            )}
          </div>
        </Modal>
      )}

      {/* ── Alta ── */}
      {alta && (
        <Modal titulo="Nuevo expediente" onCerrar={() => setAlta(null)}>
          {error && <div className="rounded-lg bg-red-50 text-red-700 text-sm px-4 py-3 mb-3">{error}</div>}
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-gray-500">Número <span className="text-red-500">*</span></span>
              <input className="input" value={alta.numero} maxLength={20} aria-label="Número"
                     onChange={(e) => setAlta({ ...alta, numero: e.target.value })} />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-gray-500">Fecha de inicio</span>
              <input type="date" className="input" value={alta.fecha_inicio} aria-label="Fecha de inicio"
                     onChange={(e) => setAlta({ ...alta, fecha_inicio: e.target.value })} />
            </label>
            <label className="flex flex-col gap-1 text-sm sm:col-span-2">
              <span className="text-gray-500">Carátula <span className="text-red-500">*</span></span>
              <input className="input" value={alta.caratula} maxLength={200} aria-label="Carátula"
                     onChange={(e) => setAlta({ ...alta, caratula: e.target.value })} />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-gray-500">Iniciador</span>
              <input className="input" value={alta.iniciador} maxLength={80} aria-label="Iniciador"
                     onChange={(e) => setAlta({ ...alta, iniciador: e.target.value })} />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-gray-500">Oficina inicial</span>
              <input className="input" value={alta.oficina} maxLength={60} aria-label="Oficina inicial"
                     onChange={(e) => setAlta({ ...alta, oficina: e.target.value })} />
            </label>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <button type="button" onClick={() => setAlta(null)}
                    className="px-4 py-2 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
              Cancelar
            </button>
            <button type="button" onClick={guardarAlta}
                    className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              Guardar
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Modal({ titulo, onCerrar, children }) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
      <div className="bg-surface rounded-xl w-full max-w-2xl max-h-[90vh] overflow-auto">
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
