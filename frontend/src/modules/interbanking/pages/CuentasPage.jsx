import { useState } from "react";
import { getCuentas, getSaldos } from "../../../api/interbanking";
import { RefreshCw, Wallet } from "lucide-react";

const fmtMoney = (n, cur = "ARS") =>
  `${cur} ${Number(n ?? 0).toLocaleString("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

// Las APIs de cuentas y saldos no comparten un campo único: cuentas devuelve
// (bank_id, account_number) y saldos devuelve (bank_number, account_number).
// bank_id y bank_number son ambos el código BCRA, así que se puede componer.
const accKey = (bank, accNum) => `${(bank || "").trim()}|${(accNum || "").trim()}`;

export default function CuentasPage() {
  const [cuentas, setCuentas] = useState([]);
  const [saldosByKey, setSaldosByKey] = useState({});  // { "bank|account_number": balanceObj }
  const [saldosMeta, setSaldosMeta] = useState(null);  // { ok, time }
  const [loadingCuentas, setLoadingCuentas] = useState(false);
  const [loadingSaldos, setLoadingSaldos] = useState(false);
  const [errorCuentas, setErrorCuentas] = useState("");
  const [errorSaldos, setErrorSaldos] = useState("");
  const [lastSync, setLastSync] = useState(null);

  const cargarCuentas = async () => {
    setLoadingCuentas(true);
    setErrorCuentas("");
    try {
      const data = await getCuentas();
      const list = data?.accounts ?? data?.cuentas ?? (Array.isArray(data) ? data : []);
      setCuentas(list);
      setLastSync({ time: new Date().toLocaleTimeString(), ok: true });
      return list;
    } catch (err) {
      setErrorCuentas(err.response?.data?.detail || "Error al consultar cuentas");
      setLastSync({ time: new Date().toLocaleTimeString(), ok: false });
      return [];
    } finally {
      setLoadingCuentas(false);
    }
  };

  const cargarSaldos = async () => {
    setLoadingSaldos(true);
    setErrorSaldos("");
    try {
      const data = await getSaldos();
      const list = data?.accounts ?? [];
      const map = {};
      for (const acc of list) {
        map[accKey(acc.bank_number || acc.bank_id, acc.account_number)] = acc;
      }
      setSaldosByKey(map);
      setSaldosMeta({ ok: true, time: new Date().toLocaleTimeString() });
    } catch (err) {
      setErrorSaldos(err.response?.data?.detail || "Error al consultar saldos");
      setSaldosMeta({ ok: false, time: new Date().toLocaleTimeString() });
    } finally {
      setLoadingSaldos(false);
    }
  };

  const refrescar = async () => {
    const list = await cargarCuentas();
    if (list.length > 0) await cargarSaldos();
  };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <h2 className="text-xl font-semibold text-gray-800">Cuentas y Saldos</h2>
        <div className="flex items-center gap-3">
          {lastSync && (
            <span className={`text-xs px-2 py-1 rounded-full ${lastSync.ok ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
              Cuentas {lastSync.ok ? "OK" : "Error"} · {lastSync.time}
            </span>
          )}
          {saldosMeta && (
            <span className={`text-xs px-2 py-1 rounded-full ${saldosMeta.ok ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
              Saldos {saldosMeta.ok ? "OK" : "Error"} · {saldosMeta.time}
            </span>
          )}
          <button
            onClick={cargarSaldos}
            disabled={loadingSaldos || cuentas.length === 0}
            className="flex items-center gap-2 bg-white border text-gray-700 px-3 py-2 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50"
          >
            <Wallet size={15} className={loadingSaldos ? "animate-pulse" : ""} />
            Actualizar saldos
          </button>
          <button
            onClick={refrescar}
            disabled={loadingCuentas || loadingSaldos}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            <RefreshCw size={15} className={(loadingCuentas || loadingSaldos) ? "animate-spin" : ""} />
            Refrescar
          </button>
        </div>
      </div>

      {errorCuentas && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm mb-2">
          <strong>Cuentas:</strong> {errorCuentas}
        </div>
      )}
      {errorSaldos && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm mb-2">
          <strong>Saldos:</strong> {errorSaldos}
        </div>
      )}

      {cuentas.length === 0 ? (
        <div className="bg-white border rounded-xl p-12 text-center text-gray-400 text-sm">
          Presioná "Refrescar" para cargar las cuentas operativas en Interbanking
        </div>
      ) : (
        <div className="bg-white border rounded-xl overflow-x-auto">
          <table className="w-full text-sm min-w-[900px]">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="text-left px-4 py-3 font-medium">Banco</th>
                <th className="text-left px-4 py-3 font-medium">Cuenta</th>
                <th className="text-left px-4 py-3 font-medium">CBU</th>
                <th className="text-left px-4 py-3 font-medium">Tipo</th>
                <th className="text-left px-4 py-3 font-medium">Moneda</th>
                <th className="text-right px-4 py-3 font-medium">Saldo operativo</th>
                <th className="text-right px-4 py-3 font-medium">Saldo contable</th>
                <th className="text-right px-4 py-3 font-medium">Proyectado 24hs</th>
                <th className="text-right px-4 py-3 font-medium">Proyectado 48hs</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {cuentas.map((c) => {
                const cbu = c.cbu || "";
                const key = accKey(c.bank_id || c.bank_number, c.account_number);
                const saldoAcc = saldosByKey[key];
                const b = saldoAcc?.balances || {};
                const cur = c.currency || saldoAcc?.currency || "ARS";
                return (
                  <tr key={key || cbu} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="font-medium">{c.bank_name || c.bank_id || "—"}</div>
                      <div className="text-xs text-gray-400 font-mono">{c.bank_id || ""}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium">{c.account_label || c.account_name || "—"}</div>
                      <div className="text-xs text-gray-400 font-mono">{c.account_number || "—"}</div>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">{cbu || "—"}</td>
                    <td className="px-4 py-3 text-gray-600">{c.account_type || "—"}</td>
                    <td className="px-4 py-3">{cur}</td>
                    <td className="px-4 py-3 text-right font-mono">
                      {saldoAcc ? fmtMoney(b.current_operating_balance, cur) : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-600">
                      {saldoAcc ? fmtMoney(b.countable_balance, cur) : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-600">
                      {saldoAcc ? fmtMoney(b.projected_balance_24hs, cur) : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-600">
                      {saldoAcc ? fmtMoney(b.projected_balance_48hs, cur) : <span className="text-gray-300">—</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
