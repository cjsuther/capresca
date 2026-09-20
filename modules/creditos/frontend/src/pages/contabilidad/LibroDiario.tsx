import { useEffect, useState } from "react";
import { api } from "../../api";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

export default function LibroDiario() {
  const [asientos, setAsientos] = useState<any[]>([]);
  useEffect(() => { api.libroDiario().then(setAsientos); }, []);

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>Libro diario</h2>
        <button onClick={() => api.verLibroDiarioPdf()}>Descargar PDF</button>
      </div>
      <p className="muted">Asientos generados automáticamente por otorgamientos y cobranzas.</p>
      {asientos.map((a) => {
        const debe = a.lineas.reduce((s: number, l: any) => s + Number(l.debe), 0);
        return (
          <div key={a.id} style={{ borderTop: "1px solid var(--borde)", padding: "0.7rem 0" }}>
            <b>#{a.id} · {a.fecha}</b> — {a.concepto} <span className="muted">({a.origen})</span>
            <table style={{ marginTop: "0.3rem" }}>
              <thead><tr><th>Cuenta</th><th>Debe</th><th>Haber</th></tr></thead>
              <tbody>
                {a.lineas.map((l: any, i: number) => (
                  <tr key={i}>
                    <td>{l.cuenta_codigo} {l.cuenta_nombre}</td>
                    <td>{Number(l.debe) ? money(l.debe) : ""}</td>
                    <td>{Number(l.haber) ? money(l.haber) : ""}</td>
                  </tr>
                ))}
                <tr><td style={{ textAlign: "right" }}><b>Total</b></td><td><b>{money(debe)}</b></td><td><b>{money(debe)}</b></td></tr>
              </tbody>
            </table>
          </div>
        );
      })}
      {!asientos.length && <p className="muted">Sin asientos todavía.</p>}
    </div>
  );
}
