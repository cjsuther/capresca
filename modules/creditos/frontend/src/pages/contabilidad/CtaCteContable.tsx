import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../../api";
import VolverFicha from "../../components/VolverFicha";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: any) =>
  v == null ? "—" : Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

// Ledger con saldo corrido: importes NO ordenables; orden por Cta/Cuota/Vto/Pago.
const COLS: Col[] = [
  { key: "cuenta", label: "Cta.", sortable: true },
  { key: "no_cuota", label: "Cuota", sortable: true, align: "right" },
  { key: "fecha_vto", label: "Vto.", sortable: true, render: (c) => c.fecha_vto || "—" },
  { key: "fecha_pago", label: "Pago", sortable: true, render: (c) => c.fecha_pago || "—" },
  { key: "capital", label: "Capital", align: "right", render: (c) => money(c.capital) },
  { key: "int_normal", label: "Int.nor.", align: "right", render: (c) => money(c.int_normal) },
  { key: "int_punit", label: "Int.pun.", align: "right", render: (c) => money(c.int_punit) },
  { key: "gastos", label: "Gastos", align: "right", render: (c) => money(c.gastos) },
  { key: "debitos", label: "Débito", align: "right", render: (c) => money(c.debitos) },
  { key: "creditos", label: "Crédito", align: "right", render: (c) => money(c.creditos) },
  { key: "saldo", label: "Saldo", align: "right", render: (c) => money(c.saldo) },
  { key: "estado", label: "", render: (c) => (c.anulada ? "anulada" : "") },
];
const tachado = (c: any) => (c.anulada ? { opacity: 0.5, textDecoration: "line-through" as const } : undefined);

// Cta. cte. contable de un crédito (VFP: Contabilidad/crctacte.dbf).
export default function CtaCteContable() {
  const [params] = useSearchParams();
  const [nc, setNc] = useState(params.get("no_credito") || "");
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  async function ver(e?: React.FormEvent, valor?: string) {
    e?.preventDefault(); setError("");
    const v = valor ?? nc;
    try { setData(await api.ctacteContableCredito(Number(v))); }
    catch (err: any) { setError(err.message); setData(null); }
  }
  useEffect(() => {
    const p = params.get("no_credito");
    if (p) ver(undefined, p);
  }, []); // eslint-disable-line

  return (
    <>
      <VolverFicha />
      <div className="card">
        <h1 style={{ marginTop: 0 }}>Cuenta corriente contable por crédito</h1>
        <p className="muted">Desglose contable (capital, interés normal/punitorio/resarcitorio, IVA, gastos, sellado) por crédito. Fuente real: <code>crctacte.dbf</code> (1M).</p>
        <form onSubmit={ver} style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
          <div><label>N° de crédito</label><input value={nc} onChange={(e) => setNc(e.target.value)} placeholder="Ej.: 8933" style={{ marginBottom: 0, width: 140 }} /></div>
          <button type="submit">Ver</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {data && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>
            Crédito {data.no_credito} · {data.cantidad} movimientos · saldo {money(data.saldo)}
          </h3>
          <div style={{ display: "flex", gap: "1.4rem", flexWrap: "wrap", marginBottom: "0.8rem" }}>
            <div><div className="kpi-label">Débitos</div><div className="kpi">{money(data.total_debitos)}</div></div>
            <div><div className="kpi-label">Créditos</div><div className="kpi">{money(data.total_creditos)}</div></div>
            <div><div className="kpi-label">Capital</div><div className="kpi">{money(data.total_capital)}</div></div>
            <div><div className="kpi-label">Int. normal</div><div className="kpi">{money(data.total_int_normal)}</div></div>
            <div><div className="kpi-label">Int. punit.</div><div className="kpi">{money(data.total_int_punit)}</div></div>
          </div>
          <DataTable columns={COLS} rows={data.items} rowStyle={tachado} pageSize={50}
                     clientSort defaultSort="no_cuota" emptyText="Sin movimientos para ese crédito." />
        </div>
      )}
    </>
  );
}
