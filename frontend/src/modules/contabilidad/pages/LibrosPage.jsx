import { useEffect, useState } from "react";
import {
  anularAsiento, borrarAsiento, crearAsiento, estadosContables, flujoEfectivo, libroIva, libroMayor,
  listarAsientos, listarCuentas, mensajeDeError, porCentro, posicionIva, publicarAsiento, sumasYSaldos,
  verAsiento,
} from "../../../api/contabilidad";
import { PermissionGate } from "../../../components/PrivateRoute";
import { Alerta, Boton, Card, Field, Modal, PageHeader, Toolbar } from "../../../components/ui";
import { Confirmacion } from "../../../components/ui/Confirmacion";
import { DataTable } from "../../../components/ui/DataTable";
import { Pill } from "../../../components/ui/Pill";
import { fecha, hoy, money } from "../formato";

const VISTAS = [["diario", "Libro diario"], ["mayor", "Mayor"], ["sumas", "Sumas y saldos"],
                ["estados", "Estados contables"], ["iva", "Libro IVA"], ["posicion", "Posición de IVA"],
                ["flujo", "Flujo de efectivo"], ["centros", "Por centro de costo"]];

export default function LibrosPage() {
  const [vista, setVista] = useState("diario");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [cuenta, setCuenta] = useState("");
  const [cuentas, setCuentas] = useState([]);
  const [libro, setLibro] = useState("VENTAS");
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [cargando, setCargando] = useState(true);
  const [detalle, setDetalle] = useState(null);
  const [anulando, setAnulando] = useState(null);
  const [nuevo, setNuevo] = useState(null);

  useEffect(() => { listarCuentas({ solo_imputables: true }).then((d) => { setCuentas(d.items); setCuenta((c) => c || d.items[0]?.codigo || ""); }).catch(() => {}); }, []);

  const cargar = () => {
    const params = { ...(desde && { desde }), ...(hasta && { hasta }) };
    setCargando(true); setError("");
    const pedido = vista === "diario" ? listarAsientos({ ...params, limit: 200 })
      : vista === "mayor" ? (cuenta ? libroMayor(cuenta, params) : Promise.resolve(null))
      : vista === "sumas" ? sumasYSaldos(params)
      : vista === "estados" ? estadosContables(params)
      : vista === "posicion" ? posicionIva(params)
      : vista === "flujo" ? flujoEfectivo(params)
      : vista === "centros" ? porCentro(params)
      : libroIva(libro, params);
    pedido.then(setDatos).catch((e) => setError(mensajeDeError(e))).finally(() => setCargando(false));
  };
  useEffect(cargar, [vista, desde, hasta, cuenta, libro]);   // eslint-disable-line react-hooks/exhaustive-deps

  const guardarAsiento = async (asiento) => {
    setError("");
    try {
      await crearAsiento(asiento);
      setNuevo(null); setOk("Asiento registrado."); cargar();
    } catch (e) { setError(mensajeDeError(e)); }
  };

  const publicar = async (id) => {
    setError("");
    try { await publicarAsiento(id); setDetalle(null); setOk("Borrador publicado: ya está en los libros."); cargar(); }
    catch (e) { setError(mensajeDeError(e)); }
  };

  const descartar = async (id) => {
    setError("");
    try { await borrarAsiento(id); setDetalle(null); setOk("Borrador descartado."); cargar(); }
    catch (e) { setError(mensajeDeError(e)); }
  };

  const confirmarAnulacion = async () => {
    try {
      await anularAsiento(anulando.id, anulando.motivo || "");
      setAnulando(null); setDetalle(null); setOk("Asiento anulado con su contra-asiento."); cargar();
    } catch (e) { setError(mensajeDeError(e)); setAnulando(null); }
  };

  return (
    <div className="space-y-4">
      <PageHeader titulo="Libros contables"
                  descripcion="Diario, mayor, sumas y saldos, estados contables y libro IVA. Los asientos no se editan: se anulan con su contra-asiento.">
        <PermissionGate moduleCode="contabilidad" action="asientos:write">
          <Boton onClick={() => setNuevo({ fecha: hoy(), concepto: "", lineas: [{ cuenta: "", debe: "", haber: "" }, { cuenta: "", debe: "", haber: "" }] })}>
            ＋ Asiento manual
          </Boton>
        </PermissionGate>
      </PageHeader>

      <Alerta>{error}</Alerta>
      {ok && <Alerta tipo="ok">{ok}</Alerta>}

      <Card padding={false}>
        <Toolbar>
          <Field label="Vista">
            <select className="input" value={vista} onChange={(e) => setVista(e.target.value)}>
              {VISTAS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
            </select>
          </Field>
          {vista === "mayor" && (
            <Field label="Cuenta">
              <select className="input w-72" value={cuenta} onChange={(e) => setCuenta(e.target.value)}>
                {cuentas.map((c) => <option key={c.codigo} value={c.codigo}>{c.codigo} · {c.nombre}</option>)}
              </select>
            </Field>
          )}
          {vista === "iva" && (
            <Field label="Libro">
              <select className="input" value={libro} onChange={(e) => setLibro(e.target.value)}>
                <option value="VENTAS">Ventas</option><option value="COMPRAS">Compras</option>
              </select>
            </Field>
          )}
          <Field label="Desde"><input type="date" className="input" value={desde} onChange={(e) => setDesde(e.target.value)} /></Field>
          <Field label="Hasta"><input type="date" className="input" value={hasta} onChange={(e) => setHasta(e.target.value)} /></Field>
        </Toolbar>

        <div className="p-4">
          {cargando && <p className="py-8 text-center text-sm text-gray-400">Cargando…</p>}

          {!cargando && vista === "diario" && datos && (
            <DataTable rowKey={(a) => a.id} rows={datos.items} pageSize={25} onRowClick={(a) => verAsiento(a.id).then(setDetalle)}
              columns={[
                { key: "numero", label: "N°", align: "right" },
                { key: "fecha", label: "Fecha", render: (a) => fecha(a.fecha) },
                { key: "diario", label: "Diario" },
                { key: "concepto", label: "Concepto" },
                { key: "origen", label: "Origen", render: (a) => (
                  <div className="flex flex-wrap gap-1">
                    <Pill tono={a.origen === "TRANSACCION" ? "brand" : "neutral"}>{a.origen.toLowerCase()}</Pill>
                    {a.estado === "ANULADO" && <Pill tono="crit">anulado</Pill>}
                    {a.estado === "BORRADOR" && <Pill tono="warn">borrador</Pill>}
                  </div>) },
                { key: "debe", label: "Debe", align: "right", render: (a) => money(a.debe) },
                { key: "haber", label: "Haber", align: "right", render: (a) => money(a.haber) },
              ]} emptyText="Sin asientos en el período" />
          )}

          {!cargando && vista === "mayor" && datos && (
            <>
              <p className="text-sm text-gray-600 mb-2">
                {datos.cuenta.codigo} · {datos.cuenta.nombre} — saldo anterior {money(datos.saldoAnterior)}
              </p>
              <DataTable rowKey={(m, i) => `${m.asientoId}-${i}`} rows={datos.movimientos} pageSize={50}
                columns={[
                  { key: "fecha", label: "Fecha", render: (m) => fecha(m.fecha) },
                  { key: "numero", label: "Asiento", align: "right" },
                  { key: "concepto", label: "Concepto" },
                  { key: "debe", label: "Debe", align: "right", render: (m) => money(m.debe) },
                  { key: "haber", label: "Haber", align: "right", render: (m) => money(m.haber) },
                  { key: "saldo", label: "Saldo", align: "right", render: (m) => money(m.saldo) },
                ]} emptyText="La cuenta no tuvo movimientos" />
              <p className="text-right text-sm font-medium text-gray-800 mt-2">Saldo final {money(datos.saldoFinal)}</p>
            </>
          )}

          {!cargando && vista === "sumas" && datos && (
            <>
              <DataTable rowKey={(f) => f.cuenta} rows={datos.items} pageSize={100}
                columns={[
                  { key: "cuenta", label: "Cuenta" },
                  { key: "nombre", label: "Nombre" },
                  { key: "debe", label: "Debe", align: "right", render: (f) => money(f.debe) },
                  { key: "haber", label: "Haber", align: "right", render: (f) => money(f.haber) },
                  { key: "saldoDeudor", label: "Saldo deudor", align: "right", render: (f) => money(f.saldoDeudor) },
                  { key: "saldoAcreedor", label: "Saldo acreedor", align: "right", render: (f) => money(f.saldoAcreedor) },
                ]} emptyText="Sin movimientos" />
              <p className="mt-2 text-sm text-gray-700 text-right tabular-nums">
                Totales: debe {money(datos.totales.debe)} · haber {money(datos.totales.haber)}{" "}
                {datos.balanceado ? <Pill tono="ok">balanceado</Pill> : <Pill tono="crit">no balancea</Pill>}
              </p>
            </>
          )}

          {!cargando && vista === "estados" && datos && (
            <div className="grid md:grid-cols-2 gap-4">
              {[["Situación patrimonial", [["Activo", datos.situacion.activo], ["Pasivo", datos.situacion.pasivo],
                                            ["Patrimonio neto", datos.situacion.patrimonio]]],
                ["Resultados", [["Ingresos", datos.resultados.ingresos], ["Egresos", datos.resultados.egresos]]]]
                .map(([titulo, bloques]) => (
                <div key={titulo} className="border border-gray-200 rounded-xl p-4">
                  <h3 className="font-semibold text-gray-800 mb-2">{titulo}</h3>
                  {bloques.map(([nombre, bloque]) => (
                    <div key={nombre} className="mb-3">
                      <p className="text-sm font-medium text-gray-700">{nombre} · {money(bloque.total)}</p>
                      <ul className="text-sm text-gray-600">
                        {bloque.cuentas.map((c) => (
                          <li key={c.cuenta} className="flex justify-between gap-2 tabular-nums">
                            <span>{c.cuenta} {c.nombre}</span><span>{money(c.importe)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                  {titulo === "Resultados" && (
                    <p className="text-sm font-semibold text-gray-800">Resultado del período: {money(datos.resultados.resultado)}</p>
                  )}
                  {titulo === "Situación patrimonial" && (
                    <p className="text-xs text-gray-500">
                      {datos.situacion.ecuacionCierra ? "Activo = Pasivo + Patrimonio + Resultado ✓" : "⚠ La ecuación no cierra"}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          {!cargando && vista === "posicion" && datos && (
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="border border-gray-200 rounded-xl p-4">
                <h3 className="font-semibold text-gray-800 mb-2">Posición del período</h3>
                <dl className="text-sm space-y-1">
                  {[["Débito fiscal (ventas)", datos.debitoFiscal], ["Crédito fiscal (compras)", datos.creditoFiscal],
                    ["Percepciones sufridas", datos.percepcionesSufridas], ["Retenciones sufridas", datos.retencionesSufridas]]
                    .map(([t, v]) => (
                    <div key={t} className="flex justify-between gap-2 tabular-nums"><dt>{t}</dt><dd>{money(v)}</dd></div>
                  ))}
                </dl>
                <p className="mt-3 font-semibold text-gray-800">
                  {datos.aPagar > 0 ? `A pagar: ${money(datos.aPagar)}` : `Saldo a favor: ${money(datos.aFavor)}`}
                </p>
              </div>
              <div className="border border-gray-200 rounded-xl p-4">
                <h3 className="font-semibold text-gray-800 mb-2">Por alícuota</h3>
                {[["Ventas", datos.ventas], ["Compras", datos.compras]].map(([t, b]) => (
                  <div key={t} className="mb-2">
                    <p className="text-sm font-medium text-gray-700">{t} · {b.comprobantes} comprobante(s) · neto {money(b.neto)}</p>
                    <ul className="text-sm text-gray-600">
                      {b.porAlicuota.map((a) => (
                        <li key={a.alicuota} className="tabular-nums">{a.alicuota}%: neto {money(a.neto)} · IVA {money(a.iva)}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!cargando && vista === "flujo" && datos && (
            <>
              <div className="flex flex-wrap gap-4 mb-3 text-sm">
                <p>Entradas <b className="tabular-nums">{money(datos.entradas)}</b></p>
                <p>Salidas <b className="tabular-nums">{money(datos.salidas)}</b></p>
                <p>Neto <b className="tabular-nums">{money(datos.neto)}</b></p>
                {Object.entries(datos.saldosPorCuenta).map(([c, s]) => (
                  <p key={c} className="text-gray-500">{c}: <span className="tabular-nums">{money(s)}</span></p>
                ))}
              </div>
              <DataTable rowKey={(m, i) => `${m.numero}-${i}`} rows={datos.movimientos} pageSize={50}
                columns={[
                  { key: "fecha", label: "Fecha", render: (m) => fecha(m.fecha) },
                  { key: "numero", label: "Asiento", align: "right" },
                  { key: "concepto", label: "Concepto" },
                  { key: "cuenta", label: "Cuenta" },
                  { key: "contrapartida", label: "Contrapartida" },
                  { key: "importe", label: "Importe", align: "right", render: (m) => money(m.importe) },
                ]} emptyText="Sin movimientos de fondos en el período" />
            </>
          )}

          {!cargando && vista === "centros" && datos && (
            datos.items.length === 0
              ? <p className="py-8 text-center text-sm text-gray-400">Todavía no hay asientos con centro de costo.</p>
              : <div className="space-y-3">
                  {datos.items.map((c) => (
                    <div key={c.centro} className="border border-gray-200 rounded-xl p-4">
                      <div className="flex flex-wrap items-center gap-3">
                        <h3 className="font-semibold text-gray-800 mr-auto">{c.centro} · {c.nombre}</h3>
                        <span className="text-sm text-gray-600 tabular-nums">Ingresos {money(c.ingresos)}</span>
                        <span className="text-sm text-gray-600 tabular-nums">Egresos {money(c.egresos)}</span>
                        <span className={`text-sm font-semibold tabular-nums ${c.resultado >= 0 ? "text-green-700" : "text-red-600"}`}>
                          Resultado {money(c.resultado)}
                        </span>
                      </div>
                      <ul className="text-sm text-gray-600 mt-2">
                        {c.cuentas.map((x) => (
                          <li key={x.cuenta} className="flex justify-between gap-2 tabular-nums">
                            <span>{x.cuenta} {x.nombre}</span>
                            <span>debe {money(x.debe)} · haber {money(x.haber)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
          )}

          {!cargando && vista === "iva" && datos && (
            <>
              <DataTable rowKey={(c) => c.id} rows={datos.items} pageSize={50}
                columns={[
                  { key: "fecha", label: "Fecha", render: (c) => fecha(c.fecha) },
                  { key: "comprobante", label: "Comprobante", render: (c) => `${c.tipoComprobante} ${String(c.puntoVenta).padStart(4, "0")}-${String(c.numero).padStart(8, "0")}` },
                  { key: "cuit", label: "CUIT" },
                  { key: "razonSocial", label: "Razón social" },
                  { key: "netoGravado", label: "Neto", align: "right", render: (c) => money(c.netoGravado) },
                  { key: "alicuota", label: "Alíc.", align: "right", render: (c) => `${c.alicuota}%` },
                  { key: "iva", label: "IVA", align: "right", render: (c) => money(c.iva) },
                  { key: "total", label: "Total", align: "right", render: (c) => money(c.total) },
                ]} emptyText="Sin comprobantes en el período" />
              <div className="mt-2 text-sm text-gray-700 text-right tabular-nums">
                <p>Neto {money(datos.totales.netoGravado)} · IVA {money(datos.totales.iva)} · Total {money(datos.totales.total)}</p>
                {datos.porAlicuota.map((a) => (
                  <p key={a.alicuota} className="text-xs text-gray-500">Alícuota {a.alicuota}%: neto {money(a.neto)} · IVA {money(a.iva)}</p>
                ))}
              </div>
            </>
          )}
        </div>
      </Card>

      {detalle && (
        <Modal titulo={`Asiento N° ${detalle.numero}`} eyebrow={`${fecha(detalle.fecha)} · ${detalle.origen.toLowerCase()}`}
               onClose={() => setDetalle(null)}
               footer={<>
                 {detalle.estado === "BORRADOR" && (
                   <PermissionGate moduleCode="contabilidad" action="asientos:write">
                     <Boton onClick={() => publicar(detalle.id)}>Publicar</Boton>
                     <Boton variante="secundario" onClick={() => descartar(detalle.id)}>Descartar</Boton>
                   </PermissionGate>
                 )}
                 {detalle.estado === "REGISTRADO" && detalle.origen !== "REVERSA" && (
                   <PermissionGate moduleCode="contabilidad" action="asientos:write">
                     <Boton variante="danger" onClick={() => setAnulando({ id: detalle.id, motivo: "" })}>Anular</Boton>
                   </PermissionGate>
                 )}
                 <span className="flex-1" />
                 <Boton variante="secundario" onClick={() => setDetalle(null)}>Cerrar</Boton>
               </>}>
          <p className="text-sm text-gray-700 mb-2">{detalle.concepto}</p>
          <table className="w-full text-sm">
            <thead><tr className="border-b border-gray-200 text-xs text-gray-500 text-left">
              <th className="py-1">Cuenta</th><th className="py-1 text-right">Debe</th><th className="py-1 text-right">Haber</th>
            </tr></thead>
            <tbody className="divide-y divide-gray-100">
              {detalle.lineas.map((l, i) => (
                <tr key={i}>
                  <td className="py-1">{l.cuenta} · {l.nombre}{l.detalle ? ` — ${l.detalle}` : ""}</td>
                  <td className="py-1 text-right tabular-nums">{l.debe ? money(l.debe) : ""}</td>
                  <td className="py-1 text-right tabular-nums">{l.haber ? money(l.haber) : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {detalle.transaccion && (
            <p className="text-xs text-gray-500 mt-3">
              Generado por la transacción {detalle.transaccion.tipo} · {detalle.transaccion.referencia} de {detalle.transaccion.modulo}
            </p>
          )}
        </Modal>
      )}

      {anulando && (
        <Confirmacion titulo="Anular el asiento" confirmar="Anular"
                      mensaje={"El asiento no se borra: se registra su contra-asiento y los dos quedan en el libro."}
                      onConfirmar={confirmarAnulacion} onCancelar={() => setAnulando(null)} />
      )}

      {nuevo && (
        <AsientoManual asiento={nuevo} cuentas={cuentas} onCerrar={() => setNuevo(null)} onGuardar={guardarAsiento} />
      )}
    </div>
  );
}

function AsientoManual({ asiento, cuentas, onCerrar, onGuardar }) {
  const [datos, setDatos] = useState(asiento);
  const cambiar = (i, campo, v) => setDatos((d) => ({
    ...d, lineas: d.lineas.map((l, j) => (j === i ? { ...l, [campo]: v } : l)),
  }));
  const n = (v) => Number(String(v).replace(",", ".") || 0);
  const debe = datos.lineas.reduce((s, l) => s + n(l.debe), 0);
  const haber = datos.lineas.reduce((s, l) => s + n(l.haber), 0);

  return (
    <Modal titulo="Asiento manual" eyebrow="Ajustes" onClose={onCerrar} ancho="max-w-3xl"
           footer={<>
             <span className={`text-sm mr-auto tabular-nums ${debe === haber && debe > 0 ? "text-green-700" : "text-red-600"}`}>
               Debe {money(debe)} · Haber {money(haber)}
             </span>
             <Boton variante="secundario" onClick={onCerrar}>Cancelar</Boton>
             <Boton variante="secundario" disabled={!(debe === haber && debe > 0 && datos.concepto.trim())}
                    onClick={() => onGuardar(armar(datos, n, true))}>Guardar borrador</Boton>
             <Boton disabled={!(debe === haber && debe > 0 && datos.concepto.trim())}
                    onClick={() => onGuardar(armar(datos, n, false))}>Registrar</Boton>
           </>}>
      <div className="grid sm:grid-cols-2 gap-3 mb-3">
        <Field label="Fecha"><input type="date" className="input w-full" value={datos.fecha} onChange={(e) => setDatos({ ...datos, fecha: e.target.value })} /></Field>
        <Field label="Concepto"><input className="input w-full" value={datos.concepto} onChange={(e) => setDatos({ ...datos, concepto: e.target.value })} /></Field>
      </div>
      <table className="w-full text-sm">
        <thead><tr className="border-b border-gray-200 text-xs text-gray-500 text-left">
          <th className="py-1">Cuenta</th><th className="py-1">Debe</th><th className="py-1">Haber</th>
        </tr></thead>
        <tbody>
          {datos.lineas.map((l, i) => (
            <tr key={i}>
              <td className="py-1 pr-2">
                <select className="input w-full" aria-label={`Cuenta ${i + 1}`} value={l.cuenta} onChange={(e) => cambiar(i, "cuenta", e.target.value)}>
                  <option value="">(elegir)</option>
                  {cuentas.map((c) => <option key={c.codigo} value={c.codigo}>{c.codigo} · {c.nombre}</option>)}
                </select>
              </td>
              <td className="py-1 pr-2"><input className="input w-32 text-right" aria-label={`Debe ${i + 1}`} value={l.debe} onChange={(e) => cambiar(i, "debe", e.target.value)} /></td>
              <td className="py-1"><input className="input w-32 text-right" aria-label={`Haber ${i + 1}`} value={l.haber} onChange={(e) => cambiar(i, "haber", e.target.value)} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <Boton variante="secundario" className="mt-2" onClick={() => setDatos((d) => ({ ...d, lineas: [...d.lineas, { cuenta: "", debe: "", haber: "" }] }))}>
        ＋ Agregar línea
      </Boton>
    </Modal>
  );
}

/** Payload del asiento manual (publicado o en borrador). */
function armar(datos, n, borrador) {
  return {
    fecha: datos.fecha, concepto: datos.concepto.trim(), borrador,
    lineas: datos.lineas.filter((l) => l.cuenta).map((l) => ({
      cuenta: l.cuenta, debe: n(l.debe), haber: n(l.haber), detalle: l.detalle || "" })),
  };
}

