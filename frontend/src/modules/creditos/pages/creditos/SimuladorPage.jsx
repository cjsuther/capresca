import { useEffect, useState } from "react";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Field, Boton, Alerta, Kpis } from "../../components/ui";
import { money, fecha, hoy, num } from "../../components/format";

const COLS = [
  { key: "numero", label: "#" },
  { key: "vencimiento", label: "Vencimiento", render: (c) => fecha(c.vencimiento) },
  { key: "saldo_capital", label: "Saldo", align: "right", render: (c) => money(c.saldo_capital) },
  { key: "amortizacion", label: "Capital", align: "right", render: (c) => money(c.amortizacion) },
  { key: "interes", label: "Interés", align: "right", render: (c) => money(c.interes) },
  { key: "iva_interes", label: "IVA int.", align: "right", render: (c) => money(c.iva_interes) },
  { key: "seguro", label: "Seguro", align: "right", render: (c) => money(c.seguro) },
  { key: "gastos_adm", label: "Gastos", align: "right", render: (c) => money(c.gastos_adm) },
  { key: "total", label: "Total", align: "right", render: (c) => <b>{money(c.total)}</b> },
];

export default function SimuladorPage() {
  const [lineas, setLineas] = useState([]);
  const [form, setForm] = useState({
    linea_id: 0, capital: "500000", plazo: 12, fecha_primer_vencimiento: hoy(),
    cuota_fija: "", sueldo: "650000", total_afectado: "0",
  });
  const [res, setRes] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    creditos.lineas().then((l) => {
      setLineas(l);
      if (l.length) setForm((f) => ({ ...f, linea_id: l[0].id }));
    }).catch((e) => setError(e.message));
  }, []);

  const lineaSel = lineas.find((l) => l.id === Number(form.linea_id));
  const esCuotaFija = lineaSel?.tipo_calculo === 5;   // el plazo lo calcula el motor

  async function simular(e) {
    e.preventDefault();
    setError(""); setRes(null);
    const payload = {
      linea_id: Number(form.linea_id),
      capital: form.capital,
      plazo: Number(form.plazo),
      fecha_primer_vencimiento: form.fecha_primer_vencimiento,
      sueldo: form.sueldo || null,
      total_afectado: form.total_afectado || "0",
      ...(esCuotaFija ? { cuota_fija: form.cuota_fija } : {}),
    };
    try { setRes(await creditos.simular(payload)); }
    catch (err) { setError(err.message); }
  }

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <>
      <PageHeader
        titulo="Simulador de crédito"
        descripcion="Plan de cuotas con el motor de cálculo del sistema, y margen disponible sobre el haber declarado."
      />

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      <Card className="mb-4">
        <form onSubmit={simular} className="grid gap-3 sm:grid-cols-3">
          <Field label="Línea de crédito">
            <select className="input w-full" value={form.linea_id} onChange={set("linea_id")}>
              {lineas.map((l) => <option key={l.id} value={l.id}>{l.nombre} (TNA {l.tna}%)</option>)}
            </select>
          </Field>
          <Field label="Capital">
            <input className="input w-full" value={form.capital} onChange={set("capital")} />
          </Field>
          <Field label={esCuotaFija ? "Plazo (lo calcula el motor)" : "Plazo (cuotas)"}>
            <input type="number" className="input w-full" value={form.plazo} onChange={set("plazo")} disabled={esCuotaFija} />
          </Field>
          <Field label="1er vencimiento">
            <input type="date" className="input w-full" value={form.fecha_primer_vencimiento}
                   onChange={set("fecha_primer_vencimiento")} />
          </Field>
          {esCuotaFija && (
            <Field label="Cuota fija">
              <input className="input w-full" value={form.cuota_fija} onChange={set("cuota_fija")} />
            </Field>
          )}
          <Field label="Sueldo (para margen)">
            <input className="input w-full" value={form.sueldo} onChange={set("sueldo")} />
          </Field>
          <Field label="Ya afectado">
            <input className="input w-full" value={form.total_afectado} onChange={set("total_afectado")} />
          </Field>
          <div className="sm:col-span-3">
            <Boton type="submit">Calcular plan de cuotas</Boton>
          </div>
        </form>
      </Card>

      {res && (
        <>
          <div className="mb-4">
            <Kpis items={[
              { label: "Cuotas", valor: num(res.cantidad_cuotas) },
              { label: "Total a pagar", valor: money(res.total_a_pagar) },
              { label: "Cuota promedio", valor: money(res.cuota_promedio) },
              ...(res.margen_disponible != null
                ? [{ label: "Margen disponible", valor: money(res.margen_disponible),
                     tono: res.puede_tomar_credito ? "ok" : "crit" }]
                : []),
            ]} />
          </div>

          {res.margen_disponible != null && (
            <div className="mb-4">
              <Alerta tipo={res.puede_tomar_credito ? "ok" : "warn"}>
                {res.puede_tomar_credito
                  ? "Con el haber declarado, el cliente PUEDE tomar el crédito."
                  : "Con el haber declarado, el cliente NO puede tomar el crédito."}
              </Alerta>
            </div>
          )}

          {res.advertencias?.map((a, i) => (
            <div className="mb-4" key={i}><Alerta tipo="warn">{a}</Alerta></div>
          ))}

          <Card padding={false}>
            <p className="px-4 py-3 text-sm text-gray-500 border-b border-gray-200">Plan de cuotas</p>
            <div className="p-4">
              <DataTable columns={COLS} rows={res.cuotas} rowKey={(c) => c.numero}
                         pageSize={24} emptyText="El plan no tiene cuotas" />
            </div>
          </Card>
        </>
      )}
    </>
  );
}
