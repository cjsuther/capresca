import { useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";
import LimpiarFiltros from "../../components/LimpiarFiltros";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const COLS: Col[] = [
  { key: "origen", label: "Origen", sortable: true },
  { key: "coding", label: "Coding", sortable: true },
  { key: "no_credito", label: "N° Créd.", sortable: true, align: "right", render: (it) => it.no_credito || "-" },
  { key: "apellido_nombre", label: "Nombre", sortable: true },
  { key: "cuota", label: "Cuota", sortable: true, align: "right", render: (it) => it.cuota || "-" },
  { key: "no_recibo", label: "N° Recibo", sortable: true, align: "right", render: (it) => it.no_recibo || "-" },
  { key: "cajero", label: "Cajero", sortable: true },
  { key: "fecha_pago", label: "Fecha", sortable: true },
  { key: "total", label: "Total", sortable: true, align: "right", sortValue: (it) => Number(it.total), render: (it) => <b>{money(it.total)}</b> },
];

// Listado de pagos realizados (23025 / frm230250000lispag): cajacreseg en un rango de
// fechas, filtrable por tipo de ingreso (coding) y por texto (nombre).
export default function PagosRealizados() {
  const hoy = new Date().toISOString().slice(0, 10);
  const [desde, setDesde] = useState(hoy);
  const [hasta, setHasta] = useState(hoy);
  const [coding, setCoding] = useState("");
  const [texto, setTexto] = useState("");
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  async function ver(e?: React.FormEvent) {
    e?.preventDefault(); setError("");
    try { setData(await api.pagosRealizados(desde, hasta, coding, texto)); }
    catch (err: any) { setError(err.message); setData(null); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Listado de pagos realizados</h2>
        <p className="muted">Cobros de créditos/seguros/extra en un rango de fechas. Fuente: <code>frm230250000lispag</code> (menú 23025).</p>
        <form onSubmit={ver} style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap" }}>
          <div><label>Desde</label><input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <div><label>Hasta</label><input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <div><label>Tipo (coding)</label><input value={coding} onChange={(e) => setCoding(e.target.value)} placeholder="todos" style={{ marginBottom: 0, width: 100 }} /></div>
          <div><label>Texto (nombre)</label><input value={texto} onChange={(e) => setTexto(e.target.value)} style={{ marginBottom: 0, width: 180 }} /></div>
          <button type="submit">Consultar</button>
          <LimpiarFiltros activo={!!coding || !!texto} onClear={() => { setCoding(""); setTexto(""); }} />
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {data && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>{data.cantidad} pagos — {money(data.total)}</h3>
          <DataTable columns={COLS} rows={data.items} clientSort pageSize={50}
                     defaultSort="fecha_pago" emptyText="Sin pagos en el rango." />
          {data.truncado && <p className="muted">El backend devolvió los primeros 500 (de {data.cantidad}). Acotá el rango o el filtro.</p>}
        </div>
      )}
    </>
  );
}
