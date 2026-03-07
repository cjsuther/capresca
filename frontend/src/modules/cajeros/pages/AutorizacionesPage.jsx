import { useEffect, useState } from "react";
import { getRequests, approveRequest, rejectRequest } from "../../../api/cajeros";
import { CheckCircle, XCircle } from "lucide-react";

export default function AutorizacionesPage() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [notes, setNotes] = useState({});

  const load = () => {
    setLoading(true);
    getRequests(true).then(setRequests).finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleApprove = async (id) => {
    await approveRequest(id, { resolution_notes: notes[id] || "" });
    load();
  };

  const handleReject = async (id) => {
    if (!confirm("¿Rechazar esta solicitud?")) return;
    await rejectRequest(id, { resolution_notes: notes[id] || "" });
    load();
  };

  const pending = requests.filter((r) => r.status === "PENDING");

  return (
    <div>
      <h2 className="text-xl font-semibold text-gray-800 mb-6">Solicitudes pendientes de autorización</h2>

      {loading ? (
        <p className="text-gray-400 text-sm">Cargando...</p>
      ) : pending.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <CheckCircle size={40} className="mx-auto mb-2 text-green-300" />
          <p>No hay solicitudes pendientes</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {pending.map((r) => (
            <div key={r.id} className="bg-white border rounded-xl p-5">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-semibold text-gray-800">#{r.id} — {r.amount} {r.currency}</p>
                  <p className="text-sm text-gray-500 mt-0.5">Cajero ID: {r.cajero_user_id}</p>
                  {r.reason && <p className="text-sm text-gray-600 mt-1">{r.reason}</p>}
                  <p className="text-xs text-gray-400 mt-1">{new Date(r.requested_at).toLocaleString()}</p>
                </div>
              </div>
              <div className="mt-4 flex gap-3 items-end">
                <div className="flex-1">
                  <label className="block text-xs text-gray-500 mb-1">Notas (opcional)</label>
                  <input
                    className="input w-full text-sm"
                    placeholder="Comentario..."
                    value={notes[r.id] || ""}
                    onChange={(e) => setNotes({ ...notes, [r.id]: e.target.value })}
                  />
                </div>
                <button
                  onClick={() => handleApprove(r.id)}
                  className="flex items-center gap-1 bg-green-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-green-700"
                >
                  <CheckCircle size={15} /> Aprobar
                </button>
                <button
                  onClick={() => handleReject(r.id)}
                  className="flex items-center gap-1 bg-red-100 text-red-700 px-4 py-2 rounded-lg text-sm hover:bg-red-200"
                >
                  <XCircle size={15} /> Rechazar
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
