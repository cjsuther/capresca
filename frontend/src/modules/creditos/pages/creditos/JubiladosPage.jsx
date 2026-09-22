import { useEffect, useState } from "react";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Kpis, Alerta } from "../../components/ui";
import { money, num } from "../../components/format";

const COLS = [
  { key: "departamento", label: "Departamento", sortable: true },
  { key: "cantidad", label: "Cantidad", sortable: true, align: "right", render: (d) => num(d.cantidad) },
  { key: "monto_total", label: "Monto", sortable: true, align: "right",
    sortValue: (d) => Number(d.monto_total), render: (d) => money(d.monto_total) },
];

export default function JubiladosPage() {
  const [resumen, setResumen] = useState(null);
  const [porDepto, setPorDepto] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    creditos.jubiladosResumen().then(setResumen).catch((e) => setError(e.message));
    creditos.jubiladosPorDepto().then(setPorDepto).catch((e) => setError(e.message));
  }, []);

  return (
    <>
      <PageHeader titulo="Créditos a jubilados / Ley 5094" descripcion="Cartera del régimen de jubilados, por departamento." />
      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      {resumen && (
        <div className="mb-4">
          <Kpis items={[
            { label: "Total", valor: num(resumen.total) },
            { label: "Liquidadas", valor: num(resumen.liquidadas) },
            { label: "Monto total", valor: money(resumen.monto_total) },
          ]} />
        </div>
      )}

      <Card padding={false} className="p-4 max-w-2xl">
        <DataTable columns={COLS} rows={porDepto} rowKey={(d) => d.departamento}
                   clientSort defaultSort="cantidad" emptyText="Sin créditos del régimen" />
      </Card>
    </>
  );
}
