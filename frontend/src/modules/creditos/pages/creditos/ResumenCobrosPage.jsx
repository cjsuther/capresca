import { useEffect, useState } from "react";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Toolbar, Field, Boton, LimpiarFiltros, Kpis, Alerta } from "../../components/ui";
import { money, num } from "../../components/format";

const COLS = [
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

export default function ResumenCobrosPage() {
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  // Los filtros viajan por argumento y no desde el estado: si se leyeran del estado, "Limpiar
  // filtros" pediría los datos con los valores del render anterior (H-206).
  async function ver(d = desde, h = hasta) {
    setError("");
    try { setData(await creditos.resumenCobros({ desde: d || undefined, hasta: h || undefined })); }
    catch (e) { setError(e.message); }
  }
  useEffect(() => { ver(); }, []); // eslint-disable-line

  const t = data?.total;

  return (
    <>
      <PageHeader
        titulo="Resumen de cobros de créditos"
        descripcion="Cobranza de cuotas por período mensual. La mora es residual (total cobrado − conceptos)."
      />

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      {t && (
        <div className="mb-4">
          <Kpis items={[
            { label: "Cuotas cobradas", valor: num(t.cuotas) },
            { label: "Capital", valor: money(t.capital) },
            { label: "Interés", valor: money(t.interes) },
            { label: "Mora", valor: money(t.mora), tono: "crit" },
            { label: "Total cobrado", valor: money(t.total), tono: "ok" },
          ]} />
        </div>
      )}

      <Card padding={false}>
        <Toolbar>
          <Field label="Desde">
            <input type="date" className="input" value={desde} onChange={(e) => setDesde(e.target.value)} />
          </Field>
          <Field label="Hasta">
            <input type="date" className="input" value={hasta} onChange={(e) => setHasta(e.target.value)} />
          </Field>
          <Boton onClick={() => ver()}>Ver</Boton>
          <LimpiarFiltros activo={!!desde || !!hasta}
                          onClear={() => { setDesde(""); setHasta(""); ver("", ""); }} />
        </Toolbar>
        <div className="p-4">
          <DataTable columns={COLS} rows={data?.items || []} clientSort pageSize={24}
                     defaultSort="periodo" rowKey={(r) => r.periodo}
                     emptyText="Sin cobros en el período." />
        </div>
      </Card>
    </>
  );
}
