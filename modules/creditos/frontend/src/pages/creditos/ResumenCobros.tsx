import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";
import LimpiarFiltros from "../../components/LimpiarFiltros";

const money = (v: any) =>
  v == null ? "—" : Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const num = (v: any) => (v == null ? "0" : Number(v).toLocaleString("es-AR"));

const cols: Col[] = [
  { key: "periodo", label: "Período", sortable: true },
  { key: "cuotas", label: "Cuotas", align: "right", sortable: true, render: (r) => num(r.cuotas) },
  { key: "creditos", label: "Créditos", align: "right", sortable: true, render: (r) => num(r.creditos) },
  { key: "capital", label: "Capital", align: "right", sortable: true, render: (r) => money(r.capital), sortValue: (r) => Number(r.capital) },
  { key: "interes", label: "Interés", align: "right", sortable: true, render: (r) => money(r.interes), sortValue: (r) => Number(r.interes) },
  { key: "iva", label: "IVA", align: "right", render: (r) => money(r.iva) },
  { key: "mora", label: "Mora", align: "right", sortable: true, render: (r) => money(r.mora), sortValue: (r) => Number(r.mora) },
  { key: "seguro", label: "Seguro", align: "right", render: (r) => money(r.seguro) },
  { key: "gastos", label: "Gastos", align: "right", render: (r) => money(r.gastos) },
  { key: "total", label: "Total", align: "right", sortable: true, render: (r) => <b>{money(r.total)}</b>, sortValue: (r) => Number(r.total) },
];

export default function ResumenCobros() {
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [data, setData] = useState<{ items: any[]; total: any } | null>(null);

  async function ver() {
    setData(await api.resumenCobros({ desde: desde || undefined, hasta: hasta || undefined }));
  }
  useEffect(() => { ver(); }, []); // eslint-disable-line

  const t = data?.total;
  return (
    <div>
      <div style={{ marginBottom: 14 }}>
        <h1 style={{ margin: 0 }}>Resumen de cobros de créditos</h1>
        <p className="muted" style={{ margin: 0 }}>Cobranza de cuotas por período mensual. Fuente: <code>frm330150000rptcobcre</code>. La mora es residual (total cobrado − conceptos).</p>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div style={{ display: "flex", gap: 10, padding: "12px 14px", borderBottom: "1px solid var(--border)", flexWrap: "wrap", alignItems: "end" }}>
          <label className="rescob-f">Desde<input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} /></label>
          <label className="rescob-f">Hasta<input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></label>
          <button onClick={ver}>Ver</button>
          <LimpiarFiltros activo={!!desde || !!hasta} onClear={() => { setDesde(""); setHasta(""); ver(); }} />
        </div>

        {t && (
          <div className="rescob-kpis">
            <div><div className="rescob-kl">Cuotas cobradas</div><div className="rescob-kv">{num(t.cuotas)}</div></div>
            <div><div className="rescob-kl">Capital</div><div className="rescob-kv">{money(t.capital)}</div></div>
            <div><div className="rescob-kl">Interés</div><div className="rescob-kv">{money(t.interes)}</div></div>
            <div><div className="rescob-kl">Mora</div><div className="rescob-kv">{money(t.mora)}</div></div>
            <div><div className="rescob-kl">Total cobrado</div><div className="rescob-kv rescob-tot">{money(t.total)}</div></div>
          </div>
        )}

        <DataTable columns={cols} rows={data?.items || []} clientSort pageSize={24}
                   defaultSort="periodo" rowKey={(r) => r.periodo}
                   emptyText="Sin cobros en el período." />
      </div>

      <style>{`
        .rescob-f { display:flex; flex-direction:column; gap:3px; font-size:.8rem; color:var(--ink-soft); }
        .rescob-kpis { display:flex; gap:1.4rem; flex-wrap:wrap; padding:12px 14px; border-bottom:1px solid var(--border); }
        .rescob-kl { font-size:.72rem; color:var(--ink-soft); }
        .rescob-kv { font-size:1.05rem; font-weight:700; }
        .rescob-tot { color:var(--brand-2); }
      `}</style>
    </div>
  );
}
