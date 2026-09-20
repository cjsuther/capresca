import { useState } from "react";
import { api } from "../../api";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

// Recálculo de cuotas (32535 / frm325350000reca). Dos modos exactos del fuente:
//  - 'vencimientos' (recaotros): sólo reprograma la fecha de las cuotas no pagadas.
//  - 'jubilatorio' (recaportes): regenera el plan pendiente como capital puro,
//    cuota = 10% del haber jubilatorio.
// Siempre con vista previa antes de confirmar; nunca toca cuotas pagadas.
export default function RecalculoCredito() {
  const [creditoId, setCreditoId] = useState("");
  const [modo, setModo] = useState("vencimientos");
  const [primerVto, setPrimerVto] = useState(new Date().toISOString().slice(0, 10));
  const [haber, setHaber] = useState("");
  const [prev, setPrev] = useState<any>(null);
  const [ok, setOk] = useState<any>(null);
  const [error, setError] = useState("");

  async function previsualizar(e?: React.FormEvent) {
    e?.preventDefault(); setError(""); setOk(null); setPrev(null);
    const id = Number(creditoId);
    if (!id) { setError("Ingresá un número de crédito."); return; }
    try {
      setPrev(await api.recalculoPreview(id, {
        modo, primer_vto: modo === "vencimientos" ? primerVto : undefined,
        haber: modo === "jubilatorio" ? haber : undefined,
      }));
    } catch (err: any) { setError(err.message); }
  }

  async function aplicar() {
    setError("");
    try {
      const r = await api.recalculoAplicar(Number(creditoId), {
        modo, primer_vto: modo === "vencimientos" ? primerVto : undefined,
        haber: modo === "jubilatorio" ? haber : undefined,
      });
      setOk(r); setPrev(null);
    } catch (err: any) { setError(err.message); }
  }

  const rows = prev ? Math.max(prev.actual.length, prev.propuesto.length) : 0;

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Recálculo de cuotas</h2>
        <p className="muted">Recalcula el plan pendiente de un crédito (nunca toca cuotas pagadas). Fuente: <code>frm325350000reca</code> (menú 32535).</p>
        <form onSubmit={previsualizar} style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap" }}>
          <div><label>N° de crédito</label><input value={creditoId} onChange={(e) => setCreditoId(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <div><label>Modo</label>
            <select value={modo} onChange={(e) => setModo(e.target.value)} style={{ marginBottom: 0 }}>
              <option value="vencimientos">Reprogramar vencimientos</option>
              <option value="jubilatorio">Jubilatorio (capital, 10% del haber)</option>
            </select></div>
          {modo === "vencimientos"
            ? <div><label>1er vto. (cuota 1)</label><input type="date" value={primerVto} onChange={(e) => setPrimerVto(e.target.value)} style={{ marginBottom: 0 }} /></div>
            : <div><label>Haber jubilatorio</label><input value={haber} onChange={(e) => setHaber(e.target.value)} placeholder="Ej: 250000" style={{ marginBottom: 0, width: 140 }} /></div>}
          <button type="submit">Previsualizar</button>
        </form>
        {error && <p className="error">{error}</p>}
        {ok && <div className="aviso" style={{ marginTop: "0.6rem", borderColor: "var(--ok)", background: "var(--ok-soft)" }}>Recálculo aplicado: {ok.cuotas_resultantes} cuotas, total {money(ok.total)}.</div>}
      </div>

      {prev && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Vista previa — {prev.modo}</h3>
          <p className="muted">Actual: {prev.cantidad_actual} cuotas ({money(prev.total_actual)}) → Propuesto: {prev.cantidad_propuesta} cuotas ({money(prev.total_propuesto)})</p>
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead><tr>
                <th colSpan={3} style={{ background: "var(--surface-2)" }}>Actual</th>
                <th colSpan={3} style={{ background: "var(--accent-soft)" }}>Propuesto</th>
              </tr><tr>
                <th>Cuota</th><th>Vto</th><th style={{ textAlign: "right" }}>Total</th>
                <th>Cuota</th><th>Vto</th><th style={{ textAlign: "right" }}>Total</th>
              </tr></thead>
              <tbody>
                {Array.from({ length: rows }).map((_, i) => {
                  const a = prev.actual[i]; const p = prev.propuesto[i];
                  return (
                    <tr key={i}>
                      <td>{a?.numero ?? "-"}</td><td>{a?.fecha_vto ?? "-"}</td><td style={{ textAlign: "right" }}>{a ? money(a.total) : "-"}</td>
                      <td>{p?.numero ?? "-"}</td>
                      <td style={{ color: a && p && a.fecha_vto !== p.fecha_vto ? "var(--crit)" : undefined }}>{p?.fecha_vto ?? "-"}</td>
                      <td style={{ textAlign: "right" }}>{p ? money(p.total) : "-"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div style={{ marginTop: "1rem" }}>
            <button onClick={aplicar} style={{ background: "var(--crit)" }}>Confirmar y aplicar recálculo</button>
          </div>
        </div>
      )}
    </>
  );
}
