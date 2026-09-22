import { useState } from "react";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Toolbar, Field, Boton, Alerta } from "../../components/ui";
import { money, fecha, num } from "../../components/format";

const COLS = [
  { key: "credito_id", label: "Crédito", sortable: true, align: "right" },
  { key: "cliente", label: "Cliente", sortable: true },
  { key: "cbu", label: "CBU" },
  { key: "cuota_numero", label: "Cuota", sortable: true, align: "right" },
  { key: "vencimiento", label: "Vto", sortable: true, render: (i) => fecha(i.vencimiento) },
  { key: "importe", label: "Importe", sortable: true, align: "right",
    sortValue: (i) => Number(i.importe), render: (i) => money(i.importe) },
];

export default function EnviosPadronPage() {
  const [desde, setDesde] = useState("2026-01-01");
  const [hasta, setHasta] = useState("2026-12-31");
  const [envios, setEnvios] = useState(null);
  const [error, setError] = useState("");

  async function ver() {
    setError("");
    try { setEnvios(await creditos.envios(desde, hasta)); }
    catch (e) { setError(e.message); setEnvios(null); }
  }

  return (
    <>
      <PageHeader
        titulo="Envíos — cuotas a debitar por planilla"
        descripcion="Padrón de débito que se manda al organismo empleador."
      />
      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      <Card padding={false}>
        <Toolbar>
          <Field label="Desde">
            <input type="date" className="input" value={desde} onChange={(e) => setDesde(e.target.value)} />
          </Field>
          <Field label="Hasta">
            <input type="date" className="input" value={hasta} onChange={(e) => setHasta(e.target.value)} />
          </Field>
          <Boton onClick={ver}>Generar</Boton>
          <Boton variante="ok" onClick={() => creditos.descargarEnviosExcel(desde, hasta)}>Padrón Excel</Boton>
          {envios && (
            <span className="ml-auto text-sm text-gray-600">
              {num(envios.cantidad)} cuotas · total <b>{money(envios.total)}</b>
            </span>
          )}
        </Toolbar>
        <div className="p-4">
          <DataTable columns={COLS} rows={envios?.items || []} clientSort pageSize={50}
                     defaultSort="cliente" rowKey={(i, n) => `${i.credito_id}-${i.cuota_numero}-${n}`}
                     emptyText={envios ? "Sin cuotas en el período" : "Elegí el período y generá el padrón."} />
        </div>
      </Card>
    </>
  );
}
