import { useEffect, useState } from "react";
import { getMyLimit, updateLimit } from "../../../api/cajeros";
import { PermissionGate } from "../../../components/PrivateRoute";
import { useUser } from "../../../context/usePermissions";

export default function LimitesPage() {
  const user = useUser();
  const [limit, setLimit] = useState(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({});

  useEffect(() => {
    getMyLimit().then((data) => {
      setLimit(data);
      setForm({ daily_limit: data.daily_limit, per_transaction_limit: data.per_transaction_limit, currency: data.currency });
    });
  }, []);

  const handleSave = async (e) => {
    e.preventDefault();
    const updated = await updateLimit(user.id, form);
    setLimit(updated);
    setEditing(false);
  };

  if (!limit) return <p className="text-gray-400 text-sm">Cargando...</p>;

  return (
    <div className="max-w-lg">
      <h2 className="text-xl font-semibold text-gray-800 mb-6">Mis Límites Operativos</h2>

      {!editing ? (
        <div className="bg-white border rounded-xl p-6 space-y-4">
          <div className="flex justify-between">
            <span className="text-gray-600">Límite diario</span>
            <span className="font-semibold">{limit.daily_limit} {limit.currency}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Límite por operación</span>
            <span className="font-semibold">{limit.per_transaction_limit} {limit.currency}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-600">Moneda</span>
            <span className="font-semibold">{limit.currency}</span>
          </div>
          <PermissionGate moduleCode="cajeros" action="limits:write">
            <button onClick={() => setEditing(true)} className="mt-2 text-sm text-blue-600 hover:underline">Editar</button>
          </PermissionGate>
        </div>
      ) : (
        <form onSubmit={handleSave} className="bg-white border rounded-xl p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Límite diario</label>
            <input type="number" step="0.01" className="input w-full" value={form.daily_limit} onChange={(e) => setForm({ ...form, daily_limit: e.target.value })} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Límite por operación</label>
            <input type="number" step="0.01" className="input w-full" value={form.per_transaction_limit} onChange={(e) => setForm({ ...form, per_transaction_limit: e.target.value })} />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Moneda</label>
            <select className="input w-full" value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}>
              <option>ARS</option><option>USD</option><option>EUR</option>
            </select>
          </div>
          <div className="flex gap-2 justify-end">
            <button type="button" onClick={() => setEditing(false)} className="px-4 py-2 text-sm text-gray-600 border rounded-lg">Cancelar</button>
            <button type="submit" className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg">Guardar</button>
          </div>
        </form>
      )}
    </div>
  );
}
