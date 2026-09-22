import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Toolbar, Field, Boton, Alerta } from "../../components/ui";
import { money, fecha, num } from "../../components/format";

const TIPO = { D: "Débito", C: "Crédito", O: "Otorgamiento", P: "Pago", A: "Ajuste" };

// Los importes NO son ordenables: la columna Saldo es un saldo corrido (cronológico).
const COLS = [
  { key: "fecha", label: "Fecha", render: (m) => fecha(m.fecha) },
  { key: "cuota", label: "Cuota", align: "right", render: (m) => m.cuota || "—" },
  { key: "tipo", label: "Tipo", render: (m) => TIPO[m.tipo] || m.tipo || "—" },
  { key: "no_recibo", label: "Recibo", render: (m) => m.no_recibo || "—" },
  { key: "debitos", label: "Débitos", align: "right", render: (m) => money(m.debitos) },
  { key: "creditos", label: "Créditos", align: "right", render: (m) => money(m.creditos) },
  { key: "capital", label: "Capital", align: "right", render: (m) => money(m.capital) },
  { key: "interes", label: "Interés", align: "right", render: (m) => money(m.interes) },
  { key: "iva", label: "IVA", align: "right", render: (m) => money(m.iva) },
  { key: "punitorio", label: "Punit.", align: "right", render: (m) => money(m.punitorio) },
  { key: "saldo", label: "Saldo", align: "right", render: (m) => <b>{money(m.saldo)}</b> },
];

export default function CuentaCorrientePage() {
  const [params] = useSearchParams();
  const [creditoId, setCreditoId] = useState(params.get("credito") || "");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  async function buscar(e, valor) {
    e?.preventDefault();
    setError("");
    const id = Number(valor ?? creditoId);
    if (!id) { setError("Ingresá un número de crédito."); setData(null); return; }
    try { setData(await creditos.cuentaCorriente(id)); }
    catch (err) { setError(err.message); setData(null); }
  }

  useEffect(() => {
    const p = params.get("credito");
    if (p) buscar(undefined, p);
  }, []); // eslint-disable-line

  return (
    <>
      <PageHeader
        titulo="Cuenta corriente del crédito"
        descripcion="Movimientos (débitos y créditos) de un crédito, con saldo corrido."
      />

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      <Card padding={false}>
        <Toolbar>
          <form onSubmit={buscar} className="flex items-end gap-2">
            <Field label="N° de crédito">
              <input className="input w-40" value={creditoId} onChange={(e) => setCreditoId(e.target.value)} />
            </Field>
            <Boton type="submit">Ver cuenta corriente</Boton>
          </form>
          {data && (
            <span className="ml-auto text-sm text-gray-500">
              {num(data.cantidad)} movimientos · saldo final <b>{money(data.saldo_final)}</b>
            </span>
          )}
        </Toolbar>
        <div className="p-4">
          <DataTable columns={COLS} rows={data?.movimientos || []} pageSize={50}
                     rowKey={(m, i) => i}
                     emptyText={data ? "El crédito no tiene movimientos en cuenta corriente."
                                     : "Buscá un crédito para ver sus movimientos."} />
        </div>
      </Card>
    </>
  );
}
