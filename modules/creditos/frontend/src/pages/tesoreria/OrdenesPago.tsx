import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const ESTADO: Record<string, string> = { P: "Pendiente", G: "Girada", A: "Anulada" };
const LIMIT = 25;

export default function OrdenesPago() {
  const [ops, setOps] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [totales, setTotales] = useState<any>(null);
  const [filtro, setFiltro] = useState("");
  const [nueva, setNueva] = useState({ beneficiario: "", concepto: "", importe: "", cuit: "" });
  const [pagar, setPagar] = useState<{ id: number; banco: string; cheque: string } | null>(null);
  const [error, setError] = useState("");

  async function cargar(off = 0) {
    const d = await api.ordenesPago({ estado: filtro || undefined, limit: LIMIT, offset: off });
    setOps(d.items); setTotal(d.total); setOffset(off);
    setTotales(await api.totalesEgresos());
  }
  useEffect(() => { cargar(0); }, [filtro]);

  const cols: Col[] = [
    { key: "numero", label: "N°" },
    { key: "fecha", label: "Fecha" },
    { key: "beneficiario", label: "Beneficiario" },
    { key: "concepto", label: "Concepto" },
    { key: "importe", label: "Importe", align: "right", render: (o) => money(o.importe) },
    { key: "estado", label: "Estado", render: (o) => ESTADO[o.estado] },
    { key: "cheque_numero", label: "Cheque", render: (o) => o.cheque_numero || "-" },
    {
      key: "acc", label: "", align: "right", render: (o) =>
        o.estado === "P" ? <a href="#" onClick={(e) => { e.preventDefault(); setPagar({ id: o.id, banco: "Banco Nación", cheque: "" }); }}>pagar</a> : null,
    },
  ];

  async function crear(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try { await api.crearOP({ ...nueva, tipo: "PROVEEDOR" }); setNueva({ beneficiario: "", concepto: "", importe: "", cuit: "" }); cargar(0); }
    catch (err: any) { setError(err.message); }
  }
  async function confirmarPago() {
    if (!pagar) return; setError("");
    try { await api.pagarOP(pagar.id, { banco: pagar.banco, cheque_numero: pagar.cheque }); setPagar(null); cargar(offset); }
    catch (err: any) { setError(err.message); }
  }

  return (
    <>
      {totales && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Órdenes de pago</h2>
          <div className="grid2">
            <div><div className="kpi">{money(totales.pendiente)}</div><div className="kpi-label">Pendiente de pago</div></div>
            <div><div className="kpi">{money(totales.girado)}</div><div className="kpi-label">Girado</div></div>
          </div>
        </div>
      )}
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Nueva OP (proveedor / licitación)</h3>
        <form onSubmit={crear}>
          <div className="grid3">
            <div><label>Beneficiario</label><input value={nueva.beneficiario} onChange={(e) => setNueva({ ...nueva, beneficiario: e.target.value })} required /></div>
            <div><label>CUIT</label><input value={nueva.cuit} onChange={(e) => setNueva({ ...nueva, cuit: e.target.value })} /></div>
            <div><label>Importe</label><input value={nueva.importe} onChange={(e) => setNueva({ ...nueva, importe: e.target.value })} required /></div>
          </div>
          <label>Concepto</label><input value={nueva.concepto} onChange={(e) => setNueva({ ...nueva, concepto: e.target.value })} required />
          <button type="submit">Registrar OP</button>
          {error && <p className="error">{error}</p>}
        </form>
      </div>
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0 }}>Listado</h3>
          <select value={filtro} onChange={(e) => setFiltro(e.target.value)} style={{ width: "auto", marginBottom: 0 }}>
            <option value="">Todas</option><option value="P">Pendientes</option><option value="G">Giradas</option><option value="A">Anuladas</option>
          </select>
        </div>
        <div style={{ marginTop: "0.6rem" }}>
          <DataTable columns={cols} rows={ops} total={total} limit={LIMIT} offset={offset}
                     onPage={(off) => cargar(off)} rowKey={(o) => o.id} emptyText="Sin órdenes" />
        </div>
      </div>
      {pagar && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Pagar OP #{pagar.id}</h3>
          <div className="grid2">
            <div><label>Banco</label><input value={pagar.banco} onChange={(e) => setPagar({ ...pagar, banco: e.target.value })} /></div>
            <div><label>N° de cheque</label><input value={pagar.cheque} onChange={(e) => setPagar({ ...pagar, cheque: e.target.value })} /></div>
          </div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button onClick={confirmarPago}>Confirmar pago</button>
            <button onClick={() => setPagar(null)} style={{ background: "var(--ink-faint)" }}>Cancelar</button>
          </div>
        </div>
      )}
    </>
  );
}
