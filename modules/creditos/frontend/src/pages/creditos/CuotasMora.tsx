import { useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const COLS: Col[] = [
  { key: "cliente", label: "Cliente", sortable: true },
  { key: "cred", label: "Cred/Cuota", render: (i) => `#${i.credito_id}-${i.cuota_numero}` },
  { key: "vencimiento", label: "Vto", sortable: true },
  { key: "dias_mora", label: "Días mora", sortable: true, align: "right" },
  { key: "importe", label: "Importe", sortable: true, align: "right",
    sortValue: (i) => Number(i.importe), render: (i) => money(i.importe) },
];

export default function CuotasMora() {
  const [corte, setCorte] = useState(new Date().toISOString().slice(0, 10));
  const [data, setData] = useState<any>(null);

  async function ver() { setData(await api.cuotasMora(corte)); }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Cuotas en mora</h2>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
        <div><label>Fecha de corte</label><input type="date" value={corte} onChange={(e) => setCorte(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <button onClick={ver}>Generar</button>
      </div>
      {data && (
        <div style={{ marginTop: "1rem" }}>
          <p>Cuotas vencidas impagas: <b>{data.cantidad}</b> · Total: <b>{money(data.total)}</b></p>
          <DataTable columns={COLS} rows={data.items} clientSort pageSize={50}
                     defaultSort="dias_mora" emptyText="Sin cuotas en mora" />
        </div>
      )}
    </div>
  );
}
