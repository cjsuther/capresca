import { useState } from "react";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Toolbar, Field, Boton, Alerta, Kpis } from "../../components/ui";
import { money, fecha, hoy, num } from "../../components/format";

const COLS = [
  { key: "cliente", label: "Cliente", sortable: true },
  { key: "cred", label: "Cred/Cuota", render: (i) => `#${i.credito_id}-${i.cuota_numero}` },
  { key: "vencimiento", label: "Vto", sortable: true, render: (i) => fecha(i.vencimiento) },
  { key: "dias_mora", label: "Días", sortable: true, align: "right" },
  { key: "importe_cuota", label: "Cuota", sortable: true, align: "right",
    sortValue: (i) => Number(i.importe_cuota), render: (i) => money(i.importe_cuota) },
  { key: "mora", label: "Mora", sortable: true, align: "right",
    sortValue: (i) => Number(i.mora), render: (i) => money(i.mora) },
  { key: "total", label: "Total", sortable: true, align: "right",
    sortValue: (i) => Number(i.total), render: (i) => <b>{money(i.total)}</b> },
];

export default function PendientesCobroPage() {
  const [corte, setCorte] = useState(hoy());
  const [pend, setPend] = useState(null);
  const [error, setError] = useState("");

  async function ver() {
    setError("");
    try { setPend(await creditos.pendientesCobro(corte)); }
    catch (e) { setError(e.message); setPend(null); }
  }

  return (
    <>
      <PageHeader titulo="Pendientes de cobro (con mora)" descripcion="Cuotas impagas a la fecha de corte, con su mora calculada." />
      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      {pend && (
        <div className="mb-4">
          <Kpis items={[
            { label: "Cuotas", valor: num(pend.cantidad) },
            { label: "Cuota", valor: money(pend.total_cuota) },
            { label: "Mora", valor: money(pend.total_mora), tono: "crit" },
            { label: "Total", valor: money(pend.total) },
          ]} />
        </div>
      )}

      <Card padding={false}>
        <Toolbar>
          <Field label="Fecha de corte">
            <input type="date" className="input" value={corte} onChange={(e) => setCorte(e.target.value)} />
          </Field>
          <Boton onClick={ver}>Generar</Boton>
          <Boton variante="secundario" onClick={() => creditos.verPendientesPdf(corte)}>PDF</Boton>
        </Toolbar>
        <div className="p-4">
          <DataTable columns={COLS} rows={pend?.items || []} clientSort pageSize={50}
                     defaultSort="dias_mora" rowKey={(i, n) => `${i.credito_id}-${i.cuota_numero}-${n}`}
                     emptyText={pend ? "Sin pendientes a la fecha" : "Elegí la fecha de corte y generá el informe."} />
        </div>
      </Card>
    </>
  );
}
