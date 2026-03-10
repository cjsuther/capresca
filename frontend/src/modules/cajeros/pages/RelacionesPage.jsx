import { useEffect, useState } from "react";
import { getRelations, createRelation, deleteRelation } from "../../../api/cajeros";
import { PermissionGate } from "../../../components/PrivateRoute";
import { Plus, Trash2 } from "lucide-react";

export default function RelacionesPage() {
  const [relations, setRelations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    cajero_user_id: "",
    authorizer_user_id: "",
    amount_threshold: "",
    currency: "ARS",
  });

  const load = () => {
    setLoading(true);
    getRelations()
      .then(setRelations)
      .catch(() => setError("Error al cargar relaciones"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await createRelation({
        cajero_user_id: parseInt(form.cajero_user_id),
        authorizer_user_id: parseInt(form.authorizer_user_id),
        amount_threshold: parseFloat(form.amount_threshold) || 0,
        currency: form.currency,
      });
      setShowForm(false);
      setForm({ cajero_user_id: "", authorizer_user_id: "", amount_threshold: "", currency: "ARS" });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al crear relación");
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("¿Eliminar esta relación?")) return;
    setError("");
    try {
      await deleteRelation(id);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al eliminar relación");
    }
  };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h2 className="text-xl font-semibold text-gray-800">Relaciones de Autorización</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Cuando una solicitud supera el umbral, se asigna automáticamente al autorizador definido.
          </p>
        </div>
        <PermissionGate moduleCode="cajeros" action="requests:write">
          <button
            onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700"
          >
            <Plus size={16} /> Nueva relación
          </button>
        </PermissionGate>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm mb-4">{error}</div>
      )}

      {showForm && (
        <form onSubmit={handleCreate} className="bg-white border rounded-xl p-5 mb-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">ID Cajero</label>
            <input
              type="number"
              className="input w-full"
              placeholder="User ID del cajero"
              value={form.cajero_user_id}
              onChange={(e) => setForm({ ...form, cajero_user_id: e.target.value })}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">ID Autorizador</label>
            <input
              type="number"
              className="input w-full"
              placeholder="User ID del autorizador"
              value={form.authorizer_user_id}
              onChange={(e) => setForm({ ...form, authorizer_user_id: e.target.value })}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Umbral de monto</label>
            <input
              type="number"
              step="0.01"
              min="0"
              className="input w-full"
              placeholder="0.00 — aplica desde este monto"
              value={form.amount_threshold}
              onChange={(e) => setForm({ ...form, amount_threshold: e.target.value })}
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Moneda</label>
            <select
              className="input w-full"
              value={form.currency}
              onChange={(e) => setForm({ ...form, currency: e.target.value })}
            >
              <option>ARS</option>
              <option>USD</option>
              <option>EUR</option>
            </select>
          </div>
          <div className="sm:col-span-2 flex gap-2 justify-end">
            <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">
              Cancelar
            </button>
            <button type="submit" className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              Crear
            </button>
          </div>
        </form>
      )}

      <div className="bg-white border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[560px]">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">ID Cajero</th>
              <th className="text-left px-4 py-3 font-medium">ID Autorizador</th>
              <th className="text-right px-4 py-3 font-medium">Umbral</th>
              <th className="text-left px-4 py-3 font-medium">Moneda</th>
              <th className="text-left px-4 py-3 font-medium">Estado</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Cargando...</td></tr>
            ) : relations.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Sin relaciones definidas</td></tr>
            ) : relations.map((rel) => (
              <tr key={rel.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-mono text-xs text-gray-600">{rel.cajero_user_id}</td>
                <td className="px-4 py-3 font-mono text-xs text-gray-600">{rel.authorizer_user_id}</td>
                <td className="px-4 py-3 text-right font-medium">
                  {Number(rel.amount_threshold) === 0
                    ? <span className="text-gray-400 text-xs">Siempre</span>
                    : `$${Number(rel.amount_threshold).toLocaleString("es-AR", { minimumFractionDigits: 2 })}`}
                </td>
                <td className="px-4 py-3 text-gray-500">{rel.currency}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${rel.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                    {rel.is_active ? "Activa" : "Inactiva"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <PermissionGate moduleCode="cajeros" action="requests:write">
                    <button
                      onClick={() => handleDelete(rel.id)}
                      className="p-1 text-gray-400 hover:text-red-600"
                      title="Eliminar"
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
