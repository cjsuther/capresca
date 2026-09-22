import { AlertTriangle } from "lucide-react";

/**
 * Confirmación de una acción irreversible (baja, borrado, payoff). Principio de diseño de
 * Portezuelo: estas acciones se confirman y se marcan en rojo.
 */
export function Confirmacion({ titulo, mensaje, confirmar = "Confirmar", cancelar = "Cancelar",
                               danger = true, ocupado = false, onConfirmar, onCancelar }) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={titulo}
      className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onCancelar(); }}
      onKeyDown={(e) => { if (e.key === "Escape") onCancelar(); }}
    >
      <div className="bg-surface rounded-xl shadow-xl w-full max-w-md">
        <div className="flex items-start gap-3 px-5 pt-5">
          <span className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
            danger ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-600"}`}>
            <AlertTriangle size={17} />
          </span>
          <div>
            <h2 className="font-semibold text-gray-800">{titulo}</h2>
            <p className="text-sm text-gray-600 mt-1 whitespace-pre-line">{mensaje}</p>
          </div>
        </div>
        <div className="flex justify-end gap-2 px-5 py-4">
          <button onClick={onCancelar} disabled={ocupado}
                  className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50 disabled:opacity-50">
            {cancelar}
          </button>
          <button onClick={onConfirmar} disabled={ocupado} autoFocus
                  className={`px-4 py-2 text-sm text-white rounded-lg disabled:opacity-50 ${
                    danger ? "bg-red-600 hover:bg-red-700" : "bg-blue-600 hover:bg-blue-700"}`}>
            {ocupado ? "Procesando…" : confirmar}
          </button>
        </div>
      </div>
    </div>
  );
}
