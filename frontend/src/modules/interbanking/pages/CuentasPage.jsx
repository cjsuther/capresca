import { useState } from "react";
import { getCuentas, getSaldo } from "../../../api/interbanking";
import { RefreshCw, Eye } from "lucide-react";

export default function CuentasPage() {
  const [cuentas, setCuentas] = useState([]);
  const [saldo, setSaldo] = useState(null);
  const [saldoCuenta, setSaldoCuenta] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastSync, setLastSync] = useState(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getCuentas();
      setCuentas(Array.isArray(data) ? data : data.cuentas || []);
      setLastSync({ time: new Date().toLocaleTimeString(), ok: true });
    } catch (err) {
      setError(err.response?.data?.detail || "Error al consultar cuentas");
      setLastSync({ time: new Date().toLocaleTimeString(), ok: false });
    } finally {
      setLoading(false);
    }
  };

  const handleVerSaldo = async (cuenta) => {
    if (saldoCuenta === cuenta.id) { setSaldoCuenta(null); setSaldo(null); return; }
    setSaldoCuenta(cuenta.id);
    setSaldo(null);
    try {
      const data = await getSaldo(cuenta.id);
      setSaldo(data);
    } catch (err) {
      setSaldo({ error: err.response?.data?.detail || "Error al consultar saldo" });
    }
  };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <h2 className="text-xl font-semibold text-gray-800">Cuentas</h2>
        <div className="flex items-center gap-3">
          {lastSync && (
            <span className={`text-xs px-2 py-1 rounded-full ${lastSync.ok ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
              {lastSync.ok ? "Sincronizado" : "Error"} · {lastSync.time}
            </span>
          )}
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
            Actualizar
          </button>
        </div>
      </div>

      {error && <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm mb-4">{error}</div>}

      {cuentas.length === 0 ? (
        <div className="bg-white border rounded-xl p-12 text-center text-gray-400 text-sm">
          Presioná "Actualizar" para cargar las cuentas
        </div>
      ) : (
        <div className="bg-white border rounded-xl overflow-x-auto">
          <table className="w-full text-sm min-w-[560px]">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="text-left px-4 py-3 font-medium">ID Cuenta</th>
                <th className="text-left px-4 py-3 font-medium">Denominación</th>
                <th className="text-left px-4 py-3 font-medium">Tipo</th>
                <th className="text-left px-4 py-3 font-medium">CBU</th>
                <th className="text-left px-4 py-3 font-medium">Moneda</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {cuentas.map((cuenta) => (
                <>
                  <tr key={cuenta.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs">{cuenta.id}</td>
                    <td className="px-4 py-3 font-medium">{cuenta.denominacion || cuenta.nombre || "—"}</td>
                    <td className="px-4 py-3 text-gray-500">{cuenta.tipo || "—"}</td>
                    <td className="px-4 py-3 font-mono text-xs">{cuenta.cbu || "—"}</td>
                    <td className="px-4 py-3">{cuenta.moneda || "ARS"}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => handleVerSaldo(cuenta)}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50"
                      >
                        <Eye size={13} /> Ver Saldo
                      </button>
                    </td>
                  </tr>
                  {saldoCuenta === cuenta.id && (
                    <tr key={`${cuenta.id}-saldo`}>
                      <td colSpan={6} className="px-4 pb-4 bg-blue-50 border-b">
                        <div className="pt-3">
                          {!saldo ? (
                            <p className="text-sm text-gray-500">Consultando saldo...</p>
                          ) : saldo.error ? (
                            <p className="text-sm text-red-600">{saldo.error}</p>
                          ) : (
                            <div className="flex gap-8 text-sm">
                              <div>
                                <p className="text-gray-500 text-xs mb-1">Saldo disponible</p>
                                <p className="text-2xl font-bold text-gray-800">
                                  {saldo.moneda || "ARS"} {Number(saldo.saldo_disponible ?? saldo.saldo ?? 0).toLocaleString("es-AR", { minimumFractionDigits: 2 })}
                                </p>
                              </div>
                              <div>
                                <p className="text-gray-500 text-xs mb-1">Fecha consulta</p>
                                <p className="text-sm">{saldo.fecha || new Date().toLocaleString()}</p>
                              </div>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
