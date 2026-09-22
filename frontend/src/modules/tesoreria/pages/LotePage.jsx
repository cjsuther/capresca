import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, RefreshCw, Send, XCircle } from "lucide-react";
import {
  actualizarLote, aprobarLote, enviarLote, excluirPago, incluirPago, mensajeDeError, rechazarLote, reintentarPago,
  resolverPago, verLote,
} from "../../../api/tesoreria";
import { Alerta, Boton, Card, Field, Kpis, Modal, PageHeader } from "../../../components/ui";
import { Confirmacion } from "../../../components/ui/Confirmacion";
import { DataTable } from "../../../components/ui/DataTable";
import { Pill } from "../../../components/ui/Pill";
import { ESTADO_LOTE, ESTADO_PAGO, ORIGENES, cbuLegible, fechaHora, money } from "../estados";

/** Pide un texto obligatorio (motivo de exclusión/rechazo, observación de lo verificado en el banco). */
function PedirTexto({ titulo, ayuda, etiqueta, confirmar, danger, opciones, onConfirmar, onCancelar, ocupado }) {
  const [texto, setTexto] = useState("");
  const [opcion, setOpcion] = useState(opciones?.[0]?.[0]);
  return (
    <Modal titulo={titulo} onClose={onCancelar} ancho="max-w-lg"
           footer={<>
             <span className="flex-1" />
             <Boton variante="secundario" onClick={onCancelar} disabled={ocupado}>Cancelar</Boton>
             <Boton variante={danger ? "danger" : "primario"} disabled={ocupado || !texto.trim()}
                    onClick={() => onConfirmar(texto.trim(), opcion)}>{ocupado ? "Procesando…" : confirmar}</Boton>
           </>}>
      <div className="space-y-3">
        {ayuda && <p className="text-sm text-gray-600">{ayuda}</p>}
        {opciones && (
          <div className="flex flex-wrap gap-3">
            {opciones.map(([v, t]) => (
              <label key={v} className="flex items-center gap-2 text-sm text-gray-700">
                <input type="radio" name="opcion" checked={opcion === v} onChange={() => setOpcion(v)} /> {t}
              </label>
            ))}
          </div>
        )}
        <Field label={etiqueta}>
          <textarea className="input w-full" rows={3} value={texto} onChange={(e) => setTexto(e.target.value)} autoFocus />
        </Field>
      </div>
    </Modal>
  );
}

