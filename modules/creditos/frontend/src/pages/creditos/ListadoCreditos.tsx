import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const LIMIT = 25;

export default function ListadoCreditos() {
  const [data, setData] = useState<any>({ items: [], total: 0, total_saldo: 0 });
  const [estado, setEstado] = useState("");
  const [busq, setBusq] = useState("");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState("credito_id");
  const [order, setOrder] = useState<"asc" | "desc">("desc");

  async function cargar(off = offset, s = sort, o = order) {
    const d = await api.listadoCreditos({
      estado: estado || undefined, q: q || undefined,
      limit: LIMIT, offset: off, sort: s, order: o,
    });
    setData(d); setOffset(off); setSort(s); setOrder(o);
  }
  useEffect(() => { cargar(0, sort, order); }, [estado, q]);

  function onSort(key: string) {
    const o = sort === key && order === "asc" ? "desc" : "asc";
    cargar(0, key, o);
  }

  const cols: Col[] = [
    { key: "credito_id", label: "Crédito", sortable: true },
    { key: "cliente", label: "Cliente", sortable: true },
    { key: "linea", label: "Línea" },
    { key: "capital", label: "Capital", sortable: true, align: "right", render: (c) => money(c.capital) },
    { key: "saldo", label: "Saldo", sortable: true, align: "right", render: (c) => money(c.saldo) },
    { key: "estado", label: "Estado", render: (c) => (c.estado === "A" ? "Activo" : c.estado === "C" ? "Cancelado" : c.estado) },
  ];

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>Listado de créditos</h2>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <button onClick={() => api.descargarListadoCreditosExcel({
            estado: estado || undefined, q: q || undefined, sort, order,
          })} style={{ background: "var(--ok)" }}>Descargar Excel</button>
          <form onSubmit={(e) => { e.preventDefault(); setQ(busq); }}>
            <input value={busq} onChange={(e) => setBusq(e.target.value)} placeholder="Buscar cliente / CUIL" style={{ marginBottom: 0 }} />
          </form>
          <select value={estado} onChange={(e) => setEstado(e.target.value)} style={{ width: "auto", marginBottom: 0 }}>
            <option value="">Todos</option>
            <option value="A">Activos</option>
            <option value="C">Cancelados</option>
          </select>
        </div>
      </div>
      <p className="muted" style={{ marginTop: "0.5rem" }}>
        {Number(data.total).toLocaleString("es-AR")} créditos · saldo total {money(data.total_saldo || 0)}
      </p>
      <DataTable columns={cols} rows={data.items} total={data.total} limit={LIMIT} offset={offset}
                 sort={sort} order={order} onSort={onSort} onPage={(off) => cargar(off)}
                 rowKey={(c) => c.credito_id} emptyText="Sin créditos" />
    </div>
  );
}
