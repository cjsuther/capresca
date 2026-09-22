import { useEffect, useState } from "react";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Toolbar, Field, Boton, LimpiarFiltros, Alerta } from "../../components/ui";
import { money, num } from "../../components/format";

const LIMIT = 25;
const ESTADO = { A: "Activo", C: "Cancelado" };

const COLS = [
  { key: "credito_id", label: "Crédito", sortable: true },
  { key: "cliente", label: "Cliente", sortable: true },
  { key: "linea", label: "Línea" },
  { key: "capital", label: "Capital", sortable: true, align: "right", render: (c) => money(c.capital) },
  { key: "saldo", label: "Saldo", sortable: true, align: "right", render: (c) => money(c.saldo) },
  { key: "estado", label: "Estado", render: (c) => ESTADO[c.estado] || c.estado },
];

export default function ListadoCreditosPage() {
  const [data, setData] = useState({ items: [], total: 0, total_saldo: 0 });
  const [estado, setEstado] = useState("");
  const [busq, setBusq] = useState("");
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState("credito_id");
  const [order, setOrder] = useState("desc");
  const [error, setError] = useState("");

  // Los filtros viajan por argumento: si se leyeran del estado, "Limpiar" pediría los datos con los
  // valores del render anterior (H-206).
  async function cargar(off = offset, s = sort, o = order, f = {}) {
    setError("");
    const est = f.estado ?? estado;
    const texto = f.q ?? q;
    try {
      const d = await creditos.listadoCreditos({
        estado: est || undefined, q: texto || undefined, limit: LIMIT, offset: off, sort: s, order: o,
      });
      setData(d); setOffset(off); setSort(s); setOrder(o);
    } catch (e) { setError(e.message); }
  }
  useEffect(() => { cargar(0, sort, order); }, [estado, q]);

  const onSort = (key) => cargar(0, key, sort === key && order === "asc" ? "desc" : "asc");

  return (
    <>
      <PageHeader titulo="Listado de créditos" descripcion="Cartera completa, con capital, saldo y estado de cada crédito.">
        <Boton variante="ok" onClick={() => creditos.descargarListadoCreditosExcel({
          estado: estado || undefined, q: q || undefined, sort, order,
        })}>Descargar Excel</Boton>
      </PageHeader>

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      <Card padding={false}>
        <Toolbar>
          <form onSubmit={(e) => { e.preventDefault(); setQ(busq); }} className="flex items-end gap-2">
            <input className="input w-64" value={busq} onChange={(e) => setBusq(e.target.value)}
                   placeholder="Buscar cliente / CUIL" />
            <button type="submit" className="px-3 py-2 text-sm border rounded-lg text-gray-600 hover:bg-gray-50">Buscar</button>
          </form>
          <Field label="Estado">
            <select className="input" value={estado} onChange={(e) => setEstado(e.target.value)}>
              <option value="">Todos</option>
              <option value="A">Activos</option>
              <option value="C">Cancelados</option>
            </select>
          </Field>
          <LimpiarFiltros activo={!!q || !!busq || !!estado} onClear={() => { setBusq(""); setQ(""); setEstado(""); }} />
          <span className="ml-auto text-sm text-gray-500">
            {num(data.total)} créditos · saldo <b>{money(data.total_saldo || 0)}</b>
          </span>
        </Toolbar>
        <div className="p-4">
          <DataTable columns={COLS} rows={data.items} total={data.total} limit={LIMIT} offset={offset}
                     sort={sort} order={order} onSort={onSort} onPage={(off) => cargar(off)}
                     rowKey={(c) => c.credito_id} emptyText="Sin créditos" />
        </div>
      </Card>
    </>
  );
}
