import { useEffect, useState } from "react";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Boton, Alerta, Modal, Field } from "../../components/ui";
import { Pill } from "../../components/Pill";
import { Confirmacion } from "../../components/Confirmacion";
import { usePuedeEscribir } from "../../permisos";
import { money, fecha, num } from "../../components/format";
import { textoResolucion } from "./SolicitudesCreditoPage";

/**
 * Lotes (H-135): las solicitudes aprobadas y liquidables entran solas al lote de su tipo de crédito y
 * fecha de aprobación (numerado por año, con el tope del parámetro LOTE_LIQUIDACION_MAX). Alguien lo
 * verifica (puede pasar solicitudes a otro lote abierto) y lo cierra; Despacho le asigna a cada lote
 * cerrado la resolución que lo otorga. Con el desembolso por Tesorería, la liquidación la hace
 * Tesorería: una orden de pago toma la resolución con sus lotes (quedan PARA_LIQUIDAR, se originan sus
 * solicitudes) y, acreditadas las transferencias, el lote queda LIQUIDADO. Sin Tesorería, el lote con
 * resolución se liquida desde acá, completo. Con el desembolso por Tesorería (H-216) la transferencia va en un
 * lote de Tesorería y el crédito se activa cuando se acredita.
 *
 * Las solicitudes de un lote cerrado o con resolución no se modifican: lo único que se puede hacer es
 * pasarlas a otro lote abierto del mismo tipo de crédito y fecha, o a uno nuevo.
 */
const ESTADO = {
  ABIERTO: ["Abierto", "warn"],
  CERRADO: ["Cerrado", "neutral"],
  CON_RESOLUCION: ["Con resolución", "brand"],
  PARA_LIQUIDAR: ["Para liquidar", "brand"],
  LIQUIDADO: ["Liquidado", "ok"],
};

const COLS_LOTES = [
  { key: "codigo", label: "Lote", sortable: true, sortValue: (l) => l.anio * 100000 + l.numero,
    render: (l) => <b className="tabular-nums">{l.codigo}</b> },
  { key: "producto", label: "Tipo de crédito", sortable: true },
  { key: "fecha", label: "Fecha", sortable: true, render: (l) => fecha(l.fecha) },
  { key: "cantidad", label: "Solicitudes", align: "right", sortable: true,
    render: (l) => <span className="tabular-nums" title={`Hasta ${num(l.maximo)} por lote`}>{num(l.cantidad)}</span> },
  { key: "montoTotal", label: "Monto", align: "right", sortable: true,
    render: (l) => <span title={l.topeMonto ? `Tope del tipo de crédito: ${money(l.topeMonto)}` : "Sin tope de monto"}>{money(l.montoTotal)}</span> },
  { key: "resolucion", label: "Resolución", render: (l) => (
    <div>
      {l.resolucion ? textoResolucion(l.resolucion) : <span className="text-gray-400">—</span>}
      {l.ordenPago && <p className="text-xs text-gray-500">Orden de pago {l.ordenPago.codigo}</p>}
    </div>
  ) },
  { key: "estado", label: "Estado", sortable: true, render: (l) => {
    const [texto, tono] = ESTADO[l.estado] || [l.estado, "neutral"];
    return (
      <div className="flex flex-wrap gap-1">
        <Pill tono={tono}>{texto}</Pill>
        {!!l.pendientes && <Pill tono="crit">{l.pendientes} esperando aprobación</Pill>}
        {!!l.enTesoreria && <Pill tono="brand">{l.enTesoreria} en Tesorería</Pill>}
        {!!l.observados && <Pill tono="crit">{l.observados} observado(s)</Pill>}
      </div>
    );
  } },
];

function EstadoItem({ c }) {
  const d = c.desembolso || {};
  if (c.pendienteAprobacion) return <Pill tono="crit">Esperando aprobación</Pill>;
  if (d.estado === "EN_TESORERIA") return <span title="Se activa cuando se acredite la transferencia"><Pill tono="brand">En Tesorería · {d.lote}{d.op ? ` · OP ${d.op}` : ""}</Pill></span>;
  if (d.estado === "OBSERVADO") return <span title={d.motivo}><Pill tono="crit">Observado: {d.motivo}</Pill></span>;
  if (c.estadoContrato === "ACTIVO") return <Pill tono="ok">Liquidado</Pill>;
  if (c.estadoContrato === "A_LIQUIDAR") return <Pill tono="warn">Originado · a liquidar</Pill>;
  return <Pill tono="neutral">Aprobada</Pill>;
}

