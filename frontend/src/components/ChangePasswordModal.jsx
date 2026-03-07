import { useState } from "react";
import { X, KeyRound } from "lucide-react";

/**
 * Modal de cambio de contraseña.
 * Props:
 *   title      — string mostrado en el header
 *   requireCurrent — bool, si true pide la contraseña actual
 *   onSave(current, newPass) — async, lanza error si falla
 *   onClose()
 */
export function ChangePasswordModal({ title, requireCurrent = false, onSave, onClose }) {
  const [current, setCurrent] = useState("");
  const [newPass, setNewPass] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (newPass.length < 6) { setError("La contraseña debe tener al menos 6 caracteres"); return; }
    if (newPass !== confirm) { setError("Las contraseñas no coinciden"); return; }
    setSaving(true);
    try {
      await onSave(current, newPass);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al cambiar la contraseña");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex items-center gap-2 text-gray-800 font-medium">
            <KeyRound size={18} />
            {title}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {requireCurrent && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Contraseña actual</label>
              <input
                type="password"
                className="input w-full"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                required
                autoFocus
              />
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nueva contraseña</label>
            <input
              type="password"
              className="input w-full"
              value={newPass}
              onChange={(e) => setNewPass(e.target.value)}
              required
              autoFocus={!requireCurrent}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Confirmar contraseña</label>
            <input
              type="password"
              className="input w-full"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-3 py-2 text-sm">
              {error}
            </div>
          )}

          <div className="flex gap-2 justify-end pt-1">
            <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">
              Cancelar
            </button>
            <button type="submit" disabled={saving} className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
              {saving ? "Guardando..." : "Cambiar contraseña"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
