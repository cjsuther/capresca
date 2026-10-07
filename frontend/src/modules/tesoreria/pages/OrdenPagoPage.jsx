import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Send, XCircle } from "lucide-react";
import { anularOrden, mensajeDeError, verOrden } from "../../../api/tesoreria";
import { Alerta, Boton, Card, Field, Kpis, Modal, PageHeader } from "../../../components/ui";
import { DataTable } from "../../../components/ui/DataTable";
import { Pill } from "../../../components/ui/Pill";
import { ESTADO_ORDEN, ESTADO_PAGO, cbuLegible, fechaHora, money, textoActo } from "../estados";

const COLUMNAS = [
  { key: "beneficiario", label: "Beneficiario", sortable: true, render: (p) => (
    <div>
      <p className="font-medium text-gray-800">{p.beneficiario}</p>
      <p className="text-xs text-gray-400">{[p.documento, p.concepto].filter(Boolean).join(" · ")}</p>
    </div>
  ) },
  { key: "cbu", label: "CBU", render: (p) => <span className="tabular-nums text-xs">{cbuLegible(p.cbu)}</span> },
  { key: "monto", label: "Monto", align: "right", sortable: true, render: (p) => <span className="tabular-nums">{money(p.monto)}</span> },
  { key: "estado", label: "Transferencia", render: (p) => {
    const [txt, tono] = ESTADO_PAGO[p.estado] || [p.estado, "neutral"];
    return (
      <div>
        <Pill tono={tono}>{txt}</Pill>
        {p.motivo && <p className="text-xs text-gray-500 mt-1 max-w-xs">{p.motivo}</p>}
      </div>
    );
  } },
];

/** Una orden de pago: sus resoluciones / disposiciones y lotes, y cómo va cada transferencia. */
export default function OrdenPagoPage() {
  const { id } = useParams();
  const [op, setOp] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [anulando, setAnulando] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    verOrden(id).then(setOp).catch((e) => setError(mensajeDeError(e, "No se pudo cargar la orden de pago")));
  }, [id]);

  const anular = async () => {
    setOcupado(true); setError(""); setOk("");
    try {
      setOp(await anularOrden(op.id, motivo.trim()));
      setOk("Orden de pago anulada: sus lotes de créditos vuelven a estar disponibles.");
      setAnulando(false);
    } catch (e) {
      setError(mensajeDeError(e, "No se pudo anular la orden de pago"));
      setAnulando(false);
    } finally {
      setOcupado(false);
    }
  };

  if (!op) return error ? <Alerta>{error}</Alerta> : <p className="text-sm text-gray-400">Cargando…</p>;

  const [txt, tono] = ESTADO_ORDEN[op.estado_pago] || [op.estado_pago, "neutral"];
  const acreditados = op.pagos.filter((p) => p.estado === "CONFIRMADO").length;
  const conProblema = op.pagos.filter((p) => ["FALLIDO", "INCIERTO"].includes(p.estado)).length;

  return (
    <div className="space-y-4">
      <Link to="/modules/tesoreria/ordenes" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
        <ArrowLeft size={14} /> Órdenes de pago
      </Link>
      <PageHeader titulo={`Orden de pago ${op.codigo}`}
                  descripcion={`${op.actos_texto} · confeccionada ${fechaHora(op.creado_en)} por ${op.creado_por}`}>
        <Pill tono={tono}>{txt}</Pill>
      </PageHeader>

      {op.estado === "ANULADA" && (
        <Alerta>Anulada por {op.anulada_por} el {fechaHora(op.anulada_en)}: {op.motivo_anulacion}</Alerta>
      )}
      <Alerta>{error}</Alerta>
      {ok && <Alerta tipo="ok">{ok}</Alerta>}

      <Kpis items={[
        { label: "Transferencias", valor: op.cantidad },
        { label: "Importe", valor: money(op.importe) },
        { label: "Acreditadas", valor: acreditados, tono: acreditados ? "ok" : undefined },
        { label: "Fallidas / inciertas", valor: conProblema, tono: conProblema ? "crit" : undefined },
      ]} />

      {op.estado !== "ANULADA" && op.lote && (
        <Card>
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm text-gray-600 mr-auto">
              Las transferencias van en el lote de pagos <b>{op.lote.codigo}</b>: ahí se aprueba según el workflow
              de Tesorería y el tesorero las envía por Interbanking. Acreditadas, los lotes de créditos quedan liquidados.
            </p>
            {op.puede_anular && (
              <Boton variante="secundario" onClick={() => { setMotivo(""); setAnulando(true); }} className="flex items-center gap-1">
                <XCircle size={15} /> Anular orden
              </Boton>
            )}
            <Link to={`/modules/tesoreria/lotes/${op.lote.id}`}
                  className="inline-flex items-center gap-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
              <Send size={15} /> {["PARA_APROBAR", "PARA_PAGAR"].includes(op.estado_pago) ? "Aprobar y pagar" : "Ver lote de pagos"}
            </Link>
          </div>
        </Card>
      )}

      <Card>
        <p className="font-medium text-gray-800 mb-2">Resoluciones y disposiciones</p>
        <ul className="space-y-2 text-sm">
          {op.actos.map((g) => (
            <li key={g.acto.clave}>
              <b>{textoActo(g.acto)}</b>
              <span className="text-gray-500"> · {g.lotes.length} lote(s) · {g.cantidad} crédito(s) · {money(g.total)}</span>
              <p className="text-gray-600 tabular-nums">
                {g.lotes.map((l) => `Lote ${l.codigo} (${l.producto}, ${l.cantidad})`).join(" · ")}
              </p>
            </li>
          ))}
        </ul>
      </Card>

      <Card padding={false}>
        <DataTable columns={COLUMNAS} rows={op.pagos} rowKey={(p) => p.id} pageSize={50} emptyText="Sin transferencias" />
      </Card>

      {anulando && (
        <Modal titulo={`Anular la orden ${op.codigo}`} onClose={() => setAnulando(false)} ancho="max-w-lg"
               footer={<>
                 <span className="flex-1" />
                 <Boton variante="secundario" onClick={() => setAnulando(false)} disabled={ocupado}>Cancelar</Boton>
                 <Boton variante="danger" disabled={ocupado || !motivo.trim()} onClick={anular}>
                   {ocupado ? "Anulando…" : "Anular orden"}
                 </Boton>
               </>}>
          <p className="text-sm text-gray-600 mb-3">
            No se hace ninguna transferencia. Los lotes de créditos vuelven a quedar con su resolución, disponibles para
            otra orden de pago.
          </p>
          <Field label="Motivo">
            <textarea className="input w-full" rows={3} value={motivo} aria-label="Motivo"
                      onChange={(e) => setMotivo(e.target.value)} autoFocus />
          </Field>
        </Modal>
      )}
    </div>
  );
}