const COLS_FUERA = [
  { key: "numero", label: "N° solicitud", render: (s) => <b>{s.numero}</b> },
  { key: "cliente", label: "Cliente" },
  { key: "producto", label: "Tipo de crédito" },
  { key: "monto", label: "Monto", align: "right", render: (s) => money(s.monto) },
  { key: "faltantes", label: "Le falta", render: (s) => <span className="text-red-600">{s.faltantes.join(", ")}</span> },
];

const fechaHora = (v) => (v ? new Date(v).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" }) : "");

export default function LiquidacionLotePage() {
  const puedeEscribir = usePuedeEscribir();
  const [lotes, setLotes] = useState([]);
  const [fuera, setFuera] = useState([]);
  const [maximo, setMaximo] = useState(50);
  const [viaTesoreria, setViaTesoreria] = useState(false);
  const [verLiquidados, setVerLiquidados] = useState(false);
  const [sel, setSel] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [cargando, setCargando] = useState(true);
  const [confirmando, setConfirmando] = useState(false);
  const [liquidando, setLiquidando] = useState(false);
  const [cerrando, setCerrando] = useState(false);       // confirmación de cierre abierta
  const [cambiando, setCambiando] = useState(false);     // cerrando / reabriendo
  const [moviendo, setMoviendo] = useState(null);     // { item, destino }
  const [detErr, setDetErr] = useState("");
  const [topes, setTopes] = useState(null);           // [{ productoId, producto, topeMonto }] mientras se editan
  const [topesErr, setTopesErr] = useState("");

  async function abrirTopes() {
    setTopesErr("");
    try { setTopes((await creditos.ctoTopesLote()).items.map((x) => ({ ...x, topeMonto: x.topeMonto ?? "" }))); }
    catch (e) { setError(e.message); }
  }

  async function guardarTopes() {
    setTopesErr("");
    try {
      await creditos.ctoGuardarTopesLote(topes.map((x) => ({
        producto_id: x.productoId, tope_monto: x.topeMonto === "" ? null : Number(x.topeMonto) })));
      setTopes(null);
      setOk("Topes de monto guardados. Rigen para las solicitudes que entren desde ahora.");
      await cargar();
    } catch (e) { setTopesErr(e.message); }
  }

  async function cargar() {
    setError(""); setCargando(true);
    try {
      const d = await creditos.ctoLotesLiquidacion(verLiquidados);
      setLotes(d.items);
      setFuera(d.fueraDeLote || []);
      setViaTesoreria(!!d.viaTesoreria);
      if (d.maximo) setMaximo(d.maximo);
      setSel((prev) => (prev ? d.items.find((l) => l.id === prev.id) || null : null));
    } catch (e) { setError(e.message); }
    finally { setCargando(false); }
  }
  useEffect(() => { cargar(); }, [verLiquidados]); // eslint-disable-line

  async function liquidar() {
    setError(""); setOk(""); setLiquidando(true);
    try {
      const r = await creditos.ctoLiquidarLote(sel.id);
      const partes = [];
      if (r.desembolsados.length || !r.enTesoreria?.length) partes.push(`Desembolsados: ${r.desembolsados.length}`);
      if (r.enTesoreria?.length) partes.push(`Enviados a Tesorería: ${r.enTesoreria.length} (lote ${r.loteTesoreria}${r.ordenPago ? `, OP N° ${r.ordenPago}` : ""}); se activan al acreditarse`);
      if (r.yaEnTesoreria?.length) partes.push(`Ya estaban en Tesorería: ${r.yaEnTesoreria.length}`);
      if (r.pendientesAprobacion.length) partes.push(`Pendientes de aprobación: ${r.pendientesAprobacion.length}`);
      if (r.errores.length) partes.push(`Con error: ${r.errores.length}`);
      setOk(`Lote ${sel.codigo} (${sel.producto}, ${fecha(sel.fecha)}) procesado. ${partes.join(" · ")}`);
      setConfirmando(false);
      setSel(null);
      await cargar();
    } catch (e) { setError(e.message); setConfirmando(false); }
    finally { setLiquidando(false); }
  }

  async function cambiarEstado(accion) {
    setDetErr(""); setOk(""); setCambiando(true);
    try {
      const d = accion === "cerrar" ? await creditos.ctoCerrarLote(sel.id) : await creditos.ctoReabrirLote(sel.id);
      setCerrando(false);
      setOk(accion === "cerrar"
        ? `Lote ${d.codigo} cerrado: Despacho ya le puede asignar la resolución.`
        : `Lote ${d.codigo} reabierto.`);
      await cargar();
    } catch (e) { setDetErr(e.message); setCerrando(false); }
    finally { setCambiando(false); }
  }

  // Lotes a los que se puede pasar un ítem: abiertos, del mismo tipo de crédito y fecha.
  const destinos = sel ? lotes.filter((l) => l.id !== sel.id && l.productoId === sel.productoId
                                            && l.fecha === sel.fecha && l.estado === "ABIERTO") : [];

  async function mover() {
    setDetErr("");
    const { item, destino } = moviendo;
    try {
      const d = await creditos.ctoMoverDeLote({
        ...(item.tipo === "solicitud" ? { solicitud_id: item.solicitudId } : { contrato_id: item.contratoId }),
        ...(destino === "nuevo" ? { nuevo: true } : { destino_id: Number(destino) }),
      });
      setMoviendo(null);
      setOk(`${item.solicitud || item.numero} pasó al lote ${d.codigo}.`);
      await cargar();
    } catch (e) { setDetErr(e.message); }
  }

  const liquidable = sel?.estado === "CON_RESOLUCION";
  const colsItems = [
    { key: "solicitud", label: "N° solicitud", render: (c) => <b>{c.solicitud || "—"}</b> },
    { key: "numero", label: "N° contrato", render: (c) => c.numero || <span className="text-gray-400">—</span> },
    { key: "cliente", label: "Cliente" },
    { key: "plazo", label: "Plazo", align: "right" },
    { key: "monto", label: "Monto", align: "right", render: (c) => money(c.monto) },
    { key: "estado", label: "Estado", render: (c) => <EstadoItem c={c} /> },
  ];
  const acciones = (c) => [{
    label: "Mover a otro lote…",
    oculta: !puedeEscribir || sel?.estado === "LIQUIDADO" || c.estadoContrato === "ACTIVO",
    onClick: () => { setDetErr(""); setMoviendo({ item: c, destino: destinos[0]?.id ? String(destinos[0].id) : "nuevo" }); },
  }];

  return (
    <>
      <PageHeader
        titulo="Lotes"
        descripcion={`Las solicitudes aprobadas que se pueden liquidar entran solas a un lote abierto por tipo de crédito y fecha (hasta ${num(maximo)} por lote y el tope de monto del tipo de crédito, lo que se alcance primero). Después de verificarlo se cierra, Despacho le asigna la resolución y recién ahí se liquida completo${viaTesoreria ? ": las transferencias van a Tesorería y cada crédito pasa a ACTIVO cuando se acredita" : ""}.`}
      >
        {puedeEscribir && <Boton variante="secundario" onClick={abrirTopes}>Topes de monto</Boton>}
        <label className="flex items-center gap-2 text-sm text-gray-600">
          <input type="checkbox" checked={verLiquidados} onChange={(e) => setVerLiquidados(e.target.checked)} />
          Ver liquidados
        </label>
      </PageHeader>

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}
      {ok && <div className="mb-4"><Alerta tipo="ok">{ok}</Alerta></div>}

      <Card padding={false}>
        <p className="px-4 py-3 text-sm text-gray-500 border-b border-gray-200">
          {cargando ? "Cargando…" : lotes.length
            ? `${num(lotes.length)} lote(s) · clickeá uno para ver sus solicitudes`
            : "No hay lotes pendientes."}
        </p>
        <div className="p-4">
          <DataTable columns={COLS_LOTES} rows={lotes} rowKey={(l) => l.id}
                     clientSort defaultSort="codigo" onRowClick={(l) => { setDetErr(""); setSel(l); }}
                     emptyText="No hay lotes pendientes." />
        </div>
      </Card>

      {fuera.length > 0 && (
        <Card padding={false} className="mt-4">
          <p className="px-4 py-3 text-sm text-gray-700 border-b border-gray-200">
            <b>Aprobadas fuera de lote ({num(fuera.length)})</b>
            <span className="text-gray-500"> · todavía no se pueden liquidar; entran solas a su lote cuando se completan.</span>
          </p>
          <div className="p-4">
            <DataTable columns={COLS_FUERA} rows={fuera} rowKey={(s) => s.id} emptyText="" />
          </div>
        </Card>
      )}

      {sel && (
        <Modal
          eyebrow={`Lote ${sel.codigo} · ${sel.producto} · ${fecha(sel.fecha)}`}
          titulo={`${num(sel.cantidad)} solicitud(es) · ${money(sel.montoTotal)}`}
          onClose={() => setSel(null)}
          ancho="max-w-4xl"
          footer={
            <>
              <Boton variante="secundario" onClick={() => setSel(null)}>Cerrar</Boton>
              <span className="flex-1" />
              {puedeEscribir && sel.estado === "ABIERTO" && (
                <Boton disabled={cambiando || !sel.cantidad} onClick={() => setCerrando(true)}>
                  Cerrar lote
                </Boton>
              )}
              {puedeEscribir && sel.estado === "CERRADO" && (
                <Boton variante="secundario" disabled={cambiando} onClick={() => cambiarEstado("reabrir")}>
                  {cambiando ? "Reabriendo…" : "Reabrir lote"}
                </Boton>
              )}
              {puedeEscribir && !viaTesoreria && ["CERRADO", "CON_RESOLUCION"].includes(sel.estado) && (
                <Boton disabled={liquidando || !liquidable || !sel.cantidad}
                       title={liquidable ? "" : "Despacho tiene que asignarle la resolución al lote cerrado antes de liquidarlo."}
                       onClick={() => setConfirmando(true)}>
                  {liquidando ? "Liquidando…" : `Liquidar lote (${num(sel.cantidad)})`}
                </Boton>
              )}
            </>
          }
        >
          {detErr && <div className="mb-3"><Alerta>{detErr}</Alerta></div>}
          <p className="flex flex-wrap items-center gap-2 mb-3">
            <Pill tono={(ESTADO[sel.estado] || [])[1] || "neutral"}>{(ESTADO[sel.estado] || [sel.estado])[0]}</Pill>
            {sel.resolucion
              ? <Pill tono="ok">{textoResolucion(sel.resolucion)}</Pill>
              : sel.estado === "CERRADO"
                ? <span className="text-sm text-gray-500">Sin resolución: se la asigna Despacho → Lotes de créditos.</span>
                : <span className="text-sm text-gray-500">Se puede verificar: pasá a otro lote abierto lo que no corresponda y cerralo.</span>}
            {sel.cerradoPor && (
              <span className="text-sm text-gray-500">Cerrado por <b>{sel.cerradoPor}</b> el {fechaHora(sel.cerradoEn)}</span>
            )}
          </p>
          {sel.estado === "CON_RESOLUCION" && viaTesoreria && (
            <p className="text-sm text-gray-500 mb-3">
              Lo liquida Tesorería: entra en una orden de pago con su resolución (Tesorería → Órdenes de pago).
            </p>
          )}
          {sel.estado === "PARA_LIQUIDAR" && (
            <div className="mb-3">
              <Alerta tipo="warn">
                Está en la orden de pago {sel.ordenPago?.codigo} de Tesorería: sus créditos ya se originaron y quedan
                liquidados cuando se acrediten las transferencias. No se modifica mientras la orden no se anule.
              </Alerta>
            </div>
          )}
          {["CERRADO", "CON_RESOLUCION"].includes(sel.estado) && (
            <div className="mb-3">
              <Alerta tipo="warn">
                Con el lote {sel.estado === "CERRADO" ? "cerrado" : "con resolución"}, sus solicitudes no se
                modifican: sólo se pueden pasar a otro lote abierto del mismo tipo de crédito y fecha, o a uno nuevo.
              </Alerta>
            </div>
          )}
          {!!sel.pendientes && (
            <div className="mb-3">
              <Alerta tipo="warn">
                {num(sel.pendientes)} crédito(s) de este lote ya están esperando la aprobación del desembolso.
                Se desembolsan cuando se aprueban en el Inbox de aprobaciones; volver a liquidar no los duplica.
              </Alerta>
            </div>
          )}
          <DataTable columns={colsItems} rows={sel.contratos} rowKey={(c) => c.id}
                     acciones={acciones} clientSort defaultSort="solicitud" emptyText="El lote no tiene solicitudes" />
        </Modal>
      )}

      {moviendo && (
        <Modal eyebrow={`Lote ${sel?.codigo}`} titulo={`Mover ${moviendo.item.solicitud || moviendo.item.numero}`}
               onClose={() => setMoviendo(null)}
               footer={<>
                 <span className="flex-1" />
                 <Boton variante="secundario" onClick={() => setMoviendo(null)}>Cancelar</Boton>
                 <Boton onClick={mover}>Mover</Boton>
               </>}>
          {detErr && <div className="mb-3"><Alerta>{detErr}</Alerta></div>}
          <p className="text-sm text-gray-500 mb-3">
            Sólo a un lote abierto del mismo tipo de crédito ({sel?.producto}) y fecha ({fecha(sel?.fecha)}), o a uno nuevo.
          </p>
          <Field label="Lote de destino">
            <select className="input w-full" value={moviendo.destino} aria-label="Lote de destino"
                    onChange={(e) => setMoviendo((m) => ({ ...m, destino: e.target.value }))}>
              {destinos.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.codigo} · {num(l.cantidad)} solicitud(es) · {(ESTADO[l.estado] || [l.estado])[0]}
                </option>
              ))}
              <option value="nuevo">Lote nuevo</option>
            </select>
          </Field>
        </Modal>
      )}

      {topes && (
        <Modal titulo="Tope de monto por tipo de crédito" onClose={() => setTopes(null)}
               footer={<>
                 <span className="flex-1" />
                 <Boton variante="secundario" onClick={() => setTopes(null)}>Cancelar</Boton>
                 <Boton onClick={guardarTopes}>Guardar</Boton>
               </>}>
          {topesErr && <div className="mb-3"><Alerta>{topesErr}</Alerta></div>}
          <p className="text-sm text-gray-500 mb-3">
            Un lote se completa al llegar a {num(maximo)} solicitudes o a este monto, lo que pase primero: la
            siguiente solicitud va a un lote nuevo. Vacío = sin tope de monto. Rige para lo que entre desde ahora.
          </p>
          <div className="space-y-2">
            {topes.map((x, i) => (
              <label key={x.productoId} className="flex items-center gap-3 text-sm">
                <span className="flex-1">{x.producto}</span>
                <input type="number" min="0" step="0.01" className="input w-44 text-right" aria-label={`Tope de ${x.producto}`}
                       value={x.topeMonto} placeholder="Sin tope"
                       onChange={(e) => setTopes((ts) => ts.map((t, j) => (j === i ? { ...t, topeMonto: e.target.value } : t)))} />
              </label>
            ))}
          </div>
        </Modal>
      )}

      {cerrando && (
        <Confirmacion
          titulo="Cerrar el lote"
          mensaje={`Se cierra el lote ${sel?.codigo}: ${num(sel?.cantidad)} solicitud(es) de ${sel?.producto} por ${money(sel?.montoTotal)}.\nNo recibe más solicitudes y Despacho ya le puede asignar la resolución. Queda registrado que lo cerraste vos.`}
          confirmar="Cerrar lote"
          danger={false}
          ocupado={cambiando}
          onConfirmar={() => cambiarEstado("cerrar")}
          onCancelar={() => setCerrando(false)}
        />
      )}

      {confirmando && (
        <Confirmacion
          titulo="Liquidar el lote"
          mensaje={`Se liquida el lote ${sel?.codigo} completo: ${num(sel?.cantidad)} solicitud(es) de ${sel?.producto} por ${money(sel?.montoTotal)}.\nSe originan los contratos y ${viaTesoreria
            ? "las transferencias se mandan a Tesorería; cada crédito pasa a ACTIVO cuando se acredita"
            : "se desembolsan"}. Si el workflow lo exige, quedan esperando aprobación.`}
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
