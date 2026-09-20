import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../../api";
import VolverFicha from "../../components/VolverFicha";
import LimpiarFiltros from "../../components/LimpiarFiltros";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const num = (v: number) => Number(v).toLocaleString("es-AR");

const cols: Col[] = [
  { key: "sub_tipo", label: "T.Egreso" },
  { key: "no_liquida", label: "N°Liq.", render: (x) => x.no_liquida || "—" },
  { key: "fecha_liqu", label: "Fecha liq.", render: (x) => x.fecha_liqu || "—" },
  { key: "nro_res", label: "N°Res.", render: (x) => x.nro_res || "—" },
  { key: "fec_res", label: "Fecha res.", render: (x) => x.fec_res || "—" },
  { key: "no_credito", label: "N°Créd.", render: (x) => x.no_credito || "—" },
  { key: "apenom", label: "Apellido y nombre" },
  { key: "cuil", label: "CUIL" },
  { key: "no_op", label: "N°O.P.", render: (x) => x.no_op || "—" },
  { key: "fecha_op", label: "Fecha O.P.", render: (x) => x.fecha_op || "—" },
  { key: "no_recibo", label: "N°Recibo", render: (x) => x.no_recibo || "—" },
  { key: "total", label: "Total", align: "right", render: (x) => money(x.total) },
  { key: "estado", label: "", render: (x) => (x.anulado ? "anulado" : x.pagado ? "" : "pend.") },
];

// Busca transacciones de egresos (VFP: frm815050000buscaegresos / menú 81505).
const MODOS = [
  { v: "apellido", label: "Apellido y nombre" },
  { v: "cuil", label: "CUIL" },
  { v: "recibo", label: "N° recibo" },
  { v: "resolucion", label: "N° resolución" },
  { v: "fecha_res", label: "Fecha resolución" },
  { v: "op", label: "N° O.P." },
  { v: "fecha_op", label: "Fecha O.P." },
];

export default function BuscaEgresos() {
  const [params] = useSearchParams();
  const [modo, setModo] = useState(params.get("modo") || "apellido");
  const [valor, setValor] = useState(params.get("valor") || "");
  const [data, setData] = useState<any>(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  const LIM = 100;
  const esFecha = modo === "fecha_res" || modo === "fecha_op";

  async function buscar(off = 0, e?: React.FormEvent, ov?: { modo: string; valor: string }) {
    e?.preventDefault(); setError(""); setOffset(off);
    try {
      setData(await api.buscarEgresos({ modo: ov?.modo ?? modo, valor: ov?.valor ?? valor, limit: LIM, offset: off }));
    } catch (err: any) { setError(err.message); setData(null); }
  }
  useEffect(() => {
    const m = params.get("modo"), v = params.get("valor");
    if (m && v) buscar(0, undefined, { modo: m, valor: v });
  }, []); // eslint-disable-line

  return (
    <>
      <VolverFicha />
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Busca transacciones de egresos</h2>
        <p className="muted">Ledger real de egresos de Tesorería. Fuente: <code>egresos.dbf</code> (340 mil, menú 81505). Cada fila permite <b>reimprimir su comprobante</b> (consolida los reimp* de VFP: créditos, seguros, premios, subsidios, varios).</p>
        <form onSubmit={(e) => buscar(0, e)} style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap" }}>
          <div><label>Buscar por</label>
            <select value={modo} onChange={(e) => { setModo(e.target.value); setValor(""); }} style={{ marginBottom: 0 }}>
              {MODOS.map((m) => <option key={m.v} value={m.v}>{m.label}</option>)}
            </select></div>
          <div><label>{esFecha ? "Fecha" : "Valor"}</label>
            <input type={esFecha ? "date" : "text"} value={valor} onChange={(e) => setValor(e.target.value)}
                   style={{ marginBottom: 0 }} placeholder={esFecha ? "" : "…"} /></div>
          <button type="submit">Buscar</button>
          <LimpiarFiltros activo={!!valor} onClear={() => { setValor(""); setData(null); }} />
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {data && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>{num(data.total)} egresos · {money(data.importe_total)}</h3>
          <DataTable columns={cols} rows={data.items} total={data.total} limit={LIM} offset={offset}
                     onPage={(off) => buscar(off)} rowKey={(x) => x.id}
                     rowStyle={(x) => (x.anulado ? { opacity: 0.5, textDecoration: "line-through" } : undefined)}
                     actions={(x) => [{ label: "Reimprimir comprobante", icon: "printer",
                                        onClick: () => api.comprobanteEgresoPdf(x.id) }]}
                     emptyText="Sin egresos para la búsqueda." />
        </div>
      )}
    </>
  );
}
