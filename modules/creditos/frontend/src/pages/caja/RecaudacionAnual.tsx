import { useState } from "react";
import { api } from "../../api";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
const ORIGEN: Record<string, string> = { CR: "Créditos/Seguros", JUEG: "Quiniela" };

// Recaudación anual por origen y mes (23030 / frm230300000reca).
export default function RecaudacionAnual() {
  const [anio, setAnio] = useState(new Date().getFullYear());
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  async function ver(e?: React.FormEvent) {
    e?.preventDefault(); setError("");
    try { setData(await api.recaudacionAnual(anio)); }
    catch (err: any) { setError(err.message); setData(null); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Recaudación anual por origen y mes</h2>
        <p className="muted">Totales recaudados por origen (créditos/seguros y quiniela) y mes del año. Fuente: <code>frm230300000reca</code> (menú 23030).</p>
        <form onSubmit={ver} style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
          <div><label>Año</label><input type="number" value={anio} onChange={(e) => setAnio(Number(e.target.value))} style={{ marginBottom: 0, width: 100 }} /></div>
          <button type="submit">Procesar</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {data && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Año {data.anio} — total {money(data.total_general)}</h3>
          {!data.origenes.length && <p className="muted">Sin recaudación en el año.</p>}
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead><tr><th>Origen</th>{MESES.map((m) => <th key={m} style={{ textAlign: "right" }}>{m}</th>)}<th style={{ textAlign: "right" }}>Total</th></tr></thead>
              <tbody>
                {data.origenes.map((o: any) => (
                  <tr key={o.origen}>
                    <td><b>{ORIGEN[o.origen] || o.origen}</b></td>
                    {o.meses.map((v: string, i: number) => (
                      <td key={i} style={{ textAlign: "right" }}>{Number(v) ? money(v) : "-"}</td>
                    ))}
                    <td style={{ textAlign: "right" }}><b>{money(o.total)}</b></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
