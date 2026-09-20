import { useEffect, useState } from "react";
import { api } from "../../api";
import LimpiarFiltros from "../../components/LimpiarFiltros";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: any) =>
  v == null ? "—" : Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const num = (v: any) => (v == null ? "—" : Number(v).toLocaleString("es-AR"));

const cols: Col[] = [
  { key: "fecha", label: "Fecha", render: (g) => g.fecha || "—" },
  { key: "periodo", label: "Período" },
  { key: "asiento", label: "Asiento" },
  { key: "recibo", label: "Recibo", render: (g) => g.recibo || "—" },
  { key: "tipo", label: "Tipo", render: (g) => (g.tipo === "I" ? "Ingreso" : g.tipo === "E" ? "Egreso" : g.tipo) },
  { key: "agencia", label: "Agencia", render: (g) => g.agencia || "—" },
  { key: "destino", label: "Destino", render: (g) => g.destino || "—" },
  { key: "origen", label: "Origen", render: (g) => g.origen || "—" },
  { key: "total_pesos", label: "Pesos", align: "right", render: (g) => money(g.total_pesos) },
  { key: "total_bonos", label: "Bonos", align: "right", render: (g) => money(g.total_bonos) },
  { key: "total_lecop", label: "Lecop", align: "right", render: (g) => money(g.total_lecop) },
];

// Contabilidad general de caja/juegos (VFP: Contabilidad/contgral.dbf).
export default function ContabilidadGeneral() {
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [tipo, setTipo] = useState("");
  const [data, setData] = useState<any>(null);
  const [offset, setOffset] = useState(0);
  const LIM = 100;

  async function ver(off = 0, e?: React.FormEvent) {
    e?.preventDefault(); setOffset(off);
    setData(await api.contabilidadGeneral({
      desde: desde || undefined, hasta: hasta || undefined, tipo: tipo || undefined,
      limit: LIM, offset: off,
    }));
  }
  useEffect(() => { ver(0); }, []); // eslint-disable-line

  return (
    <>
      <div className="card">
        <h1 style={{ marginTop: 0 }}>Contabilidad general (caja / juegos)</h1>
        <p className="muted">Movimientos contables por asiento/recibo, con importes por moneda. Fuente real: <code>contgral.dbf</code> (106 mil).</p>
        <form onSubmit={(e) => ver(0, e)} style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap" }}>
          <div><label>Desde</label><input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <div><label>Hasta</label><input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} style={{ marginBottom: 0 }} /></div>
          <div><label>Tipo</label>
            <select value={tipo} onChange={(e) => setTipo(e.target.value)} style={{ marginBottom: 0 }}>
              <option value="">Todos</option><option value="I">Ingreso</option><option value="E">Egreso</option>
            </select></div>
          <button type="submit">Ver</button>
          <LimpiarFiltros activo={!!desde || !!hasta || !!tipo}
                          onClear={() => { setDesde(""); setHasta(""); setTipo(""); ver(0); }} />
        </form>
      </div>

      {data && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>{num(data.total)} movimientos</h3>
          <div style={{ display: "flex", gap: "1.4rem", flexWrap: "wrap", marginBottom: "0.8rem" }}>
            <div><div className="kpi-label">Total pesos</div><div className="kpi">{money(data.total_pesos)}</div></div>
            <div><div className="kpi-label">Total bonos</div><div className="kpi">{money(data.total_bonos)}</div></div>
            <div><div className="kpi-label">Total lecop</div><div className="kpi">{money(data.total_lecop)}</div></div>
          </div>
          <DataTable columns={cols} rows={data.items} total={data.total} limit={LIM} offset={offset}
                     onPage={(off) => ver(off)} rowKey={(_g, i) => i} emptyText="Sin movimientos." />
        </div>
      )}
    </>
  );
}
