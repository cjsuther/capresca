import { useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: any) =>
  v == null ? "—" : Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const num = (v: any) => (v == null ? "—" : Number(v).toLocaleString("es-AR"));
const tachado = (r: any) => (r.anulado ? { opacity: 0.5, textDecoration: "line-through" as const } : undefined);

const COLS_LIQ: Col[] = [
  { key: "juego", label: "Juego", sortable: true, render: (l) => l.juego || l.cod_juego },
  { key: "no_sorteo", label: "Sorteo", sortable: true, align: "right" },
  { key: "fecha_sorteo", label: "Fecha sorteo", sortable: true, render: (l) => l.fecha_sorteo || "—" },
  { key: "recaudacion", label: "Recaudación", sortable: true, align: "right", sortValue: (l) => Number(l.recaudacion), render: (l) => money(l.recaudacion) },
  { key: "total_gral", label: "Total gral.", sortable: true, align: "right", sortValue: (l) => Number(l.total_gral), render: (l) => money(l.total_gral) },
  { key: "fecha_vto", label: "Vto.", sortable: true, render: (l) => l.fecha_vto || "—" },
  { key: "estado", label: "Estado", render: (l) => (l.anulado ? "anulado" : l.pagado ? "pagado" : "pendiente") },
];
const COLS_PAG: Col[] = [
  { key: "fecha_pago", label: "Fecha", sortable: true, render: (p) => p.fecha_pago || "—" },
  { key: "no_recibo", label: "Recibo", sortable: true, align: "right", render: (p) => p.no_recibo || "—" },
  { key: "origen", label: "Origen", sortable: true, render: (p) => p.origen || "—" },
  { key: "bonos", label: "Bonos", sortable: true, align: "right", sortValue: (p) => Number(p.bonos), render: (p) => money(p.bonos) },
  { key: "pesos", label: "Pesos", sortable: true, align: "right", sortValue: (p) => Number(p.pesos), render: (p) => money(p.pesos) },
  { key: "cobrado_total", label: "Cobrado", sortable: true, align: "right", sortValue: (p) => Number(p.cobrado_total), render: (p) => money(p.cobrado_total) },
  { key: "cajero", label: "Cajero", sortable: true, render: (p) => p.cajero || "—" },
  { key: "estado", label: "Estado", render: (p) => (p.anulado ? "anulado" : "") },
];

// Histórico de agencia (VFP: Caja/cj_liqhis.dbf + cj_paghis.dbf).
export default function AgenciaHistorico() {
  const [ag, setAg] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  async function ver(e?: React.FormEvent) {
    e?.preventDefault(); setError("");
    try { setData(await api.agenciaHistorico(Number(ag), desde, hasta)); }
    catch (err: any) { setError(err.message); setData(null); }
  }

  return (
    <>
      <div className="card">
        <h1 style={{ marginTop: 0 }}>Histórico de agencia (liquidaciones y pagos)</h1>
        <p className="muted">Liquidaciones y pagos archivados de una agencia. Fuente real: <code>cj_liqhis.dbf</code> (1,37M) + <code>cj_paghis.dbf</code> (652k).</p>
        <form onSubmit={ver} style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap" }}>
          <div><label>N° de agencia</label><input value={ag} onChange={(e) => setAg(e.target.value)} placeholder="Ej.: 113" style={{ marginBottom: 0, width: 120 }} /></div>
          <div><label>Desde</label><input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <div><label>Hasta</label><input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <button type="submit">Ver</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {data && (
        <>
          <div className="card">
            <h3 style={{ marginTop: 0 }}>Liquidaciones — agencia {data.no_agencia} · {num(data.liquidaciones.total)} · {money(data.liquidaciones.importe)}</h3>
            <DataTable columns={COLS_LIQ} rows={data.liquidaciones.items} rowStyle={tachado}
                       clientSort pageSize={50} defaultSort="no_sorteo" emptyText="Sin liquidaciones." />
          </div>

          <div className="card">
            <h3 style={{ marginTop: 0 }}>Pagos — {num(data.pagos.total)} · {money(data.pagos.importe)}</h3>
            <DataTable columns={COLS_PAG} rows={data.pagos.items} rowStyle={tachado}
                       clientSort pageSize={50} defaultSort="fecha_pago" emptyText="Sin pagos archivados." />
          </div>
        </>
      )}
    </>
  );
}
