import { useState } from "react";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Field, Alerta, Kpis } from "../../components/ui";
import { BuscadorCliente, nombreCliente } from "../../components/BuscadorCliente";
import { money, fecha, num } from "../../components/format";

const ESTADO = { A: "Activo", C: "Cancelado" };

const COLS = [
  { key: "id", label: "Crédito", sortable: true },
  { key: "linea", label: "Línea", sortable: true },
  { key: "capital", label: "Capital", sortable: true, align: "right",
    sortValue: (c) => Number(c.capital), render: (c) => money(c.capital) },
  { key: "saldo_capital", label: "Saldo", sortable: true, align: "right",
    sortValue: (c) => Number(c.saldo_capital), render: (c) => money(c.saldo_capital) },
  { key: "cuotas_pendientes", label: "Cuotas pend.", sortable: true, align: "right" },
  { key: "proxima_cuota_vto", label: "Próx. vto", sortable: true, render: (c) => fecha(c.proxima_cuota_vto) },
  { key: "estado", label: "Estado", sortable: true, render: (c) => ESTADO[c.estado] || c.estado },
];

export default function SituacionClientePage() {
  const [cliente, setCliente] = useState(null);
  const [sit, setSit] = useState(null);
  const [error, setError] = useState("");

  // El cliente se elige en el PADRÓN (módulo Clientes); Créditos consulta su situación por ese id.
  async function elegir(c) {
    setCliente(c); setSit(null); setError("");
    if (!c) return;
    try { setSit(await creditos.situacionCliente(c.id)); }
    catch (e) { setError(e.message); }
  }

  return (
    <>
      <PageHeader
        titulo="Situación del cliente"
        descripcion="Créditos, saldo y margen disponible de una persona del padrón."
      />

      <Card className="mb-4">
        <Field label="Cliente">
          <BuscadorCliente seleccionado={cliente} onSelect={elegir} autoFocus />
        </Field>
      </Card>

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      {sit && (
        <>
          <div className="mb-4">
            <Kpis items={[
              { label: "Créditos activos", valor: num(sit.creditos_activos) },
              { label: "Saldo total", valor: money(sit.saldo_total) },
              { label: "Sueldo", valor: money(sit.sueldo) },
              ...(sit.margen_disponible != null
                ? [{ label: "Margen disponible", valor: money(sit.margen_disponible), tono: "ok" }]
                : []),
            ]} />
          </div>
          <Card padding={false}>
            <p className="px-4 py-3 text-sm text-gray-500 border-b border-gray-200">
              <b className="text-gray-800">{sit.apellido_nombre || nombreCliente(cliente)}</b>
              {sit.cuil ? ` · CUIL ${sit.cuil}` : ""}
            </p>
            <div className="p-4">
              <DataTable columns={COLS} rows={sit.creditos} rowKey={(c) => c.id}
                         clientSort defaultSort="id" emptyText="El cliente no tiene créditos" />
            </div>
          </Card>
        </>
      )}
    </>
  );
}
