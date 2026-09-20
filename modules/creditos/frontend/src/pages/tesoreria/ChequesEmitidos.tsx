import { useEffect, useState } from "react";
import { api } from "../../api";
import LimpiarFiltros from "../../components/LimpiarFiltros";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const num = (v: number) => Number(v).toLocaleString("es-AR");

// Listado de cheques emitidos (VFP: Egresos/cheques.dbf / menú 83040).
export default function ChequesEmitidos() {
  const [data, setData] = useState<any>(null);
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [cuenta, setCuenta] = useState("");
  const [anulados, setAnulados] = useState(false);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const LIM = 100;

  async function ver(off = 0, e?: React.FormEvent) {
    e?.preventDefault(); setError(""); setOffset(off);
    try {
      setData(await api.chequesEmitidos({
        desde: desde || undefined, hasta: hasta || undefined, cuenta: cuenta || undefined,
        incluir_anulados: anulados, limit: LIM, offset: off,
      }));
    } catch (err: any) { setError(err.message); setData(null); }
  }
  useEffect(() => { ver(0); }, []); // eslint-disable-line

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Listado de cheques emitidos</h2>
        <p className="muted">Cheques emitidos por Tesorería. Fuente real: <code>cheques.dbf</code> (73 mil, menú 83040).</p>
        <form onSubmit={(e) => ver(0, e)} style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap" }}>
          <div><label>Desde</label><input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <div><label>Hasta</label><input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <div><label>Chequera</label>
            <select value={cuenta} onChange={(e) => setCuenta(e.target.value)} style={{ marginBottom: 0 }}>
              <option value="">Todas</option>
              <option value="CREDITOS">Créditos</option>
              <option value="SEGUROS">Seguros</option>
              <option value="JUEGOS">Juegos</option>
              <option value="RENTAS">Rentas</option>
            </select></div>
          <label style={{ display: "flex", gap: "0.35rem", alignItems: "center" }}>
            <input type="checkbox" checked={anulados} onChange={(e) => setAnulados(e.target.checked)} style={{ marginBottom: 0 }} /> Incluir anulados</label>
          <button type="submit">Ver</button>
          <LimpiarFiltros activo={!!desde || !!hasta || !!cuenta || anulados}
                          onClear={() => { setDesde(""); setHasta(""); setCuenta(""); setAnulados(false); ver(0); }} />
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {data && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>{num(data.total)} cheques · {money(data.importe_total)}</h3>
          {data.resumen.length > 1 && (
            <table style={{ marginBottom: "1rem" }}>
              <thead><tr><th>Chequera</th><th style={{ textAlign: "right" }}>Cheques</th><th style={{ textAlign: "right" }}>Importe</th></tr></thead>
              <tbody>
                {data.resumen.map((r: any) => (
                  <tr key={r.cuenta} style={{ cursor: "pointer" }} onClick={() => { setCuenta(r.cuenta); ver(0); }}>
                    <td>{r.cuenta}</td><td style={{ textAlign: "right" }}>{num(r.cantidad)}</td>
                    <td style={{ textAlign: "right" }}>{money(r.importe)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <table>
            <thead><tr><th>N° cheque</th><th>Fecha</th><th>Banco</th><th>Chequera</th><th style={{ textAlign: "right" }}>Importe</th><th>OP</th><th>Res.</th><th>Liq.</th><th></th></tr></thead>
            <tbody>
              {data.items.map((c: any) => (
                <tr key={c.id} style={c.anulado ? { opacity: 0.5, textDecoration: "line-through" } : undefined}>
                  <td>{c.ncheque}</td><td>{c.fecha || "—"}</td><td>{c.banco}</td><td>{c.cuenta}</td>
                  <td style={{ textAlign: "right" }}>{money(c.importe)}</td>
                  <td>{c.nop || "—"}</td><td>{c.nres || "—"}</td><td>{c.nliqui || "—"}</td>
                  <td>{c.anulado ? "anulado" : ""}</td>
                </tr>
              ))}
              {!data.items.length && <tr><td colSpan={9} className="muted">Sin cheques para el filtro.</td></tr>}
            </tbody>
          </table>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginTop: "0.6rem" }}>
            <button disabled={offset === 0} onClick={() => ver(Math.max(0, offset - LIM))}>‹ Anterior</button>
            <span className="muted">{data.total ? offset + 1 : 0}–{Math.min(offset + LIM, data.total)} de {num(data.total)}</span>
            <button disabled={offset + LIM >= data.total} onClick={() => ver(offset + LIM)}>Siguiente ›</button>
          </div>
        </div>
      )}
    </>
  );
}
