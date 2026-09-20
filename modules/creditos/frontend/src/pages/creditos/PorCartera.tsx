import { useEffect, useState } from "react";
import { api } from "../../api";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

export default function PorCartera() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { api.situacionPorCartera().then(setData); }, []);

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>Créditos por cartera</h2>
        <button onClick={() => api.verPorCarteraPdf()} style={{ background: "var(--ink-soft)" }}>Descargar PDF</button>
      </div>
      <p className="muted">Cantidades y situación de créditos agrupados por cartera. El saldo corresponde a los créditos activos.</p>
      {data?.anomalias_saldo_negativo > 0 && (
        <div className="aviso" style={{ marginBottom: "0.8rem" }}>
          ⚠ {data.anomalias_saldo_negativo} crédito(s) con saldo negativo (dato corrupto del backup) se excluyen del saldo. Ver hallazgo H-023.
        </div>
      )}
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr><th>Cartera</th><th style={{ textAlign: "right" }}>Activos</th>
              <th style={{ textAlign: "right" }}>Cancelados</th>
              <th style={{ textAlign: "right" }}>Capital otorgado</th>
              <th style={{ textAlign: "right" }}>Saldo (activos)</th></tr>
          </thead>
          <tbody>
            {data?.por_cartera.map((c: any) => (
              <tr key={c.cartera}>
                <td>{c.nombre} <span className="muted">({c.cartera})</span></td>
                <td style={{ textAlign: "right" }}>{c.activos.toLocaleString("es-AR")}</td>
                <td style={{ textAlign: "right" }}>{c.cancelados.toLocaleString("es-AR")}</td>
                <td style={{ textAlign: "right" }}>{money(c.capital)}</td>
                <td style={{ textAlign: "right" }}><b>{money(c.saldo)}</b></td>
              </tr>
            ))}
            {data && !data.por_cartera.length && <tr><td colSpan={5} className="muted">Sin créditos</td></tr>}
          </tbody>
          {data?.por_cartera.length > 0 && (
            <tfoot>
              <tr style={{ borderTop: "2px solid var(--borde)" }}>
                <td><b>Total</b></td>
                <td style={{ textAlign: "right" }}><b>{data.total.activos.toLocaleString("es-AR")}</b></td>
                <td style={{ textAlign: "right" }}><b>{data.total.cancelados.toLocaleString("es-AR")}</b></td>
                <td style={{ textAlign: "right" }}><b>{money(data.total.capital)}</b></td>
                <td style={{ textAlign: "right" }}><b>{money(data.total.saldo)}</b></td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}
