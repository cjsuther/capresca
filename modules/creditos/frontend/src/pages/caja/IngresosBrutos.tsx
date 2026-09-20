import { useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const COLS: Col[] = [
  { key: "cod_agencia", label: "Cód. Agencia", sortable: true },
  { key: "no_agencia", label: "N° Ag.", sortable: true },
  { key: "subagencia", label: "Sub", sortable: true },
  { key: "cantidad", label: "Liq.", sortable: true, align: "right" },
  { key: "recaudacion", label: "Recaudación", sortable: true, align: "right", sortValue: (a) => Number(a.recaudacion), render: (a) => money(a.recaudacion) },
  { key: "comisiones", label: "Comisiones", sortable: true, align: "right", sortValue: (a) => Number(a.comisiones), render: (a) => money(a.comisiones) },
  { key: "ing_brutos", label: "Ing. Brutos", sortable: true, align: "right", sortValue: (a) => Number(a.ing_brutos), render: (a) => <b>{money(a.ing_brutos)}</b> },
];

// Informe de Ingresos Brutos (23035 / frm230350000infingbru): retención de IIBB por
// agencia sobre las liquidaciones cobradas en un mes/año.
export default function IngresosBrutos() {
  const now = new Date();
  const [mes, setMes] = useState(now.getMonth() + 1);
  const [anio, setAnio] = useState(now.getFullYear());
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  async function ver(e?: React.FormEvent) {
    e?.preventDefault(); setError("");
    try { setData(await api.ingresosBrutos(mes, anio)); }
    catch (err: any) { setError(err.message); setData(null); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Informe de Ingresos Brutos</h2>
        <p className="muted">Retención de IIBB por agencia sobre liquidaciones cobradas en el período. Fuente: <code>frm230350000infingbru</code> (menú 23035).</p>
        <form onSubmit={ver} style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
          <div><label>Mes</label><input type="number" min={1} max={12} value={mes} onChange={(e) => setMes(Number(e.target.value))} style={{ marginBottom: 0, width: 80 }} /></div>
          <div><label>Año</label><input type="number" value={anio} onChange={(e) => setAnio(Number(e.target.value))} style={{ marginBottom: 0, width: 100 }} /></div>
          <button type="submit">Procesar</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {data && (
        <div className="card">
          <div className="grid3">
            <div><div className="kpi">{money(data.total_recaudacion)}</div><div className="kpi-label">Recaudación</div></div>
            <div><div className="kpi">{money(data.total_comisiones)}</div><div className="kpi-label">Comisiones</div></div>
            <div><div className="kpi">{money(data.total_ing_brutos)}</div><div className="kpi-label">Ingresos Brutos ({data.cantidad_agencias} ag.)</div></div>
          </div>
          <div style={{ marginTop: "1rem" }}>
            <DataTable columns={COLS} rows={data.items} clientSort pageSize={50}
                       defaultSort="ing_brutos" emptyText="Sin liquidaciones cobradas en el período." />
          </div>
        </div>
      )}
    </>
  );
}
