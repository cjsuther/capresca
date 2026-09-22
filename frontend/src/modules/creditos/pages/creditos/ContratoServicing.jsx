import { useState } from "react";
import { creditos } from "../../../../api/creditos";
import { Boton, Field, Alerta, Modal } from "../../components/ui";
import { Pill } from "../../components/Pill";
import { Confirmacion } from "../../components/Confirmacion";
import { PedirNumero } from "../../components/PedirNumero";
import { money, fecha, hoy } from "../../components/format";

const TONO_ESTADO = {
  ACTIVO: "ok", A_LIQUIDAR: "warn", EN_MORA: "warn", REFINANCIADO: "brand",
  ANULADO: "crit", CASTIGADO: "crit", CERRADO: "neutral", CANCELADO: "neutral",
};

const NO_REVERSABLES = ["DISBURSEMENT", "REVERSAL", "RENEGOTIATION"];

/**
 * Servicing de un contrato: acciones sobre el préstamo (pagos, prepago, diferimiento,
 * refinanciación, cancelación total), plan de cuotas, actividades y asientos.
 * Las acciones que mueven dinero o cierran el contrato se confirman.
 */
export function ContratoServicing({ c, onChange, onReload, soloLectura }) {
  const [fechaValor, setFechaValor] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [pedido, setPedido] = useState(null);          // "parcial" | "prepago" | "diferir"
  const [modoPrepago, setModoPrepago] = useState("BAJA_CUOTA");
  const [confirmando, setConfirmando] = useState(null); // { titulo, mensaje, onSi }
  const [refi, setRefi] = useState(null);

  const activo = c.estado === "ACTIVO";
  // Si el endpoint no devolviera el contrato (204/cuerpo vacío), igual se recarga: propagar un
  // undefined a onChange rompía el render de la pantalla entera.
  const aplicar = (nc) => { if (nc?.id) onChange(nc); onReload(); };

  async function actividad(tipo, importe = 0, modo) {
    setError(""); setOk("");
    try { aplicar(await creditos.ctoActividad(c.id, tipo, importe, "", fechaValor || undefined, modo)); }
    catch (e) { setError(e.message); }
  }

  async function devengar() {
    setError("");
    try { aplicar(await creditos.ctoDevengar(c.id)); } catch (e) { setError(e.message); }
  }
  async function desembolsar() {
    setError("");
    try { aplicar(await creditos.ctoDesembolsar(c.id)); } catch (e) { setError(e.message); }
  }
  async function reversar(a) {
    setError("");
    try { aplicar(await creditos.ctoReversar(c.id, a.id)); } catch (e) { setError(e.message); }
    setConfirmando(null);
  }

  function abrirRefi() {
    const pendientes = (c.cuotas || []).filter((q) => q.estado === "PENDIENTE").length || c.plazo;
    setRefi({ tasa: Number(c.tasa) || 0, plazo: pendientes, sim: null, cargando: false });
  }
  async function simularRefi() {
    setRefi((r) => ({ ...r, cargando: true }));
    try {
      const snap = c.snapshot || {};
      const sim = await creditos.ppPreview({
        sistema: c.sistema, monto: Number(c.saldo_capital), plazo: refi.plazo, tna: refi.tasa,
        cargoOtorg: 0, frecuencia: snap.frecuencia || "MENSUAL", impuestos: snap.impuestos || [],
      });
      setRefi((r) => ({ ...r, sim, cargando: false }));
    } catch (e) { setError(e.message); setRefi((r) => ({ ...r, cargando: false })); }
  }
  async function confirmarRefi() {
    setError("");
    try {
      const r = await creditos.ctoRefinanciar(c.id, refi.tasa, refi.plazo);
      setRefi(null); setConfirmando(null);
      onChange(r.anterior); onReload(c.id);
      setOk(`Refinanciado. Nuevo contrato ${r.nuevo.numero_contrato} (aparece en la lista).`);
    } catch (e) { setError(e.message); setConfirmando(null); }
  }

  return (
    <div className="bg-gray-50 border-t border-gray-200">
      <div className="flex flex-wrap items-center gap-2 px-4 py-3 border-b border-gray-200">
        <b className="text-gray-800">{c.numero_contrato} — {c.cliente_nombre}</b>
        <Pill tono={TONO_ESTADO[c.estado] || "neutral"}>{c.estado}</Pill>
        {c.solicitud_origen && <Pill>Solicitud N° {c.solicitud_origen}</Pill>}
        <span className="flex-1" />
        <span className="text-xs text-gray-500">
          Snapshot: {c.snapshot?.producto} v{c.snapshot?.version} · {c.sistema} · {c.snapshot?.tna}%
        </span>
        <Boton variante="secundario" onClick={() => creditos.ctoPdf(c.id, c.numero_contrato).catch((e) => setError(e.message))}>
          PDF
        </Boton>
      </div>

      {error && <div className="px-4 pt-3"><Alerta>{error}</Alerta></div>}
      {ok && <div className="px-4 pt-3"><Alerta tipo="ok">{ok}</Alerta></div>}

      <div className="flex flex-wrap items-end gap-3 px-4 py-3 border-b border-gray-200">
        <div>
          <p className="text-xs text-gray-500">Saldo capital</p>
          <p className="font-semibold text-gray-800 tabular-nums">{money(c.saldo_capital)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Cuotas pagadas</p>
          <p className="font-semibold text-gray-800 tabular-nums">
            {c.cuotas.filter((q) => q.estado === "PAGADA").length} / {c.cuotas.length}
          </p>
        </div>
        {c.datos_adicionales?.destino && (
          <div>
            <p className="text-xs text-gray-500">Destino</p>
            <p className="font-medium text-gray-800 text-sm">{c.datos_adicionales.destino}</p>
          </div>
        )}
        <span className="flex-1" />

        {soloLectura ? (
          <Pill>Sólo lectura</Pill>
        ) : c.estado === "A_LIQUIDAR" ? (
          <Boton onClick={desembolsar}>Desembolsar (neto {money(c.liquidacion?.neto || 0)})</Boton>
        ) : (
          <>
            <Field label="Fecha valor (backdating)">
              <input type="date" className="input" value={fechaValor} max={hoy()} min={c.fecha_valor}
                     onChange={(e) => setFechaValor(e.target.value)} />
            </Field>
            {c.snapshot?.indice && (
              <Boton variante="secundario" disabled={!activo} onClick={() => actividad("REPRICING")}>
                Repricing ({c.snapshot.indice})
              </Boton>
            )}
            <Boton variante="secundario" disabled={!activo} onClick={devengar}>Devengar interés</Boton>
            <Boton variante="secundario" disabled={!activo} onClick={() => actividad("PAYMENT")}>Pagar próxima cuota</Boton>
            <Boton variante="secundario" disabled={!activo} onClick={() => setPedido("parcial")}>Pago parcial</Boton>
            <Boton variante="secundario" disabled={!activo} onClick={() => setPedido("prepago")}>Prepago capital</Boton>
            <Boton variante="secundario" disabled={!activo} onClick={() => setPedido("diferir")}>Diferir cuotas</Boton>
            <Boton variante="secundario" disabled={!activo} onClick={abrirRefi}>Refinanciar…</Boton>
            <Boton variante="danger" disabled={!activo} onClick={() => setConfirmando({
              titulo: "Cancelación total (payoff)",
              mensaje: "Salda el capital remanente y cierra el contrato. No se deshace.",
              confirmar: "Cancelar contrato",
              onSi: () => { actividad("PAYOFF"); setConfirmando(null); },
            })}>Cancelación total</Boton>
          </>
        )}
      </div>

      <div className="grid lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-gray-200">
        <div className="max-h-80 overflow-auto p-3">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wide text-gray-500">
                <th className="px-2 py-1 text-left">#</th><th className="px-2 py-1 text-left">Vto</th>
                <th className="px-2 py-1 text-right">Capital</th><th className="px-2 py-1 text-right">Interés</th>
                <th className="px-2 py-1 text-right">Cuota</th><th className="px-2 py-1 text-right">Saldo</th>
                <th className="px-2 py-1 text-left">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {c.cuotas.map((q) => (
                <tr key={q.numero_cuota} className={q.estado === "PAGADA" ? "opacity-60" : ""}>
                  <td className="px-2 py-1 font-medium">{q.numero_cuota}</td>
                  <td className="px-2 py-1">{fecha(q.fecha_vencimiento)}</td>
                  <td className="px-2 py-1 text-right tabular-nums">{money(q.capital)}</td>
                  <td className="px-2 py-1 text-right tabular-nums">{money(q.interes)}</td>
                  <td className="px-2 py-1 text-right tabular-nums font-semibold">{money(q.total)}</td>
                  <td className="px-2 py-1 text-right tabular-nums">{money(q.saldo_final)}</td>
                  <td className="px-2 py-1">{q.estado === "PAGADA" ? "pagada" : q.devengada ? "devengada" : "pendiente"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="max-h-80 overflow-auto p-3">
          <h3 className="text-sm font-semibold text-gray-800 mb-2">Actividades (servicing)</h3>
          {!c.actividades.length && <p className="text-sm text-gray-400">Sin actividades (pendiente de desembolso).</p>}
          {c.actividades.map((a, i) => {
            const reversada = a.estado === "REVERSADA";
            const puedeReversar = !reversada && !NO_REVERSABLES.includes(a.tipo);
            return (
              <div key={a.id || i}
                   className={`flex items-start gap-2 py-2 border-b border-gray-100 text-sm ${reversada ? "opacity-60" : ""}`}>
                <div className="flex-1">
                  <b className={reversada ? "line-through" : a.tipo === "REVERSAL" ? "text-red-600" : ""}>{a.tipo}</b>
                  {" · "}<span className="tabular-nums">{money(a.importe)}</span>
                  {reversada && <span className="ml-2"><Pill>REVERSADA</Pill></span>}
                  {a.dato?.interes_punitorio > 0 && (
                    <span className="ml-2">
                      <Pill tono="crit">mora {a.dato.mora_dias}d · {money(a.dato.interes_punitorio + (a.dato.iva_punitorio || 0))}</Pill>
                    </span>
                  )}
                  <p className="text-xs text-gray-400">{fecha(a.fecha)} · {a.detalle} · {a.por}</p>
                </div>
                {puedeReversar && !soloLectura && (
                  <button
                    onClick={() => setConfirmando({
                      titulo: "Reversar actividad",
                      mensaje: `Reversar ${a.tipo} del ${fecha(a.fecha)}: deshace su efecto y recalcula el contrato.`,
                      confirmar: "Reversar",
                      onSi: () => reversar(a),
                    })}
                    aria-label={`Reversar ${a.tipo}`}
                    className="px-2 py-1 text-xs text-red-600 border border-red-300 rounded-lg hover:bg-red-50"
                  >↩</button>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {c.asientos?.length > 0 && (
        <div className="border-t border-gray-200 p-3">
          <h3 className="text-sm font-semibold text-gray-800 mb-2">
            Asientos contables ({c.asientos.length})
            <span className="font-normal text-gray-400"> — también en el Libro Diario</span>
          </h3>
          <div className="max-h-60 overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wide text-gray-500">
                  <th className="px-2 py-1 text-left">N°</th><th className="px-2 py-1 text-left">Fecha</th>
                  <th className="px-2 py-1 text-left">Concepto</th><th className="px-2 py-1 text-left">Cuenta</th>
                  <th className="px-2 py-1 text-right">Debe</th><th className="px-2 py-1 text-right">Haber</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {c.asientos.map((as) => as.lineas.map((l, j) => (
                  <tr key={`${as.id}-${j}`} className={as.origen === "pp_reversa" ? "text-red-600" : ""}>
                    <td className="px-2 py-1">{j === 0 ? as.id : ""}</td>
                    <td className="px-2 py-1">{j === 0 ? fecha(as.fecha) : ""}</td>
                    <td className="px-2 py-1 max-w-[220px] truncate" title={as.concepto}>{j === 0 ? as.concepto : ""}</td>
                    <td className="px-2 py-1">{l.cuenta} · {l.nombre}</td>
                    <td className="px-2 py-1 text-right tabular-nums">{l.debe ? money(l.debe) : ""}</td>
                    <td className="px-2 py-1 text-right tabular-nums">{l.haber ? money(l.haber) : ""}</td>
                  </tr>
                )))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {pedido === "parcial" && (
        <PedirNumero
          titulo="Pago parcial" etiqueta="Importe del pago parcial" boton="Pagar"
          ayuda="Abona la próxima cuota sin completarla."
          onCancelar={() => setPedido(null)}
          onConfirmar={(v) => { setPedido(null); actividad("PAYMENT", v); }}
        />
      )}
      {pedido === "prepago" && (
        <PedirNumero
          titulo="Prepago de capital" etiqueta="Importe del prepago" boton="Aplicar prepago"
          onCancelar={() => setPedido(null)}
          onConfirmar={(v) => { setPedido(null); actividad("PARTIAL_PREPAYMENT", v, modoPrepago); }}
        >
          <div className="mt-3">
            <Field label="¿Cómo aplicar el prepago?">
              <select className="input w-full" value={modoPrepago} onChange={(e) => setModoPrepago(e.target.value)}>
                <option value="BAJA_CUOTA">Baja de cuota (mismo plazo, cuota menor)</option>
                <option value="BAJA_PLAZO">Baja de plazo (misma cuota, menos plazo)</option>
              </select>
            </Field>
          </div>
        </PedirNumero>
      )}
      {pedido === "diferir" && (
        <PedirNumero
          titulo="Diferimiento de cuotas" etiqueta="¿Cuántas cuotas diferir?" boton="Diferir"
          ayuda="El interés del período diferido se capitaliza."
          onCancelar={() => setPedido(null)}
          onConfirmar={(v) => { setPedido(null); actividad("PAYMENT_HOLIDAY", v); }}
        />
      )}

      {refi && (
        <Modal
          titulo="Refinanciar contrato"
          onClose={() => setRefi(null)}
          footer={
            <>
              <Boton variante="secundario" onClick={() => setRefi(null)}>Cancelar</Boton>
              <span className="flex-1" />
              <Boton variante="secundario" onClick={simularRefi} disabled={refi.cargando}>
                {refi.cargando ? "Simulando…" : "Simular"}
              </Boton>
              <Boton variante="danger" onClick={() => setConfirmando({
                titulo: "Refinanciar el contrato",
                mensaje: `Refinanciar el saldo ${money(Number(c.saldo_capital))} a TNA ${refi.tasa}% en ${refi.plazo} cuotas: cierra este contrato y crea uno nuevo.`,
                confirmar: "Refinanciar",
                onSi: confirmarRefi,
              })}>Refinanciar</Boton>
            </>
          }
        >
          <div className="grid sm:grid-cols-2 gap-3">
            <Field label="TNA %">
              <input type="number" className="input w-full" value={refi.tasa}
                     onChange={(e) => setRefi({ ...refi, tasa: Number(e.target.value), sim: null })} />
            </Field>
            <Field label="Plazo (cuotas)">
              <input type="number" className="input w-full" value={refi.plazo}
                     onChange={(e) => setRefi({ ...refi, plazo: Number(e.target.value), sim: null })} />
            </Field>
          </div>
          <p className="text-sm text-gray-500 mt-3">
            Saldo a refinanciar: <b>{money(c.saldo_capital)}</b>
          </p>
          {refi.sim && (
            <div className="mt-3 border border-gray-200 rounded-lg p-3 text-sm">
              <p>Cuota estimada: <b>{money(refi.sim.cuotaPromedio ?? refi.sim.cuota_promedio)}</b></p>
              <p className="text-gray-500">
                Total a pagar {money(refi.sim.totalAPagar ?? refi.sim.total_a_pagar)} · CFT {refi.sim.cft}%
              </p>
            </div>
          )}
        </Modal>
      )}

      {confirmando && (
        <Confirmacion
          titulo={confirmando.titulo}
          mensaje={confirmando.mensaje}
          confirmar={confirmando.confirmar}
          onConfirmar={confirmando.onSi}
          onCancelar={() => setConfirmando(null)}
        />
      )}
    </div>
  );
}
