import { useState } from "react";
import { api } from "../../api";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

// Planilla para contabilidad: créditos cobrados en un día (23045 / frm230450000rciecre),
// descompuestos por concepto contable (capital, interés, IVA, seguro, gastos, punitorio).
export default function PlanillaContable() {
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  async function ver(e?: React.FormEvent) {
    e?.preventDefault(); setError("");
    try { setData(await api.planillaContableCreditos(fecha)); }
    catch (err: any) { setError(err.message); setData(null); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Planilla contable — créditos cobrados por día</h2>
        <p className="muted">Créditos cobrados en un día, descompuestos por concepto para el asiento contable. Fuente: <code>frm230450000rciecre</code> (menú 23045).</p>
        <form onSubmit={ver} style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
          <div><label>Día</label><input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <button type="submit">Generar planilla</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {data && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>{data.cantidad} créditos cobrados — total {money(data.total)}</h3>
          <table style={{ maxWidth: 420 }}>
            <thead><tr><th>Concepto</th><th style={{ textAlign: "right" }}>Importe</th></tr></thead>
            <tbody>
              {data.conceptos.map((c: any) => (
                <tr key={c.concepto}><td>{c.concepto}</td><td style={{ textAlign: "right" }}>{money(c.importe)}</td></tr>
              ))}
              {!data.conceptos.length && <tr><td colSpan={2} className="muted">Sin créditos cobrados ese día.</td></tr>}
              {data.conceptos.length > 0 && (
                <tr><td><b>Total</b></td><td style={{ textAlign: "right" }}><b>{money(data.total)}</b></td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
