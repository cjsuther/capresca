import { useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const ORIGEN: Record<string, string> = {
  CRED: "Créditos", SEGU: "Seguros", EXTR: "Extraordinarios", JUEG: "Quiniela",
};
const mny = (k: string) => (i: any) => Number(i[k]);
const COLS: Col[] = [
  { key: "origen", label: "Origen", sortable: true, render: (i) => <b>{ORIGEN[i.origen] || i.origen}</b> },
  { key: "cantidad", label: "Cant.", sortable: true, align: "right" },
  { key: "interes", label: "Interés normal", sortable: true, align: "right", sortValue: mny("interes"), render: (i) => money(i.interes) },
  { key: "iva_interes", label: "IVA normal", sortable: true, align: "right", sortValue: mny("iva_interes"), render: (i) => money(i.iva_interes) },
  { key: "interes_punit", label: "Punitorio", sortable: true, align: "right", sortValue: mny("interes_punit"), render: (i) => money(i.interes_punit) },
  { key: "iva_punit", label: "IVA punit.", sortable: true, align: "right", sortValue: mny("iva_punit"), render: (i) => money(i.iva_punit) },
  { key: "total_interes", label: "Total interés", sortable: true, align: "right", sortValue: mny("total_interes"), render: (i) => <b>{money(i.total_interes)}</b> },
  { key: "total_iva", label: "Total IVA", sortable: true, align: "right", sortValue: mny("total_iva"), render: (i) => <b>{money(i.total_iva)}</b> },
];

// Reporte mensual de intereses e IVA (23015 / frm230150000rptinte): combina el interés
// e IVA cobrado en el mes de créditos/seguros/extra (cajacreseg) y quiniela (cajaliq).
export default function InteresesIva() {
  const now = new Date();
  const [mes, setMes] = useState(now.getMonth() + 1);
  const [anio, setAnio] = useState(now.getFullYear());
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  async function ver(e?: React.FormEvent) {
    e?.preventDefault(); setError("");
    try { setData(await api.interesesIvaMensual(mes, anio)); }
    catch (err: any) { setError(err.message); setData(null); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Reporte mensual de intereses e IVA</h2>
        <p className="muted">Interés e IVA cobrado en el mes por origen (créditos/seguros/extra y quiniela). Fuente: <code>frm230150000rptinte</code> (menú 23015).</p>
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
            <div><div className="kpi">{money(data.total_interes)}</div><div className="kpi-label">Intereses</div></div>
            <div><div className="kpi">{money(data.total_iva)}</div><div className="kpi-label">IVA</div></div>
            <div><div className="kpi">{money(data.total)}</div><div className="kpi-label">Total</div></div>
          </div>
          <div style={{ marginTop: "1rem" }}>
            <DataTable columns={COLS} rows={data.items} rowKey={(i) => i.origen}
                       clientSort defaultSort="total_interes" emptyText="Sin intereses/IVA cobrados en el período." />
          </div>
        </div>
      )}
    </>
  );
}
