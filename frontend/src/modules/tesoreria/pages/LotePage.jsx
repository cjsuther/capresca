import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, CheckCircle2, Download, FileText, RefreshCw, RotateCcw, Send, XCircle } from "lucide-react";
import {
  actualizarLote, aprobarLote, archivoAltaCuentas, cuentasOrigen, enviarLote, excluirPago, incluirPago, mensajeDeError, rechazarLote,
  reintentarFallidos, reintentarPago, resolverPago, verLote,
} from "../../../api/tesoreria";
import { Alerta, Boton, Card, Field, Kpis, Modal, PageHeader } from "../../../components/ui";
import { Confirmacion } from "../../../components/ui/Confirmacion";
import { DataTable } from "../../../components/ui/DataTable";
import { Pill } from "../../../components/ui/Pill";
import { ESTADO_LOTE, ESTADO_PAGO, ORIGENES, cbuLegible, cuentaLegible, fechaHora, money } from "../estados";
import { descargarReporte, reporteEnvio } from "../reporteEnvio";

/** Resultado del envío: qué salió, qué no y qué cuentas hay que habilitar en Interbanking. */
function ReporteEnvio({ lote, puedeReintentar, ocupado, onReintentar, onAltaCuentas }) {
  const r = reporteEnvio(lote);
  const [operador, setOperador] = useState("");
  const faltaHabilitar = r.cuentasAHabilitar.length > 0 || r.origenSinHabilitar;
  // El nombre del operador de API sale de la credencial de Interbanking; sólo hace falta si hay algo que habilitar.
  useEffect(() => {
    if (!faltaHabilitar) return;
    cuentasOrigen().then((c) => setOperador(c?.operador || "")).catch(() => {});
  }, [faltaHabilitar]);
  const quien = operador ? <>al operador <b>{operador}</b></> : "al operador de API";

  return (
    <Card>
      <div className="flex flex-wrap items-start gap-3">
        <div className="mr-auto">
          <h2 className="text-sm font-semibold text-gray-700">Reporte de envío</h2>
          <p className="text-sm text-gray-600">
            {r.realizadas.length} realizada(s) por {money(r.totalRealizadas)} · {" "}
            <span className={r.noRealizadas.length ? "text-red-600 font-medium" : ""}>
              {r.noRealizadas.length} no realizada(s) por {money(r.totalNoRealizadas)}
            </span>
          </p>
        </div>
        <Boton variante="secundario" className="flex items-center gap-1" onClick={() => descargarReporte(lote, operador)}>
          <Download size={15} /> Descargar reporte
        </Boton>
        {puedeReintentar && r.fallidos > 0 && (
          <Boton variante="secundario" disabled={ocupado} className="flex items-center gap-1"
                 onClick={() => onAltaCuentas(true)}>
            <FileText size={15} /> Alta de cuentas de los fallidos
          </Boton>
        )}
        {puedeReintentar && r.fallidos > 0 && (
          <Boton disabled={ocupado} className="flex items-center gap-1" onClick={onReintentar}>
            <RotateCcw size={15} /> Reintentar fallidos ({r.fallidos})
          </Boton>
        )}
      </div>
      {r.cuentasAHabilitar.length > 0 && (
        <div className="mt-3 rounded-lg border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-900">
          <p>
            Interbanking rechazó {r.cuentasAHabilitar.length === 1 ? "una cuenta destino que no está habilitada"
              : `${r.cuentasAHabilitar.length} cuentas destino que no están habilitadas`}. Un administrador de
            Interbanking tiene que darlas de alta como cuentas de terceros (con el archivo de "Alta de cuentas de los
            fallidos") y habilitárselas {quien} (Administración → Colaboradores → Habilitaciones de Cuentas). Después,
            reintentá los fallidos.
          </p>
          <ul className="mt-2 space-y-0.5">
            {r.cuentasAHabilitar.map((c) => (
              <li key={c.cbu} className="tabular-nums">
                {cbuLegible(c.cbu)} · {c.beneficiario}{c.documento ? ` (${c.documento})` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}
      {r.origenSinHabilitar && (
        <p className="mt-2 text-sm text-red-600">
          La cuenta de origen tampoco está habilitada: hay que habilitársela {quien} en Interbanking.
        </p>
      )}
    </Card>
  );
}

function descargarTxt(nombre, contenido) {
  const url = URL.createObjectURL(new Blob([contenido], { type: "text/plain" }));
  const a = document.createElement("a");
  a.href = url; a.download = nombre;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

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
  const [cuentas, setCuentas] = useState(null);   // {items, error} | null mientras carga
  const [cuentaElegida, setCuentaElegida] = useState("");   // cuenta de origen elegida para enviar
  const [omitidas, setOmitidas] = useState([]);   // cuentas que quedaron fuera del archivo de alta

  useEffect(() => {
    verLote(id).then(setLote).catch((e) => setError(mensajeDeError(e, "No se pudo cargar el lote")));
  }, [id]);

  // Cuentas desde las que se puede pagar: se piden cuando el lote está listo para enviarse.
  useEffect(() => {
    if (!lote || lote.estado !== "APROBADO" || !lote.puede_enviar || cuentas) return;
    cuentasOrigen()
      .then((r) => {
        setCuentas(r);
        setCuentaElegida((c) => c || (r.items.find((x) => x.predeterminada) || r.items[0])?.account_number || "");
      })
      .catch((e) => setCuentas({ items: [], error: mensajeDeError(e, "No se pudieron consultar las cuentas") }));
  }, [lote, cuentas]);

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

  // Interbanking no da de alta cuentas por API: se baja el TXT y se sube a mano en su portal.
  const altaCuentas = async (soloFallidos) => {
    setOcupado(true); setError(""); setOk(""); setOmitidas([]);
    try {
      const r = await archivoAltaCuentas(lote.id, soloFallidos);
      descargarTxt(r.nombre, r.contenido);
      setOk(`Se descargó ${r.nombre} con ${r.cuentas} cuenta(s). Subilo en Interbanking: Administración → Cuenta → `
        + "Alta y Modificación desde Archivo (diseño \"Carga de cuentas para todo tipo de transferencias\"); "
        + "otro administrador lo autoriza en Administración → Cuenta → Autorizaciones masivas.");
      setOmitidas(r.omitidas || []);
      setLote(await verLote(lote.id));
    } catch (e) {
      setError(mensajeDeError(e, "No se pudo generar el archivo de alta de cuentas"));
    } finally {
      setOcupado(false);
    }
  };

  if (!lote) {
    return error ? <Alerta>{error}</Alerta> : <p className="text-sm text-gray-400">Cargando…</p>;
  }

  const [estadoTxt, estadoTono] = ESTADO_LOTE[lote.estado] || [lote.estado, "neutral"];
  // Los pagos de una orden de pago no se excluyen: la liquidación es completa (se anula la orden).
  const revisable = lote.estado === "PENDIENTE_APROBACION" && lote.puede_editar && !lote.orden_pago;
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
          {p.enviado_por && <p className="text-xs text-gray-400 mt-0.5">Enviado por {p.enviado_por}</p>}
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
      {lote.orden_pago && (
        <Alerta tipo="warn">
          Es el lote de la orden de pago{" "}
          <Link to={`/modules/tesoreria/ordenes/${lote.orden_pago.id}`} className="underline font-medium">{lote.orden_pago.codigo}</Link>.
          Se paga completo: sus pagos no se excluyen; si algo no corresponde, se anula la orden.
        </Alerta>
      )}
      {lote.estado === "RECHAZADO" && <Alerta>Rechazado: {lote.motivo_rechazo}</Alerta>}
      <Alerta>{error}</Alerta>
      {ok && <Alerta tipo="ok">{ok}</Alerta>}
      {omitidas.length > 0 && (
        <Alerta tipo="warn">
          Quedaron fuera del archivo {omitidas.length} cuenta(s) sin CUIT/CUIL válido; cargalas a mano en Interbanking
          o corregí el documento en el origen:
          <ul className="mt-1">
            {omitidas.map((o) => (
              <li key={o.cbu} className="tabular-nums">{cbuLegible(o.cbu)} · {o.beneficiario}{o.documento ? ` (${o.documento})` : ""}</li>
            ))}
          </ul>
        </Alerta>
      )}

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
          <div className="flex flex-wrap items-end gap-3">
            <p className="text-sm text-gray-600 mr-auto">
              Aprobado. {lote.puede_enviar ? `Al enviar salen ${lote.cantidad} transferencia(s) por ${money(lote.total)}.`
                                           : "Lo envía quien tenga el permiso tesoreria:lotes:enviar."}
            </p>
            {lote.puede_enviar && (
              <>
                <Boton variante="secundario" disabled={ocupado} className="flex items-center gap-1"
                       onClick={() => altaCuentas(false)}>
                  <FileText size={15} /> Archivo de alta de cuentas
                </Boton>
                <Field label="Cuenta desde la que se paga">
                  <select className="input min-w-[18rem]" value={cuentaElegida} disabled={!cuentas}
                          onChange={(e) => setCuentaElegida(e.target.value)}>
                    {!cuentas && <option value="">Cargando cuentas…</option>}
                    {cuentas?.items.length === 0 && <option value="">Sin cuentas disponibles</option>}
                    {cuentas?.items.map((c) => (
                      <option key={c.account_number} value={c.account_number}>
                        {cuentaLegible(c)}{c.predeterminada ? " (predeterminada)" : ""}
                      </option>
                    ))}
                  </select>
                </Field>
                <Boton disabled={ocupado || !cuentas || !cuentaElegida} onClick={() => setDialogo({ tipo: "enviar" })}
                       className="flex items-center gap-1">
                  <Send size={15} /> Enviar por Interbanking
                </Boton>
              </>
            )}
          </div>
          {cuentas?.items.length === 0 && (
            <p className="text-sm text-red-600 mt-2">
              No hay ninguna cuenta para pagar: cargá la cuenta de pagos en Interbanking → Configuración.
              Sin cuenta de origen el lote no se envía.
            </p>
          )}
          {cuentas?.error && <p className="text-xs text-yellow-700 mt-2">{cuentas.error}</p>}
        </Card>
      )}
      {enCurso && (
        <Card>
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm text-gray-600 mr-auto">
              Enviado {fechaHora(lote.enviado_en)}{lote.enviado_por ? ` por ${lote.enviado_por}` : ""}
              {lote.cuenta_origen ? ` desde ${cuentaLegible(lote.cuenta_origen)}` : ""}.
              {cuenta("ENVIADO") ? ` ${cuenta("ENVIADO")} pago(s) esperando la acreditación.` : ""}
            </p>
            <Boton variante="secundario" disabled={ocupado} className="flex items-center gap-1"
                   onClick={() => correr(() => actualizarLote(lote.id), (r) => (r.cambios ? `${r.cambios} pago(s) cambiaron de estado.` : "Sin novedades del banco."))}>
              <RefreshCw size={15} /> Consultar estado en el banco
            </Boton>
          </div>
        </Card>
      )}

      {(enCurso || lote.estado === "CONFIRMADO") && (
        <ReporteEnvio lote={lote} puedeReintentar={enCurso && lote.puede_enviar} ocupado={ocupado}
                      onReintentar={() => setDialogo({ tipo: "reintentarFallidos" })} onAltaCuentas={altaCuentas} />
      )}

      {lote.cuenta_origen && !enCurso && lote.estado !== "APROBADO" && (
        <p className="text-sm text-gray-500">Pagado desde {cuentaLegible(lote.cuenta_origen)}</p>
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
                      mensaje={`Salen ${lote.cantidad} transferencia(s) por ${money(lote.total)} desde la cuenta ${
                        cuentaLegible(cuentas?.items.find((c) => c.account_number === cuentaElegida)) }.${
                        lote.envio_simulado ? "\n(Modo simulación: no se mueve dinero.)" : "\nEsta acción mueve dinero y no se puede deshacer."}`}
                      onConfirmar={() => correr(() => enviarLote(lote.id, cuentaElegida), "Lote enviado.")} onCancelar={() => setDialogo(null)} />
      )}
      {dialogo?.tipo === "reintentarFallidos" && (
        <Confirmacion titulo="Reintentar los pagos fallidos" confirmar="Reintentar" ocupado={ocupado}
                      mensaje={`Se vuelven a enviar los ${reporteEnvio(lote).fallidos} pago(s) fallido(s) del lote. Si rechazó cuentas sin habilitar, confirmá antes que ya estén habilitadas en Interbanking.`}
                      onConfirmar={() => correr(() => reintentarFallidos(lote.id), (r) =>
                        `${r.reenviados} pago(s) reenviado(s)${r.salteados ? `; ${r.salteados} salteado(s) porque ya se cargaron en otro lote` : ""}.`)}
                      onCancelar={() => setDialogo(null)} />
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
