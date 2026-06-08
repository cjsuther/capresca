import { useState, useEffect, useCallback } from "react";
import { RefreshCw, CheckCircle2, XCircle, Power, HardDriveDownload } from "lucide-react";
import { getStatus, drainOutbox } from "../../../api/legacy";
import { PermissionGate } from "../../../components/PrivateRoute";

const fmtDateTime = (s) => (s ? new Date(s).toLocaleString("es-AR") : "—");

function Bool({ value }) {
  return value ? (
    <span className="inline-flex items-center gap-1 text-green-700"><CheckCircle2 size={16} /> Sí</span>
  ) : (
    <span className="inline-flex items-center gap-1 text-red-600"><XCircle size={16} /> No</span>
  );
}

export default function EstadoPage() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [draining, setDraining] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setStatus(await getStatus());
    } catch (e) {
      setError(e.response?.data?.detail || "Error al cargar el estado");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleDrain = async () => {
    setDraining(true);
    try {
      await drainOutbox();
      await load();
    } catch (e) {
      setError(e.response?.data?.detail || "Error al drenar el outbox");
    } finally {
      setDraining(false);
    }
  };

  const smb = status?.smb;

  return (
    <div className="p-4 md:p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-800">Estado de la integración</h1>
          <p className="text-sm text-gray-500">Salud del montaje, sincronización por tabla y outbox de escrituras.</p>
        </div>
        <button onClick={load} className="flex items-center gap-2 text-sm px-3 py-2 rounded-lg border border-gray-300 hover:bg-gray-50 text-gray-700">
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} /> Actualizar
        </button>
      </div>

      {error && <div className="mb-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">{error}</div>}

      {status && (
        <>
          {/* Tarjetas resumen */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
            <Card title="Integración" icon={Power}>
              <span className={status.integration_enabled ? "text-green-700 font-semibold" : "text-red-600 font-semibold"}>
                {status.integration_enabled ? "ACTIVA" : "APAGADA"}
              </span>
              <div className="text-xs text-gray-500 mt-1">modo escritura: {status.write_mode}</div>
            </Card>
            <Card title="Montaje SMB" icon={HardDriveDownload}>
              <Bool value={smb?.mounted} />
              <div className="text-xs text-gray-500 mt-1">{smb?.mount_root} · {smb?.tables_present}/{smb?.tables_total} tablas</div>
            </Card>
            <Card title="Outbox pendiente">
              <span className="text-2xl font-semibold text-gray-800">{status.outbox_pending}</span>
              <PermissionGate moduleCode="legacy" action="admin:write">
                <button onClick={handleDrain} disabled={draining || status.outbox_pending === 0} className="mt-2 block text-xs px-2 py-1 rounded border border-gray-300 hover:bg-gray-50 disabled:opacity-40">
                  {draining ? "Drenando…" : "Drenar outbox"}
                </button>
              </PermissionGate>
            </Card>
          </div>

          {/* Sincronización por tabla */}
          <div className="bg-white border border-gray-200 rounded-xl overflow-hidden mb-4">
            <div className="px-4 py-2 border-b border-gray-100 text-sm font-medium text-gray-700">Sincronización por tabla</div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-500 text-xs uppercase">
                  <tr>
                    <th className="text-left px-3 py-2">Tabla</th>
                    <th className="text-left px-3 py-2">Base</th>
                    <th className="text-left px-3 py-2">Último sync</th>
                    <th className="text-left px-3 py-2">Estado</th>
                    <th className="text-right px-3 py-2">Filas vistas</th>
                    <th className="text-right px-3 py-2">Cambios</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {(status.sync_state || []).length === 0 && (
                    <tr><td colSpan={6} className="px-3 py-6 text-center text-gray-400">Aún no se ejecutó ninguna sincronización.</td></tr>
                  )}
                  {(status.sync_state || []).map((s) => (
                    <tr key={s.table_name}>
                      <td className="px-3 py-2 font-mono text-xs text-gray-700">{s.table_name}</td>
                      <td className="px-3 py-2 text-gray-700">{s.database}</td>
                      <td className="px-3 py-2 text-gray-600">{fmtDateTime(s.last_run_at)}</td>
                      <td className="px-3 py-2 text-gray-700">{s.last_status || "—"}</td>
                      <td className="px-3 py-2 text-right text-gray-700">{s.rows_seen ?? "—"}</td>
                      <td className="px-3 py-2 text-right text-gray-700">{s.rows_changed ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Detalle SMB por base de datos */}
          {smb?.databases && (
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <div className="text-sm font-medium text-gray-700 mb-2">Tablas detectadas en el share</div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {Object.entries(smb.databases).map(([db, info]) => (
                  <div key={db} className="border border-gray-100 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium text-gray-700">{db}</span>
                      <Bool value={info.subdir_exists} />
                    </div>
                    <ul className="text-xs space-y-0.5">
                      {Object.entries(info.tables).map(([t, present]) => (
                        <li key={t} className="flex items-center justify-between">
                          <span className="font-mono text-gray-600">{t}</span>
                          <span className={present ? "text-green-600" : "text-gray-400"}>{present ? "✓" : "—"}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Card({ title, icon: Icon, children }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4">
      <div className="flex items-center gap-2 text-xs uppercase text-gray-400 mb-2">
        {Icon && <Icon size={14} />} {title}
      </div>
      <div>{children}</div>
    </div>
  );
}
