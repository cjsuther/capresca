import { useEffect, useState } from "react";
import { getAuditoria, exportAuditoria } from "../../../api/interbanking";
import { Download, ChevronDown, ChevronUp } from "lucide-react";

export default function AuditoriaPage() {
  const [data, setData] = useState({ data: [], total: 0 });
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ user_id: "", operation: "", success: "", date_from: "", date_to: "" });
  const [page, setPage] = useState(1);
  const [detailId, setDetailId] = useState(null);
  const [modal, setModal] = useState(null);

  const OPERATIONS = [
    "OBTENER_TOKEN", "LISTAR_CUENTAS", "CONSULTAR_SALDO",
    "VALIDAR_CBU", "INICIAR_TRANSFERENCIA", "ESTADO_TRANSFERENCIA",
    "PROCESAR_LOTE", "ESTADO_LOTE",
  ];

  const load = () => {
    setLoading(true);
    const params = { page, per_page: 50, ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== "")) };
    getAuditoria(params)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [page]);

  const handleExport = async () => {
    const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== ""));
    const resp = await exportAuditoria(params);
    const url = window.URL.createObjectURL(resp.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = "auditoria.csv";
    a.click();
    window.URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-800">Auditoría</h2>
        <button
          onClick={handleExport}
          className="flex items-center gap-2 px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50"
        >
          <Download size={15} /> Exportar CSV
        </button>
      </div>

      {/* Filtros */}
      <div className="bg-white border rounded-xl p-4 mb-4">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Usuario ID</label>
            <input className="input w-full text-sm" placeholder="ID numérico" value={filters.user_id} onChange={(e) => setFilters({ ...filters, user_id: e.target.value })} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Operación</label>
            <select className="input w-full text-sm" value={filters.operation} onChange={(e) => setFilters({ ...filters, operation: e.target.value })}>
              <option value="">Todas</option>
              {OPERATIONS.map((op) => <option key={op} value={op}>{op}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Resultado</label>
            <select className="input w-full text-sm" value={filters.success} onChange={(e) => setFilters({ ...filters, success: e.target.value })}>
              <option value="">Todos</option>
              <option value="true">Éxito</option>
              <option value="false">Error</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Desde</label>
            <input type="date" className="input w-full text-sm" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Hasta</label>
            <input type="date" className="input w-full text-sm" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} />
          </div>
        </div>
        <div className="flex justify-end mt-3">
          <button onClick={() => { setPage(1); load(); }} className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            Filtrar
          </button>
        </div>
      </div>

      {/* Tabla */}
      <div className="bg-white border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[720px]">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Fecha/Hora</th>
              <th className="text-left px-4 py-3 font-medium">Usuario</th>
              <th className="text-left px-4 py-3 font-medium">Operación</th>
              <th className="text-left px-4 py-3 font-medium">Endpoint</th>
              <th className="text-left px-4 py-3 font-medium">Status</th>
              <th className="text-right px-4 py-3 font-medium">ms</th>
              <th className="text-left px-4 py-3 font-medium">Resultado</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">Cargando...</td></tr>
            ) : data.data.length === 0 ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">Sin registros</td></tr>
            ) : data.data.map((entry) => (
              <tr key={entry.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => setModal(entry)}>
                <td className="px-4 py-3 text-xs text-gray-500">{new Date(entry.created_at).toLocaleString()}</td>
                <td className="px-4 py-3">{entry.username || entry.user_id}</td>
                <td className="px-4 py-3 font-mono text-xs">{entry.operation}</td>
                <td className="px-4 py-3 text-gray-500 text-xs truncate max-w-xs">{entry.endpoint}</td>
                <td className="px-4 py-3">{entry.response_status || "—"}</td>
                <td className="px-4 py-3 text-right text-gray-500">{entry.duration_ms ?? "—"}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${entry.success ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
                    {entry.success ? "Éxito" : "Error"}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-400"><ChevronDown size={14} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        {data.total > 50 && (
          <div className="flex justify-between items-center px-4 py-3 border-t text-sm text-gray-500">
            <span>{data.total} registros</span>
            <div className="flex gap-2">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="px-3 py-1 border rounded hover:bg-gray-50 disabled:opacity-40">Anterior</button>
              <span className="px-2">Página {page}</span>
              <button onClick={() => setPage((p) => p + 1)} disabled={page * 50 >= data.total} className="px-3 py-1 border rounded hover:bg-gray-50 disabled:opacity-40">Siguiente</button>
            </div>
          </div>
        )}
      </div>

      {/* Modal detalle */}
      {modal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setModal(null)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-2xl max-h-[80vh] overflow-y-auto shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-800">{modal.operation}</h3>
              <button onClick={() => setModal(null)} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
            </div>
            <dl className="grid grid-cols-2 gap-3 text-sm mb-4">
              <div><dt className="text-gray-500 text-xs">Usuario</dt><dd>{modal.username || modal.user_id}</dd></div>
              <div><dt className="text-gray-500 text-xs">Fecha</dt><dd>{new Date(modal.created_at).toLocaleString()}</dd></div>
              <div><dt className="text-gray-500 text-xs">Método</dt><dd>{modal.http_method}</dd></div>
              <div><dt className="text-gray-500 text-xs">Status HTTP</dt><dd>{modal.response_status}</dd></div>
              <div><dt className="text-gray-500 text-xs">Duración</dt><dd>{modal.duration_ms}ms</dd></div>
              <div><dt className="text-gray-500 text-xs">IP</dt><dd>{modal.ip_address || "—"}</dd></div>
              {modal.error_message && (
                <div className="col-span-2"><dt className="text-gray-500 text-xs">Error</dt><dd className="text-red-600">{modal.error_message}</dd></div>
              )}
            </dl>
            {modal.request_payload && (
              <div className="mb-3">
                <p className="text-xs font-medium text-gray-600 mb-1">Request Payload</p>
                <pre className="text-xs bg-gray-50 border rounded-lg p-3 overflow-auto max-h-36">{JSON.stringify(modal.request_payload, null, 2)}</pre>
              </div>
            )}
            {modal.response_payload && (
              <div>
                <p className="text-xs font-medium text-gray-600 mb-1">Response Payload</p>
                <pre className="text-xs bg-gray-50 border rounded-lg p-3 overflow-auto max-h-36">{JSON.stringify(modal.response_payload, null, 2)}</pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
