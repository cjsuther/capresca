import { useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const COLS: Col[] = [
  { key: "credito_id", label: "Crédito", sortable: true, align: "right" },
  { key: "cliente", label: "Cliente", sortable: true },
  { key: "cbu", label: "CBU" },
  { key: "cuota_numero", label: "Cuota", sortable: true, align: "right" },
  { key: "vencimiento", label: "Vto", sortable: true },
  { key: "importe", label: "Importe", sortable: true, align: "right",
    sortValue: (i) => Number(i.importe), render: (i) => money(i.importe) },
];

export default function EnviosPadron() {
  const [desde, setDesde] = useState("2026-01-01");
  const [hasta, setHasta] = useState("2026-12-31");
  const [envios, setEnvios] = useState<any>(null);

  async function ver() { setEnvios(await api.envios(desde, hasta)); }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Envíos — cuotas a debitar por planilla</h2>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
        <div><label>Desde</label><input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <div><label>Hasta</label><input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <button onClick={ver}>Generar</button>
        <button onClick={() => api.descargarEnviosExcel(desde, hasta)} style={{ background: "var(--ok)" }}>Padrón Excel</button>
      </div>
      {envios && (
        <div style={{ marginTop: "1rem" }}>
          <p>Cuotas a debitar: <b>{envios.cantidad}</b> · Total: <b>{money(envios.total)}</b></p>
          <DataTable columns={COLS} rows={envios.items} clientSort pageSize={50}
                     defaultSort="cliente" emptyText="Sin cuotas en el período" />
        </div>
      )}
    </div>
  );
}
