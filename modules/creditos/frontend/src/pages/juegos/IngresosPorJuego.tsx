import { useEffect, useState } from "react";
import { api } from "../../api";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

export default function IngresosPorJuego() {
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [filas, setFilas] = useState<any[]>([]);

  async function cargar() { setFilas(await api.ingresosPorJuego(desde, hasta)); }
  useEffect(() => { cargar(); }, []);

  const tot = filas.reduce((a, f) => ({
    recaudacion: a.recaudacion + Number(f.recaudacion),
    premios: a.premios + Number(f.premios),
    comisiones: a.comisiones + Number(f.comisiones),
    neto: a.neto + Number(f.neto),
    total: a.total + Number(f.total),
  }), { recaudacion: 0, premios: 0, comisiones: 0, neto: 0, total: 0 });

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Ingresos por juego</h2>
      <p className="muted">Recaudación, premios y comisiones agrupados por juego. Neto = recaudación − premios − comisiones.</p>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap", marginBottom: "0.8rem" }}>
        <div><label>Desde</label><input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <div><label>Hasta</label><input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <button onClick={cargar}>Filtrar</button>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr><th>Juego</th><th style={{ textAlign: "right" }}>Liq.</th>
              <th style={{ textAlign: "right" }}>Recaudación</th><th style={{ textAlign: "right" }}>Premios</th>
              <th style={{ textAlign: "right" }}>Comisiones</th><th style={{ textAlign: "right" }}>Neto</th></tr>
          </thead>
          <tbody>
            {filas.map((f) => (
              <tr key={f.juego}>
                <td>{f.juego}</td>
                <td style={{ textAlign: "right" }}>{f.cantidad.toLocaleString("es-AR")}</td>
                <td style={{ textAlign: "right" }}>{money(f.recaudacion)}</td>
                <td style={{ textAlign: "right" }}>{money(f.premios)}</td>
                <td style={{ textAlign: "right" }}>{money(f.comisiones)}</td>
                <td style={{ textAlign: "right" }}><b>{money(f.neto)}</b></td>
              </tr>
            ))}
            {!filas.length && <tr><td colSpan={6} className="muted">Sin datos</td></tr>}
          </tbody>
          {filas.length > 0 && (
            <tfoot>
              <tr style={{ borderTop: "2px solid var(--borde)" }}>
                <td><b>Total</b></td><td></td>
                <td style={{ textAlign: "right" }}><b>{money(tot.recaudacion)}</b></td>
                <td style={{ textAlign: "right" }}><b>{money(tot.premios)}</b></td>
                <td style={{ textAlign: "right" }}><b>{money(tot.comisiones)}</b></td>
                <td style={{ textAlign: "right" }}><b>{money(tot.neto)}</b></td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}
