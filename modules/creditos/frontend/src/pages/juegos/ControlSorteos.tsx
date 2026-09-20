import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const LIMIT = 25;

export default function ControlSorteos() {
  const [juegos, setJuegos] = useState<any[]>([]);
  const [codJuego, setCodJuego] = useState<string>("");
  const [rows, setRows] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState("fecha_sorteo");
  const [order, setOrder] = useState<"asc" | "desc">("desc");

  useEffect(() => { api.maestroJuegos().then(setJuegos); }, []);

  async function cargar(off = offset, s = sort, o = order, cod = codJuego) {
    const d = await api.sorteos({
      cod_juego: cod !== "" ? Number(cod) : undefined,
      limit: LIMIT, offset: off, sort: s, order: o,
    });
    setRows(d.items); setTotal(d.total); setOffset(off); setSort(s); setOrder(o);
  }
  useEffect(() => { cargar(0, sort, order, codJuego); }, [codJuego]);

  function onSort(key: string) {
    const o = sort === key && order === "asc" ? "desc" : "asc";
    cargar(0, key, o, codJuego);
  }

  // Códigos únicos para el filtro (modalidad base).
  const codigos = Array.from(new Map(juegos.map((j) => [j.codigo, j.denominacion])).entries());

  const cols: Col[] = [
    { key: "cod_juego", label: "Cód.", sortable: true },
    { key: "juego", label: "Juego" },
    { key: "no_sorteo", label: "N° sorteo", sortable: true },
    { key: "fecha_sorteo", label: "Fecha sorteo", sortable: true, render: (s) => s.fecha_sorteo || "-" },
    { key: "fecha_vto", label: "Vencimiento", sortable: true, render: (s) => s.fecha_vto || "-" },
    { key: "importado_caja", label: "En caja", render: (s) => (s.importado_caja ? "Sí" : "—") },
  ];

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Control de sorteos</h2>
      <p className="muted">Calendario de sorteos/jugadas por juego, con fecha de vencimiento y si fueron importados a caja. Fuente: maejugadas.</p>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "end", marginBottom: "0.8rem" }}>
        <div><label>Juego</label>
          <select value={codJuego} onChange={(e) => setCodJuego(e.target.value)} style={{ marginBottom: 0 }}>
            <option value="">Todos</option>
            {codigos.map(([cod, den]) => <option key={cod} value={cod}>{den}</option>)}
          </select>
        </div>
      </div>
      <DataTable columns={cols} rows={rows} total={total} limit={LIMIT} offset={offset}
                 sort={sort} order={order} onSort={onSort} onPage={(off) => cargar(off)}
                 rowKey={(s) => s.id} emptyText="Sin sorteos" />
    </div>
  );
}
