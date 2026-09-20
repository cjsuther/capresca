/** Botón estándar "Limpiar filtros": sólo se muestra cuando hay algún filtro activo. */
export default function LimpiarFiltros({ activo, onClear }: { activo: boolean; onClear: () => void }) {
  if (!activo) return null;
  return (
    <button type="button" className="btn-limpiar" onClick={onClear}
            title="Quitar todos los filtros y ver el listado completo">
      ✕ Limpiar filtros
    </button>
  );
}
