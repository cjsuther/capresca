import { ReactNode, useMemo, useState } from "react";
import Icon from "./Icon";
import RowMenu, { RowAction } from "./RowMenu";

export type Col = {
  key: string;
  label: string;
  sortable?: boolean;
  align?: "left" | "right";
  render?: (row: any) => ReactNode;
  /** Valor usado para ordenar en modo cliente (por defecto row[key]). */
  sortValue?: (row: any) => string | number;
};

type Props = {
  columns: Col[];
  rows: any[];
  /** --- Modo servidor (el padre controla orden/paginado) --- */
  total?: number;
  limit?: number;
  offset?: number;
  sort?: string;
  order?: "asc" | "desc";
  onSort?: (key: string) => void;
  onPage?: (offset: number) => void;
  /** --- Modo cliente (DataTable ordena/pagina sobre `rows` en memoria) --- */
  clientSort?: boolean;
  /** Si se define, pagina en el cliente con este tamaño de página. */
  pageSize?: number;
  defaultSort?: string;
  rowKey?: (row: any, i: number) => string | number;
  rowStyle?: (row: any) => React.CSSProperties | undefined;
  /** Menú ⋮ de acciones por fila, en la primera columna. */
  actions?: (row: any) => RowAction[];
  emptyText?: string;
};

/** Tabla reutilizable con orden por columna y paginado (modo servidor o cliente). */
export default function DataTable({
  columns, rows, total, limit = 25, offset = 0, sort, order = "asc",
  onSort, onPage, clientSort, pageSize, defaultSort, rowKey, rowStyle, actions, emptyText = "Sin datos",
}: Props) {
  const colCount = columns.length + (actions ? 1 : 0);
  // Estado interno para el modo cliente.
  const [cSort, setCSort] = useState<string>(defaultSort || "");
  const [cOrder, setCOrder] = useState<"asc" | "desc">("asc");
  const [cOffset, setCOffset] = useState(0);

  const usaCliente = clientSort || pageSize != null;
  const sortActivo = usaCliente ? cSort : sort;
  const orderActivo = usaCliente ? cOrder : order;

  function handleSort(key: string) {
    if (onSort) return onSort(key);
    if (!usaCliente) return;
    const o = cSort === key && cOrder === "asc" ? "desc" : "asc";
    setCSort(key); setCOrder(o); setCOffset(0);
  }

  // Orden en memoria (sólo modo cliente).
  const ordenadas = useMemo(() => {
    if (!usaCliente || !cSort) return rows;
    const col = columns.find((c) => c.key === cSort);
    const val = (r: any) => (col?.sortValue ? col.sortValue(r) : r[cSort]);
    const dir = cOrder === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const va = val(a), vb = val(b);
      if (va == null) return 1;
      if (vb == null) return -1;
      if (typeof va === "number" && typeof vb === "number") return (va - vb) * dir;
      return String(va).localeCompare(String(vb), "es", { numeric: true }) * dir;
    });
  }, [usaCliente, cSort, cOrder, rows, columns]);

  // Paginado.
  const pageLimit = pageSize ?? limit;
  const pageOffset = pageSize != null ? cOffset : offset;
  const totalRows = pageSize != null ? ordenadas.length : total;
  const visibles = pageSize != null
    ? ordenadas.slice(cOffset, cOffset + pageSize)
    : ordenadas;

  const paginado = (total != null && onPage) || (pageSize != null);
  const desde = totalRows ? pageOffset + 1 : 0;
  const hasta = Math.min(pageOffset + pageLimit, totalRows ?? visibles.length);

  function irPagina(off: number) {
    if (pageSize != null) return setCOffset(off);
    onPage && onPage(off);
  }

  return (
    <>
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              {actions && (
                <th className="col-actions" aria-label="Acciones" title="Acciones">
                  <Icon name="row-actions" size={16} />
                </th>
              )}
              {columns.map((c) => {
                const clickable = c.sortable && (onSort || usaCliente);
                const activo = c.sortable && sortActivo === c.key;
                return (
                  <th key={c.key}
                      className={clickable ? "sortable" : undefined}
                      style={{ textAlign: c.align || "left", cursor: clickable ? "pointer" : "default", userSelect: "none" }}
                      onClick={() => clickable && handleSort(c.key)}>
                    {c.label}
                    {c.sortable && (
                      <span style={{ marginLeft: 4, fontSize: 10,
                                     color: activo ? "var(--brand)" : "var(--border-strong)" }}>
                        {activo ? (orderActivo === "asc" ? "▲" : "▼") : "↕"}
                      </span>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {visibles.map((r, i) => (
              <tr key={rowKey ? rowKey(r, i) : i} style={rowStyle ? rowStyle(r) : undefined}>
                {actions && (
                  <td className="col-actions" onClick={(e) => e.stopPropagation()}>
                    <RowMenu actions={actions(r)} />
                  </td>
                )}
                {columns.map((c) => (
                  <td key={c.key} style={{ textAlign: c.align || "left" }}>
                    {c.render ? c.render(r) : r[c.key]}
                  </td>
                ))}
              </tr>
            ))}
            {!visibles.length && (
              <tr><td colSpan={colCount} className="muted">{emptyText}</td></tr>
            )}
          </tbody>
        </table>
      </div>
      {paginado && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "0.7rem" }}>
          <span className="muted">
            {totalRows ? `${desde}–${hasta} de ${totalRows.toLocaleString("es-AR")}` : "0 resultados"}
          </span>
          <div style={{ display: "flex", gap: "0.4rem" }}>
            <button disabled={pageOffset <= 0} onClick={() => irPagina(Math.max(0, pageOffset - pageLimit))}
                    style={{ background: pageOffset <= 0 ? "#aaa" : undefined }}>‹ Anterior</button>
            <button disabled={hasta >= (totalRows ?? 0)} onClick={() => irPagina(pageOffset + pageLimit)}
                    style={{ background: hasta >= (totalRows ?? 0) ? "#aaa" : undefined }}>Siguiente ›</button>
          </div>
        </div>
      )}
    </>
  );
}
