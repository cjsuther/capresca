import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  getTransactions, authorizeTransaction, rejectTransaction, deleteTransaction
} from "../../../api/cajeros";
import { useUser, useHasPermission } from "../../../context/usePermissions";
import { CheckCircle, XCircle, Trash2, X } from "lucide-react";

const STATUS_COLORS = {
  PROCESADA:              "bg-blue-100 text-blue-700",
  PENDIENTE_AUTORIZACION: "bg-yellow-100 text-yellow-700",
  AUTORIZADA:             "bg-green-100 text-green-700",
  RECHAZADA:              "bg-red-100 text-red-600",
  ELIMINADA:              "bg-gray-100 text-gray-400 line-through",
};

const STATUS_LABELS = {
  PROCESADA: "Procesada",
  PENDIENTE_AUTORIZACION: "Pend. Autorización",
  AUTORIZADA: "Autorizada",
  RECHAZADA: "Rechazada",
  ELIMINADA: "Eliminada",
};

const ALL_STATUSES = ["PROCESADA", "PENDIENTE_AUTORIZACION", "AUTORIZADA", "RECHAZADA", "ELIMINADA"];

function RejectModal({ onConfirm, onClose }) {
  const [reason, setReason] = useState("");
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-800">Rechazar transacción</h3>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Motivo de rechazo *</label>
        <textarea
          className="input w-full mb-4"
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Describe el motivo del rechazo..."
        />
        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">
            Cancelar
          </button>
          <button
            onClick={() => onConfirm(reason)}
            disabled={!reason.trim()}
            className="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
          >
            Confirmar rechazo
          </button>
        </div>
      </div>
    </div>
  );
}

