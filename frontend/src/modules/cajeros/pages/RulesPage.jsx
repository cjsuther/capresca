import { useEffect, useState } from "react";
import { getRules, createRule, deleteRule } from "../../../api/cajeros";
import { getUsers } from "../../../api/security";
import { PermissionGate } from "../../../components/PrivateRoute";
import { Plus, Trash2, HelpCircle } from "lucide-react";

const CURRENCIES = ["ARS", "USD", "EUR"];

export default function RulesPage() {
  const [rules, setRules] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [cajeroFilter, setCajeroFilter] = useState("");
  const [currencyFilter, setCurrencyFilter] = useState("");
  const [form, setForm] = useState({
    cajero_user_id: "",
    cajero_username: "",
    authorizer_user_id: "",
    authorizer_username: "",
    currency: "ARS",
    amount_limit: "",
    reference: "",
  });

  const load = () => {
    setLoading(true);
    const params = {};
    if (cajeroFilter) params.cajero = cajeroFilter;
    if (currencyFilter) params.currency = currencyFilter;
    getRules(params)
      .then(setRules)
      .catch(() => setError("Error al cargar reglas"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    getUsers().then((d) => setUsers(Array.isArray(d) ? d : d.data || [])).catch(() => {});
  }, []);

  useEffect(load, [cajeroFilter, currencyFilter]);

  const userLabel = (u) => u.full_name || u.username;

  const handleUserSelect = (field_id, field_name, userId) => {
    const u = users.find((u) => u.id === parseInt(userId));
    setForm((f) => ({
      ...f,
      [field_id]: userId,
      [field_name]: u ? userLabel(u) : "",
    }));
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await createRule({
        cajero_user_id: parseInt(form.cajero_user_id),
        cajero_username: form.cajero_username || null,
        authorizer_user_id: parseInt(form.authorizer_user_id),
        authorizer_username: form.authorizer_username || null,
        currency: form.currency,
        amount_limit: parseFloat(form.amount_limit),
        reference: form.reference || null,
      });
      setShowForm(false);
      setForm({ cajero_user_id: "", cajero_username: "", authorizer_user_id: "", authorizer_username: "", currency: "ARS", amount_limit: "", reference: "" });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al crear regla");
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("¿Confirmar eliminación de esta regla?")) return;
    setError("");
    try {
      await deleteRule(id);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al eliminar");
    }
  };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h2 className="text-xl font-semibold text-gray-800">Administración de Autorizaciones</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Define qué autorizador actúa para cada cajero según moneda y monto acumulado.
          </p>
        </div>
        <PermissionGate moduleCode="cajeros" action="rules:write">
          <button
            onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700"
          >
            <Plus size={16} /> Agregar Regla
          </button>
        </PermissionGate>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm mb-4">{error}</div>
      )}

      {showForm && (
        <form onSubmit={handleCreate} className="bg-white border rounded-xl p-5 mb-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Cajero</label>
            <select
              className="input w-full"
              value={form.cajero_user_id}
              onChange={(e) => handleUserSelect("cajero_user_id", "cajero_username", e.target.value)}
              required
            >
              <option value="">Seleccionar cajero...</option>
              {users.map((u) => <option key={u.id} value={u.id}>{userLabel(u)}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Autorizador</label>
            <select
              className="input w-full"
              value={form.authorizer_user_id}
              onChange={(e) => handleUserSelect("authorizer_user_id", "authorizer_username", e.target.value)}
              required
            >
              <option value="">Seleccionar autorizador...</option>
              {users.map((u) => <option key={u.id} value={u.id}>{userLabel(u)}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Moneda</label>
            <select className="input w-full" value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}>
              {CURRENCIES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Monto límite</label>
            <input
              type="number"
              step="0.01"
              min="0"
              className="input w-full"
              placeholder="50000.00"
              value={form.amount_limit}
              onChange={(e) => setForm({ ...form, amount_limit: e.target.value })}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1 flex items-center gap-1">
              Referencia (opcional)
              <span title="Si no se ingresa, aplica sobre la suma total de transacciones del cajero para esa moneda.">
                <HelpCircle size={13} className="text-gray-400" />
              </span>
            </label>
            <input
              type="text"
              className="input w-full"
              placeholder="Dejar vacío = aplica a todas"
              value={form.reference}
              onChange={(e) => setForm({ ...form, reference: e.target.value })}
            />
          </div>
          <div className="flex gap-2 items-end justify-end sm:col-span-2 lg:col-span-1">
            <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">
              Cancelar
            </button>
            <button type="submit" className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              Agregar Regla
            </button>
          </div>
        </form>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <select className="input text-sm" value={cajeroFilter} onChange={(e) => setCajeroFilter(e.target.value)}>
          <option value="">Todos los cajeros</option>
          {users.map((u) => <option key={u.id} value={u.id}>{userLabel(u)}</option>)}
        </select>
        <select className="input text-sm" value={currencyFilter} onChange={(e) => setCurrencyFilter(e.target.value)}>
          <option value="">Todas las monedas</option>
          {CURRENCIES.map((c) => <option key={c}>{c}</option>)}
        </select>
      </div>

      <div className="bg-white border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[640px]">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Cajero</th>
              <th className="text-left px-4 py-3 font-medium">Autorizador</th>
              <th className="text-left px-4 py-3 font-medium">Moneda</th>
              <th className="text-right px-4 py-3 font-medium">Monto Límite</th>
              <th className="text-left px-4 py-3 font-medium">Referencia</th>
              <th className="text-left px-4 py-3 font-medium">Creación</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Cargando...</td></tr>
            ) : rules.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Sin reglas definidas</td></tr>
            ) : rules.map((rule) => (
              <tr key={rule.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">{rule.cajero_username || rule.cajero_user_id}</td>
                <td className="px-4 py-3">{rule.authorizer_username || rule.authorizer_user_id}</td>
                <td className="px-4 py-3">{rule.currency}</td>
                <td className="px-4 py-3 text-right font-mono">
                  ${Number(rule.amount_limit).toLocaleString("es-AR", { minimumFractionDigits: 2 })}
                </td>
                <td className="px-4 py-3 text-gray-500">{rule.reference || "—"}</td>
                <td className="px-4 py-3 text-xs text-gray-400">
                  {rule.created_at ? new Date(rule.created_at).toLocaleDateString() : "—"}
                </td>
                <td className="px-4 py-3">
                  <PermissionGate moduleCode="cajeros" action="rules:write">
                    <button
                      onClick={() => handleDelete(rule.id)}
                      className="p-1 text-gray-400 hover:text-red-600"
                      title="Eliminar regla"
                    >
                      <Trash2 size={14} />
                    </button>
                  </PermissionGate>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
