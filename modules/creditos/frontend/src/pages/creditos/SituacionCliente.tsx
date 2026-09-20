import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const estadoTxt = (e: string) => (e === "A" ? "Activo" : e === "C" ? "Cancelado" : e);
const COLS: Col[] = [
  { key: "id", label: "Crédito", sortable: true },
  { key: "linea", label: "Línea", sortable: true },
  { key: "capital", label: "Capital", sortable: true, align: "right",
    sortValue: (c) => Number(c.capital), render: (c) => money(c.capital) },
  { key: "saldo_capital", label: "Saldo", sortable: true, align: "right",
    sortValue: (c) => Number(c.saldo_capital), render: (c) => money(c.saldo_capital) },
  { key: "cuotas_pendientes", label: "Cuotas pend.", sortable: true, align: "right" },
  { key: "proxima_cuota_vto", label: "Próx. vto", sortable: true, render: (c) => c.proxima_cuota_vto || "-" },
  { key: "estado", label: "Estado", sortable: true, render: (c) => estadoTxt(c.estado) },
];

export default function SituacionCliente() {
  const [clientes, setClientes] = useState<any[]>([]);
  const [clienteId, setClienteId] = useState(0);
  const [sit, setSit] = useState<any>(null);

  useEffect(() => {
    api.clientes({ limit: 100 }).then((d) => {
      setClientes(d.items);
      if (d.items.length) setClienteId(d.items[0].id);
    });
  }, []);

  async function ver() { setSit(await api.situacionCliente(clienteId)); }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Situación del cliente</h2>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
        <div style={{ flex: 1 }}>
          <label>Cliente</label>
          <select value={clienteId} onChange={(e) => setClienteId(Number(e.target.value))} style={{ marginBottom: 0 }}>
            {clientes.map((c) => <option key={c.id} value={c.id}>{c.apellido_nombre}</option>)}
          </select>
        </div>
        <button onClick={ver}>Ver situación</button>
      </div>
      {sit && (
        <div style={{ marginTop: "1rem" }}>
          <p>
            <b>{sit.apellido_nombre}</b> · CUIL {sit.cuil} · Sueldo {money(sit.sueldo)}<br />
            Créditos activos: <b>{sit.creditos_activos}</b> · Saldo total: <b>{money(sit.saldo_total)}</b>
            {sit.margen_disponible != null && <> · Margen disponible: <b>{money(sit.margen_disponible)}</b></>}
          </p>
          <DataTable columns={COLS} rows={sit.creditos} rowKey={(c) => c.id}
                     clientSort defaultSort="id" emptyText="Sin créditos" />
        </div>
      )}
    </div>
  );
}
