import { useState } from "react";
import { api } from "../../api";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

export default function ControlCaja() {
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [cajero, setCajero] = useState("");
  const [control, setControl] = useState<any>(null);

  async function ver() { setControl(await api.controlCaja(fecha, cajero)); }

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.5rem" }}>
        <h2 style={{ margin: 0 }}>Control de caja</h2>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
          <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} style={{ marginBottom: 0 }} />
          <input value={cajero} onChange={(e) => setCajero(e.target.value)} placeholder="Cajero (opcional)" style={{ marginBottom: 0, width: 150 }} />
          <button onClick={ver}>Ver</button>
          <button onClick={() => api.verControlPdf(fecha, cajero)} style={{ background: "var(--ink-soft)" }}>PDF (reimpresión)</button>
        </div>
      </div>
      {control && (
        <div style={{ marginTop: "1rem" }}>
          <p>Recibos: <b>{control.cantidad_total}</b> · Total general: <b>{money(control.total_general)}</b></p>
          {control.cajeros.map((c: any) => (
            <div key={c.cajero} style={{ marginBottom: "0.8rem" }}>
              <b>{c.cajero}</b> — {c.cantidad} recibos · subtotal {money(c.subtotal)}
              <table>
                <thead><tr><th>Recibo</th><th>Cliente</th><th>Vía</th><th>Total</th></tr></thead>
                <tbody>
                  {c.recibos.map((r: any) => (
                    <tr key={r.numero}><td>{r.numero}</td><td>{r.cliente}</td><td>{r.via_pago}</td><td>{money(r.total)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
          {!control.cajeros.length && <p className="muted">Sin movimientos en la fecha.</p>}
        </div>
      )}
    </div>
  );
}
