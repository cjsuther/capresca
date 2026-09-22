/**
 * Componentes de pantalla compartidos por los módulos de Portezuelo (nacieron en Créditos): encabezado,
 * tarjeta, barra de filtros, campo, KPIs, alertas, botones y modal. Usan sólo las clases del tema
 * (claro/oscuro), así que no necesitan variantes `dark:`.
 */
import { X } from "lucide-react";

/** Encabezado de pantalla: título, bajada y acciones a la derecha. */
export function PageHeader({ titulo, descripcion, children }) {
  return (
    <div className="flex items-start justify-between gap-3 mb-4">
      <div>
        <h1 className="text-xl font-semibold text-gray-800">{titulo}</h1>
        {descripcion && <p className="text-sm text-gray-500 mt-0.5">{descripcion}</p>}
      </div>
      {children && <div className="flex items-center gap-2 shrink-0">{children}</div>}
    </div>
  );
}

const VARIANTES = {
  primario: "bg-blue-600 text-white hover:bg-blue-700",
  secundario: "border border-gray-300 text-gray-600 hover:bg-gray-50",
  ok: "bg-green-600 text-white hover:bg-green-700",
  danger: "bg-red-600 text-white hover:bg-red-700",
};

/** Botón. `variante`: primario | secundario | ok | danger. */
export function Boton({ variante = "primario", className = "", ...props }) {
  return (
    <button
      {...props}
      className={`px-4 py-2 text-sm rounded-lg disabled:opacity-50 disabled:cursor-not-allowed ${VARIANTES[variante]} ${className}`}
    />
  );
}

export function Card({ children, className = "", padding = true }) {
  return (
    <div className={`bg-surface border border-gray-200 rounded-xl ${padding ? "p-4 sm:p-5" : ""} ${className}`}>
      {children}
    </div>
  );
}

/** Barra de filtros arriba de una tabla (dentro de una Card sin padding). */
export function Toolbar({ children }) {
  return <div className="flex flex-wrap items-end gap-3 px-4 py-3 border-b border-gray-200">{children}</div>;
}

/** Campo con rótulo, para las barras de filtros y formularios simples. */
export function Field({ label, children, className = "" }) {
  return (
    <label className={`flex flex-col gap-1 ${className}`}>
      {label && <span className="text-xs font-medium text-gray-500">{label}</span>}
      {children}
    </label>
  );
}

/** Botón "✕ Limpiar filtros": sólo aparece cuando hay algún filtro activo. */
export function LimpiarFiltros({ activo, onClear }) {
  if (!activo) return null;
  return (
    <button
      type="button"
      onClick={onClear}
      title="Quitar todos los filtros y ver el listado completo"
      className="px-3 py-2 text-sm text-gray-500 border rounded-lg hover:bg-gray-50"
    >✕ Limpiar filtros</button>
  );
}

/** Tarjetas de indicadores. `items`: [{ label, valor, tono? }] */
export function Kpis({ items }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {items.map((k) => (
        <div key={k.label} className="bg-surface border border-gray-200 rounded-xl px-4 py-3">
          <p className="text-xs text-gray-500">{k.label}</p>
          <p className={`text-lg font-semibold ${k.tono === "crit" ? "text-red-600" : k.tono === "ok" ? "text-green-700" : "text-gray-800"}`}>
            {k.valor}
          </p>
        </div>
      ))}
    </div>
  );
}

export function Alerta({ tipo = "error", children }) {
  if (!children) return null;
  const clases = {
    error: "bg-red-50 text-red-700 border-red-200",
    ok: "bg-green-50 text-green-700 border-green-200",
    warn: "bg-yellow-50 text-yellow-800 border-yellow-200",
  }[tipo];
  return <div className={`border rounded-lg px-3 py-2 text-sm ${clases}`}>{children}</div>;
}

/** Modal centrado con encabezado y pie. */
export function Modal({ titulo, eyebrow, onClose, children, footer, ancho = "max-w-3xl" }) {
  return (
    <div
      className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4"
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div role="dialog" aria-modal="true" aria-label={titulo}
           className={`bg-surface rounded-xl shadow-xl w-full ${ancho} max-h-[92vh] flex flex-col`}>
        <div className="flex items-start gap-3 px-5 py-4 border-b">
          <div>
            {eyebrow && <p className="text-xs uppercase tracking-wide text-blue-600 font-semibold">{eyebrow}</p>}
            <h2 className="font-semibold text-gray-800">{titulo}</h2>
          </div>
          <button onClick={onClose} aria-label="Cerrar" className="ml-auto p-1 text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>
        <div className="px-5 py-4 overflow-y-auto">{children}</div>
        {footer && <div className="flex items-center gap-2 px-5 py-3 border-t bg-gray-50 rounded-b-xl">{footer}</div>}
      </div>
    </div>
  );
}
