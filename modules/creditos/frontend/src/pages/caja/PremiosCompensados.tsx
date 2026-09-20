import { useState } from "react";
import { api } from "../../api";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

// Premios compensados por capital/interior (23055 / frm230550000premioscompensados):
// agrupa cajaliq por interior y agencia en una fecha de vencimiento.
export default function PremiosCompensados() {
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  async function ver(e?: React.FormEvent) {
    e?.preventDefault(); setError("");
    try { setData(await api.premiosCompensados(fecha)); }
    catch (err: any) { setError(err.message); setData(null); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Premios compensados (capital / interior)</h2>
        <p className="muted">Compensación de premios por agencia, separada en capital e interior, para una fecha de vencimiento. Fuente: <code>frm230550000premioscompensados</code> (menú 23055).</p>
        <form onSubmit={ver} style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
          <div><label>Fecha de vencimiento</label><input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <button type="submit">Consultar</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {data && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Total general {money(data.total_general)}</h3>
          {!data.grupos.length && <p className="muted">Sin datos para esa fecha.</p>}
          {data.grupos.map((g: any) => (
            <div key={g.grupo} style={{ marginBottom: "1.2rem" }}>
              <h4 style={{ margin: "0.6rem 0" }}>{g.grupo} — {g.cantidad} agencias · {money(g.total_gral)}</h4>
              <div style={{ overflowX: "auto" }}>
                <table>
                  <thead><tr><th>Cód. Agencia</th><th>N° Ag.</th><th>Sub</th><th style={{ textAlign: "right" }}>Total liq.</th><th style={{ textAlign: "right" }}>Premios</th><th style={{ textAlign: "right" }}>Com. premios</th><th style={{ textAlign: "right" }}>Total gral.</th></tr></thead>
                  <tbody>
                    {g.items.map((it: any) => (
                      <tr key={it.cod_agencia}>
                        <td>{it.cod_agencia}</td><td>{it.no_agencia}</td><td>{it.subagencia}</td>
                        <td style={{ textAlign: "right" }}>{money(it.total)}</td>
                        <td style={{ textAlign: "right" }}>{money(it.premios)}</td>
                        <td style={{ textAlign: "right" }}>{money(it.com_premios)}</td>
                        <td style={{ textAlign: "right", color: Number(it.total_gral) < 0 ? "var(--crit)" : undefined }}><b>{money(it.total_gral)}</b></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
