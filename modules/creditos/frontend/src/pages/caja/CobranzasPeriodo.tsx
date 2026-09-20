import { useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";
import LimpiarFiltros from "../../components/LimpiarFiltros";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const COLS: Col[] = [
  { key: "origen", label: "Origen", sortable: true },
  { key: "denominacion", label: "Denominación", sortable: true },
  { key: "nombres", label: "Nombres", sortable: true },
  { key: "no_recibo", label: "N° Recibo", sortable: true, align: "right" },
  { key: "fecha_pago", label: "Fecha", sortable: true },
  { key: "via_pago", label: "Vía", sortable: true },
  { key: "cajero", label: "Cajero", sortable: true },
  { key: "total", label: "Total", sortable: true, align: "right", sortValue: (it) => Number(it.total), render: (it) => <b>{money(it.total)}</b> },
];

// Informe de cobranzas en un período (23065 / frminformecobros): unifica los recibos
// de créditos/seguros y los cobros de quiniela entre dos fechas.
export default function CobranzasPeriodo() {
  const hoy = new Date().toISOString().slice(0, 10);
  const [desde, setDesde] = useState(hoy);
  const [hasta, setHasta] = useState(hoy);
  const [origen, setOrigen] = useState("");
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  async function ver(e?: React.FormEvent) {
    e?.preventDefault(); setError("");
    try { setData(await api.cobranzasPeriodo(desde, hasta, origen)); }
    catch (err: any) { setError(err.message); setData(null); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Cobranzas en un período</h2>
        <p className="muted">Recibos de créditos/seguros y cobros de quiniela entre dos fechas. Fuente: <code>frminformecobros</code> (menú 23065).</p>
        <form onSubmit={ver} style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap" }}>
          <div><label>Desde</label><input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <div><label>Hasta</label><input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <div><label>Origen</label>
            <select value={origen} onChange={(e) => setOrigen(e.target.value)} style={{ marginBottom: 0 }}>
              <option value="">Todos</option>
              <option value="CR">Créditos/Seguros</option>
              <option value="JUEG">Quiniela</option>
            </select></div>
          <button type="submit">Consultar</button>
          <LimpiarFiltros activo={!!origen} onClear={() => setOrigen("")} />
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {data && (
        <div className="card">
          <div className="grid3">
            <div><div className="kpi">{money(data.total_creditos)}</div><div className="kpi-label">Créditos/Seguros</div></div>
            <div><div className="kpi">{money(data.total_quiniela)}</div><div className="kpi-label">Quiniela</div></div>
            <div><div className="kpi">{money(data.total)}</div><div className="kpi-label">Total ({data.cantidad})</div></div>
          </div>
          <div style={{ marginTop: "1rem" }}>
            <DataTable columns={COLS} rows={data.items} clientSort pageSize={50}
                       defaultSort="fecha_pago" emptyText="Sin cobranzas en el período." />
          </div>
        </div>
      )}
    </>
  );
}
