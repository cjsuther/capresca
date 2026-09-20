import { useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const COLS_RES: Col[] = [
  { key: "cajero", label: "Cajero", sortable: true, render: (r) => r.cajero || "-" },
  { key: "cantidad", label: "Cantidad", sortable: true, align: "right" },
  { key: "total", label: "Total premios", sortable: true, align: "right", sortValue: (r) => Number(r.total), render: (r) => money(r.total) },
];
const COLS_DET: Col[] = [
  { key: "cajero", label: "Cajero", sortable: true },
  { key: "no_recibo", label: "N° Recibo", sortable: true, align: "right" },
  { key: "cod_agencia", label: "Agencia", sortable: true },
  { key: "juego", label: "Juego", sortable: true },
  { key: "no_sorteo", label: "N° Sorteo", sortable: true, align: "right" },
  { key: "moneda", label: "Moneda" },
  { key: "premio", label: "Premio", sortable: true, align: "right", sortValue: (it) => Number(it.premio), render: (it) => <b>{money(it.premio)}</b> },
];

// Control de premios de quiniela (egresos) de un día (23020 / frm230200000prequi).
export default function PremiosQuiniela() {
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [modo, setModo] = useState("cobradas");
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  async function ver(e?: React.FormEvent) {
    e?.preventDefault(); setError("");
    try { setData(await api.premiosQuiniela(fecha, modo)); }
    catch (err: any) { setError(err.message); setData(null); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Control de premios de quiniela</h2>
        <p className="muted">Premios pagados por las agencias (egresos) en un día. Fuente: <code>frm230200000prequi</code> (menú 23020).</p>
        <form onSubmit={ver} style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap" }}>
          <div><label>Día</label><input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <div><label>Modo</label>
            <select value={modo} onChange={(e) => setModo(e.target.value)} style={{ marginBottom: 0 }}>
              <option value="cobradas">Cobradas (fecha de pago)</option>
              <option value="pendientes">Pendientes (fecha de vto.)</option>
              <option value="ambas">Ambas</option>
            </select></div>
          <button type="submit">Consultar</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {data && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>{data.cantidad} premios — {money(data.total)}</h3>
          <div style={{ maxWidth: 520 }}>
            <DataTable columns={COLS_RES} rows={data.resumen} rowKey={(r) => r.cajero}
                       clientSort defaultSort="total" emptyText="Sin premios ese día." />
          </div>

          {data.items.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <DataTable columns={COLS_DET} rows={data.items} clientSort pageSize={50} defaultSort="cajero" />
            </div>
          )}
        </div>
      )}
    </>
  );
}
