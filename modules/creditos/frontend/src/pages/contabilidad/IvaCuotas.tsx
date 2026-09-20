import { useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const mny = (k: string) => (p: any) => Number(p[k]);
const COLS: Col[] = [
  { key: "periodo", label: "Período", sortable: true },
  { key: "cantidad", label: "Cuotas", sortable: true, align: "right" },
  { key: "iva_interes", label: "IVA interés", sortable: true, align: "right", sortValue: mny("iva_interes"), render: (p) => money(p.iva_interes) },
  { key: "iva_seguro", label: "IVA seguro", sortable: true, align: "right", sortValue: mny("iva_seguro"), render: (p) => money(p.iva_seguro) },
  { key: "iva_gastos", label: "IVA gastos", sortable: true, align: "right", sortValue: mny("iva_gastos"), render: (p) => money(p.iva_gastos) },
  { key: "iva_total", label: "IVA total", sortable: true, align: "right", sortValue: mny("iva_total"), render: (p) => <b>{money(p.iva_total)}</b> },
];

// IVA débito de cuotas de crédito cobradas por período, sobre dato real (maecuotas).
// VFP: cb-cjcreditoscobrados / cb-iva-a-pagar-periodo (menú 61005 / 60505).
export default function IvaCuotas() {
  const [desde, setDesde] = useState("2025-01-01");
  const [hasta, setHasta] = useState("2025-12-31");
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  async function ver(e?: React.FormEvent) {
    e?.preventDefault(); setError("");
    try { setData(await api.ivaCuotas(desde, hasta)); }
    catch (err: any) { setError(err.message); setData(null); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>IVA de cuotas cobradas (dato real)</h2>
        <p className="muted">IVA débito fiscal de las cuotas de crédito cobradas, por período. Fuente real: <code>maecuotas</code> (menú 61005 / 60505).</p>
        <form onSubmit={ver} style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
          <div><label>Desde</label><input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <div><label>Hasta</label><input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <button type="submit">Calcular</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {data && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>IVA total del rango: {money(data.total_iva)} · {data.cantidad_periodos} períodos</h3>
          <DataTable columns={COLS} rows={data.periodos} rowKey={(p) => p.periodo}
                     clientSort defaultSort="periodo" emptyText="Sin cuotas cobradas en el rango." />
        </div>
      )}
    </>
  );
}
