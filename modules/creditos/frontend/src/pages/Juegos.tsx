import { useEffect, useState } from "react";
import { api } from "../api";
import DataTable, { Col } from "../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const JUEGOS = ["quiniela", "quini6", "loto", "brinco", "prode", "telekino"];
const LIMIT = 25;

export default function Juegos() {
  const [agencias, setAgencias] = useState<any[]>([]);
  const [resumen, setResumen] = useState<any>(null);
  const [liqs, setLiqs] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [soloPend, setSoloPend] = useState(true);

  async function cargarLiqs(off = 0, pend = soloPend) {
    const d = await api.liquidacionesJuego({ pagado: pend ? false : undefined, limit: LIMIT, offset: off });
    setLiqs(d.items); setTotal(d.total); setOffset(off);
  }
  useEffect(() => {
    api.agenciasJuego().then(setAgencias);
    api.resumenJuegos().then(setResumen);
  }, []);
  useEffect(() => { cargarLiqs(0, soloPend); }, [soloPend]);

  async function cobrar(id: number) {
    const recibo = Math.floor(Math.random() * 90000) + 10000;
    await api.cobrarLiquidacion(id, recibo);
    cargarLiqs(offset);
  }

  const cols: Col[] = [
    { key: "agencia", label: "Agencia", render: (l) => `${l.no_agencia}${l.subagencia ? `/${l.subagencia}` : ""}` },
    { key: "juego", label: "Juego" },
    { key: "no_sorteo", label: "Sorteo" },
    { key: "fecha_sorteo", label: "Fecha", render: (l) => l.fecha_sorteo || "-" },
    { key: "recaudacion", label: "Recaudación", align: "right", render: (l) => money(l.recaudacion) },
    { key: "premios", label: "Premios", align: "right", render: (l) => money(l.premios) },
    { key: "total", label: "Total", align: "right", render: (l) => <b>{money(l.total)}</b> },
    { key: "estado", label: "Estado", render: (l) => (l.pagado ? "Cobrada" : "Pendiente") },
    {
      key: "acc", label: "", align: "right", render: (l) =>
        !l.pagado ? <a href="#" onClick={(e) => { e.preventDefault(); cobrar(l.id); }}>cobrar</a> : null,
    },
  ];

  return (
    <>
      {resumen && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Juegos / Quiniela — resumen</h2>
          <div className="grid3">
            <div><div className="kpi">{money(resumen.recaudacion)}</div><div className="kpi-label">Recaudación</div></div>
            <div><div className="kpi">{money(resumen.premios)}</div><div className="kpi-label">Premios</div></div>
            <div><div className="kpi">{money(resumen.comisiones)}</div><div className="kpi-label">Comisiones agencia</div></div>
          </div>
          <p className="muted" style={{ marginTop: "0.6rem" }}>
            {resumen.cantidad.toLocaleString("es-AR")} liquidaciones · multas {money(resumen.multas)} · total a cobrar {money(resumen.total)}
          </p>
        </div>
      )}

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Agencias ({agencias.length})</h3>
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead><tr><th>N°</th><th>Subag.</th><th>Interior</th>{JUEGOS.map(j => <th key={j}>{j}</th>)}</tr></thead>
            <tbody>
              {agencias.slice(0, 30).map((a) => (
                <tr key={a.id}>
                  <td>{a.numero}</td><td>{a.subagencia}</td><td>{a.interior ? "Sí" : "—"}</td>
                  {JUEGOS.map(j => <td key={j} style={{ textAlign: "center" }}>{a[j] ? "✓" : ""}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0 }}>Liquidaciones de agencias</h3>
          <label style={{ margin: 0 }}>
            <input type="checkbox" checked={soloPend} onChange={(e) => setSoloPend(e.target.checked)} style={{ width: "auto" }} /> solo pendientes
          </label>
        </div>
        <div style={{ marginTop: "0.6rem" }}>
          <DataTable columns={cols} rows={liqs} total={total} limit={LIMIT} offset={offset}
                     onPage={(off) => cargarLiqs(off)} rowKey={(l) => l.id}
                     emptyText="Sin liquidaciones" />
        </div>
      </div>
    </>
  );
}
