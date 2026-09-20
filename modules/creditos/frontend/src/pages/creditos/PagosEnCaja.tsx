import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const LIMIT = 25;

export default function PagosEnCaja() {
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [credito, setCredito] = useState("");
  const [rows, setRows] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPagado, setTotalPagado] = useState(0);
  const [offset, setOffset] = useState(0);

  async function cargar(off = 0) {
    const d = await api.pagosEnCaja({
      desde: desde || undefined, hasta: hasta || undefined,
      credito_id: credito ? Number(credito) : undefined, limit: LIMIT, offset: off,
    });
    setRows(d.items); setTotal(d.total); setTotalPagado(d.total_pagado); setOffset(off);
  }
  useEffect(() => { cargar(0); }, []);

  const cols: Col[] = [
    { key: "fecha_pago", label: "Fecha pago", render: (r) => r.fecha_pago || "-" },
    { key: "credito_id", label: "Crédito" },
    { key: "cuota", label: "Cuota" },
    { key: "cliente", label: "Cliente" },
    { key: "nro_recibo", label: "Recibo" },
    { key: "via_pago", label: "Vía" },
    { key: "cajero", label: "Cajero" },
    { key: "total_pagado", label: "Pagado", align: "right", render: (r) => money(r.total_pagado) },
  ];

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Pagos de créditos en caja</h2>
      <p className="muted">Cuotas efectivamente pagadas, con recibo, vía de pago y cajero. Fuente: maecuotas (datos de pago reales).</p>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap", marginBottom: "0.8rem" }}>
        <div><label>Desde</label><input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <div><label>Hasta</label><input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <div><label>N° crédito</label><input value={credito} onChange={(e) => setCredito(e.target.value)} style={{ marginBottom: 0, width: 120 }} /></div>
        <button onClick={() => cargar(0)}>Filtrar</button>
        <button onClick={() => api.descargarPagosEnCajaExcel({
          desde: desde || undefined, hasta: hasta || undefined,
          credito_id: credito ? Number(credito) : undefined,
        })} style={{ background: "var(--ok)" }}>Descargar Excel</button>
      </div>
      <p className="muted">
        <b>{Number(total).toLocaleString("es-AR")}</b> pagos · total cobrado {money(totalPagado || 0)}
      </p>
      <DataTable columns={cols} rows={rows} total={total} limit={LIMIT} offset={offset}
                 onPage={(off) => cargar(off)} rowKey={(r, i) => `${r.credito_id}-${r.cuota}-${i}`}
                 emptyText="Sin pagos en el período" />
    </div>
  );
}
