import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createTransaction } from "../../../api/cajeros";

const CURRENCIES = ["ARS", "USD", "EUR"];

export default function NewTransactionPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ currency: "ARS", amount: "", reference: "", description: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const tx = await createTransaction({
        currency: form.currency,
        amount: parseFloat(form.amount),
        reference: form.reference || null,
        description: form.description || null,
      });
      setResult(tx);
    } catch (err) {
      setError(err.response?.data?.detail || "Error al registrar transacción");
    } finally {
      setLoading(false);
    }
  };

  if (result) {
    const isPending = result.status === "PENDIENTE_AUTORIZACION";
    return (
      <div className="max-w-lg mx-auto">
        <div className={`rounded-xl border p-6 text-center ${isPending ? "bg-yellow-50 border-yellow-200" : "bg-green-50 border-green-200"}`}>
          <p className={`text-lg font-semibold ${isPending ? "text-yellow-800" : "text-green-800"}`}>
            {isPending ? "Transacción pendiente de autorización" : "Transacción procesada correctamente"}
          </p>
          <p className={`text-sm mt-2 ${isPending ? "text-yellow-700" : "text-green-700"}`}>
            {isPending
              ? `La transacción #${result.id} queda pendiente. Se envió una notificación al autorizador.`
              : `La transacción #${result.id} fue procesada exitosamente.`}
          </p>
          <button
            onClick={() => navigate("/modules/cajeros/transactions", { state: { highlightId: result.id } })}
            className="mt-4 px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700"
          >
            Ver transacciones
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto">
      <h2 className="text-xl font-semibold text-gray-800 mb-6">Nueva Transacción</h2>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm mb-4">{error}</div>
      )}

      <form onSubmit={handleSubmit} className="bg-white border rounded-xl p-6 grid gap-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Moneda</label>
            <select
              className="input w-full"
              value={form.currency}
              onChange={(e) => setForm({ ...form, currency: e.target.value })}
            >
              {CURRENCIES.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Monto</label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              className="input w-full"
              placeholder="0.00"
              value={form.amount}
              onChange={(e) => setForm({ ...form, amount: e.target.value })}
              required
            />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Referencia (opcional)</label>
          <input
            type="text"
            className="input w-full"
            placeholder="Referencia de la operación"
            value={form.reference}
            onChange={(e) => setForm({ ...form, reference: e.target.value })}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Descripción (opcional)</label>
          <textarea
            className="input w-full"
            rows={3}
            placeholder="Descripción libre"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </div>
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={() => navigate("/modules/cajeros/transactions")}
            className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={loading || !form.amount}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Registrando..." : "Registrar Transacción"}
          </button>
        </div>
      </form>
    </div>
  );
}
