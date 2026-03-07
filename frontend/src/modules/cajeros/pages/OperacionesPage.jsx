import { useEffect, useState } from "react";
import { getOperations } from "../../../api/cajeros";

export default function OperacionesPage() {
  const [ops, setOps] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getOperations().then(setOps).finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-800 mb-6">Historial de Operaciones</h2>
      <div className="bg-white border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[500px]">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">#</th>
              <th className="text-left px-4 py-3 font-medium">Solicitud</th>
              <th className="text-left px-4 py-3 font-medium">Monto</th>
              <th className="text-left px-4 py-3 font-medium">Ejecutado por</th>
              <th className="text-left px-4 py-3 font-medium">Fecha</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">Cargando...</td></tr>
            ) : ops.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">Sin operaciones registradas</td></tr>
            ) : ops.map((op) => (
              <tr key={op.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-gray-500">#{op.id}</td>
                <td className="px-4 py-3">Solicitud #{op.request_id}</td>
                <td className="px-4 py-3 font-medium">{op.amount}</td>
                <td className="px-4 py-3 text-gray-600">Usuario #{op.executed_by_user_id}</td>
                <td className="px-4 py-3 text-gray-500">{new Date(op.executed_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
