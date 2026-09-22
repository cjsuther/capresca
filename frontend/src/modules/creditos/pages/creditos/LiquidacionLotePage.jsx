import { useEffect, useState } from "react";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Boton, Alerta, Modal } from "../../components/ui";
import { Pill } from "../../components/Pill";
import { Confirmacion } from "../../components/Confirmacion";
import { usePuedeEscribir } from "../../permisos";
import { money, fecha, num } from "../../components/format";

/**
 * Liquidación de préstamos por lote (H-135): los contratos originados quedan A_LIQUIDAR y se
 * liquidan agrupados por DÍA de originación. Al liquidar, cada crédito pasa a desembolso (si el
 * workflow lo exige, queda esperando aprobación).
 */
const COLS_LOTES = [
  { key: "fecha", label: "Día de originación", sortable: true, render: (l) => <b>{fecha(l.fecha)}</b> },
  { key: "cantidad", label: "Créditos", align: "right", sortable: true },
  { key: "montoTotal", label: "Monto a liquidar", align: "right", sortable: true, render: (l) => money(l.montoTotal) },
  { key: "estado", label: "Estado", render: (l) => (l.pendientes
    ? <Pill tono="crit">{l.pendientes} esperando aprobación</Pill>
    : <Pill tono="warn">A liquidar</Pill>) },
];

const COLS_CONTRATOS = [
  { key: "numero", label: "N° contrato", render: (c) => <b>{c.numero}</b> },
  { key: "cliente", label: "Cliente" },
  { key: "producto", label: "Producto" },
  { key: "plazo", label: "Plazo", align: "right" },
  { key: "monto", label: "Monto", align: "right", render: (c) => money(c.monto) },
  { key: "estado", label: "Estado", render: (c) => (c.pendienteAprobacion
    ? <Pill tono="crit">Esperando aprobación</Pill>
    : <Pill tono="warn">A liquidar</Pill>) },
];

export default function LiquidacionLotePage() {
  const puedeEscribir = usePuedeEscribir();
  const [lotes, setLotes] = useState([]);
  const [sel, setSel] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [cargando, setCargando] = useState(true);
  const [confirmando, setConfirmando] = useState(false);
  const [liquidando, setLiquidando] = useState(false);

  async function cargar() {
    setError(""); setCargando(true);
    try {
      const d = await creditos.ctoLotesLiquidacion();
      setLotes(d.items);
      setSel((prev) => (prev ? d.items.find((l) => l.fecha === prev.fecha) || null : null));
    } catch (e) { setError(e.message); }
    finally { setCargando(false); }
  }
  useEffect(() => { cargar(); }, []);

  async function liquidar() {
    setError(""); setOk(""); setLiquidando(true);
    try {
      const r = await creditos.ctoLiquidarLote(sel.fecha);
      const partes = [`Desembolsados: ${r.desembolsados.length}`];
      if (r.pendientesAprobacion.length) partes.push(`Pendientes de aprobación: ${r.pendientesAprobacion.length}`);
      if (r.errores.length) partes.push(`Con error: ${r.errores.length}`);
      setOk(`Lote del ${fecha(sel.fecha)} procesado. ${partes.join(" · ")}`);
      setConfirmando(false);
      setSel(null);
      await cargar();
    } catch (e) { setError(e.message); setConfirmando(false); }
    finally { setLiquidando(false); }
  }

  return (
    <>
      <PageHeader
        titulo="Liquidación por lote"
        descripcion="Créditos originados pendientes de liquidar, agrupados por día. Al liquidar el lote pasan a desembolso."
      />

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}
      {ok && <div className="mb-4"><Alerta tipo="ok">{ok}</Alerta></div>}

      <Card padding={false}>
        <p className="px-4 py-3 text-sm text-gray-500 border-b border-gray-200">
          {cargando ? "Cargando…" : lotes.length
            ? `${num(lotes.length)} lote(s) pendientes · clickeá uno para ver sus créditos`
            : "No hay créditos pendientes de liquidar."}
        </p>
        <div className="p-4">
          <DataTable columns={COLS_LOTES} rows={lotes} rowKey={(l) => l.fecha}
                     clientSort defaultSort="fecha" onRowClick={setSel}
                     emptyText="No hay créditos pendientes de liquidar." />
        </div>
      </Card>

      {sel && (
        <Modal
          eyebrow={`Lote del ${fecha(sel.fecha)}`}
          titulo={`${num(sel.cantidad)} crédito(s) · ${money(sel.montoTotal)}`}
          onClose={() => setSel(null)}
          footer={
            <>
              <Boton variante="secundario" onClick={() => setSel(null)}>Cerrar</Boton>
              <span className="flex-1" />
              {puedeEscribir && (
                <Boton disabled={liquidando || !sel.cantidad} onClick={() => setConfirmando(true)}>
                  {liquidando ? "Liquidando…" : `Liquidar lote (${num(sel.cantidad)}) → desembolso`}
                </Boton>
              )}
            </>
          }
        >
          {!!sel.pendientes && (
            <div className="mb-3">
              <Alerta tipo="warn">
                {num(sel.pendientes)} crédito(s) de este lote ya están esperando la aprobación del desembolso.
                Se desembolsan cuando se aprueban en el Inbox de aprobaciones; volver a liquidar no los duplica.
              </Alerta>
            </div>
          )}
          <DataTable columns={COLS_CONTRATOS} rows={sel.contratos} rowKey={(c) => c.id}
                     clientSort defaultSort="numero" emptyText="El lote no tiene créditos" />
        </Modal>
      )}

      {confirmando && (
        <Confirmacion
          titulo="Liquidar el lote"
          mensaje={`Se liquidan ${num(sel?.cantidad)} crédito(s) del ${fecha(sel?.fecha)} por ${money(sel?.montoTotal)}.\nCada uno pasa a desembolso; si el workflow lo exige, queda esperando aprobación.`}
          confirmar="Liquidar"
          danger={false}
          ocupado={liquidando}
          onConfirmar={liquidar}
          onCancelar={() => setConfirmando(false)}
        />
      )}
    </>
  );
}
