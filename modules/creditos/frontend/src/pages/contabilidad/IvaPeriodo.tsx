import { useState } from "react";
import { api } from "../../api";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

export default function IvaPeriodo() {
  const [desde, setDesde] = useState("2026-01-01");
  const [hasta, setHasta] = useState("2026-12-31");
  const [iva, setIva] = useState<any>(null);

  async function ver() { setIva(await api.ivaPeriodo(desde, hasta)); }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>IVA a pagar por período</h2>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap" }}>
        <div><label>Desde</label><input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <div><label>Hasta</label><input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <button onClick={ver}>Calcular</button>
        <button onClick={() => api.verIvaPdf(desde, hasta)} style={{ background: "var(--ink-soft)" }}>PDF</button>
        {iva && <span className="kpi" style={{ marginLeft: "0.5rem" }}>{money(iva.iva_debito)}</span>}
      </div>
      {iva && <p className="muted" style={{ marginTop: "0.5rem" }}>IVA débito fiscal · {iva.cantidad_asientos} asientos considerados.</p>}
    </div>
  );
}
