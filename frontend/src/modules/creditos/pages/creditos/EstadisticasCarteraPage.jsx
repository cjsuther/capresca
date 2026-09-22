import { useEffect, useState } from "react";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Kpis, Boton, Alerta } from "../../components/ui";
import { money, num } from "../../components/format";

const COLS = [
  { key: "linea", label: "Línea", sortable: true },
  { key: "cartera", label: "Cartera", sortable: true },
  { key: "cantidad", label: "Cantidad", sortable: true, align: "right", render: (l) => num(l.cantidad) },
  { key: "capital_otorgado", label: "Otorgado", sortable: true, align: "right",
    sortValue: (l) => Number(l.capital_otorgado), render: (l) => money(l.capital_otorgado) },
  { key: "saldo", label: "Saldo", sortable: true, align: "right",
    sortValue: (l) => Number(l.saldo), render: (l) => money(l.saldo) },
];

export default function EstadisticasCarteraPage() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => { creditos.estadisticas().then(setStats).catch((e) => setError(e.message)); }, []);

  return (
    <>
      <PageHeader titulo="Estadísticas de cartera" descripcion="Créditos vigentes, capital otorgado y saldo, por línea y cartera.">
        <Boton variante="secundario" onClick={() => creditos.verCarteraPdf()}>Cartera PDF</Boton>
      </PageHeader>

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}
      {!stats && !error && <Card>Cargando…</Card>}

      {stats && (
        <>
          <div className="mb-4">
            <Kpis items={[
              { label: "Créditos activos", valor: num(stats.creditos_activos) },
              { label: "Capital otorgado", valor: money(stats.capital_otorgado_total) },
              { label: "Saldo en cartera", valor: money(stats.saldo_total) },
            ]} />
          </div>
          <Card padding={false} className="p-4">
            <DataTable columns={COLS} rows={stats.por_linea || []} rowKey={(l) => l.linea_id}
                       clientSort defaultSort="cantidad" emptyText="Sin líneas con cartera" />
          </Card>
        </>
      )}
    </>
  );
}
