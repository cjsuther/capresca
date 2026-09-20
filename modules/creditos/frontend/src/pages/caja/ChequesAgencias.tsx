import { useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const mny = (k: string) => (it: any) => Number(it[k]);
const COLS: Col[] = [
  { key: "cod_agencia", label: "Cód. Agencia", sortable: true },
  { key: "premios", label: "Premios", sortable: true, align: "right", sortValue: mny("premios"), render: (it) => money(it.premios) },
  { key: "total", label: "Total liq.", sortable: true, align: "right", sortValue: mny("total"), render: (it) => money(it.total) },
  { key: "intereses", label: "Intereses", sortable: true, align: "right", sortValue: mny("intereses"), render: (it) => money(it.intereses) },
  { key: "iva", label: "IVA", sortable: true, align: "right", sortValue: mny("iva"), render: (it) => money(it.iva) },
  { key: "neto", label: "Neto", sortable: true, align: "right", sortValue: mny("neto"), render: (it) => <span style={{ color: "var(--crit)" }}>{money(it.neto)}</span> },
  { key: "cheque", label: "Cheque", sortable: true, align: "right", sortValue: mny("cheque"), render: (it) => <b>{money(it.cheque)}</b> },
];

// Listado de cheques para agencias (23057 / frm230570000listado_cheques): agencias con
// neto a favor (sum(total_gral) <= -10000) en una fecha de vencimiento reciben cheque.
export default function ChequesAgencias() {
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  async function ver(e?: React.FormEvent) {
    e?.preventDefault(); setError("");
    try { setData(await api.chequesAgencias(fecha)); }
    catch (err: any) { setError(err.message); setData(null); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Listado de cheques para agencias</h2>
        <p className="muted">Agencias con neto a favor (premios &gt; deuda) que reciben cheque, por fecha de vencimiento. Fuente: <code>frm230570000listado_cheques</code> (menú 23057).</p>
        <form onSubmit={ver} style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
          <div><label>Fecha de vencimiento</label><input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <button type="submit">Consultar</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {data && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>{data.cantidad} cheques — total {money(data.total_cheques)}</h3>
          <DataTable columns={COLS} rows={data.items} rowKey={(it) => it.cod_agencia}
                     clientSort pageSize={50} defaultSort="cheque"
                     emptyText="Ninguna agencia con cheque a favor en esa fecha." />
        </div>
      )}
    </>
  );
}
