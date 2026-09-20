import { useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const COLS_RES: Col[] = [
  { key: "cajero", label: "Cajero", sortable: true, render: (r) => r.cajero || "-" },
  { key: "cantidad", label: "Cantidad", sortable: true, align: "right" },
  { key: "total", label: "Total", sortable: true, align: "right", sortValue: (r) => Number(r.total), render: (r) => money(r.total) },
];
const COLS_DET: Col[] = [
  { key: "cajero", label: "Cajero", sortable: true },
  { key: "no_recibo", label: "N° Recibo", sortable: true, align: "right" },
  { key: "cod_agencia", label: "Agencia", sortable: true },
  { key: "juego", label: "Juego", sortable: true },
  { key: "no_sorteo", label: "N° Sorteo", sortable: true, align: "right" },
  { key: "moneda", label: "Moneda" },
  { key: "total_gral", label: "Total", sortable: true, align: "right", sortValue: (it) => Number(it.total_gral), render: (it) => money(it.total_gral) },
];

// Liquidaciones cobradas/pagadas en un día (23050 / frm230500000liqcob), con resumen
// por cajero y detalle. Casilla "Resumido" muestra sólo el resumen.
export default function LiquidacionesCobradas() {
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [resumido, setResumido] = useState(false);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  async function ver(e?: React.FormEvent) {
    e?.preventDefault(); setError("");
    try { setData(await api.liquidacionesCobradas(fecha)); }
    catch (err: any) { setError(err.message); setData(null); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Liquidaciones cobradas en una fecha</h2>
        <p className="muted">Liquidaciones de quiniela pagadas en un día, por cajero. Fuente: <code>frm230500000liqcob</code> (menú 23050).</p>
        <form onSubmit={ver} style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
          <div><label>Día</label><input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <label style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
            <input type="checkbox" checked={resumido} onChange={(e) => setResumido(e.target.checked)} style={{ width: "auto", margin: 0 }} /> Resumido
          </label>
          <button type="submit">Consultar</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {data && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>{data.cantidad} liquidaciones — {money(data.total)}</h3>
          <div style={{ maxWidth: 520 }}>
            <DataTable columns={COLS_RES} rows={data.resumen} rowKey={(r) => r.cajero}
                       clientSort defaultSort="total" emptyText="Sin liquidaciones cobradas ese día." />
          </div>

          {!resumido && data.items.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <DataTable columns={COLS_DET} rows={data.items} clientSort pageSize={50} defaultSort="cajero" />
            </div>
          )}
        </div>
      )}
    </>
  );
}
