import { useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const COLS_MON: Col[] = [
  { key: "concepto", label: "Moneda", sortable: true },
  { key: "importe", label: "Ingresos", sortable: true, align: "right", sortValue: (c) => Number(c.importe), render: (c) => money(c.importe) },
];
const COLS_CON: Col[] = [
  { key: "concepto", label: "Concepto (créditos)", sortable: true },
  { key: "importe", label: "Importe", sortable: true, align: "right", sortValue: (c) => Number(c.importe), render: (c) => money(c.importe) },
];

export default function Cierre() {
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [cierre, setCierre] = useState<any>(null);

  async function ver() { setCierre(await api.cierre(fecha)); }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Cierre de caja</h2>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
        <div><label>Fecha</label><input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <button onClick={ver}>Generar cierre</button>
        <button onClick={() => api.verCierrePdf(fecha)} style={{ background: "var(--ink-soft)" }}>PDF</button>
      </div>
      {cierre && (
        <div style={{ marginTop: "1rem" }}>
          <div className="grid3">
            <div><div className="kpi">{cierre.cantidad_recibos}</div><div className="kpi-label">Recibos créditos/seguros</div></div>
            <div><div className="kpi">{cierre.quiniela_cantidad ?? 0}</div><div className="kpi-label">Cobros quiniela</div></div>
            <div><div className="kpi">{money(cierre.total_cobrado)}</div><div className="kpi-label">Total cobrado</div></div>
          </div>
          <div style={{ display: "flex", gap: "2rem", flexWrap: "wrap", marginTop: "1rem" }}>
            {cierre.por_moneda?.length > 0 && (
              <div style={{ maxWidth: 340 }}>
                <DataTable columns={COLS_MON} rows={cierre.por_moneda} rowKey={(c) => c.concepto}
                           clientSort defaultSort="importe" />
              </div>
            )}
            {cierre.por_concepto?.length > 0 && (
              <div style={{ maxWidth: 440 }}>
                <DataTable columns={COLS_CON} rows={cierre.por_concepto} rowKey={(c) => c.concepto}
                           clientSort defaultSort="importe" />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
