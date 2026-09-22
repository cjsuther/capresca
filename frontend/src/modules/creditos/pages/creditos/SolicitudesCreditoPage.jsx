import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { creditos } from "../../../../api/creditos";
import { PageHeader, Card, Field, Boton, Alerta, Modal } from "../../components/ui";
import { Pill } from "../../components/Pill";
import { Confirmacion } from "../../components/Confirmacion";
import { VisorDocumento } from "../../components/VisorDocumento";
import { BuscadorCliente, nombreCliente } from "../../components/BuscadorCliente";
import { useSoloLectura } from "../../permisos";
import { fecha, fmtBytes } from "../../components/format";

const TONO_ESTADO = {
  BORRADOR: "neutral", EN_EVALUACION: "warn", APROBADA: "ok",
  RECHAZADA: "crit", ORIGINADA: "brand", ANULADA: "neutral",
};
const RELACIONES = ["ESTANDAR", "PREFERENCIAL", "PREMIUM"];
const TIPODOC = { DNI_FRENTE: "DNI (frente)", DNI_DORSO: "DNI (dorso)", SELFIE_DNI: "Selfie con el DNI en la mano",
                  RECIBO: "Recibo de sueldo", OTRO: "Otro" };

/** Años cumplidos a hoy: la solicitud guarda la fecha de nacimiento y la edad se muestra calculada. */
export function edadDe(fecha) {
  if (!fecha) return null;
  const n = new Date(`${String(fecha).slice(0, 10)}T00:00:00`);
  if (isNaN(n.getTime())) return null;
  const h = new Date();
  let e = h.getFullYear() - n.getFullYear();
  const m = h.getMonth() - n.getMonth();
  if (m < 0 || (m === 0 && h.getDate() < n.getDate())) e--;
  return e;
}
const DESTINO = {
  VIVIENDA: "Vivienda / refacción", VEHICULO: "Vehículo", CONSUMO: "Consumo / gastos personales",
  EDUCACION: "Educación", SALUD: "Salud", REFINANCIACION: "Refinanciación de deudas",
  EMPRENDIMIENTO: "Emprendimiento / negocio", OTRO: "Otro",
};
const PASOS = ["Solicitante", "Simulación", "Confirmación"];

/** Sólo dígitos, acotado al rango que valida el backend. Vacío = sin valor (H-200). */
const acotar = (v, min, max) => {
  const d = String(v).replace(/\D/g, "");
  return d === "" ? "" : String(Math.max(min, Math.min(max, parseInt(d, 10))));
};

const FORM_VACIO = {
  producto_id: "", monto_solicitado: 1000000, plazo_solicitado: 24,
  segmento: "", canal: "SUCURSAL", fecha_nacimiento: "", antiguedad_meses: "", relacion: "ESTANDAR",
  datos_adicionales: { destino: "", cbu: "", observaciones: "" },
};

