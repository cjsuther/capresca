import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const COLS: Col[] = [
  { key: "departamento", label: "Departamento", sortable: true },
  { key: "cantidad", label: "Cantidad", sortable: true, align: "right" },
  { key: "monto_total", label: "Monto", sortable: true, align: "right",
    sortValue: (d) => Number(d.monto_total), render: (d) => money(d.monto_total) },
];

export default function Jubilados() {
  const [jubR, setJubR] = useState<any>(null);
  const [jubDep, setJubDep] = useState<any[]>([]);
  useEffect(() => {
    api.jubiladosResumen().then(setJubR);
    api.jubiladosPorDepto().then(setJubDep);
  }, []);

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Créditos a jubilados / Ley 5094</h2>
      {jubR && (
        <div className="grid3">
          <div><div className="kpi">{jubR.total}</div><div className="kpi-label">Total</div></div>
          <div><div className="kpi">{jubR.liquidadas}</div><div className="kpi-label">Liquidadas</div></div>
          <div><div className="kpi">{money(jubR.monto_total)}</div><div className="kpi-label">Monto total</div></div>
        </div>
      )}
      {jubDep.length > 0 && (
        <div style={{ marginTop: "1rem", maxWidth: 560 }}>
          <DataTable columns={COLS} rows={jubDep} rowKey={(d) => d.departamento}
                     clientSort defaultSort="cantidad" />
        </div>
      )}
    </div>
  );
}
