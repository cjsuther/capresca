import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const LIMIT = 25;

type Filtros = {
  estado: string; linea_id: string; cartera: string; organismo_id: string;
  desde: string; hasta: string; con_saldo: string; q: string;
};
const VACIO: Filtros = { estado: "", linea_id: "", cartera: "", organismo_id: "", desde: "", hasta: "", con_saldo: "", q: "" };

export default function InformeCreditos() {
  const [f, setF] = useState<Filtros>({ ...VACIO });
  const [aplicado, setAplicado] = useState<Filtros>({ ...VACIO });
  const [lineas, setLineas] = useState<any[]>([]);
  const [carteras, setCarteras] = useState<any[]>([]);
  const [organismos, setOrganismos] = useState<any[]>([]);
  const [data, setData] = useState<any>({ items: [], total: 0, total_capital: 0, total_saldo: 0 });
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState("credito_id");
  const [order, setOrder] = useState<"asc" | "desc">("desc");

  useEffect(() => {
    api.lineas().then(setLineas);
    api.situacionPorCartera().then((d) => setCarteras(d.por_cartera));
    api.adminOrganismos().then(setOrganismos).catch(() => {});
  }, []);

  const params = (a: Filtros) => ({
    estado: a.estado || undefined, linea_id: a.linea_id || undefined,
    cartera: a.cartera || undefined, organismo_id: a.organismo_id || undefined,
    desde: a.desde || undefined, hasta: a.hasta || undefined,
    con_saldo: a.con_saldo || undefined, q: a.q || undefined,
  });

  async function cargar(off = 0, a = aplicado, s = sort, o = order) {
    const d = await api.informeCreditos({ ...params(a), limit: LIMIT, offset: off, sort: s, order: o });
    setData(d); setOffset(off); setSort(s); setOrder(o);
  }
  useEffect(() => { cargar(0, aplicado); }, [aplicado]);

  function onSort(key: string) {
    const o = sort === key && order === "asc" ? "desc" : "asc";
    cargar(0, aplicado, key, o);
  }
  const set = (k: keyof Filtros) => (e: any) => setF({ ...f, [k]: e.target.value });

  const cols: Col[] = [
    { key: "credito_id", label: "Crédito", sortable: true },
    { key: "cliente", label: "Cliente", sortable: true },
    { key: "cuil", label: "CUIL" },
    { key: "linea", label: "Línea" },
    { key: "fecha_otorgamiento", label: "Otorgado", sortable: true, render: (c) => c.fecha_otorgamiento || "-" },
    { key: "capital", label: "Capital", sortable: true, align: "right", render: (c) => money(c.capital) },
    { key: "saldo", label: "Saldo", sortable: true, align: "right", render: (c) => money(c.saldo) },
    { key: "estado", label: "Estado", render: (c) => (c.estado === "A" ? "Activo" : c.estado === "C" ? "Cancelado" : c.estado) },
  ];

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>Informe de créditos</h2>
        <button onClick={() => api.descargarInformeCreditosExcel({ ...params(aplicado), sort, order })}
                style={{ background: "var(--ok)" }}>Descargar Excel</button>
      </div>
      <p className="muted" style={{ marginTop: "0.4rem" }}>Generador de informes: combiná filtros (estado, línea, cartera, organismo, fechas, saldo). Cubre el submenú de reportes de Créditos.</p>

      <div className="grid3" style={{ marginTop: "0.5rem" }}>
        <div><label>Estado</label>
          <select value={f.estado} onChange={set("estado")}>
            <option value="">Todos</option><option value="A">Activos</option><option value="C">Cancelados</option>
          </select></div>
        <div><label>Línea</label>
          <select value={f.linea_id} onChange={set("linea_id")}>
            <option value="">Todas</option>
            {lineas.map((l) => <option key={l.id} value={l.id}>{l.nombre}</option>)}
          </select></div>
        <div><label>Cartera</label>
          <select value={f.cartera} onChange={set("cartera")}>
            <option value="">Todas</option>
            {carteras.map((c) => <option key={c.cartera} value={c.cartera}>{c.nombre}</option>)}
          </select></div>
      </div>
      <div className="grid3">
        <div><label>Organismo</label>
          <select value={f.organismo_id} onChange={set("organismo_id")}>
            <option value="">Todos</option>
            {organismos.map((o) => <option key={o.id} value={o.id}>{o.nombre}</option>)}
          </select></div>
        <div><label>Saldo</label>
          <select value={f.con_saldo} onChange={set("con_saldo")}>
            <option value="">Cualquiera</option><option value="true">Con saldo &gt; 0</option><option value="false">Sin saldo</option>
          </select></div>
        <div><label>Buscar cliente / CUIL</label><input value={f.q} onChange={set("q")} /></div>
      </div>
      <div className="grid3">
        <div><label>Otorgado desde</label><input type="date" value={f.desde} onChange={set("desde")} /></div>
        <div><label>Otorgado hasta</label><input type="date" value={f.hasta} onChange={set("hasta")} /></div>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
          <button onClick={() => setAplicado({ ...f })}>Generar</button>
          <button onClick={() => { setF({ ...VACIO }); setAplicado({ ...VACIO }); }} style={{ background: "var(--ink-faint)" }}>Limpiar</button>
        </div>
      </div>

      <p className="muted" style={{ marginTop: "0.8rem" }}>
        <b>{Number(data.total).toLocaleString("es-AR")}</b> créditos · capital {money(data.total_capital || 0)} · saldo {money(data.total_saldo || 0)}
      </p>
      <DataTable columns={cols} rows={data.items} total={data.total} limit={LIMIT} offset={offset}
                 sort={sort} order={order} onSort={onSort} onPage={(off) => cargar(off)}
                 rowKey={(c) => c.credito_id} emptyText="Sin créditos para los filtros" />
    </div>
  );
}
