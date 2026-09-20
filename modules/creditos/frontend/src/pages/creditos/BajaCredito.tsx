import { useState } from "react";
import { api } from "../../api";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

// Baja / anulación administrativa de crédito (32565 / frm325650000bajacre). Distinta de
// la cancelación por pago: anula el crédito con un motivo obligatorio (no admite crédito
// con cuotas pagadas).
export default function BajaCredito() {
  const [creditoId, setCreditoId] = useState("");
  const [motivo, setMotivo] = useState("");
  const [credito, setCredito] = useState<any>(null);
  const [ok, setOk] = useState<any>(null);
  const [error, setError] = useState("");

  async function buscar(e?: React.FormEvent) {
    e?.preventDefault(); setError(""); setOk(null); setCredito(null);
    const id = Number(creditoId);
    if (!id) { setError("Ingresá un número de crédito."); return; }
    try { setCredito(await api.credito(id)); }
    catch (err: any) { setError(err.message); }
  }

  async function darBaja() {
    setError("");
    if (!motivo.trim()) { setError("El motivo de baja es obligatorio."); return; }
    try { setOk(await api.bajaCredito(Number(creditoId), motivo.trim())); setCredito(null); }
    catch (err: any) { setError(err.message); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Baja de crédito</h2>
        <p className="muted">Anulación administrativa de un crédito (p. ej. cargado por error), con motivo obligatorio. No aplica a créditos con cuotas pagadas (para ésos va la cancelación). Fuente: <code>frm325650000bajacre</code> (menú 32565).</p>
        <form onSubmit={buscar} style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
          <div><label>N° de crédito</label><input value={creditoId} onChange={(e) => setCreditoId(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <button type="submit">Buscar</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {credito && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Crédito {credito.id} — estado {credito.estado}</h3>
          <p className="muted">Capital {money(credito.capital)} · Saldo {money(credito.saldo_capital)}</p>
          <div><label>Motivo de baja</label>
            <input value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Ej: cargado por error" style={{ width: "100%", maxWidth: 500 }} /></div>
          <button onClick={darBaja} disabled={!motivo.trim()} style={{ background: "var(--crit)" }}>Dar de baja el crédito</button>
        </div>
      )}

      {ok && (
        <div className="card">
          <div className="aviso" style={{ borderColor: "var(--ok)", background: "var(--ok-soft)" }}>
            Crédito <b>{ok.id}</b> dado de baja (estado {ok.estado}).
          </div>
        </div>
      )}
    </>
  );
}
