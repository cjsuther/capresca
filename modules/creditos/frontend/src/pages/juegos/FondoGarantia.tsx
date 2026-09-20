import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";
import LimpiarFiltros from "../../components/LimpiarFiltros";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const num = (v: number) => Number(v).toLocaleString("es-AR");

const COLS_DET: Col[] = [
  { key: "juego", label: "Juego", sortable: true },
  { key: "liquidaciones", label: "Liquidaciones", sortable: true, align: "right" },
  { key: "fdo_gtia", label: "Fondo de garantía", sortable: true, align: "right", sortValue: (d) => Number(d.fdo_gtia), render: (d) => money(d.fdo_gtia) },
];

// Informe de Fondo de Garantía (VFP: frm430250000infor_f_gara / menú 43025).
// Une liquidaciones históricas (jghisliq) + vigentes y suma fdo_gtia por agencia.
export default function FondoGarantia() {
  const [data, setData] = useState<any>(null);
  const [agencia, setAgencia] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [sel, setSel] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function ver(e?: React.FormEvent) {
    e?.preventDefault(); setError(""); setSel(null);
    try {
      setData(await api.fondoGarantia({
        no_agencia: agencia || undefined, desde: desde || undefined, hasta: hasta || undefined,
      }));
    } catch (err: any) { setError(err.message); setData(null); }
  }
  useEffect(() => { ver(); }, []); // eslint-disable-line

  const detalleSel = data && sel != null
    ? data.detalle.filter((d: any) => d.no_agencia === sel) : [];

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Informe de Fondo de Garantía</h2>
        <p className="muted">Fondo de garantía retenido por agencia, sobre liquidaciones <b>históricas + vigentes</b>. Fuente real: <code>jghisliq</code> (273 mil) + <code>liquidaciones</code> (menú 43025).</p>
        <form onSubmit={ver} style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap" }}>
          <div><label>N° agencia</label><input value={agencia} onChange={(e) => setAgencia(e.target.value)} placeholder="Todas" style={{ marginBottom: 0, width: 110 }} /></div>
          <div><label>Desde</label><input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <div><label>Hasta</label><input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <button type="submit">Ver</button>
          <LimpiarFiltros activo={!!agencia || !!desde || !!hasta}
                          onClear={() => { setAgencia(""); setDesde(""); setHasta(""); }} />
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {data && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>
            Total fondo de garantía: {money(data.total_fdo_gtia)} · {num(data.cantidad_agencias)} agencias
          </h3>
          <DataTable rows={data.agencias} rowKey={(a) => `${a.no_agencia}-${a.subagencia}`}
                     rowStyle={(a) => (sel === a.no_agencia ? { background: "var(--accent-soft)" } : undefined)}
                     actions={(a) => [{ label: sel === a.no_agencia ? "Ocultar detalle" : "Ver detalle por juego", icon: "eye", onClick: () => setSel(sel === a.no_agencia ? null : a.no_agencia) }]}
                     clientSort pageSize={50} defaultSort="fdo_gtia"
                     emptyText="Sin fondo de garantía para el filtro."
                     columns={[
                       { key: "no_agencia", label: "N° agencia", sortable: true },
                       { key: "subagencia", label: "Sub", sortable: true, render: (a) => a.subagencia || "—" },
                       { key: "liquidaciones", label: "Liquidaciones", sortable: true, align: "right", render: (a) => num(a.liquidaciones) },
                       { key: "fdo_gtia", label: "Fondo de garantía", sortable: true, align: "right", sortValue: (a) => Number(a.fdo_gtia), render: (a) => <b>{money(a.fdo_gtia)}</b> },
                     ]} />
          {sel != null && detalleSel.length > 0 && (
            <div style={{ marginTop: "1rem" }}>
              <h4>Detalle por juego — agencia {sel}</h4>
              <DataTable columns={COLS_DET} rows={detalleSel}
                         rowKey={(d) => `${d.no_agencia}-${d.subagencia}-${d.cod_juego}`}
                         clientSort defaultSort="fdo_gtia" />
            </div>
          )}
        </div>
      )}
    </>
  );
}
