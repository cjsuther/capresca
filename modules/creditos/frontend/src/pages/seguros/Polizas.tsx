import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../../api";
import VolverFicha from "../../components/VolverFicha";
import LimpiarFiltros from "../../components/LimpiarFiltros";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const num = (v: number) => Number(v).toLocaleString("es-AR");

export default function Polizas() {
  const [desde, setDesde] = useState("2026-01-01");
  const [hasta, setHasta] = useState(new Date().toISOString().slice(0, 10));
  const [liq, setLiq] = useState<any[]>([]);

  // Pólizas de seguro de vida por agente (VFP: seguros.dbf, 207 mil).
  const [params] = useSearchParams();
  const [pag, setPag] = useState<any>(null);
  const [q, setQ] = useState(params.get("q") || "");
  const [codigo, setCodigo] = useState<number | "">("");
  const [vig, setVig] = useState(true);
  const [offset, setOffset] = useState(0);
  const LIM = 50;

  async function buscar(off = 0) {
    setOffset(off);
    setPag(await api.polizasAgente({
      q: q || undefined, codigo: codigo || undefined,
      solo_vigentes: vig, limit: LIM, offset: off,
    }));
  }
  useEffect(() => { buscar(0); }, []); // eslint-disable-line

  async function liquidar() { setLiq(await api.liquidacionSeguros(desde, hasta)); }

  return (
    <>
      <VolverFicha />
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Liquidación de seguros</h2>
        <p className="muted">Seguro cobrado en el período a remitir a la compañía aseguradora.</p>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
          <div><label>Desde</label><input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <div><label>Hasta</label><input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <button onClick={liquidar}>Liquidar</button>
        </div>
        {liq.length > 0 ? (
          <table style={{ marginTop: "1rem" }}>
            <thead><tr><th>Compañía</th><th>Recibos</th><th>Total a remitir</th></tr></thead>
            <tbody>
              {liq.map((l) => (
                <tr key={l.compania_id}><td>{l.compania}</td><td>{l.cantidad_recibos}</td><td><b>{money(l.total_seguro)}</b></td></tr>
              ))}
            </tbody>
          </table>
        ) : <p className="muted" style={{ marginTop: "0.6rem" }}>Sin datos para el período (ejecutá "Liquidar").</p>}
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Pólizas de seguro de vida (por agente)</h2>
        <p className="muted">Seguro de vida colectivo del agente público. Fuente real: <code>seguros.dbf</code> (207 mil pólizas).</p>

        {pag && (
          <table style={{ marginBottom: "1rem" }}>
            <thead><tr><th>Tipo de seguro</th><th style={{ textAlign: "right" }}>Pólizas</th><th style={{ textAlign: "right" }}>Coberturas</th></tr></thead>
            <tbody>
              {pag.resumen.map((r: any) => (
                <tr key={r.codigo} style={{ cursor: "pointer" }}
                    onClick={() => { setCodigo(r.codigo); buscar(0); }}>
                  <td>{r.tipo}</td>
                  <td style={{ textAlign: "right" }}>{num(r.polizas)}</td>
                  <td style={{ textAlign: "right" }}>{num(r.cantidad)}</td>
                </tr>
              ))}
              <tr><td><b>Total {vig ? "vigentes" : ""}</b></td><td style={{ textAlign: "right" }}><b>{num(pag.total)}</b></td><td></td></tr>
            </tbody>
          </table>
        )}

        <form onSubmit={(e) => { e.preventDefault(); buscar(0); }}
              style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap" }}>
          <div><label>CUIL / N° agente / N° póliza</label>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar…" style={{ marginBottom: 0 }} /></div>
          <div><label>Tipo</label>
            <select value={codigo} onChange={(e) => setCodigo(e.target.value ? Number(e.target.value) : "")} style={{ marginBottom: 0 }}>
              <option value="">Todos</option>
              <option value={1}>Subsidio Protección Familia</option>
              <option value={2}>Sepelio</option>
              <option value={3}>Vida Obligatorio</option>
              <option value={4}>Incapacidad</option>
              <option value={5}>Vida Adicional</option>
            </select></div>
          <label style={{ display: "flex", gap: "0.35rem", alignItems: "center" }}>
            <input type="checkbox" checked={vig} onChange={(e) => setVig(e.target.checked)} style={{ marginBottom: 0 }} /> Solo vigentes</label>
          <button type="submit">Buscar</button>
          <LimpiarFiltros activo={!!q || codigo !== "" || !vig}
                          onClear={() => { setQ(""); setCodigo(""); setVig(true); buscar(0); }} />
        </form>

        {pag && (
          <>
            <table style={{ marginTop: "1rem" }}>
              <thead><tr><th>N° póliza</th><th>Tipo</th><th>N° agente</th><th>CUIL</th><th>Sexo</th><th style={{ textAlign: "right" }}>Cant.</th><th>Alta</th><th>Estado</th></tr></thead>
              <tbody>
                {pag.items.map((p: any) => (
                  <tr key={p.id}>
                    <td>{p.no_poliza || "—"}</td><td>{p.tipo}</td><td>{p.no_agente}</td>
                    <td>{p.cuil}</td><td>{p.sexo || "—"}</td>
                    <td style={{ textAlign: "right" }}>{p.cantidad}</td>
                    <td>{p.fecha_alta || p.fecha || "—"}</td>
                    <td>{p.estado === "A" ? "Vigente" : p.estado}</td>
                  </tr>
                ))}
                {!pag.items.length && <tr><td colSpan={8} className="muted">Sin pólizas para el filtro.</td></tr>}
              </tbody>
            </table>
            <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", marginTop: "0.6rem" }}>
              <button disabled={offset === 0} onClick={() => buscar(Math.max(0, offset - LIM))}>‹ Anterior</button>
              <span className="muted">{offset + 1}–{Math.min(offset + LIM, pag.total)} de {num(pag.total)}</span>
              <button disabled={offset + LIM >= pag.total} onClick={() => buscar(offset + LIM)}>Siguiente ›</button>
            </div>
          </>
        )}
      </div>
    </>
  );
}
