import { useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const COLS: Col[] = [
  { key: "cliente", label: "Cliente", sortable: true },
  { key: "cred", label: "Cred/Cuota", render: (i) => `#${i.credito_id}-${i.cuota_numero}` },
  { key: "vencimiento", label: "Vto", sortable: true },
  { key: "dias_mora", label: "Días", sortable: true, align: "right" },
  { key: "importe_cuota", label: "Cuota", sortable: true, align: "right",
    sortValue: (i) => Number(i.importe_cuota), render: (i) => money(i.importe_cuota) },
  { key: "mora", label: "Mora", sortable: true, align: "right",
    sortValue: (i) => Number(i.mora), render: (i) => money(i.mora) },
  { key: "total", label: "Total", sortable: true, align: "right",
    sortValue: (i) => Number(i.total), render: (i) => <b>{money(i.total)}</b> },
];

export default function PendientesCobro() {
  const [corte, setCorte] = useState(new Date().toISOString().slice(0, 10));
  const [pend, setPend] = useState<any>(null);

  async function ver() { setPend(await api.pendientesCobro(corte)); }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Pendientes de cobro (con mora)</h2>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
        <div><label>Fecha de corte</label><input type="date" value={corte} onChange={(e) => setCorte(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <button onClick={ver}>Generar</button>
        <button onClick={() => api.verPendientesPdf(corte)} style={{ background: "var(--ink-soft)" }}>PDF</button>
      </div>
      {pend && (
        <div style={{ marginTop: "1rem" }}>
          <p>Cuotas: <b>{pend.cantidad}</b> · Cuota: <b>{money(pend.total_cuota)}</b> · Mora: <b>{money(pend.total_mora)}</b> · Total: <b>{money(pend.total)}</b></p>
          <DataTable columns={COLS} rows={pend.items} clientSort pageSize={50}
                     defaultSort="dias_mora" emptyText="Sin pendientes a la fecha" />
        </div>
      )}
    </div>
  );
}
