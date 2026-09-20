import { useEffect, useState } from "react";
import { api } from "../../api";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

export default function ReporteOP() {
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [rep, setRep] = useState<any>(null);

  async function cargar() { setRep(await api.reporteOP(desde, hasta)); }
  useEffect(() => { cargar(); }, []);

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Reporte de órdenes de pago</h2>
      <p className="muted">Órdenes de pago agrupadas por tipo, con desglose por estado. El importe excluye lo anulado.</p>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap", marginBottom: "0.8rem" }}>
        <div><label>Desde</label><input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <div><label>Hasta</label><input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={{ marginBottom: 0 }} /></div>
        <button onClick={cargar}>Filtrar</button>
      </div>
      {rep && (
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr><th>Tipo</th><th style={{ textAlign: "right" }}>Cant.</th>
                <th style={{ textAlign: "right" }}>Pendiente</th><th style={{ textAlign: "right" }}>Girado</th>
                <th style={{ textAlign: "right" }}>Anulado</th><th style={{ textAlign: "right" }}>Importe</th></tr>
            </thead>
            <tbody>
              {rep.por_tipo.map((f: any) => (
                <tr key={f.tipo}>
                  <td>{f.tipo}</td>
                  <td style={{ textAlign: "right" }}>{f.cantidad.toLocaleString("es-AR")}</td>
                  <td style={{ textAlign: "right" }}>{money(f.pendiente)}</td>
                  <td style={{ textAlign: "right" }}>{money(f.girado)}</td>
                  <td style={{ textAlign: "right" }}>{money(f.anulado)}</td>
                  <td style={{ textAlign: "right" }}><b>{money(f.importe)}</b></td>
                </tr>
              ))}
              {!rep.por_tipo.length && <tr><td colSpan={6} className="muted">Sin órdenes en el período</td></tr>}
            </tbody>
            {rep.por_tipo.length > 0 && (
              <tfoot>
                <tr style={{ borderTop: "2px solid var(--borde)" }}>
                  <td><b>Total</b></td>
                  <td style={{ textAlign: "right" }}><b>{rep.total.cantidad.toLocaleString("es-AR")}</b></td>
                  <td style={{ textAlign: "right" }}><b>{money(rep.total.pendiente)}</b></td>
                  <td style={{ textAlign: "right" }}><b>{money(rep.total.girado)}</b></td>
                  <td style={{ textAlign: "right" }}><b>{money(rep.total.anulado)}</b></td>
                  <td style={{ textAlign: "right" }}><b>{money(rep.total.importe)}</b></td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      )}
    </div>
  );
}
