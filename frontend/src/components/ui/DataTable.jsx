import { useMemo, useState } from "react";

/**
 * Tabla compartida: orden por columna y paginado, en modo servidor (el padre controla
 * `total/offset/sort/order`) o en modo cliente (`clientSort` / `pageSize` ordenan y paginan en memoria).
 *
 * columns: [{ key, label, align?: "right", sortable?, render?(row), sortValue?(row) }]
 */
export function DataTable({
  columns, rows, total, limit = 25, offset = 0, sort, order = "asc",
  onSort, onPage, clientSort, pageSize, defaultSort, rowKey, rowClass, onRowClick,
  emptyText = "Sin datos",
}) {
  const colCount = columns.length;
  const [cSort, setCSort] = useState(defaultSort || "");
  const [cOrder, setCOrder] = useState("asc");
  const [cOffset, setCOffset] = useState(0);

  const usaCliente = clientSort || pageSize != null;
  const sortActivo = usaCliente ? cSort : sort;
  const orderActivo = usaCliente ? cOrder : order;

  function handleSort(key) {
    if (onSort) return onSort(key);
    if (!usaCliente) return;
    const o = cSort === key && cOrder === "asc" ? "desc" : "asc";
    setCSort(key); setCOrder(o); setCOffset(0);
  }

  const ordenadas = useMemo(() => {
    if (!usaCliente || !cSort) return rows;
    const col = columns.find((c) => c.key === cSort);
    const val = (r) => (col?.sortValue ? col.sortValue(r) : r[cSort]);
    const dir = cOrder === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const va = val(a), vb = val(b);
      if (va == null) return 1;
      if (vb == null) return -1;
      if (typeof va === "number" && typeof vb === "number") return (va - vb) * dir;
      return String(va).localeCompare(String(vb), "es", { numeric: true }) * dir;
    });
  }, [usaCliente, cSort, cOrder, rows, columns]);

  const pageLimit = pageSize ?? limit;
  const pageOffset = pageSize != null ? cOffset : offset;
  const totalRows = pageSize != null ? ordenadas.length : total;
  const visibles = pageSize != null ? ordenadas.slice(cOffset, cOffset + pageSize) : ordenadas;

  const paginado = (total != null && onPage) || pageSize != null;
  const desde = totalRows ? pageOffset + 1 : 0;
  const hasta = Math.min(pageOffset + pageLimit, totalRows ?? visibles.length);

  const irPagina = (off) => (pageSize != null ? setCOffset(off) : onPage && onPage(off));

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              {columns.map((c) => {
                const clickable = c.sortable && (onSort || usaCliente);
                const activo = c.sortable && sortActivo === c.key;
                return (
                  <th
                    key={c.key}
                    scope="col"
                    onClick={() => clickable && handleSort(c.key)}
                    className={`px-3 py-2 text-xs font-semibold uppercase tracking-wide text-gray-500 whitespace-nowrap ${
                      c.align === "right" ? "text-right" : "text-left"} ${
                      clickable ? "cursor-pointer select-none hover:text-gray-700" : ""}`}
                  >
                    {c.label}
                    {c.sortable && (
                      <span className={`ml-1 text-[10px] ${activo ? "text-blue-600" : "text-gray-300"}`}>
                        {activo ? (orderActivo === "asc" ? "▲" : "▼") : "↕"}
                      </span>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {visibles.map((r, i) => (
              <tr
                key={rowKey ? rowKey(r, i) : i}
                onClick={onRowClick ? () => onRowClick(r) : undefined}
                className={`${onRowClick ? "cursor-pointer" : ""} hover:bg-gray-50 ${rowClass ? rowClass(r) || "" : ""}`}
              >
                {columns.map((c) => (
                  <td key={c.key} className={`px-3 py-2 text-gray-700 ${c.align === "right" ? "text-right tabular-nums" : ""}`}>
                    {c.render ? c.render(r) : r[c.key]}
                  </td>
                ))}
              </tr>
            ))}
            {!visibles.length && (
              <tr><td colSpan={colCount} className="px-3 py-8 text-center text-sm text-gray-400">{emptyText}</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {paginado && (
        <div className="flex items-center justify-between gap-2 pt-3">
          <span className="text-xs text-gray-500">
            {totalRows ? `${desde}–${hasta} de ${Number(totalRows).toLocaleString("es-AR")}` : "0 resultados"}
          </span>
          <div className="flex gap-2">
            <button
              disabled={pageOffset <= 0}
              onClick={() => irPagina(Math.max(0, pageOffset - pageLimit))}
              className="px-3 py-1.5 text-sm border rounded-lg text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:hover:bg-surface"
            >‹ Anterior</button>
            <button
              disabled={hasta >= (totalRows ?? 0)}
              onClick={() => irPagina(pageOffset + pageLimit)}
              className="px-3 py-1.5 text-sm border rounded-lg text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:hover:bg-surface"
            >Siguiente ›</button>
          </div>
        </div>
      )}
    </>
  );
}
