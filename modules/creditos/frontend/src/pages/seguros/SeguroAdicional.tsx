import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const LIMIT = 25;

export default function SeguroAdicional() {
  const [resumen, setResumen] = useState<any>(null);
  const [conAdic, setConAdic] = useState(false);   // por defecto: agentes SIN adicional
  const [rows, setRows] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [busq, setBusq] = useState("");
  const [q, setQ] = useState("");

  useEffect(() => { api.resumenSeguroAdicional().then(setResumen); }, []);

  async function cargar(off = 0, con = conAdic, query = q) {
    const d = await api.agentesSeguroAdicional({ con_adicional: con, q: query || undefined, limit: LIMIT, offset: off });
    setRows(d.items); setTotal(d.total); setOffset(off);
  }
  useEffect(() => { cargar(0, conAdic, q); }, [conAdic, q]);

  const cols: Col[] = [
    { key: "cuil", label: "CUIL" },
    { key: "titular", label: "Titular" },
    { key: "remuneracion", label: "Remuneración", align: "right", render: (r) => money(r.remuneracion) },
    { key: "seg_obligatorio", label: "Obligatorio", align: "right", render: (r) => money(r.seg_obligatorio) },
    { key: "seg_sepelio", label: "Sepelio", align: "right", render: (r) => money(r.seg_sepelio) },
    { key: "seg_conyuge", label: "Cónyuge", align: "right", render: (r) => money(r.seg_conyuge) },
    { key: "seg_adicional", label: "Adicional", align: "right", render: (r) => money(r.seg_adicional) },
  ];

  return (
    <>
      {resumen && (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Seguro de vida adicional</h2>
          <p className="muted">Seguro del agente por concepto (período {resumen.periodo}). Fuente: segurosap.</p>
          <div className="grid3">
            <div><div className="kpi">{resumen.agentes.toLocaleString("es-AR")}</div><div className="kpi-label">Agentes</div></div>
            <div><div className="kpi">{resumen.con_adicional.toLocaleString("es-AR")}</div><div className="kpi-label">Con adicional</div></div>
            <div><div className="kpi">{resumen.sin_adicional.toLocaleString("es-AR")}</div><div className="kpi-label">Sin adicional</div></div>
          </div>
          <p className="muted" style={{ marginTop: "0.6rem" }}>
            Total adicional {money(resumen.total_adicional)} · obligatorio {money(resumen.total_obligatorio)} ·
            sepelio {money(resumen.total_sepelio)} · cónyuge {money(resumen.total_conyuge)}
          </p>
        </div>
      )}

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
          <h3 style={{ margin: 0 }}>{conAdic ? "Agentes con seguro adicional" : "Agentes sin seguro adicional"}</h3>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <form onSubmit={(e) => { e.preventDefault(); setQ(busq); }}>
              <input value={busq} onChange={(e) => setBusq(e.target.value)} placeholder="Buscar titular / CUIL" style={{ marginBottom: 0 }} />
            </form>
            <label style={{ margin: 0, whiteSpace: "nowrap" }}>
              <input type="checkbox" checked={conAdic} onChange={(e) => setConAdic(e.target.checked)} style={{ width: "auto" }} /> con adicional
            </label>
          </div>
        </div>
        <div style={{ marginTop: "0.6rem" }}>
          <DataTable columns={cols} rows={rows} total={total} limit={LIMIT} offset={offset}
                     onPage={(off) => cargar(off)} rowKey={(r, i) => `${r.cuil}-${i}`} emptyText="Sin agentes" />
        </div>
      </div>
    </>
  );
}
