import { useState, useEffect, useCallback, Fragment } from "react";
import { ArrowDownToLine, ArrowUpFromLine, ChevronDown, ChevronRight, RefreshCw } from "lucide-react";
import { getInteractions, getDatabases } from "../../../api/legacy";

const DIRECTIONS = [
  { value: "", label: "Todas" },
  { value: "IN", label: "IN (lectura)" },
  { value: "OUT", label: "OUT (escritura)" },
];

const STATUSES = [
  { value: "", label: "Todos" },
  { value: "OK", label: "OK" },
  { value: "ERROR", label: "ERROR" },
  { value: "SKIPPED", label: "SKIPPED" },
];

function DirectionBadge({ direction }) {
  if (direction === "IN") {
    return (
      <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium bg-sky-100 text-sky-700">
        <ArrowDownToLine size={12} /> IN
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium bg-violet-100 text-violet-700">
      <ArrowUpFromLine size={12} /> OUT
    </span>
  );
}

function StatusBadge({ status }) {
  const styles = {
    OK: "bg-green-100 text-green-700",
    ERROR: "bg-red-100 text-red-700",
    SKIPPED: "bg-gray-100 text-gray-600",
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${styles[status] || "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}

const fmtDateTime = (s) => (s ? new Date(s).toLocaleString("es-AR") : "—");

export default function InteraccionesPage() {
  const today = new Date().toISOString().slice(0, 10);
  const [filters, setFilters] = useState({
    date_from: today,
    date_to: today,
    database: "",
    direction: "",
    table: "",
    status: "",
  });
  const [databases, setDatabases] = useState([]);
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: 50 });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    getDatabases()
      .then((d) => setDatabases(d.databases || []))
      .catch(() => setDatabases([]));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = { page, page_size: 50 };
      Object.entries(filters).forEach(([k, v]) => {
        if (v) params[k] = v;
      });
      const res = await getInteractions(params);
      setData(res);
    } catch (e) {
      setError(e.response?.data?.detail || "Error al cargar interacciones");
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    load();
  }, [load]);

  const setF = (k, v) => {
    setPage(1);
    setFilters((prev) => ({ ...prev, [k]: v }));
  };

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  return (
    <div className="p-4 md:p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-800">Interacciones con el legacy</h1>
          <p className="text-sm text-gray-500">Registro de lecturas (IN) y escrituras (OUT) hacia el sistema VFP9.</p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 text-sm px-3 py-2 rounded-lg border border-gray-300 hover:bg-gray-50 text-gray-700"
        >
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} /> Actualizar
        </button>
      </div>

      {/* Filtros */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 mb-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3">
        <Field label="Desde">
          <input type="date" value={filters.date_from} onChange={(e) => setF("date_from", e.target.value)} className={inputCls} />
        </Field>
        <Field label="Hasta">
          <input type="date" value={filters.date_to} onChange={(e) => setF("date_to", e.target.value)} className={inputCls} />
        </Field>
        <Field label="Base de datos">
          <select value={filters.database} onChange={(e) => setF("database", e.target.value)} className={inputCls}>
            <option value="">Todas</option>
            {databases.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </Field>
        <Field label="Dirección">
          <select value={filters.direction} onChange={(e) => setF("direction", e.target.value)} className={inputCls}>
            {DIRECTIONS.map((d) => (
              <option key={d.value} value={d.value}>{d.label}</option>
            ))}
          </select>
        </Field>
        <Field label="Tabla">
          <input type="text" placeholder="ej. cajaliq" value={filters.table} onChange={(e) => setF("table", e.target.value)} className={inputCls} />
        </Field>
        <Field label="Estado">
          <select value={filters.status} onChange={(e) => setF("status", e.target.value)} className={inputCls}>
            {STATUSES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </Field>
      </div>

      {error && <div className="mb-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">{error}</div>}

      {/* Tabla */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
              <tr>
                <th className="w-8" />
                <th className="text-left px-3 py-2">Fecha / hora</th>
                <th className="text-left px-3 py-2">Dir.</th>
                <th className="text-left px-3 py-2">Base</th>
                <th className="text-left px-3 py-2">Tabla</th>
                <th className="text-left px-3 py-2">Operación</th>
                <th className="text-right px-3 py-2">Filas</th>
                <th className="text-left px-3 py-2">Estado</th>
                <th className="text-right px-3 py-2">Latencia</th>
                <th className="text-left px-3 py-2">Origen</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.items.length === 0 && !loading && (
                <tr>
                  <td colSpan={10} className="px-3 py-8 text-center text-gray-400">
                    No hay interacciones para los filtros seleccionados.
                  </td>
                </tr>
              )}
              {data.items.map((it) => (
                <Fragment key={it.id}>
                  <tr className="hover:bg-gray-50 cursor-pointer" onClick={() => setExpanded(expanded === it.id ? null : it.id)}>
                    <td className="px-2 text-gray-400">{expanded === it.id ? <ChevronDown size={16} /> : <ChevronRight size={16} />}</td>
                    <td className="px-3 py-2 whitespace-nowrap text-gray-700">{fmtDateTime(it.occurred_at)}</td>
                    <td className="px-3 py-2"><DirectionBadge direction={it.direction} /></td>
                    <td className="px-3 py-2 text-gray-700">{it.database}</td>
                    <td className="px-3 py-2 font-mono text-xs text-gray-700">{it.table_name}</td>
                    <td className="px-3 py-2 text-gray-700">{it.operation}</td>
                    <td className="px-3 py-2 text-right text-gray-700">{it.rows_affected ?? "—"}</td>
                    <td className="px-3 py-2"><StatusBadge status={it.status} /></td>
                    <td className="px-3 py-2 text-right text-gray-500">{it.latency_ms != null ? `${it.latency_ms} ms` : "—"}</td>
                    <td className="px-3 py-2 text-gray-500">{it.origin_module || "—"}</td>
                  </tr>
                  {expanded === it.id && (
                    <tr className="bg-gray-50">
                      <td />
                      <td colSpan={9} className="px-3 py-3">
                        {it.error_message && (
                          <div className="text-sm text-red-600 mb-2"><strong>Error:</strong> {it.error_message}</div>
                        )}
                        {it.outbox_id && (
                          <div className="text-xs text-gray-600 mb-2">outbox_id: {it.outbox_id}</div>
                        )}
                        <div className="text-xs text-gray-500 mb-1">payload_summary:</div>
                        <pre className="text-xs bg-white border border-gray-200 rounded p-2 overflow-x-auto">
                          {JSON.stringify(it.payload_summary ?? {}, null, 2)}
                        </pre>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>

        {/* Paginación */}
        <div className="flex items-center justify-between px-3 py-2 border-t border-gray-100 text-sm text-gray-600">
          <span>{data.total} interacciones</span>
          <div className="flex items-center gap-2">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="px-2 py-1 rounded border border-gray-300 disabled:opacity-40">Anterior</button>
            <span>Página {page} de {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} className="px-2 py-1 rounded border border-gray-300 disabled:opacity-40">Siguiente</button>
          </div>
        </div>
      </div>
    </div>
  );
}

const inputCls = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-200";

function Field({ label, children }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-medium text-gray-500">{label}</span>
      {children}
    </label>
  );
}
