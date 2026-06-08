import { useEffect, useState } from "react";
import {
  listarTransferencias,
  crearTransferencia,
  getCuentas,
} from "../../../api/interbanking";
import { PermissionGate } from "../../../components/PrivateRoute";
import { CheckCircle, Plus, RefreshCw, X } from "lucide-react";

const todayISO = () => new Date().toISOString().slice(0, 10);

const STATUS_COLORS = {
  ACREDITADA: "bg-green-100 text-green-700",
  PROCESANDO: "bg-yellow-100 text-yellow-700",
  PENDING_AUTHORIZATION: "bg-yellow-100 text-yellow-700",
  INICIADA:   "bg-blue-100 text-blue-700",
  RECHAZADA:  "bg-red-100 text-red-600",
  ERROR:      "bg-gray-100 text-gray-600",
};

const fmtMoney = (n, cur = "ARS") =>
  `${cur} ${Number(n ?? 0).toLocaleString("es-AR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

// FastAPI devuelve `detail` como string en 4xx normales y como array de
// {loc, msg, type, ...} en 422. Convertir a string siempre.
const errMsg = (err, fallback) => {
  const d = err?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map(e => `${(e.loc || []).join(".")} - ${e.msg}`).join("; ");
  return fallback;
};

export default function TransferenciasPage() {
  const [filtros, setFiltros] = useState({ date_since: todayISO(), date_until: todayISO() });
  const [data, setData] = useState({ transfers: [], general_data: {} });
  const [isMock, setIsMock] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [cuentas, setCuentas] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    cuenta_debito_key: "",
    cuenta_debito_account_number: "",
    cuenta_debito_account_type: "",
    cuenta_debito_bank_id: "",
    cbu_destino: "",
    monto: "",
    moneda: "ARS",
    comentario: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(null);

  const cargar = async () => {
    setLoading(true);
    setError("");
    try {
      const result = await listarTransferencias(filtros);
      setData({
        transfers: result.transfers || [],
        general_data: result.general_data || {},
      });
      setIsMock(!!result.mock);
    } catch (err) {
      setError(errMsg(err, "Error al listar transferencias"));
    } finally {
      setLoading(false);
    }
  };

  const cargarCuentas = async () => {
    try {
      const d = await getCuentas();
      const list = d?.accounts ?? (Array.isArray(d) ? d : []);
      setCuentas(list);
    } catch {
      // si falla, el dropdown queda vacío y se puede pegar el CBU a mano
    }
  };

  useEffect(() => {
    cargar();
    cargarCuentas();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const created = await crearTransferencia({
        cuenta_debito_account_number: form.cuenta_debito_account_number,
        cuenta_debito_account_type: form.cuenta_debito_account_type,
        cuenta_debito_bank_id: form.cuenta_debito_bank_id || null,
        cbu_destino: form.cbu_destino,
        monto: parseFloat(form.monto),
        moneda: form.moneda,
        comentario: form.comentario,
      });
      setSuccess(created);
      setShowForm(false);
      setForm({
        cuenta_debito_key: "",
        cuenta_debito_account_number: "",
        cuenta_debito_account_type: "",
        cuenta_debito_bank_id: "",
        cbu_destino: "", monto: "", moneda: "ARS", comentario: "",
      });
      cargar();
    } catch (err) {
      setError(errMsg(err, "Error al crear transferencia"));
    } finally {
      setSubmitting(false);
    }
  };

  // Clave compuesta para identificar cada cuenta del listado (bank_id|account_number|account_type)
  const accountKey = (c) =>
    `${c.bank_id || c.bank_number || ""}|${c.account_number || ""}|${c.account_type || ""}`;
  const cuentaSeleccionada = cuentas.find((c) => accountKey(c) === form.cuenta_debito_key);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-semibold text-gray-800">Transferencias</h2>
          {isMock && (
            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200">
              MOCK
            </span>
          )}
        </div>
        <PermissionGate moduleCode="interbanking" action="transferencias:write">
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700"
          >
            <Plus size={15} /> Nueva transferencia
          </button>
        </PermissionGate>
      </div>

      {/* Filtros */}
      <div className="bg-white border rounded-xl p-4 mb-4 flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Desde</label>
          <input
            type="date"
            className="input text-sm"
            value={filtros.date_since}
            onChange={(e) => setFiltros({ ...filtros, date_since: e.target.value })}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Hasta</label>
          <input
            type="date"
            className="input text-sm"
            value={filtros.date_until}
            onChange={(e) => setFiltros({ ...filtros, date_until: e.target.value })}
          />
        </div>
        <button
          onClick={cargar}
          disabled={loading}
          className="flex items-center gap-2 bg-white border text-gray-700 px-3 py-2 rounded-lg text-sm hover:bg-gray-50 disabled:opacity-50"
        >
          <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
          Consultar
        </button>
        <div className="ml-auto text-xs text-gray-400">
          {data.general_data?.total_rows != null && `${data.general_data.total_rows} resultados`}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm mb-4">{error}</div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-4 flex items-center gap-3">
          <CheckCircle size={20} className="text-green-600" />
          <div className="flex-1">
            <p className="text-sm font-medium text-green-800">Transferencia creada</p>
            <p className="text-xs text-green-600">
              ID Operación: {success.id_operacion_ib || success.id} · Estado: {success.status}
            </p>
          </div>
          <button onClick={() => setSuccess(null)} className="text-xs text-green-600 hover:underline">Cerrar</button>
        </div>
      )}

      {/* Listado */}
      <div className="bg-white border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[900px]">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Fecha</th>
              <th className="text-left px-4 py-3 font-medium">ID</th>
              <th className="text-left px-4 py-3 font-medium">CBU Débito</th>
              <th className="text-left px-4 py-3 font-medium">CBU Crédito</th>
              <th className="text-right px-4 py-3 font-medium">Monto</th>
              <th className="text-left px-4 py-3 font-medium">Comentario</th>
              <th className="text-left px-4 py-3 font-medium">Estado</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Cargando...</td></tr>
            ) : data.transfers.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Sin transferencias en el rango</td></tr>
            ) : data.transfers.map((t) => {
              const status = t._status || t.status || "—";
              return (
                <tr key={t.transfer_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-500 text-xs">{t.request_date}</td>
                  <td className="px-4 py-3 font-mono text-xs">{t.transfer_id}</td>
                  <td className="px-4 py-3 font-mono text-xs">{t.debit_account?.cbu || "—"}</td>
                  <td className="px-4 py-3 font-mono text-xs">{t.credit_account?.cbu || "—"}</td>
                  <td className="px-4 py-3 text-right font-mono">{fmtMoney(t.amount, t.currency)}</td>
                  <td className="px-4 py-3 text-gray-600">{t.comments || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[status] || "bg-gray-100 text-gray-600"}`}>
                      {status}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Modal Nueva Transferencia */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl p-6 w-full max-w-lg shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-800">Nueva Transferencia</h3>
              <button onClick={() => setShowForm(false)} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Cuenta débito</label>
                <select
                  className="input w-full text-sm"
                  value={form.cuenta_debito_key}
                  onChange={(e) => {
                    const key = e.target.value;
                    const acc = cuentas.find((c) => accountKey(c) === key);
                    setForm({
                      ...form,
                      cuenta_debito_key: key,
                      cuenta_debito_account_number: acc?.account_number || "",
                      cuenta_debito_account_type: acc?.account_type || "",
                      cuenta_debito_bank_id: acc?.bank_id || acc?.bank_number || "",
                      moneda: acc?.currency || form.moneda,
                    });
                  }}
                  required
                >
                  <option value="">Seleccionar cuenta...</option>
                  {cuentas.map((c) => {
                    const k = accountKey(c);
                    return (
                      <option key={k} value={k}>
                        {c.bank_name || c.bank_id || c.bank_number} · {c.account_label || c.account_number} · {c.account_type} ({c.currency})
                      </option>
                    );
                  })}
                </select>
                {cuentaSeleccionada && (
                  <p className="text-xs text-gray-400 mt-1 font-mono">
                    Cuenta: {cuentaSeleccionada.account_number} · Tipo: {cuentaSeleccionada.account_type}
                    {cuentaSeleccionada.bank_id ? ` · BCRA: ${cuentaSeleccionada.bank_id}` : ""}
                  </p>
                )}
                {cuentas.length === 0 && (
                  <p className="text-xs text-amber-600 mt-1">
                    No hay cuentas cargadas. Andá a Cuentas → Refrescar primero.
                  </p>
                )}
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">CBU destino</label>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="\d{22}"
                  maxLength={22}
                  className="input w-full text-sm font-mono"
                  placeholder="22 dígitos"
                  value={form.cbu_destino}
                  onChange={(e) => setForm({ ...form, cbu_destino: e.target.value.replace(/\D/g, "") })}
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Monto</label>
                  <input
                    type="number" step="0.01" min="0.01"
                    className="input w-full text-sm"
                    placeholder="0.00"
                    value={form.monto}
                    onChange={(e) => setForm({ ...form, monto: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Moneda</label>
                  <select
                    className="input w-full text-sm"
                    value={form.moneda}
                    onChange={(e) => setForm({ ...form, moneda: e.target.value })}
                  >
                    <option value="ARS">ARS</option>
                    <option value="USD">USD</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Comentario</label>
                <input
                  className="input w-full text-sm"
                  placeholder="Descripción / concepto"
                  value={form.comentario}
                  onChange={(e) => setForm({ ...form, comentario: e.target.value })}
                  maxLength={255}
                  required
                />
              </div>

              <div className="text-xs text-gray-400">
                Fecha de solicitud: <span className="font-mono">{todayISO()}</span>
              </div>

              <div className="flex gap-2 justify-end pt-2">
                <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={
                    submitting
                    || !form.cuenta_debito_account_number
                    || !form.cuenta_debito_account_type
                    || form.cbu_destino.length !== 22
                    || !form.monto
                    || !form.comentario
                  }
                  className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {submitting ? "Creando..." : "Crear transferencia"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
