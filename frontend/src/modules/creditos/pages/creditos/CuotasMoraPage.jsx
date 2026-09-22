import { useState } from "react";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Toolbar, Field, Boton, Alerta } from "../../components/ui";
import { money, fecha, hoy, num } from "../../components/format";

const COLS = [
  { key: "cliente", label: "Cliente", sortable: true },
  { key: "cred", label: "Cred/Cuota", render: (i) => `#${i.credito_id}-${i.cuota_numero}` },
  { key: "vencimiento", label: "Vto", sortable: true, render: (i) => fecha(i.vencimiento) },
  { key: "dias_mora", label: "Días mora", sortable: true, align: "right" },
  { key: "importe", label: "Importe", sortable: true, align: "right",
    sortValue: (i) => Number(i.importe), render: (i) => money(i.importe) },
];

export default function CuotasMoraPage() {
  const [corte, setCorte] = useState(hoy());
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  async function ver() {
    setError("");
    try { setData(await creditos.cuotasMora(corte)); }
    catch (e) { setError(e.message); setData(null); }
  }

  return (
    <>
      <PageHeader titulo="Cuotas en mora" descripcion="Cuotas vencidas impagas a una fecha de corte." />
      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      <Card padding={false}>
        <Toolbar>
          <Field label="Fecha de corte">
            <input type="date" className="input" value={corte} onChange={(e) => setCorte(e.target.value)} />
          </Field>
          <Boton onClick={ver}>Generar</Boton>
          {data && (
            <span className="ml-auto text-sm text-gray-600">
              {num(data.cantidad)} cuotas vencidas · total <b>{money(data.total)}</b>
            </span>
          )}
        </Toolbar>
        <div className="p-4">
          <DataTable columns={COLS} rows={data?.items || []} clientSort pageSize={50}
                     defaultSort="dias_mora" rowKey={(i, n) => `${i.credito_id}-${i.cuota_numero}-${n}`}
                     emptyText={data ? "Sin cuotas en mora" : "Elegí la fecha de corte y generá el informe."} />
        </div>
      </Card>
    </>
  );
}
