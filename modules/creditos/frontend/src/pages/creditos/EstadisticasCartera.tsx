import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const COLS: Col[] = [
  { key: "linea", label: "Línea", sortable: true },
  { key: "cartera", label: "Cartera", sortable: true },
  { key: "cantidad", label: "Cantidad", sortable: true, align: "right" },
  { key: "capital_otorgado", label: "Otorgado", sortable: true, align: "right",
    sortValue: (l) => Number(l.capital_otorgado), render: (l) => money(l.capital_otorgado) },
  { key: "saldo", label: "Saldo", sortable: true, align: "right",
    sortValue: (l) => Number(l.saldo), render: (l) => money(l.saldo) },
];

export default function EstadisticasCartera() {
  const [stats, setStats] = useState<any>(null);
  useEffect(() => { api.estadisticas().then(setStats); }, []);
  if (!stats) return <div className="card">Cargando…</div>;

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>Estadísticas de cartera</h2>
        <button onClick={() => api.verCarteraPdf()} style={{ background: "var(--ink-soft)" }}>Cartera PDF</button>
      </div>
      <div className="grid3" style={{ marginTop: "1rem" }}>
        <div><div className="kpi">{stats.creditos_activos}</div><div className="kpi-label">Créditos activos</div></div>
        <div><div className="kpi">{money(stats.capital_otorgado_total)}</div><div className="kpi-label">Capital otorgado</div></div>
        <div><div className="kpi">{money(stats.saldo_total)}</div><div className="kpi-label">Saldo en cartera</div></div>
      </div>
      {stats.por_linea?.length > 0 && (
        <div style={{ marginTop: "1rem" }}>
          <DataTable columns={COLS} rows={stats.por_linea} rowKey={(l) => l.linea_id}
                     clientSort defaultSort="cantidad" />
        </div>
      )}
    </div>
  );
}