function DetailPanel({ tx, onClose }) {
  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-end sm:items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h3 className="font-semibold text-gray-800">Transacción #{tx.id}</h3>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>
        <div className="px-6 py-4 grid grid-cols-2 gap-x-8 gap-y-3 text-sm">
          <div><p className="text-gray-500 text-xs">Estado</p>
            <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[tx.status]}`}>{STATUS_LABELS[tx.status] || tx.status}</span>
          </div>
          <div><p className="text-gray-500 text-xs">Monto</p><p className="font-semibold">{tx.currency} {Number(tx.amount).toLocaleString("es-AR", { minimumFractionDigits: 2 })}</p></div>
          <div><p className="text-gray-500 text-xs">Cajero</p><p>{tx.cajero_username || tx.cajero_user_id}</p></div>
          <div><p className="text-gray-500 text-xs">Autorizador</p><p>{tx.authorizer_username || tx.authorizer_user_id || "—"}</p></div>
          <div><p className="text-gray-500 text-xs">Referencia</p><p>{tx.reference || "—"}</p></div>
          <div><p className="text-gray-500 text-xs">Creación</p><p>{new Date(tx.created_at).toLocaleString()}</p></div>
          {tx.authorized_at && (
            <div><p className="text-gray-500 text-xs">Fecha autorización</p><p>{new Date(tx.authorized_at).toLocaleString()}</p></div>
          )}
          {tx.description && (
            <div className="col-span-2"><p className="text-gray-500 text-xs">Descripción</p><p>{tx.description}</p></div>
          )}
          {tx.rejection_reason && (
            <div className="col-span-2"><p className="text-gray-500 text-xs">Motivo de rechazo</p>
              <p className="text-red-600">{tx.rejection_reason}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function TransactionsPage() {
  const { id: paramId } = useParams();
  const navigate = useNavigate();
  const user = useUser();
  const canReadAll = useHasPermission("cajeros", "transactions:read_all");
  const canAdmin = useHasPermission("cajeros", "transactions:admin");
  const canAuthorize = useHasPermission("cajeros", "transactions:authorize");
  const canDelete = useHasPermission("cajeros", "transactions:delete") || canAdmin;

  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [detailTx, setDetailTx] = useState(null);
  const [rejectTarget, setRejectTarget] = useState(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState(["PENDIENTE_AUTORIZACION", "PROCESADA", "AUTORIZADA", "RECHAZADA"]);
  const [currencyFilter, setCurrencyFilter] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    const params = {};
    if (statusFilter.length && statusFilter.length < ALL_STATUSES.length) params.status = statusFilter.join(",");
    if (currencyFilter) params.currency = currencyFilter;
    getTransactions(params)
      .then(setTransactions)
      .catch(() => setError("Error al cargar transacciones"))
      .finally(() => setLoading(false));
  }, [statusFilter, currencyFilter]);

  useEffect(load, [load]);

  // Open detail if URL has ID (from notification click)
  useEffect(() => {
    if (paramId && transactions.length > 0) {
      const tx = transactions.find((t) => t.id === parseInt(paramId));
      if (tx) setDetailTx(tx);
    }
  }, [paramId, transactions]);

  const handleAuthorize = async (tx) => {
    setError("");
    try {
      await authorizeTransaction(tx.id);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al autorizar");
    }
  };

  const handleReject = async (reason) => {
    setError("");
    try {
      await rejectTransaction(rejectTarget.id, { rejection_reason: reason });
      setRejectTarget(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al rechazar");
      setRejectTarget(null);
    }
  };

  const handleDelete = async (tx) => {
    if (!confirm(`¿Eliminar transacción #${tx.id}?`)) return;
    setError("");
    try {
      await deleteTransaction(tx.id);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al eliminar");
    }
  };

  const toggleStatus = (s) =>
    setStatusFilter((prev) => prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <h2 className="text-xl font-semibold text-gray-800">Transacciones</h2>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm mb-4">{error}</div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4 items-center">
        <div className="flex flex-wrap gap-1">
          {ALL_STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => toggleStatus(s)}
              className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                statusFilter.includes(s)
                  ? STATUS_COLORS[s] + " border-transparent"
                  : "bg-white text-gray-400 border-gray-200"
              }`}
            >
              {STATUS_LABELS[s]}
            </button>
          ))}
        </div>
        <select
          className="input text-sm"
          value={currencyFilter}
          onChange={(e) => setCurrencyFilter(e.target.value)}
        >
          <option value="">Todas las monedas</option>
          <option>ARS</option><option>USD</option><option>EUR</option>
        </select>
      </div>

      <div className="bg-white border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[720px]">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              {(canReadAll || canAdmin) && <th className="text-left px-4 py-3 font-medium">Cajero</th>}
              <th className="text-left px-4 py-3 font-medium">Autorizador</th>
              <th className="text-left px-4 py-3 font-medium">Moneda</th>
              <th className="text-right px-4 py-3 font-medium">Monto</th>
              <th className="text-left px-4 py-3 font-medium">Referencia</th>
              <th className="text-left px-4 py-3 font-medium">Estado</th>
              <th className="text-left px-4 py-3 font-medium">Fecha modif.</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">Cargando...</td></tr>
            ) : transactions.length === 0 ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">Sin transacciones</td></tr>
            ) : transactions.map((tx) => {
              const isPending = tx.status === "PENDIENTE_AUTORIZACION";
              const isMyAuth = tx.authorizer_user_id === user?.id;

              return (
                <tr
                  key={tx.id}
                  className={`hover:bg-gray-50 cursor-pointer ${isPending ? "bg-yellow-50/30" : ""}`}
                  onClick={() => { setDetailTx(tx); navigate(`/modules/cajeros/transactions/${tx.id}`, { replace: true }); }}
                >
                  {(canReadAll || canAdmin) && <td className="px-4 py-3 text-gray-600">{tx.cajero_username || tx.cajero_user_id}</td>}
                  <td className="px-4 py-3 text-gray-500">{tx.authorizer_username || tx.authorizer_user_id || "—"}</td>
                  <td className="px-4 py-3">{tx.currency}</td>
                  <td className="px-4 py-3 text-right font-medium">
                    {Number(tx.amount).toLocaleString("es-AR", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-3 text-gray-500">{tx.reference || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[tx.status]}`}>
                      {STATUS_LABELS[tx.status] || tx.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-400">{new Date(tx.updated_at).toLocaleString()}</td>
                  <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                    {isPending && (
                      <div className="flex items-center gap-1">
                        {canAuthorize && isMyAuth && (
                          <>
                            <button
                              onClick={() => handleAuthorize(tx)}
                              className="flex items-center gap-1 px-2 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700"
                            >
                              <CheckCircle size={12} /> Autorizar
                            </button>
                            <button
                              onClick={() => setRejectTarget(tx)}
                              className="flex items-center gap-1 px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700"
                            >
                              <XCircle size={12} /> Rechazar
                            </button>
                          </>
                        )}
                        {canDelete && (tx.cajero_user_id === user?.id || canAdmin) && (
                          <button
                            onClick={() => handleDelete(tx)}
                            className="p-1 text-gray-400 hover:text-red-600"
                            title="Eliminar"
                          >
                            <Trash2 size={13} />
                          </button>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {detailTx && <DetailPanel tx={detailTx} onClose={() => { setDetailTx(null); navigate("/modules/cajeros/transactions", { replace: true }); }} />}
      {rejectTarget && <RejectModal onConfirm={handleReject} onClose={() => setRejectTarget(null)} />}
    </div>
  );
}
