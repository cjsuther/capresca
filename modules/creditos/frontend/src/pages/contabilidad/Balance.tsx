import { useEffect, useState } from "react";
import { api } from "../../api";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

export default function Balance() {
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [data, setData] = useState<any>(null);

  async function cargar() { setData(await api.balance(desde, hasta)); }
  useEffect(() => { cargar(); }, []);

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>Balance de sumas y saldos</h2>
        <button onClick={() => api.verBalancePdf(desde, hasta)} style={{ background: "var(--ink-soft)" }}>Descargar PDF</button>
      </div>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap", margin: "0.8rem 0" }}>
        <div><label>Desde</label><input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <div><label>Hasta</label><input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <button onClick={cargar}>Filtrar</button>
        {data && (data.cuadra
          ? <span className="badge-ok">Cuadra ✓</span>
          : <span className="error" style={{ margin: 0 }}>No cuadra ⚠</span>)}
      </div>
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr><th>Cuenta</th><th style={{ textAlign: "right" }}>Debe</th>
              <th style={{ textAlign: "right" }}>Haber</th>
              <th style={{ textAlign: "right" }}>Saldo deudor</th>
              <th style={{ textAlign: "right" }}>Saldo acreedor</th></tr>
          </thead>
          <tbody>
            {data?.cuentas.map((c: any) => (
              <tr key={c.cuenta_codigo}>
                <td>{c.cuenta_codigo} {c.cuenta_nombre}</td>
                <td style={{ textAlign: "right" }}>{money(c.debe)}</td>
                <td style={{ textAlign: "right" }}>{money(c.haber)}</td>
                <td style={{ textAlign: "right" }}>{money(c.saldo_deudor)}</td>
                <td style={{ textAlign: "right" }}>{money(c.saldo_acreedor)}</td>
              </tr>
            ))}
            {data && !data.cuentas.length && <tr><td colSpan={5} className="muted">Sin movimientos contables en el período</td></tr>}
          </tbody>
          {data?.cuentas.length > 0 && (
            <tfoot>
              <tr style={{ borderTop: "2px solid var(--borde)" }}>
                <td><b>TOTALES</b></td>
                <td style={{ textAlign: "right" }}><b>{money(data.total.debe)}</b></td>
                <td style={{ textAlign: "right" }}><b>{money(data.total.haber)}</b></td>
                <td style={{ textAlign: "right" }}><b>{money(data.total.deudor)}</b></td>
                <td style={{ textAlign: "right" }}><b>{money(data.total.acreedor)}</b></td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}
