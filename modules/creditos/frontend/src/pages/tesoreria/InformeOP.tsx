import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const LIMIT = 25;
const ESTADO: Record<string, string> = { P: "Pendiente", G: "Girada", A: "Anulada" };

type Filtros = { estado: string; tipo: string; q: string; desde: string; hasta: string };
const VACIO: Filtros = { estado: "", tipo: "", q: "", desde: "", hasta: "" };

export default function InformeOP() {
  const [f, setF] = useState<Filtros>({ ...VACIO });
  const [aplicado, setAplicado] = useState<Filtros>({ ...VACIO });
  const [rows, setRows] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState("numero");
  const [order, setOrder] = useState<"asc" | "desc">("desc");

  const params = (a: Filtros) => ({
    estado: a.estado || undefined, tipo: a.tipo || undefined, q: a.q || undefined,
    desde: a.desde || undefined, hasta: a.hasta || undefined,
  });

  async function cargar(off = 0, a = aplicado, s = sort, o = order) {
    const d = await api.informeOP({ ...params(a), limit: LIMIT, offset: off, sort: s, order: o });
    setRows(d.items); setTotal(d.total); setOffset(off); setSort(s); setOrder(o);
  }
  useEffect(() => { cargar(0, aplicado); }, [aplicado]);

  function onSort(key: string) {
    const o = sort === key && order === "asc" ? "desc" : "asc";
    cargar(0, aplicado, key, o);
  }
  const set = (k: keyof Filtros) => (e: any) => setF({ ...f, [k]: e.target.value });

  const cols: Col[] = [
    { key: "numero", label: "N°", sortable: true },
    { key: "fecha", label: "Fecha", sortable: true },
    { key: "beneficiario", label: "Beneficiario", sortable: true },
    { key: "tipo", label: "Tipo" },
    { key: "concepto", label: "Concepto" },
    { key: "importe", label: "Importe", sortable: true, align: "right", render: (o) => money(o.importe) },
    { key: "estado", label: "Estado", render: (o) => ESTADO[o.estado] || o.estado },
    { key: "cheque_numero", label: "Cheque", render: (o) => o.cheque_numero || "-" },
  ];

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>Informe de órdenes de pago</h2>
        <button onClick={() => api.descargarInformeOPExcel(params(aplicado))} style={{ background: "var(--ok)" }}>Descargar Excel</button>
      </div>
      <p className="muted" style={{ marginTop: "0.4rem" }}>Generador: combiná estado, tipo, beneficiario y fechas. Cubre el submenú de reportes de OP (830).</p>
      <div className="grid3" style={{ marginTop: "0.5rem" }}>
        <div><label>Estado</label>
          <select value={f.estado} onChange={set("estado")}>
            <option value="">Todos</option><option value="P">Pendientes</option>
            <option value="G">Giradas</option><option value="A">Anuladas</option>
          </select></div>
        <div><label>Tipo</label>
          <select value={f.tipo} onChange={set("tipo")}>
            <option value="">Todos</option><option value="CREDITO">Crédito</option>
            <option value="SEGURO">Seguro</option><option value="PROVEEDOR">Proveedor</option>
          </select></div>
        <div><label>Beneficiario / CUIT</label><input value={f.q} onChange={set("q")} /></div>
      </div>
      <div className="grid3">
        <div><label>Desde</label><input type="date" value={f.desde} onChange={set("desde")} /></div>
        <div><label>Hasta</label><input type="date" value={f.hasta} onChange={set("hasta")} /></div>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
          <button onClick={() => setAplicado({ ...f })}>Generar</button>
          <button onClick={() => { setF({ ...VACIO }); setAplicado({ ...VACIO }); }} style={{ background: "var(--ink-faint)" }}>Limpiar</button>
        </div>
      </div>
      <p className="muted" style={{ marginTop: "0.8rem" }}><b>{Number(total).toLocaleString("es-AR")}</b> órdenes de pago</p>
      <DataTable columns={cols} rows={rows} total={total} limit={LIMIT} offset={offset}
                 sort={sort} order={order} onSort={onSort} onPage={(off) => cargar(off)}
                 rowKey={(o) => o.id} emptyText="Sin órdenes para los filtros" />
    </div>
  );
}
