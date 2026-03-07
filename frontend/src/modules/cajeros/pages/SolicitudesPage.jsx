import { useEffect, useState } from "react";
import { getRequests, createRequest } from "../../../api/cajeros";
import { PermissionGate } from "../../../components/PrivateRoute";
import { Plus, Clock, CheckCircle, XCircle } from "lucide-react";

const STATUS_ICONS = {
  PENDING: <Clock size={14} className="text-yellow-500" />,
  APPROVED: <CheckCircle size={14} className="text-green-500" />,
  REJECTED: <XCircle size={14} className="text-red-500" />,
  EXPIRED: <Clock size={14} className="text-gray-400" />,
};

const STATUS_LABELS = {
  PENDING: "Pendiente",
  APPROVED: "Aprobada",
  REJECTED: "Rechazada",
  EXPIRED: "Expirada",
};

export default function SolicitudesPage() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ amount: "", currency: "ARS", reason: "", authorizer_user_id: "" });

  const load = () => {
    setLoading(true);
    getRequests(false).then(setRequests).finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    await createRequest({
      amount: parseFloat(form.amount),
      currency: form.currency,
      reason: form.reason,
      authorizer_user_id: form.authorizer_user_id ? parseInt(form.authorizer_user_id) : null,
    });
    setShowForm(false);
    setForm({ amount: "", currency: "ARS", reason: "", authorizer_user_id: "" });
    load();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-800">Mis Solicitudes</h2>
        <PermissionGate moduleCode="cajeros" action="requests:write">
          <button
            onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700"
          >
            <Plus size={16} /> Nueva solicitud
          </button>
        </PermissionGate>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="bg-white border rounded-xl p-6 mb-6 grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Monto</label>
            <input type="number" step="0.01" className="input w-full" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} required />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Moneda</label>
            <select className="input w-full" value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}>
              <option>ARS</option><option>USD</option><option>EUR</option>
            </select>
          </div>
          <div className="col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">Motivo</label>
            <textarea className="input w-full" rows={2} value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">ID Autorizador (opcional)</label>
            <input type="number" className="input w-full" value={form.authorizer_user_id} onChange={(e) => setForm({ ...form, authorizer_user_id: e.target.value })} />
          </div>
          <div className="flex gap-2 items-end justify-end">
            <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-gray-600 border rounded-lg">Cancelar</button>
            <button type="submit" className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg">Enviar</button>
          </div>
        </form>
      )}

      <div className="bg-white border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">#</th>
              <th className="text-left px-4 py-3 font-medium">Monto</th>
              <th className="text-left px-4 py-3 font-medium">Motivo</th>
              <th className="text-left px-4 py-3 font-medium">Estado</th>
              <th className="text-left px-4 py-3 font-medium">Fecha</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">Cargando...</td></tr>
            ) : requests.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">Sin solicitudes</td></tr>
            ) : requests.map((r) => (
              <tr key={r.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-gray-500">#{r.id}</td>
                <td className="px-4 py-3 font-medium">{r.amount} {r.currency}</td>
                <td className="px-4 py-3 text-gray-600">{r.reason || "—"}</td>
                <td className="px-4 py-3">
                  <span className="flex items-center gap-1">{STATUS_ICONS[r.status]} {STATUS_LABELS[r.status]}</span>
                </td>
                <td className="px-4 py-3 text-gray-500">{new Date(r.requested_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