export default function LotePage() {
  const { id } = useParams();
  const [lote, setLote] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [dialogo, setDialogo] = useState(null);   // {tipo, pago?}

  useEffect(() => {
    verLote(id).then(setLote).catch((e) => setError(mensajeDeError(e, "No se pudo cargar el lote")));
  }, [id]);

  const correr = async (fn, exito) => {
    setOcupado(true); setError(""); setOk("");
    try {
      const r = await fn();
      setLote(r);
      if (exito) setOk(typeof exito === "function" ? exito(r) : exito);
      setDialogo(null);
    } catch (e) {
      setError(mensajeDeError(e));
      setDialogo(null);
    } finally {
      setOcupado(false);
    }
  };

  if (!lote) {
    return error ? <Alerta>{error}</Alerta> : <p className="text-sm text-gray-400">Cargando…</p>;
  }

  const [estadoTxt, estadoTono] = ESTADO_LOTE[lote.estado] || [lote.estado, "neutral"];
  const revisable = lote.estado === "PENDIENTE_APROBACION" && lote.puede_editar;
  const enCurso = ["ENVIADO", "CON_ERRORES"].includes(lote.estado);
  const cuenta = (e) => lote.por_estado?.[e] || 0;

  const columnas = [
    { key: "beneficiario", label: "Beneficiario", sortable: true, render: (p) => (
      <div>
        <p className="font-medium text-gray-800">{p.beneficiario}</p>
        <p className="text-xs text-gray-400">{[p.documento, p.concepto].filter(Boolean).join(" · ")}</p>
      </div>
    ) },
    { key: "cbu", label: "CBU", render: (p) => <span className="tabular-nums text-xs">{cbuLegible(p.cbu)}</span> },
    { key: "monto", label: "Monto", align: "right", sortable: true, render: (p) => <span className="tabular-nums">{money(p.monto)}</span> },
    { key: "estado", label: "Estado", render: (p) => {
      const [txt, tono] = ESTADO_PAGO[p.estado] || [p.estado, "neutral"];
      return (
        <div>
          <Pill tono={tono}>{txt}</Pill>
          {p.motivo && <p className="text-xs text-gray-500 mt-1 max-w-xs">{p.motivo}</p>}
          {p.id_operacion_ib && <p className="text-xs text-gray-400 mt-0.5">Op. {p.id_operacion_ib}</p>}
        </div>
      );
    } },
    { key: "acciones", label: "", align: "right", render: (p) => (
      <div className="flex justify-end gap-1">
        {revisable && p.estado === "PENDIENTE" && (
          <button className="text-xs px-2 py-1 border rounded-lg text-gray-600 hover:bg-gray-50"
                  onClick={() => setDialogo({ tipo: "excluir", pago: p })}>Excluir</button>
        )}
        {revisable && p.estado === "EXCLUIDO" && (
          <button className="text-xs px-2 py-1 border rounded-lg text-gray-600 hover:bg-gray-50" disabled={ocupado}
                  onClick={() => correr(() => incluirPago(lote.id, p.id), `${p.beneficiario} vuelve al lote.`)}>Volver a incluir</button>
        )}
        {enCurso && lote.puede_enviar && p.estado === "FALLIDO" && (
          <button className="text-xs px-2 py-1 border rounded-lg text-blue-600 border-blue-200 hover:bg-blue-50" disabled={ocupado}
                  onClick={() => setDialogo({ tipo: "reintentar", pago: p })}>Reintentar</button>
        )}
        {lote.puede_enviar && p.estado === "INCIERTO" && (
          <button className="text-xs px-2 py-1 border rounded-lg text-red-600 border-red-200 hover:bg-red-50"
                  onClick={() => setDialogo({ tipo: "resolver", pago: p })}>Resolver</button>
        )}
      </div>
    ) },
  ];

  return (
    <div className="space-y-4">
      <Link to="/modules/tesoreria/lotes" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
        <ArrowLeft size={14} /> Lotes de pagos
      </Link>
      <PageHeader titulo={`Lote ${lote.codigo}`}
                  descripcion={`${ORIGENES[lote.origen] || lote.origen} · ${lote.descripcion || lote.referencia_origen} · recibido ${fechaHora(lote.creado_en)}${lote.creado_por ? ` por ${lote.creado_por}` : ""}`}>
        <Pill tono={estadoTono}>{estadoTxt}</Pill>
      </PageHeader>

      {(lote.envio_simulado || lote.simulado) && (
        <Alerta tipo="warn">
          {lote.simulado
            ? "Este lote se envió en modo simulación: no se movió dinero."
            : "Modo simulación activo: al enviar se registran los pagos como acreditados sin mover dinero."}
        </Alerta>
      )}
      {lote.estado === "RECHAZADO" && <Alerta>Rechazado: {lote.motivo_rechazo}</Alerta>}
      <Alerta>{error}</Alerta>
      {ok && <Alerta tipo="ok">{ok}</Alerta>}

      <Kpis items={[
        { label: "Pagos a enviar", valor: lote.cantidad },
        { label: "Total", valor: money(lote.total) },
        { label: "Acreditados", valor: cuenta("CONFIRMADO"), tono: cuenta("CONFIRMADO") ? "ok" : undefined },
        { label: "Fallidos / inciertos", valor: cuenta("FALLIDO") + cuenta("INCIERTO"),
          tono: cuenta("FALLIDO") + cuenta("INCIERTO") ? "crit" : undefined },
      ]} />

      {/* Acciones del lote */}
      {lote.estado === "PENDIENTE_APROBACION" && (
        <Card>
          <div className="flex flex-wrap items-center gap-3">
            <div className="text-sm text-gray-600 mr-auto">
              <p className="font-medium text-gray-800">
                Aprobación · nivel {Math.min(lote.nivel_actual || 1, lote.niveles)} de {lote.niveles}
              </p>
              {lote.aprobaciones.map((a) => (
                <p key={a.nivel} className="text-xs text-gray-500">Nivel {a.nivel}: aprobado por {a.aprobado_por} ({fechaHora(a.fecha)})</p>
              ))}
              {!lote.puede_aprobar && lote.motivo_no_aprueba && (
                <p className="text-xs text-gray-500">{lote.motivo_no_aprueba}</p>
              )}
            </div>
            {lote.puede_aprobar && (
              <>
                <Boton variante="secundario" onClick={() => setDialogo({ tipo: "rechazar" })} className="flex items-center gap-1">
                  <XCircle size={15} /> Rechazar lote
                </Boton>
                <Boton variante="ok" disabled={ocupado} onClick={() => setDialogo({ tipo: "aprobar" })} className="flex items-center gap-1">
                  <CheckCircle2 size={15} /> Aprobar
                </Boton>
              </>
            )}
          </div>
        </Card>
      )}
      {lote.estado === "APROBADO" && (
        <Card>
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm text-gray-600 mr-auto">
              Aprobado. {lote.puede_enviar ? `Al enviar salen ${lote.cantidad} transferencia(s) por ${money(lote.total)}.`
                                           : "Lo envía quien tenga el permiso tesoreria:lotes:enviar."}
            </p>
            {lote.puede_enviar && (
              <Boton disabled={ocupado} onClick={() => setDialogo({ tipo: "enviar" })} className="flex items-center gap-1">
                <Send size={15} /> Enviar por Interbanking
              </Boton>
            )}
          </div>
        </Card>
      )}
      {enCurso && (
        <Card>
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm text-gray-600 mr-auto">
              Enviado {fechaHora(lote.enviado_en)}{lote.enviado_por ? ` por ${lote.enviado_por}` : ""}.
              {cuenta("ENVIADO") ? ` ${cuenta("ENVIADO")} pago(s) esperando la acreditación.` : ""}
            </p>
            <Boton variante="secundario" disabled={ocupado} className="flex items-center gap-1"
                   onClick={() => correr(() => actualizarLote(lote.id), (r) => (r.cambios ? `${r.cambios} pago(s) cambiaron de estado.` : "Sin novedades del banco."))}>
              <RefreshCw size={15} /> Consultar estado en el banco
            </Boton>
          </div>
        </Card>
      )}

      <Card padding={false}>
        <DataTable columns={columnas} rows={lote.pagos} rowKey={(p) => p.id} clientSort pageSize={50}
                   emptyText="El lote no tiene pagos" />
      </Card>

      <Card>
        <h2 className="text-sm font-semibold text-gray-700 mb-2">Historial</h2>
        <ol className="space-y-1.5">
          {lote.eventos.map((e, i) => (
            <li key={i} className="text-sm text-gray-600 flex flex-wrap gap-x-2">
              <span className="text-xs text-gray-400 tabular-nums w-32 shrink-0">{fechaHora(e.fecha)}</span>
              <span className="font-medium text-gray-700">{e.accion.replaceAll("_", " ").toLowerCase()}</span>
              {e.usuario && <span className="text-gray-400">· {e.usuario}</span>}
              {e.detalle && <span className="basis-full sm:basis-auto">{e.detalle}</span>}
            </li>
          ))}
        </ol>
      </Card>

      {dialogo?.tipo === "excluir" && (
        <PedirTexto titulo={`Excluir el pago a ${dialogo.pago.beneficiario}`} etiqueta="Motivo" confirmar="Excluir"
                    ayuda="El pago no se envía y se avisa al módulo de origen. Si el lote ya tenía aprobaciones, vuelven a empezar."
                    ocupado={ocupado} onCancelar={() => setDialogo(null)}
                    onConfirmar={(motivo) => correr(() => excluirPago(lote.id, dialogo.pago.id, motivo), "Pago excluido.")} />
      )}
      {dialogo?.tipo === "rechazar" && (
        <PedirTexto titulo={`Rechazar el lote ${lote.codigo}`} etiqueta="Motivo" confirmar="Rechazar lote" danger
                    ayuda="No se envía ningún pago y el módulo de origen recibe el rechazo."
                    ocupado={ocupado} onCancelar={() => setDialogo(null)}
                    onConfirmar={(motivo) => correr(() => rechazarLote(lote.id, motivo), "Lote rechazado.")} />
      )}
      {dialogo?.tipo === "resolver" && (
        <PedirTexto titulo={`Resolver el pago a ${dialogo.pago.beneficiario}`} etiqueta="Qué verificaste en el banco"
                    confirmar="Registrar" opciones={[["CONFIRMADO", "Se acreditó"], ["FALLIDO", "No salió"]]}
                    ayuda="Se cortó la comunicación al enviarlo y no se sabe si salió. Verificalo en Interbanking o en el extracto antes de registrarlo: nunca se reenvía solo."
                    ocupado={ocupado} onCancelar={() => setDialogo(null)}
                    onConfirmar={(obs, resultado) => correr(() => resolverPago(lote.id, dialogo.pago.id, resultado, obs), "Pago resuelto.")} />
      )}
      {dialogo?.tipo === "aprobar" && (
        <Confirmacion titulo={`Aprobar el lote ${lote.codigo}`} confirmar="Aprobar" danger={false} ocupado={ocupado}
                      mensaje={`${lote.cantidad} pago(s) por ${money(lote.total)}.`}
                      onConfirmar={() => correr(() => aprobarLote(lote.id), (r) => (r.estado === "APROBADO" ? "Lote aprobado: listo para enviar." : "Nivel aprobado: falta el siguiente."))}
                      onCancelar={() => setDialogo(null)} />
      )}
      {dialogo?.tipo === "enviar" && (
        <Confirmacion titulo="Enviar por Interbanking" confirmar="Enviar" ocupado={ocupado}
                      mensaje={`Salen ${lote.cantidad} transferencia(s) por ${money(lote.total)} desde la cuenta de pagos.${lote.envio_simulado ? "\n(Modo simulación: no se mueve dinero.)" : "\nEsta acción mueve dinero y no se puede deshacer."}`}
                      onConfirmar={() => correr(() => enviarLote(lote.id), "Lote enviado.")} onCancelar={() => setDialogo(null)} />
      )}
      {dialogo?.tipo === "reintentar" && (
        <Confirmacion titulo={`Reintentar el pago a ${dialogo.pago.beneficiario}`} confirmar="Reintentar" ocupado={ocupado}
                      mensaje={`Se vuelve a enviar ${money(dialogo.pago.monto)} a ${cbuLegible(dialogo.pago.cbu)}.\nMotivo del fallo: ${dialogo.pago.motivo || "—"}`}
                      onConfirmar={() => correr(() => reintentarPago(lote.id, dialogo.pago.id), "Pago reenviado.")}
                      onCancelar={() => setDialogo(null)} />
      )}
    </div>
  );
}
