import { useState } from "react";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Toolbar, Field, Boton, Alerta, Kpis } from "../../components/ui";
import { Confirmacion } from "../../components/Confirmacion";
import { usePuedeEscribir } from "../../permisos";
import { money, hoy } from "../../components/format";

const COLS = [
  { key: "cuota", label: "Cuota" },
  { key: "vencida", label: "Estado", render: (i) => (i.vencida ? "Vencida" : "Futura (s/ int.)") },
  { key: "capital", label: "Capital", align: "right", render: (i) => money(i.capital) },
  { key: "interes", label: "Interés", align: "right", render: (i) => money(i.interes) },
  { key: "iva", label: "IVA", align: "right", render: (i) => money(i.iva) },
  { key: "punitorio", label: "Punit.", align: "right", render: (i) => money(i.punitorio) },
  { key: "subtotal", label: "Subtotal", align: "right", render: (i) => <b>{money(i.subtotal)}</b> },
];

/**
 * Cancelación anticipada: salda todas las cuotas —las vencidas con su mora, las futuras sólo
 * capital (se condona el interés no devengado)— y emite el recibo.
 */
export default function CancelacionCreditoPage() {
  const puedeEscribir = usePuedeEscribir();
  const [creditoId, setCreditoId] = useState("");
  const [fecha, setFecha] = useState(hoy());
  const [det, setDet] = useState(null);
  const [recibo, setRecibo] = useState(null);
  const [error, setError] = useState("");
  const [confirmando, setConfirmando] = useState(false);
  const [ocupado, setOcupado] = useState(false);

  async function simular(e) {
    e?.preventDefault();
    setError(""); setRecibo(null); setDet(null);
    const id = Number(creditoId);
    if (!id) { setError("Ingresá un número de crédito."); return; }
    try { setDet(await creditos.simularCancelacion(id, fecha)); }
    catch (err) { setError(err.message); }
  }

  async function cancelar() {
    setError(""); setOcupado(true);
    try {
      setRecibo(await creditos.cancelarCredito(Number(creditoId), { fecha_pago: fecha, via_pago: "EFECTIVO" }));
      setDet(null);
    } catch (err) { setError(err.message); }
    finally { setOcupado(false); setConfirmando(false); }
  }

  return (
    <>
      <PageHeader
        titulo="Cancelación anticipada de crédito"
        descripcion="Salda todas las cuotas: las vencidas con su mora y las futuras sólo capital, condonando el interés no devengado."
      />

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      <Card padding={false} className="mb-4">
        <Toolbar>
          <form onSubmit={simular} className="flex items-end gap-2">
            <Field label="N° de crédito">
              <input className="input w-40" value={creditoId} onChange={(e) => setCreditoId(e.target.value)} />
            </Field>
            <Field label="Fecha">
              <input type="date" className="input" value={fecha} onChange={(e) => setFecha(e.target.value)} />
            </Field>
            <Boton type="submit">Calcular cancelación</Boton>
          </form>
        </Toolbar>
      </Card>

      {det && (
        <>
          <div className="mb-4">
            <Kpis items={[
              { label: "Total a cancelar", valor: money(det.total), tono: "ok" },
              { label: "Capital", valor: money(det.capital) },
              { label: "Interés", valor: money(det.interes) },
              { label: "Punitorio", valor: money(det.punitorio), tono: "crit" },
            ]} />
          </div>
          <Card padding={false}>
            <div className="p-4">
              <DataTable columns={COLS} rows={det.items} rowKey={(i) => i.cuota}
                         emptyText="El crédito no tiene cuotas pendientes" />
            </div>
            {puedeEscribir && (
              <div className="px-4 pb-4">
                <Boton variante="danger" onClick={() => setConfirmando(true)}>
                  Confirmar cancelación y emitir recibo
                </Boton>
              </div>
            )}
          </Card>
        </>
      )}

      {recibo && (
        <Card>
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="font-semibold text-gray-800">
                Crédito cancelado — Recibo N° {recibo.numero}
              </h2>
              <p className="text-sm text-gray-500 mt-0.5">{recibo.cliente_nombre}</p>
              <p className="text-lg font-semibold text-gray-800 mt-2">Total: {money(recibo.total)}</p>
            </div>
            <Boton variante="secundario" onClick={() => creditos.verReciboPdf(recibo.id)}>Ver recibo PDF</Boton>
          </div>
        </Card>
      )}

      {confirmando && (
        <Confirmacion
          titulo="Cancelar el crédito"
          mensaje={`Se va a saldar el crédito ${creditoId} por ${money(det?.total)} y emitir el recibo. La operación mueve dinero y no se deshace.`}
          confirmar="Cancelar y emitir recibo"
          ocupado={ocupado}
          onConfirmar={cancelar}
          onCancelar={() => setConfirmando(false)}
        />
      )}
    </>
  );
}
