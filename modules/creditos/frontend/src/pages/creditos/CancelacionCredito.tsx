import { useState } from "react";
import { api } from "../../api";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

// Cancelación anticipada de crédito (32045 / frm320450000cancre): calcula el total a
// cancelar (cuotas vencidas completas + mora; cuotas futuras sólo capital, condonando
// el interés no devengado) y salda el crédito.
export default function CancelacionCredito() {
  const [creditoId, setCreditoId] = useState("");
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [det, setDet] = useState<any>(null);
  const [recibo, setRecibo] = useState<any>(null);
  const [error, setError] = useState("");

  async function simular(e?: React.FormEvent) {
    e?.preventDefault(); setError(""); setRecibo(null); setDet(null);
    const id = Number(creditoId);
    if (!id) { setError("Ingresá un número de crédito."); return; }
    try { setDet(await api.simularCancelacion(id, fecha)); }
    catch (err: any) { setError(err.message); }
  }

  async function cancelar() {
    setError("");
    try {
      const r = await api.cancelarCredito(Number(creditoId), { fecha_pago: fecha, via_pago: "EFECTIVO" });
      setRecibo(r); setDet(null);
    } catch (err: any) { setError(err.message); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Cancelación anticipada de crédito</h2>
        <p className="muted">Salda todas las cuotas: las vencidas con su mora, las futuras sólo capital (se condona el interés no devengado). Fuente: <code>frm320450000cancre</code> (menú 32045).</p>
        <form onSubmit={simular} style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
          <div><label>N° de crédito</label><input value={creditoId} onChange={(e) => setCreditoId(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <div><label>Fecha</label><input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <button type="submit">Calcular cancelación</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {det && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Total a cancelar: {money(det.total)}</h3>
          <p className="muted">Capital {money(det.capital)} · Interés {money(det.interes)} · IVA {money(det.iva)} · Punitorio {money(det.punitorio)} · IVA punit. {money(det.iva_punit)}</p>
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead><tr><th>Cuota</th><th>Estado</th><th style={{ textAlign: "right" }}>Capital</th><th style={{ textAlign: "right" }}>Interés</th><th style={{ textAlign: "right" }}>IVA</th><th style={{ textAlign: "right" }}>Punit.</th><th style={{ textAlign: "right" }}>Subtotal</th></tr></thead>
              <tbody>
                {det.items.map((it: any) => (
                  <tr key={it.cuota}>
                    <td>{it.cuota}</td><td>{it.vencida ? "Vencida" : "Futura (s/ int.)"}</td>
                    <td style={{ textAlign: "right" }}>{money(it.capital)}</td>
                    <td style={{ textAlign: "right" }}>{money(it.interes)}</td>
                    <td style={{ textAlign: "right" }}>{money(it.iva)}</td>
                    <td style={{ textAlign: "right" }}>{money(it.punitorio)}</td>
                    <td style={{ textAlign: "right" }}><b>{money(it.subtotal)}</b></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ marginTop: "1rem" }}>
            <button onClick={cancelar} style={{ background: "var(--crit)" }}>Confirmar cancelación y emitir recibo</button>
          </div>
        </div>
      )}

      {recibo && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
            <h3 style={{ marginTop: 0 }}>Crédito cancelado — Recibo N° {recibo.numero} ({recibo.cliente_nombre})</h3>
            <button onClick={() => api.verReciboPdf(recibo.id)}>Ver recibo PDF</button>
          </div>
          <p className="kpi">Total cancelación: {money(recibo.total)}</p>
        </div>
      )}
    </>
  );
}
