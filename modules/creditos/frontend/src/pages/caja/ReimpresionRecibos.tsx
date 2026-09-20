import { useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const ORIGEN: Record<string, string> = {
  JUEG: "Quiniela", CRED: "Crédito", SEGU: "Seguro", EXTR: "Extraordinario",
};
const COLS: Col[] = [
  { key: "no_recibo", label: "N° Recibo", sortable: true, align: "right" },
  { key: "origen", label: "Origen", sortable: true, render: (it) => ORIGEN[it.origen] || it.origen },
  { key: "titular", label: "Cod. Ag. / Titular", sortable: true, render: (it) => (it.origen === "JUEG" ? `Agencia ${it.cod_agencia}` : it.titular) },
  { key: "fecha_pago", label: "Fecha de pago", sortable: true },
  { key: "cajero", label: "Cajero", sortable: true },
  { key: "importe", label: "Importe", sortable: true, align: "right", sortValue: (it) => Number(it.importe), render: (it) => <b>{money(it.importe)}</b> },
];

// Reimpresión de recibos (23010/23012 / frm230100000rptreci): recibos emitidos en un
// día, unificando quiniela (cajapagos) y créditos/seguros (cajacreseg).
export default function ReimpresionRecibos() {
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  async function ver(e?: React.FormEvent) {
    e?.preventDefault(); setError("");
    try { setData(await api.recibosDelDia(fecha)); }
    catch (err: any) { setError(err.message); setData(null); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Reimpresión de recibos</h2>
        <p className="muted">Recibos emitidos en un día (quiniela y créditos/seguros), para reimpresión. Fuente: <code>frm230100000rptreci</code> (menú 23010/23012).</p>
        <form onSubmit={ver} style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
          <div><label>Fecha del recibo</label><input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <button type="submit">Buscar recibos</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {data && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>{data.cantidad} recibos — total {money(data.total)}</h3>
          <DataTable columns={COLS} rows={data.items} clientSort pageSize={50} defaultSort="no_recibo"
                     actions={(it) => [{ label: "Reimprimir", icon: "edit", onClick: () => api.reimprimirRecibo(it.no_recibo, it.origen, it.fecha_pago) }]}
                     emptyText="Sin recibos emitidos ese día." />
        </div>
      )}
    </>
  );
}