export default function SolicitudesCreditoPage() {
  const soloLectura = useSoloLectura();
  const [items, setItems] = useState([]);
  const [estados, setEstados] = useState([]);
  const [permisos, setPermisos] = useState({ edita: false, aprueba: false });
  const [filtro, setFiltro] = useState("");
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const [lineas, setLineas] = useState([]);
  const [cat, setCat] = useState({ segmentos: [], canales: [] });

  // Alta (asistente de 3 pasos)
  const [nueva, setNueva] = useState(false);
  const [paso, setPaso] = useState(1);
  const [cliente, setCliente] = useState(null);
  const [form, setForm] = useState(FORM_VACIO);
  const [sim, setSim] = useState(null);
  const [simulando, setSimulando] = useState(false);
  const [creando, setCreando] = useState(false);

  // Detalle de una solicitud
  const [sel, setSel] = useState(null);
  const [docs, setDocs] = useState([]);
  const [viendoDoc, setViendoDoc] = useState(null);   // índice del documento abierto en el visor
  const [crono, setCrono] = useState([]);
  const [cronoAbierto, setCronoAbierto] = useState(false);
  const [cargandoCrono, setCargandoCrono] = useState(false);
  const [obs, setObs] = useState("");
  const [detErr, setDetErr] = useState("");
  const [accionando, setAccionando] = useState(false);
  const [confirmando, setConfirmando] = useState(null);
  const [vinculando, setVinculando] = useState(null);      // solicitud express a vincular
  const [altaCliente, setAltaCliente] = useState(null);    // formulario de alta del cliente desde la solicitud
  const [altaErr, setAltaErr] = useState("");
  const [detOk, setDetOk] = useState(null);                // { texto, clienteId } tras crear/vincular/guardar docs

  const decimales = Math.max(0, Math.min(6, cat.decimalesMostrar ?? 2));
  const money = (n) => "$" + Number(n || 0).toLocaleString("es-AR",
    { minimumFractionDigits: decimales, maximumFractionDigits: decimales });

  const cargar = () => creditos.ppSolicitudes({ estado: filtro, q })
    .then((d) => { setItems(d.items); setEstados(d.estados); setPermisos(d.permisos); })
    .catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, [filtro, q]); // eslint-disable-line

  // Deep-link desde el Inbox de aprobaciones: abre directo la solicitud a revisar.
  useEffect(() => {
    const abrirId = sessionStorage.getItem("solicitud_abrir");
    if (!abrirId) return;
    sessionStorage.removeItem("solicitud_abrir");
    creditos.ppSolicitud(abrirId).then(setSel).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    // La oferta del backoffice se filtra por su canal (H-185/H-199): una línea "solo web" no se
    // puede originar por sucursal, así que no se lista acá.
    const cargarOferta = (canal) => creditos.ppOferta(canal ? { canal } : {})
      .then((d) => { setLineas(d.items); if (d.items[0]) setForm((f) => ({ ...f, producto_id: f.producto_id || d.items[0].id })); })
      .catch(() => {});
    creditos.ctoSegmentos().then((c) => { setCat(c); cargarOferta(c?.canalBackoffice); }).catch(() => cargarOferta());
  }, []);

  // Al abrir una solicitud: documentación, cronograma estimado y observación previa.
  useEffect(() => {
    setViendoDoc(null); setDetOk(null);
    if (!sel?.id) { setDocs([]); setCrono([]); return; }
    setObs(sel.datosAdicionales?.obs_revision || ""); setDetErr(""); setCronoAbierto(false);
    creditos.ppSolicitudDocs(sel.id).then((d) => setDocs(d.items)).catch(() => setDocs([]));
    if (!sel.productoId) { setCrono([]); return; }
    setCargandoCrono(true);
    creditos.ppSimPreview(sel.productoId, {
      monto: sel.monto, plazo: sel.plazo, segmento: sel.segmento || undefined, canal: sel.canal || undefined,
      fecha_nacimiento: sel.fechaNacimiento || undefined, antiguedad_meses: sel.antiguedadMeses ?? undefined,
    }).then((s) => setCrono(s.cuotas || [])).catch(() => setCrono([])).finally(() => setCargandoCrono(false));
  }, [sel?.id]); // eslint-disable-line

  const edadForm = edadDe(form.fecha_nacimiento);
  const edadInvalida = form.fecha_nacimiento !== "" && (edadForm === null || edadForm < 18 || edadForm > 99);
  const paso1OK = !!cliente && !edadInvalida;
  const paso2OK = !!form.producto_id && Number(form.monto_solicitado) > 0 && Number(form.plazo_solicitado) > 0;

  async function simular() {
    if (!paso2OK) return;
    setSimulando(true); setError("");
    try {
      setSim(await creditos.ppSimPreview(form.producto_id, {
        monto: Number(form.monto_solicitado), plazo: Number(form.plazo_solicitado),
        segmento: form.segmento || undefined, canal: form.canal || undefined,
        fecha_nacimiento: form.fecha_nacimiento || undefined,
        antiguedad_meses: form.antiguedad_meses ? Number(form.antiguedad_meses) : undefined,
      }));
    } catch (e) { setSim(null); setError(e.message); }
    finally { setSimulando(false); }
  }

  // Simulación en vivo del paso 2 (H-195).
  useEffect(() => {
    if (!nueva || paso !== 2 || !paso2OK) return;
    const t = setTimeout(() => { simular(); }, 450);
    return () => clearTimeout(t);
  }, [nueva, paso, form.producto_id, form.monto_solicitado, form.plazo_solicitado]); // eslint-disable-line

  function abrirNueva() {
    setNueva(true); setSel(null); setPaso(1); setSim(null); setError(""); setCliente(null);
    // Se conserva la línea ofrecida (viene de la oferta del canal): si se limpiara, el paso 2
    // quedaría sin línea y la simulación en vivo no arrancaría.
    setForm((f) => ({ ...FORM_VACIO, producto_id: f.producto_id || lineas[0]?.id || "" }));
  }
  const cerrarNueva = () => { setNueva(false); setPaso(1); setSim(null); };

  async function crear(enviar) {
    setError(""); setCreando(true);
    try {
      const payload = {
        ...form,
        solicitante_tipo: "REGISTRADO",
        cliente_id: cliente.id,
        fecha_nacimiento: form.fecha_nacimiento || null,
        antiguedad_meses: form.antiguedad_meses ? Number(form.antiguedad_meses) : null,
      };
      let s = await creditos.ppSolicitudCrear(payload);
      if (enviar) {
        // Crear y mandar a evaluación en un paso: queda en el Inbox de aprobaciones.
        try { const r = await creditos.ppSolicitudEstado(s.id, "enviar", "", ""); if (r?.id) s = r; }
        catch { /* si falla el envío queda en borrador */ }
      }
      cerrarNueva(); setSel(s); cargar();
    } catch (e) { setError(e.message); }
    finally { setCreando(false); }
  }

  async function originarContrato(s, observacion) {
    const c = await creditos.ctoOriginar({
      producto_id: s.productoId, cliente_nombre: s.clienteNombre, monto: s.monto, plazo: s.plazo,
      segmento: s.segmento || undefined, canal: s.canal || undefined,
      fecha_nacimiento: s.fechaNacimiento || undefined, antiguedad_meses: s.antiguedadMeses ?? undefined,
      relacion: s.relacion || undefined, solicitud_pp_id: s.id,
      datos_adicionales: {
        destino: s.datosAdicionales?.destino || "", cbu: s.datosAdicionales?.cbu || "",
        observaciones: observacion.trim() || s.datosAdicionales?.observaciones || "",
      },
      desembolsar: false,
    });
    const rec = await creditos.ppSolicitudes({ estado: filtro, q })
      .then((d) => d.items.find((x) => x.id === s.id)).catch(() => null);
    cargar(); setSel(rec || null);
    return c;
  }

  async function resolver(accion) {
    const s = sel;
    if (!s) return;
    setDetErr(""); setOk("");
    if (accion === "rechazar" && !obs.trim()) {
      setDetErr("Para rechazar, escribí el motivo en Observación.");
      return;
    }
    setAccionando(true);
    try {
      if (accion === "originar") {
        const c = await originarContrato(s, obs);
        setOk(`Contrato originado: ${c.numeroContrato || c.numero_contrato || ""} · quedó A LIQUIDAR para el desembolso por lote.`);
      } else {
        const motivo = accion === "rechazar" || accion === "anular" ? obs.trim() : "";
        setSel(await creditos.ppSolicitudEstado(s.id, accion, motivo, obs.trim()));
        cargar();
      }
    } catch (e) { setDetErr(e.message); }
    finally { setAccionando(false); setConfirmando(null); }
  }

  /** Texto de lo que pasó con los adjuntos al crear/vincular el cliente. */
  const resumenDocs = (d) => {
    if (!d) return "";
    if (d.error) return ` ${d.error} Reintentá con "Guardar en el cliente".`;
    if (!d.guardados && !d.repetidos) return "";
    return ` ${d.guardados} documento(s) guardado(s) en su ficha${d.repetidos ? ` (${d.repetidos} ya estaba(n))` : ""}.`;
  };

  async function vincularCliente(c) {
    setDetErr("");
    try {
      const r = await creditos.ppSolicitudPromover(vinculando.id, { cliente_id: c.id });
      setVinculando(null); setSel(r.solicitud); cargar();
      const texto = `Cliente ${nombreCliente(c)} vinculado a la solicitud.${resumenDocs(r.documentos)}`;
      setOk(texto); setDetOk({ texto, clienteId: r.clienteId });
    } catch (e) { setDetErr(e.message); }
  }

  /** Alta en el módulo Clientes con lo que trajo la solicitud; el asesor completa lo que falte. */
  function abrirAltaCliente(s) {
    const cd = s.clienteDatos || {};
    const [apellido, ...resto] = (cd.apellido_nombre || s.clienteNombre || "").split(",");
    setAltaErr("");
    setAltaCliente({
      apellido: (apellido || "").trim(), nombres: resto.join(",").trim(),
      dni: cd.dni || "", cuil: cd.cuil || "",
      email: cd.email || s.datosAdicionales?.portal_email || "", telefono: cd.telefono || "",
      domicilio: cd.domicilio || "", localidad: cd.localidad || "", copiar_documentos: true,
    });
  }

  async function crearCliente() {
    const f = altaCliente;
    const cuil = f.cuil.replace(/\D/g, ""), dni = f.dni.replace(/\D/g, "");
    if (!f.apellido.trim() || !f.nombres.trim()) { setAltaErr("Completá apellido y nombres."); return; }
    if (!dni && !cuil) { setAltaErr("Hace falta el DNI o el CUIL."); return; }
    if (cuil && cuil.length !== 11) { setAltaErr("El CUIL debe tener 11 dígitos."); return; }
    setAccionando(true); setAltaErr("");
    try {
      const r = await creditos.ppSolicitudPromover(sel.id, {
        apellido_nombre: `${f.apellido.trim()}, ${f.nombres.trim()}`, dni, cuil,
        email: f.email.trim(), telefono: f.telefono.trim(), domicilio: f.domicilio.trim(), localidad: f.localidad.trim(),
        copiar_documentos: f.copiar_documentos,
      });
      setAltaCliente(null); setSel(r.solicitud); cargar();
      const texto = (r.yaExistia ? "La persona ya estaba en Clientes: se vinculó a la solicitud."
                                 : "Cliente creado en el módulo Clientes y vinculado a la solicitud.") + resumenDocs(r.documentos);
      setOk(texto); setDetOk({ texto, clienteId: r.clienteId });
    } catch (e) { setAltaErr(e.message); }
    finally { setAccionando(false); }
  }

  async function guardarDocsEnCliente() {
    setDetErr(""); setAccionando(true);
    try {
      const r = await creditos.ppSolicitudDocsAlCliente(sel.id);
      setDetOk({ texto: `Documentos en la ficha del cliente: ${r.guardados} nuevo(s)${r.repetidos ? `, ${r.repetidos} ya estaba(n)` : ""}.`,
                 clienteId: r.clienteId });
    } catch (e) { setDetErr(e.message); }
    finally { setAccionando(false); }
  }

  const puedeEditar = permisos.edita && !soloLectura;
  const puedeAprobar = permisos.aprueba && !soloLectura;

  return (
    <>
      <PageHeader
        titulo="Solicitudes de crédito"
        descripcion="Carga y evaluación de solicitudes de la línea nueva. Una solicitud aprobada se origina como contrato."
      >
        {puedeEditar && <Boton onClick={abrirNueva}>＋ Nueva solicitud</Boton>}
      </PageHeader>

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}
      {ok && <div className="mb-4"><Alerta tipo="ok">{ok}</Alerta></div>}

      <Card padding={false}>
        <div className="flex flex-wrap items-center gap-2 px-4 py-3 border-b border-gray-200">
          <button onClick={() => setFiltro("")}
                  className={`px-3 py-1 text-sm rounded-full border ${filtro === "" ? "bg-blue-50 border-blue-200 text-blue-700" : "border-gray-200 text-gray-600"}`}>
            Todas
          </button>
          {estados.map((e) => (
            <button key={e} onClick={() => setFiltro(e)}
                    className={`px-3 py-1 text-sm rounded-full border ${filtro === e ? "bg-blue-50 border-blue-200 text-blue-700" : "border-gray-200 text-gray-600"}`}>
              {e}
            </button>
          ))}
          <input className="input ml-auto w-60" value={q} onChange={(e) => setQ(e.target.value)}
                 placeholder="Buscar cliente o N°…" aria-label="Buscar cliente o número" />
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500">
                <th className="px-3 py-2 text-left">N°</th>
                <th className="px-3 py-2 text-left">Cliente</th>
                <th className="px-3 py-2 text-right">Monto</th>
                <th className="px-3 py-2 text-right">Plazo</th>
                <th className="px-3 py-2 text-right">Cuota est.</th>
                <th className="px-3 py-2 text-left">Estado</th>
                <th className="px-3 py-2 text-left">Elegible</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map((s) => (
                <tr key={s.id} onClick={() => { setSel(s); setNueva(false); }}
                    className="cursor-pointer hover:bg-gray-50">
                  <td className="px-3 py-2 font-medium">{s.numero}</td>
                  <td className="px-3 py-2">
                    {s.clienteNombre}
                    {s.solicitanteTipo === "NO_REGISTRADO" && <span className="ml-2"><Pill>express</Pill></span>}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{money(s.monto)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{s.plazo}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{money(s.evaluacion?.cuota_estimada || 0)}</td>
                  <td className="px-3 py-2"><Pill tono={TONO_ESTADO[s.estado] || "neutral"}>{s.estado}</Pill></td>
                  <td className="px-3 py-2">{s.evaluacion?.elegible ? "Sí" : "No"}</td>
                </tr>
              ))}
              {!items.length && (
                <tr><td colSpan={7} className="px-3 py-8 text-center text-gray-400">Sin solicitudes.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ── Asistente de alta ── */}
      {nueva && (
        <Modal
          titulo="Nueva solicitud"
          onClose={cerrarNueva}
          footer={
            <>
              <Boton variante="secundario" onClick={cerrarNueva}>Cancelar</Boton>
              <span className="flex-1" />
              {paso > 1 && <Boton variante="secundario" onClick={() => setPaso(paso - 1)}>← Volver</Boton>}
              {paso === 1 && (
                <Boton disabled={!paso1OK} onClick={() => { setPaso(2); if (!sim) simular(); }}>Continuar →</Boton>
              )}
              {paso === 2 && (
                <Boton disabled={!paso2OK || sim?.elegible === false}
                       title={sim?.elegible === false ? "No cumple las condiciones de la línea" : ""}
                       onClick={() => setPaso(3)}>Continuar →</Boton>
              )}
              {paso === 3 && (
                <>
                  <Boton variante="secundario" disabled={creando || sim?.elegible === false} onClick={() => crear(false)}>
                    Guardar borrador
                  </Boton>
                  <Boton disabled={creando || sim?.elegible === false} onClick={() => crear(true)}>
                    {creando ? "Creando…" : "Crear y enviar a evaluación"}
                  </Boton>
                </>
              )}
            </>
          }
        >
          <ol className="flex gap-2 mb-4">
            {PASOS.map((t, i) => {
              const n = i + 1;
              return (
                <li key={t} className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm ${
                  paso === n ? "bg-blue-50 text-blue-700 font-medium" : paso > n ? "text-green-700" : "text-gray-400"}`}>
                  <span className="w-5 h-5 rounded-full border grid place-items-center text-xs">{paso > n ? "✓" : n}</span>
                  {t}
                </li>
              );
            })}
          </ol>

          {error && <div className="mb-3"><Alerta>{error}</Alerta></div>}

          {paso === 1 && (
            <>
              <Field label="Cliente (padrón del sistema)">
                <BuscadorCliente seleccionado={cliente} onSelect={setCliente} />
              </Field>
              {!cliente && (
                <p className="text-xs text-gray-500 mt-1">
                  ¿Es un cliente nuevo? Dalo de alta en{" "}
                  <Link to="/modules/clientes/nuevo/humano" className="text-blue-600 hover:underline">Clientes</Link>.
                </p>
              )}
              <div className="grid gap-3 sm:grid-cols-2 mt-4">
                <Field label="Segmento">
                  <select className="input w-full" value={form.segmento}
                          onChange={(e) => setForm({ ...form, segmento: e.target.value })}>
                    <option value="">(cualquiera)</option>
                    {cat.segmentos.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </Field>
                <Field label="Fecha de nacimiento">
                  <input type="date" className="input w-full" value={form.fecha_nacimiento || ""}
                         max={new Date().toISOString().slice(0, 10)}
                         onChange={(e) => setForm({ ...form, fecha_nacimiento: e.target.value })} />
                  {edadInvalida
                    ? <span className="text-xs text-red-600">La edad debe estar entre 18 y 99 años.</span>
                    : edadForm !== null && <span className="text-xs text-gray-500">{edadForm} años</span>}
                </Field>
                <Field label="Antigüedad (meses)">
                  <input type="number" min={0} max={1200} className="input w-full" value={form.antiguedad_meses}
                         onChange={(e) => setForm({ ...form, antiguedad_meses: acotar(e.target.value, 0, 1200) })} />
                </Field>
                <Field label="Relación">
                  <select className="input w-full" value={form.relacion}
                          onChange={(e) => setForm({ ...form, relacion: e.target.value })}>
                    {RELACIONES.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </Field>
              </div>
            </>
          )}

          {paso === 2 && (
            <>
              <div className="grid gap-3 sm:grid-cols-3">
                <Field label="Línea">
                  <select className="input w-full" value={form.producto_id}
                          onChange={(e) => { setForm({ ...form, producto_id: e.target.value }); setSim(null); }}>
                    {lineas.map((l) => <option key={l.id} value={l.id}>{l.nombre} ({l.codigo})</option>)}
                  </select>
                </Field>
                <Field label="Monto">
                  <input type="number" min={1} max={999999999} className="input w-full" value={form.monto_solicitado}
                         onChange={(e) => { setForm({ ...form, monto_solicitado: Math.max(0, Math.min(999999999, Math.floor(Number(e.target.value) || 0))) }); setSim(null); }} />
                </Field>
                <Field label="Plazo (cuotas, 1–240)">
                  <input type="number" min={1} max={240} className="input w-full" value={form.plazo_solicitado}
                         onChange={(e) => { setForm({ ...form, plazo_solicitado: Math.max(0, Math.min(240, Math.floor(Number(e.target.value) || 0))) }); setSim(null); }} />
                </Field>
              </div>
              <p className="text-sm text-gray-500 mt-3">
                {simulando ? "Calculando…"
                  : paso2OK ? "La simulación se recalcula sola al cambiar los datos."
                  : "Completá línea, monto y plazo para simular."}
              </p>
              {sim && (
                <div className="mt-3 border border-gray-200 rounded-xl p-3">
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                    <div><p className="text-xs text-gray-500">Cuota promedio</p><b>{money(sim.cuotaPromedio)}</b></div>
                    <div><p className="text-xs text-gray-500">Total a pagar</p><b>{money(sim.totalCuotas)}</b></div>
                    <div><p className="text-xs text-gray-500">Cuotas</p><b>{sim.cantidadCuotas}</b></div>
                    <div><p className="text-xs text-gray-500">TNA</p><b>{sim.tna}%</b></div>
                  </div>
                  <div className="mt-3">
                    {sim.elegible === false
                      ? <Alerta>No cumple las condiciones: {sim.motivos.join(" · ")}. Ajustá los datos o elegí otra línea.</Alerta>
                      : <Alerta tipo="ok">Elegible con estos datos.</Alerta>}
                  </div>
                </div>
              )}
            </>
          )}

          {paso === 3 && (
            <>
              <dl className="grid sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
                <div className="flex justify-between border-b border-gray-100 py-1">
                  <dt className="text-gray-500">Cliente</dt><dd>{nombreCliente(cliente)}</dd></div>
                <div className="flex justify-between border-b border-gray-100 py-1">
                  <dt className="text-gray-500">Línea</dt>
                  <dd>{lineas.find((l) => l.id === form.producto_id)?.nombre || "—"}</dd></div>
                <div className="flex justify-between border-b border-gray-100 py-1">
                  <dt className="text-gray-500">Monto</dt><dd>{money(Number(form.monto_solicitado))}</dd></div>
                <div className="flex justify-between border-b border-gray-100 py-1">
                  <dt className="text-gray-500">Plazo</dt><dd>{form.plazo_solicitado} cuotas</dd></div>
                {sim && (
                  <>
                    <div className="flex justify-between border-b border-gray-100 py-1">
                      <dt className="text-gray-500">Cuota estimada</dt><dd>{money(sim.cuotaPromedio)}</dd></div>
                    <div className="flex justify-between border-b border-gray-100 py-1">
                      <dt className="text-gray-500">Elegible</dt><dd>{sim.elegible === false ? "No (revisar)" : "Sí"}</dd></div>
                  </>
                )}
              </dl>
              <div className="grid gap-3 sm:grid-cols-2 mt-4">
                <Field label="Destino">
                  <select className="input w-full" value={form.datos_adicionales.destino}
                          onChange={(e) => setForm({ ...form, datos_adicionales: { ...form.datos_adicionales, destino: e.target.value } })}>
                    <option value="">(sin especificar)</option>
                    {Object.entries(DESTINO).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                  </select>
                </Field>
                <Field label="Relación">
                  <select className="input w-full" value={form.relacion}
                          onChange={(e) => setForm({ ...form, relacion: e.target.value })}>
                    {RELACIONES.map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </Field>
              </div>
              <div className="mt-3">
                <Field label="Observaciones">
                  <textarea rows={2} className="input w-full" value={form.datos_adicionales.observaciones}
                            onChange={(e) => setForm({ ...form, datos_adicionales: { ...form.datos_adicionales, observaciones: e.target.value } })} />
                </Field>
              </div>
            </>
          )}
        </Modal>
      )}

      {/* ── Detalle / resolución ── */}
      {sel && (
        <Modal
          eyebrow={`${sel.numero} · ${sel.estado}`}
          titulo={sel.clienteNombre}
          onClose={() => setSel(null)}
          footer={
            <>
              <Boton variante="secundario" onClick={() => setSel(null)}>Cerrar</Boton>
              <span className="flex-1" />
              {sel.solicitanteTipo === "NO_REGISTRADO" && puedeEditar && (
                <>
                  <Boton variante="secundario" onClick={() => setVinculando(sel)}>Vincular existente</Boton>
                  <Boton variante="secundario" onClick={() => abrirAltaCliente(sel)}>Crear cliente</Boton>
                </>
              )}
              {sel.estado === "BORRADOR" && (
                <Boton disabled={accionando || !puedeEditar} onClick={() => resolver("enviar")}>Enviar a evaluación</Boton>
              )}
              {!["ORIGINADA", "ANULADA"].includes(sel.estado) && (
                <Boton variante="secundario" disabled={accionando || !puedeEditar}
                       title="Baja administrativa del trámite (no es una decisión crediticia)."
                       onClick={() => setConfirmando({
                         titulo: "Anular solicitud",
                         mensaje: `¿Anular ${sel.numero}? Es una baja administrativa del trámite, no una decisión crediticia.`,
                         confirmar: "Anular",
                         onSi: () => resolver("anular"),
                       })}>Anular</Boton>
              )}
              {sel.estado === "EN_EVALUACION" && (
                <>
                  <Boton variante="danger" disabled={accionando || !puedeAprobar} onClick={() => resolver("rechazar")}>
                    Rechazar
                  </Boton>
                  <Boton disabled={accionando || !puedeAprobar || sel.solicitanteTipo === "NO_REGISTRADO"}
                         title={sel.solicitanteTipo === "NO_REGISTRADO"
                           ? "El cliente no está en el padrón: vinculá uno antes de aprobar."
                           : "Aprueba el crédito (decisión crediticia)."}
                         onClick={() => resolver("aprobar")}>Aprobar</Boton>
                </>
              )}
              {sel.estado === "APROBADA" && (
                <Boton disabled={accionando || (sel.datosLiquidacion?.aplica && !sel.datosLiquidacion?.lista)}
                       title={sel.datosLiquidacion?.aplica && !sel.datosLiquidacion?.lista ? "Faltan datos para liquidar" : ""}
                       onClick={() => resolver("originar")}>Originar contrato</Boton>
              )}
            </>
          }
        >
          {detErr && <div className="mb-3"><Alerta>{detErr}</Alerta></div>}
          {detOk && (
            <div className="mb-3">
              <Alerta tipo="ok">
                {detOk.texto}{" "}
                {detOk.clienteId && <Link to={`/modules/clientes/${detOk.clienteId}`} className="underline font-medium">Ver ficha del cliente</Link>}
              </Alerta>
            </div>
          )}

          <dl className="grid sm:grid-cols-3 gap-3 text-sm">
            <div><dt className="text-xs text-gray-500">Línea</dt>
              <dd className="font-medium">{lineas.find((l) => l.id === sel.productoId)?.nombre || sel.productoId}</dd></div>
            <div><dt className="text-xs text-gray-500">Monto</dt><dd className="font-medium">{money(sel.monto)}</dd></div>
            <div><dt className="text-xs text-gray-500">Plazo</dt><dd className="font-medium">{sel.plazo} cuotas</dd></div>
            <div><dt className="text-xs text-gray-500">TNA ofrecida</dt>
              <dd className="font-medium">{sel.evaluacion?.tna_ofrecida ?? "—"}%</dd></div>
            <div><dt className="text-xs text-gray-500">Cuota estimada</dt>
              <dd className="font-medium">{money(sel.evaluacion?.cuota_estimada || 0)}</dd></div>
            <div><dt className="text-xs text-gray-500">Relación</dt><dd className="font-medium">{sel.relacion}</dd></div>
            {sel.datosAdicionales?.destino && (
              <div><dt className="text-xs text-gray-500">Destino</dt>
                <dd className="font-medium">{DESTINO[sel.datosAdicionales.destino] || sel.datosAdicionales.destino}</dd></div>
            )}
            {sel.datosAdicionales?.cbu && (
              <div><dt className="text-xs text-gray-500">CBU</dt><dd className="font-medium">{sel.datosAdicionales.cbu}</dd></div>
            )}
            {sel.fechaNacimiento && (
              <div><dt className="text-xs text-gray-500">Fecha de nacimiento</dt>
                <dd className="font-medium">{fecha(sel.fechaNacimiento)}{edadDe(sel.fechaNacimiento) !== null
                  ? ` · ${edadDe(sel.fechaNacimiento)} años` : ""}</dd></div>
            )}
            {(sel.clienteDatos?.email || sel.datosAdicionales?.email) && (
              <div><dt className="text-xs text-gray-500">Email</dt>
                <dd className="font-medium break-all">{sel.clienteDatos?.email || sel.datosAdicionales?.email}</dd></div>
            )}
            {(sel.clienteDatos?.telefono || sel.datosAdicionales?.telefono) && (
              <div><dt className="text-xs text-gray-500">Teléfono</dt>
                <dd className="font-medium">{sel.clienteDatos?.telefono || sel.datosAdicionales?.telefono}</dd></div>
            )}
          </dl>

          {sel.evaluacion?.motivos?.length > 0 && (
            <div className="mt-3"><Alerta>No elegible: {sel.evaluacion.motivos.join(" · ")}</Alerta></div>
          )}
          {sel.motivoRechazo && <p className="mt-3 text-sm text-gray-500">Motivo: {sel.motivoRechazo}</p>}
          {sel.datosAdicionales?.observaciones && (
            <p className="mt-2 text-sm text-gray-500">Nota del solicitante: {sel.datosAdicionales.observaciones}</p>
          )}

          {docs.length > 0 && (
            <div className="mt-4">
              <div className="flex items-center gap-2 mb-1">
                <p className="text-xs text-gray-500">Documentación del solicitante</p>
                <span className="flex-1" />
                {sel.solicitanteTipo === "REGISTRADO" && sel.clienteId && puedeEditar && (
                  <button onClick={guardarDocsEnCliente} disabled={accionando}
                          className="text-xs text-blue-600 hover:underline disabled:opacity-50">Guardar en el cliente</button>
                )}
              </div>
              {docs.map((d) => (
                <div key={d.id} className="flex items-center gap-2 py-1 text-sm">
                  <Pill>{TIPODOC[d.tipo] || d.tipo}</Pill>
                  <button onClick={() => setViendoDoc(docs.indexOf(d))}
                          className="text-blue-600 hover:underline truncate max-w-xs" title={`Ver ${d.nombre}`}>{d.nombre}</button>
                  <span className="text-gray-400 text-xs">{fmtBytes(d.tamano)}</span>
                </div>
              ))}
            </div>
          )}

          {sel.datosLiquidacion?.aplica && (
            <div className="mt-4 border border-gray-200 rounded-xl p-3">
              <p className="text-sm font-medium text-gray-700 mb-2">
                Revisión para liquidar{" "}
                {sel.datosLiquidacion.lista ? <Pill tono="ok">lista</Pill> : <Pill tono="warn">faltan datos</Pill>}
              </p>
              <ul className="grid sm:grid-cols-2 gap-1 text-sm">
                {sel.datosLiquidacion.items.map((it) => (
                  <li key={it.campo} className={`flex gap-2 ${it.ok ? "text-gray-700" : it.requerido ? "text-red-600" : "text-gray-400"}`}>
                    <span>{it.ok ? "✓" : it.requerido ? "✕" : "○"}</span>
                    <span className="flex-1">{it.label}{!it.requerido && <em className="text-gray-400"> (opcional)</em>}</span>
                    <span>{it.ok ? (it.valor || "—") : it.requerido ? "falta" : "—"}</span>
                  </li>
                ))}
              </ul>
              {!sel.datosLiquidacion.lista && (
                <p className="mt-2 text-sm text-red-600">
                  No se puede originar: completá {sel.datosLiquidacion.faltantes.join(", ")}.
                </p>
              )}
            </div>
          )}

          <div className="mt-4">
            <button onClick={() => setCronoAbierto((v) => !v)} className="text-sm text-gray-600 hover:text-gray-900">
              {cronoAbierto ? "▾" : "▸"} Cronograma estimado
              {crono.length > 0 ? ` · ${crono.length} cuotas` : ""}{cargandoCrono ? " · calculando…" : ""}
            </button>
            {cronoAbierto && crono.length > 0 && (
              <div className="mt-2 max-h-60 overflow-auto border border-gray-200 rounded-lg">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                      <th className="px-3 py-2 text-left">Cuota</th><th className="px-3 py-2 text-left">Vencimiento</th>
                      <th className="px-3 py-2 text-right">Capital</th><th className="px-3 py-2 text-right">Interés</th>
                      <th className="px-3 py-2 text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {crono.map((q) => (
                      <tr key={q.numero_cuota}>
                        <td className="px-3 py-1.5 tabular-nums">{q.numero_cuota}</td>
                        <td className="px-3 py-1.5">{fecha(q.fecha_vencimiento)}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{money(q.capital)}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{money(q.interes)}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums font-semibold">{money(q.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {cronoAbierto && !cargandoCrono && !crono.length && (
              <p className="mt-2 text-sm text-gray-400">Sin cronograma disponible.</p>
            )}
          </div>

          {!["ORIGINADA", "ANULADA"].includes(sel.estado) && (
            <div className="mt-4">
              <Field label="Observación del asesor (para rechazar, es el motivo)">
                <textarea rows={2} maxLength={500} className="input w-full" value={obs}
                          onChange={(e) => setObs(e.target.value)}
                          placeholder="Nota interna que queda registrada en la solicitud…" />
              </Field>
            </div>
          )}

          {sel.estado === "ORIGINADA" && sel.contratoId && (
            <p className="mt-3"><Pill tono="brand">Originada · contrato {sel.contratoId.slice(0, 8)}</Pill></p>
          )}
          {sel.estado === "EN_EVALUACION" && sel.solicitanteTipo === "NO_REGISTRADO" && (
            <div className="mt-3">
              <Alerta tipo="warn">
                El cliente no está en el padrón. Para aprobar, vinculá un cliente existente o dalo de alta
                en <Link to="/modules/clientes/nuevo/humano" className="underline">Clientes</Link>.
              </Alerta>
            </div>
          )}
        </Modal>
      )}

      {vinculando && (
        <Modal
          titulo="Vincular cliente del padrón"
          ancho="max-w-md"
          onClose={() => setVinculando(null)}
          footer={<><span className="flex-1" /><Boton variante="secundario" onClick={() => setVinculando(null)}>Cancelar</Boton></>}
        >
          <p className="text-sm text-gray-500 mb-3">
            Elegí el cliente del padrón para {vinculando.numero}. El alta de personas se hace en el módulo Clientes.
          </p>
          <BuscadorCliente onSelect={(c) => c && vincularCliente(c)} autoFocus />
        </Modal>
      )}

      {altaCliente && sel && (
        <Modal titulo="Crear cliente con los datos de la solicitud" eyebrow={`${sel.numero} · alta en el módulo Clientes`}
               ancho="max-w-2xl" onClose={() => setAltaCliente(null)}
               footer={<>
                 <span className="flex-1" />
                 <Boton variante="secundario" onClick={() => setAltaCliente(null)}>Cancelar</Boton>
                 <Boton onClick={crearCliente} disabled={accionando}>{accionando ? "Creando…" : "Crear cliente"}</Boton>
               </>}>
          <p className="text-sm text-gray-500 mb-3">
            Revisá lo que declaró el solicitante y completá lo que falte (la web no trae el CUIL). Si la persona ya
            existe en Clientes (mismo documento), no se duplica: se vincula.
          </p>
          {altaErr && <div className="mb-3"><Alerta>{altaErr}</Alerta></div>}
          <div className="grid sm:grid-cols-2 gap-3">
            {[["apellido", "Apellido"], ["nombres", "Nombres"], ["dni", "DNI"], ["cuil", "CUIL"],
              ["email", "Email"], ["telefono", "Teléfono"], ["domicilio", "Domicilio"], ["localidad", "Localidad"]].map(([k, l]) => (
              <Field key={k} label={l}>
                <input className="input" value={altaCliente[k]} inputMode={["dni", "cuil", "telefono"].includes(k) ? "numeric" : undefined}
                       onChange={(e) => setAltaCliente((f) => ({ ...f, [k]: e.target.value }))} />
              </Field>
            ))}
          </div>
          {docs.length > 0 && (
            <label className="flex items-center gap-2 mt-4 text-sm text-gray-600">
              <input type="checkbox" checked={altaCliente.copiar_documentos}
                     onChange={(e) => setAltaCliente((f) => ({ ...f, copiar_documentos: e.target.checked }))} />
              Guardar los {docs.length} documento(s) adjuntos en la ficha del cliente
            </label>
          )}
        </Modal>
      )}

      {viendoDoc != null && sel && docs[viendoDoc] && (
        <VisorDocumento docs={docs} inicial={viendoDoc} etiquetas={TIPODOC} eyebrow="Documentación del solicitante"
                        cargar={(d) => creditos.ppSolicitudDocArchivo(sel.id, d.id)}
                        onClose={() => setViendoDoc(null)} />
      )}

      {confirmando && (
        <Confirmacion
          titulo={confirmando.titulo}
          mensaje={confirmando.mensaje}
          confirmar={confirmando.confirmar}
          ocupado={accionando}
          onConfirmar={confirmando.onSi}
          onCancelar={() => setConfirmando(null)}
        />
      )}
    </>
  );
}
