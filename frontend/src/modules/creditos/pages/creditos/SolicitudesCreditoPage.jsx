import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { creditos } from "../../../../api/creditos";
import { PageHeader, Card, Field, Boton, Alerta, Modal } from "../../components/ui";
import { Pill } from "../../components/Pill";
import { DataTable } from "../../components/DataTable";
import { Confirmacion } from "../../components/Confirmacion";
import { VisorDocumento } from "../../components/VisorDocumento";
import { BuscadorCliente, nombreCliente } from "../../components/BuscadorCliente";
import { useSoloLectura } from "../../permisos";
import { fecha, fmtBytes } from "../../components/format";
import { CANAL_SOLICITUDES, resumenDocs, urlAltaCliente } from "./AltaClienteSolicitudPage";
import { CampoCbu, CampoSueldo, CondicionesCredito, enRangoDe } from "./solicitud/CondicionesCredito";
import { EditarSolicitud } from "./solicitud/EditarSolicitud";
import { AvisoCobro } from "./solicitud/AvisoCobro";
import { CAMPO_EDITADO, HistorialModificaciones, fechaHora } from "./solicitud/HistorialModificaciones";

const TONO_ESTADO = {
  BORRADOR: "neutral", EN_EVALUACION: "warn", OBSERVADA: "warn", APROBADA: "ok",
  RECHAZADA: "crit", ORIGINADA: "brand", ANULADA: "neutral",
};
const RELACIONES = ["ESTANDAR", "PREFERENCIAL", "PREMIUM"];
const ESTADO_LOTE = { ABIERTO: "abierto", CERRADO: "cerrado", CON_RESOLUCION: "con resolución",
                      PARA_LIQUIDAR: "para liquidar", LIQUIDADO: "liquidado" };
const TONO_LOTE = { ABIERTO: "warn", CERRADO: "neutral", CON_RESOLUCION: "brand", PARA_LIQUIDAR: "brand", LIQUIDADO: "ok" };
/** "Resolución N° 120/2026 · 15/3/2026" (el N° oficial si ya lo tiene; si no, el correlativo). */
export const textoResolucion = (r) =>
  `Resolución ${r.numeroOficial ? `N° ${r.numeroOficial}` : `correlativo ${r.numero}`}${r.anio ? `/${r.anio}` : ""}`
  + (r.fecha ? ` · ${fecha(r.fecha)}` : "");
const TIPODOC = { DNI_FRENTE: "DNI (frente)", DNI_DORSO: "DNI (dorso)", SELFIE_DNI: "Selfie con el DNI en la mano",
                  RECIBO: "Recibo de sueldo", CERTIFICADO_SERVICIOS: "Certificado de servicios",
                  CONSTANCIA_CBU: "Constancia de CBU", OTRO: "Otro" };

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
/** 20301234563 → "20-30123456-3" (si no son 11 dígitos, tal cual). */
const cuilFmt = (v) => {
  const d = String(v || "").replace(/\D/g, "");
  return d.length === 11 ? `${d.slice(0, 2)}-${d.slice(2, 10)}-${d[10]}` : String(v || "");
};
/** Situación laboral con el mismo texto que eligió el ciudadano en el portal. */
const SITUACION = {
  AGENTE_PUBLICO: "Empleado público provincial", MUNICIPAL: "Empleado municipal", DOCENTE: "Docente",
  JUBILADO: "Jubilado", PENSIONADO: "Pensionado", CONTRATADO: "Contratado / monotributo", LIBRE: "Otro / independiente",
};
/** Códigos de catálogo sin texto propio, legibles: CONVENIO → "Convenio". */
const humano = (cod) => String(cod || "").toLowerCase().replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
/** 30 → "2 años y 6 meses". */
const antiguedad = (meses) => {
  const a = Math.floor(meses / 12), m = meses % 12;
  const partes = [a && `${a} año${a === 1 ? "" : "s"}`, m && `${m} mes${m === 1 ? "" : "es"}`].filter(Boolean);
  return partes.length ? partes.join(" y ") : "Menos de un mes";
};

const DESTINO = {
  VIVIENDA: "Vivienda / refacción", VEHICULO: "Vehículo", CONSUMO: "Consumo / gastos personales",
  EDUCACION: "Educación", SALUD: "Salud", REFINANCIACION: "Refinanciación de deudas",
  EMPRENDIMIENTO: "Emprendimiento / negocio", OTRO: "Otro",
};
const PASOS = ["Solicitante", "Simulación", "Confirmación"];

/** Años declarados → meses, que es como lo guarda la solicitud. Vacío = sin valor. */
const aniosAMeses = (v) => {
  const n = parseFloat(String(v).replace(",", "."));
  return String(v).trim() === "" || isNaN(n) ? "" : String(Math.max(0, Math.min(1200, Math.round(n * 12))));
};

const FORM_VACIO = {
  producto_id: "", monto_solicitado: 1000000, plazo_solicitado: 24,
  segmento: "", canal: "SUCURSAL", fecha_nacimiento: "", antiguedad_meses: "", relacion: "ESTANDAR", sueldo: "",
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
  const [lineasTodas, setLineasTodas] = useState([]);   // para corregir: también las líneas sólo web del portal
  const [cat, setCat] = useState({ segmentos: [], canales: [] });

  // Alta (asistente de 3 pasos)
  const [nueva, setNueva] = useState(false);
  const [paso, setPaso] = useState(1);
  const [cliente, setCliente] = useState(null);
  const [form, setForm] = useState(FORM_VACIO);
  const [sim, setSim] = useState(null);
  const [precarga, setPrecarga] = useState(null);   // lo que vino del padrón al elegir el cliente
  const [editando, setEditando] = useState(null);    // corrección de una solicitud en curso
  const [enPadron, setEnPadron] = useState(null);    // la persona de una express, si ya está en el padrón
  const [creando, setCreando] = useState(false);

  // Detalle de una solicitud
  const [sel, setSel] = useState(null);
  const selRef = useRef(null);
  selRef.current = sel;
  const [docs, setDocs] = useState([]);
  const [docsPedidos, setDocsPedidos] = useState([]);       // lo que pide la línea (para observar)
  const [observando, setObservando] = useState(null);       // { detalle, documentos: [], cbu }
  const [docsFaltantes, setDocsFaltantes] = useState([]);   // obligatorios de la línea que no llegaron
  const [viendoDoc, setViendoDoc] = useState(null);   // índice del documento abierto en el visor
  const [crono, setCrono] = useState([]);
  const [cronoAbierto, setCronoAbierto] = useState(false);
  const [cargandoCrono, setCargandoCrono] = useState(false);
  const [obs, setObs] = useState("");
  const [detErr, setDetErr] = useState("");
  const [accionando, setAccionando] = useState(false);
  const [confirmando, setConfirmando] = useState(null);
  const [vinculando, setVinculando] = useState(null);      // solicitud express a vincular
  const [detOk, setDetOk] = useState(null);                // { texto, clienteId } tras crear/vincular/guardar docs

  const decimales = Math.max(0, Math.min(6, cat.decimalesMostrar ?? 2));
  const columnas = [
    { key: "numero", label: "N°", sortable: true, filtro: "texto",
      render: (s) => <span className="font-medium">{s.numero}</span> },
    { key: "clienteNombre", label: "Cliente", sortable: true, filtro: "texto",
      render: (s) => (<>
        {s.clienteNombre}
        {s.solicitanteTipo === "NO_REGISTRADO" && <span className="ml-2"><Pill>express</Pill></span>}
      </>) },
    { key: "clienteCuil", label: "CUIL", sortable: true, filtro: "texto",
      render: (s) => <span className="tabular-nums whitespace-nowrap">{cuilFmt(s.clienteCuil) || "—"}</span> },
    { key: "productoNombre", label: "Línea", sortable: true, filtro: "opciones",
      render: (s) => (
        <span title={s.productoCodigo || ""}>{s.productoNombre || s.productoCodigo || "—"}</span>
      ) },
    { key: "monto", label: "Monto", align: "right", sortable: true, render: (s) => money(s.monto) },
    { key: "plazo", label: "Plazo", align: "right", sortable: true },
    { key: "cuota", label: "Cuota est.", align: "right", sortable: true,
      sortValue: (s) => s.evaluacion?.cuota_estimada || 0, render: (s) => money(s.evaluacion?.cuota_estimada || 0) },
    { key: "estado", label: "Estado", sortable: true, filtro: "opciones",
      render: (s) => <Pill tono={TONO_ESTADO[s.estado] || "neutral"}>{s.estado}</Pill> },
    { key: "elegible", label: "Elegible", sortable: true, filtro: "opciones",
      sortValue: (s) => (s.evaluacion?.elegible ? "Sí" : "No"), render: (s) => (s.evaluacion?.elegible ? "Sí" : "No") },
  ];
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
    creditos.ppOferta({}).then((d) => setLineasTodas(d.items)).catch(() => {});
  }, []);

  // Al abrir una solicitud: documentación, cronograma estimado y observación previa.
  useEffect(() => {
    setViendoDoc(null); setDetOk(null); setEnPadron(null);
    // Una express puede ser de alguien que ya está en el padrón (llegó con el CUIL y el padrón lo tiene
    // por DNI, o lo dieron de alta después): el detalle del backend lo busca y se sugiere vincularlo.
    if (sel?.id && sel.solicitanteTipo === "NO_REGISTRADO") {
      Promise.resolve(creditos.ppSolicitud(sel.id)).then((d) => setEnPadron(d?.clienteEnPadron || null)).catch(() => {});
    }
    if (!sel?.id) { setDocs([]); setDocsFaltantes([]); setCrono([]); return; }
    setObs(sel.datosAdicionales?.obs_revision || ""); setDetErr(""); setCronoAbierto(false);
    creditos.ppSolicitudDocs(sel.id)
      .then((d) => { setDocs(d.items); setDocsFaltantes(d.faltantes || []); setDocsPedidos(d.pedidos || []); })
      .catch(() => { setDocs([]); setDocsFaltantes([]); });
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
  const lineaForm = lineas.find((l) => l.id === form.producto_id) || null;
  const paso2OK = !!lineaForm && !!sim && sim.elegible !== false;
  const cbuForm = String(form.datos_adicionales.cbu || "").replace(/\D/g, "");
  const cbuOK = cbuForm.length === 22;

  /** Monto y cuotas dentro del rango de la línea (al cambiarla o al entrar al paso 2). */
  const enRango = (f, l) => {
    const { monto, plazo } = enRangoDe(l, f.monto_solicitado, f.plazo_solicitado);
    return { ...f, monto_solicitado: monto, plazo_solicitado: plazo };
  };

  /** Al elegir el cliente se precarga lo que el padrón ya sabe: nacimiento, antigüedad, sueldo y CBU. */
  async function elegirCliente(c) {
    setCliente(c); setPrecarga(null);
    if (!c) return;
    try {
      const d = await creditos.ppDatosCliente(c.id);
      setPrecarga(d);
      setForm((f) => ({
        ...f,
        fecha_nacimiento: d.fecha_nacimiento || "",
        antiguedad_meses: d.antiguedad_meses == null ? "" : String(d.antiguedad_meses),
        sueldo: d.sueldo || "",
        datos_adicionales: { ...f.datos_adicionales, cbu: d.cbu || "" },
      }));
    } catch { /* sin padrón se carga a mano */ }
  }

  function abrirNueva() {
    setNueva(true); setSel(null); setPaso(1); setSim(null); setError(""); setCliente(null); setPrecarga(null);
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
        antiguedad_meses: form.antiguedad_meses === "" ? null : Number(form.antiguedad_meses),
        datos_adicionales: {
          ...form.datos_adicionales,
          ...(Number(form.sueldo) > 0 ? { sueldo_declarado: Number(form.sueldo) } : {}),
        },
      };
      delete payload.sueldo;
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
      const motivo = accion === "rechazar" || accion === "anular" ? obs.trim() : "";
      setSel(await creditos.ppSolicitudEstado(s.id, accion, motivo, obs.trim()));
      cargar();
    } catch (e) { setDetErr(e.message); }
    finally { setAccionando(false); setConfirmando(null); }
  }

  /** Abre el pedido de corrección con los obligatorios que no llegaron ya marcados. */
  const abrirObservar = () => {
    const faltan = docsPedidos.filter((d) => docsFaltantes.includes(d.titulo)).map((d) => d.tipo);
    setObservando({ detalle: "", documentos: faltan, cbu: false });
  };
  async function observar() {
    setAccionando(true); setDetErr("");
    try {
      setSel(await creditos.ppSolicitudEstado(sel.id, "observar", "", "", {
        detalle: observando.detalle.trim(), documentos: observando.documentos, corregir_cbu: observando.cbu }));
      setObservando(null);
      setOk(`${sel.numero} quedó observada: el solicitante ve el pedido en el portal.`);
      cargar();
    } catch (e) { setDetErr(e.message); setObservando(null); }
    finally { setAccionando(false); }
  }

  async function vincularCliente(c, solicitud = vinculando) {
    setDetErr("");
    try {
      const r = await creditos.ppSolicitudPromover(solicitud.id, { cliente_id: c.id });
      setVinculando(null); setEnPadron(null); setSel(r.solicitud); cargar();
      const texto = `Cliente ${r.solicitud.clienteNombre || nombreCliente(c)} vinculado a la solicitud.${resumenDocs(r.documentos)}`;
      setOk(texto); setDetOk({ texto, clienteId: r.clienteId });
    } catch (e) { setDetErr(e.message); }
  }

  /** El alta se abre en otra solapa, para seguir viendo el detalle y los anexos mientras se carga. */
  const abrirAltaCliente = (s) => window.open(urlAltaCliente(s.id), "_blank");

  // Cuando la otra solapa crea/vincula el cliente, el detalle abierto se actualiza solo.
  useEffect(() => {
    let canal;
    try { canal = new BroadcastChannel(CANAL_SOLICITUDES); } catch { return undefined; }
    canal.onmessage = ({ data }) => {
      if (data?.tipo !== "cliente-vinculado" || !data.solicitud) return;
      cargar();
      if (selRef.current?.id !== data.solicitud.id) return;
      setSel(data.solicitud); setOk(data.texto); setDetOk({ texto: data.texto, clienteId: data.clienteId });
    };
    return () => canal.close();
  }, [filtro, q]); // eslint-disable-line

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
  const congelada = !!sel?.lote && sel.lote.estado !== "ABIERTO";
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
                 placeholder="Buscar cliente, CUIL o N°…" aria-label="Buscar cliente o número" />
        </div>

        <DataTable columns={columnas} rows={items} clientSort rowKey={(s) => s.id}
                   onRowClick={(s) => { setSel(s); setNueva(false); }} emptyText="Sin solicitudes." />
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
                <Boton disabled={!paso1OK} onClick={() => { setForm((f) => enRango(f, lineaForm)); setPaso(2); }}>Continuar →</Boton>
              )}
              {paso === 2 && (
                <Boton disabled={!paso2OK}
                       title={sim?.elegible === false ? "No cumple las condiciones de la línea" : ""}
                       onClick={() => setPaso(3)}>Continuar →</Boton>
              )}
              {paso === 3 && (
                <>
                  <Boton variante="secundario" disabled={creando || sim?.elegible === false} onClick={() => crear(false)}>
                    Guardar borrador
                  </Boton>
                  <Boton disabled={creando || sim?.elegible === false || !cbuOK}
                         title={cbuOK ? "" : "Cargá el CBU de acreditación (22 dígitos) para enviarla."}
                         onClick={() => crear(true)}>
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
                <BuscadorCliente seleccionado={cliente} onSelect={elegirCliente} />
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
                {/* Se declara en años (lo que dice el recibo); el formulario la guarda en meses. */}
                <Field label="Antigüedad laboral (años)">
                  <input type="number" min={0} max={100} step="0.5" className="input w-full"
                         value={form.antiguedad_meses === "" ? "" : Number(form.antiguedad_meses) / 12}
                         onChange={(e) => setForm({ ...form, antiguedad_meses: aniosAMeses(e.target.value) })} />
                </Field>
                <CampoSueldo valor={form.sueldo} onChange={(v) => setForm({ ...form, sueldo: v })} />
              </div>
              {precarga && (
                <p className="text-xs text-gray-500 mt-2">
                  Datos traídos del padrón de clientes
                  {[!precarga.fecha_nacimiento && "sin fecha de nacimiento", !precarga.sueldo && "sin sueldo",
                    precarga.antiguedad_meses == null && "sin fecha de ingreso", !precarga.cbu && "sin CBU"]
                    .filter(Boolean).map((x, i) => `${i ? ", " : " ("}${x}`).join("")}{
                    [!precarga.fecha_nacimiento, !precarga.sueldo, precarga.antiguedad_meses == null, !precarga.cbu].some(Boolean) ? ")" : ""}.
                  {" "}Se pueden corregir para esta solicitud.
                </p>
              )}
            </>
          )}

          {paso === 2 && (
            <>
              <Field label="Línea">
                <select className="input w-full" value={form.producto_id}
                        onChange={(e) => { setForm(enRango({ ...form, producto_id: e.target.value }, lineas.find((l) => l.id === e.target.value))); setSim(null); }}>
                  {lineas.map((l) => <option key={l.id} value={l.id}>{l.nombre} ({l.codigo})</option>)}
                </select>
              </Field>
              <div className="mt-4">
                <CondicionesCredito linea={lineaForm} monto={Number(form.monto_solicitado)} plazo={Number(form.plazo_solicitado)}
                                    sueldo={form.sueldo} money={money} onSim={setSim}
                                    perfil={{ segmento: form.segmento, canal: form.canal, fecha_nacimiento: form.fecha_nacimiento,
                                              antiguedad_meses: form.antiguedad_meses }}
                                    onChange={({ monto, plazo }) => setForm((f) => ({ ...f, monto_solicitado: monto, plazo_solicitado: plazo }))} />
              </div>
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
                {Number(form.sueldo) > 0 && (
                  <div className="flex justify-between border-b border-gray-100 py-1">
                    <dt className="text-gray-500">Sueldo neto</dt>
                    <dd>{money(Number(form.sueldo))}{sim?.afectacion != null ? ` · cuota ${String(sim.afectacion).replace(".", ",")}%` : ""}</dd></div>
                )}
              </dl>
              {lineaForm?.cobro && (
                <div className="mt-4">
                  <AvisoCobro cobro={lineaForm.cobro} cuota={sim?.primeraCuota} money={money}
                              titulo="Avisale al solicitante cómo se cobra" />
                </div>
              )}
              <div className="mt-4">
                <CampoCbu valor={form.datos_adicionales.cbu} requerido
                          onChange={(v) => setForm({ ...form, datos_adicionales: { ...form.datos_adicionales, cbu: v } })} />
                <p className="text-xs text-gray-500 mt-1">
                  {precarga?.cbu && cbuForm === precarga.cbu ? "Es el CBU del cliente en el padrón. " : ""}
                  A esta cuenta se transfiere el desembolso; sin CBU la solicitud no entra a un lote de liquidación.
                </p>
              </div>
              {/* El destino del crédito ya no se pregunta; las solicitudes viejas lo siguen mostrando. */}
              <div className="grid gap-3 sm:grid-cols-2 mt-4">
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
              {sel.editable && puedeEditar && (
                <Boton variante="secundario" disabled={accionando} onClick={() => setEditando(sel)}>Modificar</Boton>
              )}
              {sel.estado === "BORRADOR" && (
                <Boton disabled={accionando || !puedeEditar} onClick={() => resolver("enviar")}>Enviar a evaluación</Boton>
              )}
              {!["ORIGINADA", "ANULADA"].includes(sel.estado) && (
                <Boton variante="secundario" disabled={accionando || !puedeEditar || congelada}
                       title={congelada ? "Está en un lote con resolución: no se modifica."
                         : "Baja administrativa del trámite (no es una decisión crediticia)."}
                       onClick={() => setConfirmando({
                         titulo: "Anular solicitud",
                         mensaje: `¿Anular ${sel.numero}? Es una baja administrativa del trámite, no una decisión crediticia.`,
                         confirmar: "Anular",
                         onSi: () => resolver("anular"),
                       })}>Anular</Boton>
              )}
              {sel.estado === "EN_EVALUACION" && sel.origen === "PORTAL" && (
                <Boton variante="secundario" disabled={accionando || !puedeEditar}
                       title="Le pide al solicitante que corrija documentación o datos desde el portal."
                       onClick={abrirObservar}>Observar</Boton>
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

          {enPadron && sel.solicitanteTipo === "NO_REGISTRADO" && (
            <div className="mb-3">
              <Alerta tipo="warn">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="flex-1">
                    Esta persona ya está en el padrón de clientes: <b>{enPadron.nombre}</b> ({enPadron.documento}).
                  </span>
                  {puedeEditar && (
                    <Boton disabled={accionando} onClick={() => vincularCliente({ id: enPadron.id }, sel)}>
                      Vincular a este cliente
                    </Boton>
                  )}
                </span>
              </Alerta>
            </div>
          )}
          {sel.ultimaModificacion && (
            <p className="text-xs text-gray-500 mb-3">
              Modificada por <b>{sel.ultimaModificacion.por}</b> el {fechaHora(sel.ultimaModificacion.en)}
              {sel.ultimaModificacion.campos?.length ? ` (${sel.ultimaModificacion.campos.map((c) => (CAMPO_EDITADO[c] || c).toLowerCase()).join(", ")})` : ""}
              {(sel.datosAdicionales?.modificaciones || []).length > 1 ? ` · ${sel.datosAdicionales.modificaciones.length} modificaciones` : ""}.
            </p>
          )}
          <dl className="grid sm:grid-cols-3 gap-3 text-sm">
            <div><dt className="text-xs text-gray-500">Línea</dt>
              <dd className="font-medium">{[...lineas, ...lineasTodas].find((l) => l.id === sel.productoId)?.nombre || sel.productoId}</dd></div>
            <div><dt className="text-xs text-gray-500">Monto</dt><dd className="font-medium">{money(sel.monto)}</dd></div>
            <div><dt className="text-xs text-gray-500">Plazo</dt><dd className="font-medium">{sel.plazo} cuotas</dd></div>
            <div><dt className="text-xs text-gray-500">TNA ofrecida</dt>
              <dd className="font-medium">{sel.evaluacion?.tna_ofrecida ?? "—"}%</dd></div>
            <div><dt className="text-xs text-gray-500">Cuota estimada</dt>
              <dd className="font-medium">{money(sel.evaluacion?.cuota_estimada || 0)}</dd></div>
            <div><dt className="text-xs text-gray-500">Relación</dt><dd className="font-medium">{sel.relacion}</dd></div>
            <div><dt className="text-xs text-gray-500">Origen</dt>
              <dd className="font-medium">{sel.origen === "PORTAL" ? "Portal web" : sel.canal ? humano(sel.canal) : "Sucursal"}</dd></div>
            {sel.clienteCuil && (
              <div><dt className="text-xs text-gray-500">CUIL</dt><dd className="font-medium tabular-nums">{cuilFmt(sel.clienteCuil)}</dd></div>
            )}
            {sel.segmento && (
              <div><dt className="text-xs text-gray-500">Situación laboral</dt>
                <dd className="font-medium">{SITUACION[sel.segmento] || humano(sel.segmento)}</dd></div>
            )}
            {sel.antiguedadMeses != null && (
              <div><dt className="text-xs text-gray-500">Antigüedad laboral</dt>
                <dd className="font-medium">{antiguedad(sel.antiguedadMeses)}</dd></div>
            )}
            {sel.datosAdicionales?.sueldo_declarado > 0 && (
              <div><dt className="text-xs text-gray-500">Sueldo neto declarado</dt>
                <dd className="font-medium tabular-nums">{money(sel.datosAdicionales.sueldo_declarado)}</dd></div>
            )}
            {sel.datosAdicionales?.afectacion != null && (
              <div><dt className="text-xs text-gray-500">Afectación (cuota / sueldo)</dt>
                <dd className="font-medium tabular-nums">{String(sel.datosAdicionales.afectacion).replace(".", ",")}%</dd></div>
            )}
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
            {sel.datosAdicionales?.consentimiento && (
              <div><dt className="text-xs text-gray-500">Términos y tratamiento de datos</dt>
                <dd className="font-medium">Aceptados{sel.datosAdicionales.consentimiento.fecha
                  ? ` el ${fecha(sel.datosAdicionales.consentimiento.fecha)}` : ""}</dd></div>
            )}
            {sel.datosAdicionales?.videos_vistos?.videos?.length > 0 && (
              <div><dt className="text-xs text-gray-500">Videos obligatorios</dt>
                <dd className="font-medium">Vio {sel.datosAdicionales.videos_vistos.videos.length}
                  {sel.datosAdicionales.videos_vistos.fecha ? ` · ${fecha(sel.datosAdicionales.videos_vistos.fecha)}` : ""}</dd></div>
            )}
            {/* Lo que pidió la línea (componente "Documentación y datos"), tal como se preguntó. */}
            {(sel.datosAdicionales?.requisitos || []).map((r) => (
              <div key={r.codigo}><dt className="text-xs text-gray-500">{r.etiqueta}</dt>
                <dd className="font-medium">{r.valores.length ? r.valores.join(", ") : "—"}</dd></div>
            ))}
          </dl>

          {sel.datosAdicionales?.cobro && (
            <div className="mt-3">
              <AvisoCobro cobro={sel.datosAdicionales.cobro} cuota={sel.evaluacion?.cuota_estimada} money={money}
                          titulo="Cómo se cobra (lo que se le avisó)" />
            </div>
          )}
          {sel.evaluacion?.motivos?.length > 0 && (
            <div className="mt-3"><Alerta>No elegible: {sel.evaluacion.motivos.join(" · ")}</Alerta></div>
          )}
          {sel.motivoRechazo && <p className="mt-3 text-sm text-gray-500">Motivo: {sel.motivoRechazo}</p>}
          {sel.datosAdicionales?.observaciones && (
            <p className="mt-2 text-sm text-gray-500">Nota del solicitante: {sel.datosAdicionales.observaciones}</p>
          )}

          {(sel.datosAdicionales?.correcciones || []).length > 0 && (
            <div className="mt-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">Observaciones al solicitante</h3>
              <ul className="flex flex-col gap-2">
                {[...sel.datosAdicionales.correcciones].reverse().map((o, i) => (
                  <li key={o.fecha + i} className="border border-gray-200 rounded-lg p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      {o.respondida
                        ? <Pill tono="ok">Corregida · {fecha(o.respondida)}</Pill>
                        : <Pill tono="warn">Esperando al solicitante</Pill>}
                      <span className="text-xs text-gray-500">{fecha(o.fecha)} · {o.por}</span>
                    </div>
                    <p className="text-gray-800 whitespace-pre-line">{o.detalle}</p>
                    {(o.documentos?.length > 0 || o.cbu) && (
                      <p className="text-xs text-gray-500 mt-1">
                        Pidió: {[...(o.documentos || []).map((t) => docsPedidos.find((d) => d.tipo === t)?.titulo || t),
                                 ...(o.cbu ? ["corregir el CBU"] : [])].join(", ")}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <HistorialModificaciones modificaciones={sel.datosAdicionales?.modificaciones || []} money={money}
                                   nombreLinea={(id) => [...lineas, ...lineasTodas].find((l) => l.id === id)?.nombre || id} />

          {docsFaltantes.length > 0 && (
            <div className="mt-3"><Alerta tipo="warn">Falta documentación obligatoria: {docsFaltantes.join(", ")}.</Alerta></div>
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
                  <Pill>{d.titulo || TIPODOC[d.tipo] || d.tipo}</Pill>
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
                  No se puede liquidar: completá {sel.datosLiquidacion.faltantes.join(", ")}.
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
          {sel.lote ? (
            <div className="mt-3">
              <p className="flex flex-wrap items-center gap-2">
                <Pill tono={TONO_LOTE[sel.lote.estado] || "neutral"}>Lote {sel.lote.codigo} · {ESTADO_LOTE[sel.lote.estado] || sel.lote.estado}</Pill>
                {sel.lote.resolucion && <Pill tono="ok">{textoResolucion(sel.lote.resolucion)}</Pill>}
              </p>
              {sel.lote.estado === "ABIERTO" && (
                <p className="text-sm text-gray-500 mt-1">El lote espera que lo verifiquen y lo cierren; después Despacho le asigna la resolución que lo otorga.</p>
              )}
              {sel.lote.estado === "CERRADO" && (
                <p className="text-sm text-gray-500 mt-1">Espera que Despacho le asigne al lote la resolución que lo otorga.</p>
              )}
              {sel.lote.estado === "PARA_LIQUIDAR" && (
                <p className="text-sm text-gray-500 mt-1">En la orden de pago {sel.lote.ordenPago} de Tesorería: se liquida al acreditarse la transferencia.</p>
              )}
              {["CERRADO", "CON_RESOLUCION"].includes(sel.lote.estado) && (
                <div className="mt-2">
                  <Alerta tipo="warn">
                    Está en un lote {sel.lote.estado === "CERRADO" ? "cerrado" : "con resolución"}: no se modifica. Si hace falta, se puede pasar a otro lote en{" "}
                    <Link to="/modules/creditos/liquidacion-lote" className="underline">Créditos → Lotes</Link>.
                  </Alerta>
                </div>
              )}
            </div>
          ) : sel.resolucion ? (
            <p className="mt-3">
              <Pill tono="ok">Resolución N° {sel.resolucion.numero}{sel.resolucion.fecha ? ` · ${fecha(sel.resolucion.fecha)}` : ""}</Pill>
            </p>
          ) : null}
          {sel.estado === "APROBADA" && !sel.lote && sel.faltaParaLote?.length > 0 && (
            <div className="mt-3">
              <Alerta tipo="warn">
                No entra a ningún lote porque no se puede liquidar: falta {sel.faltaParaLote.join(", ")}.
                Cuando se complete, entra sola al lote que le corresponde.
              </Alerta>
            </div>
          )}
          {sel.estado === "EN_EVALUACION" && sel.solicitanteTipo === "NO_REGISTRADO" && (
            <div className="mt-3">
              <Alerta tipo="warn">
                El cliente no está en el padrón. Para aprobar, vinculá un cliente existente o dalo de alta
                en <a href={urlAltaCliente(sel.id)} target="_blank" rel="noopener" className="underline">Clientes</a>.
              </Alerta>
            </div>
          )}
        </Modal>
      )}

      {/* Después del detalle: con el mismo z-index, el que va último en el DOM queda arriba. */}
      {editando && (
        <EditarSolicitud solicitud={editando} lineas={lineasTodas.length ? lineasTodas : lineas} segmentos={cat.segmentos}
                         money={money} onClose={() => setEditando(null)}
                         onGuardada={(r) => { setEditando(null); setSel(r); setOk(`${r.numero} modificada.`); cargar(); }} />
      )}

      {observando && (
        <Modal
          titulo="Observar solicitud"
          eyebrow={`${sel.numero} · el solicitante corrige desde el portal`}
          ancho="max-w-lg"
          onClose={() => setObservando(null)}
          footer={<>
            <span className="flex-1" />
            <Boton variante="secundario" onClick={() => setObservando(null)}>Cancelar</Boton>
            <Boton disabled={accionando || !observando.detalle.trim()} onClick={observar}>Observar</Boton>
          </>}
        >
          <Field label="Explicación para el solicitante">
            <textarea className="input w-full" rows={4} value={observando.detalle} maxLength={1000} autoFocus
                      placeholder="Ej.: La foto del DNI está borrosa y falta el certificado de servicios."
                      onChange={(e) => setObservando((o) => ({ ...o, detalle: e.target.value }))} />
          </Field>
          {docsPedidos.length > 0 && (
            <fieldset className="mt-4">
              <legend className="text-sm font-medium text-gray-700 mb-1">Documentos a adjuntar o reemplazar</legend>
              {docsPedidos.map((d) => (
                <label key={d.tipo} className="flex items-center gap-2 text-sm text-gray-700 py-0.5">
                  <input type="checkbox" checked={observando.documentos.includes(d.tipo)}
                         onChange={(e) => setObservando((o) => ({ ...o, documentos: e.target.checked
                           ? [...o.documentos, d.tipo] : o.documentos.filter((t) => t !== d.tipo) }))} />
                  {d.titulo}
                  {docsFaltantes.includes(d.titulo) && <Pill tono="warn">falta</Pill>}
                </label>
              ))}
            </fieldset>
          )}
          <label className="flex items-center gap-2 text-sm text-gray-700 mt-3">
            <input type="checkbox" checked={observando.cbu}
                   onChange={(e) => setObservando((o) => ({ ...o, cbu: e.target.checked }))} />
            Corregir el CBU de acreditación
          </label>
          <p className="text-xs text-gray-500 mt-3">
            La solicitud queda observada: no se aprueba ni se rechaza hasta que el solicitante corrija y la reenvíe.
          </p>
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

      {viendoDoc != null && sel && docs[viendoDoc] && (
        <VisorDocumento docs={docs} inicial={viendoDoc} etiquetas={{ ...TIPODOC, ...Object.fromEntries(docs.map((d) => [d.tipo, d.titulo || TIPODOC[d.tipo] || d.tipo])) }}
                        eyebrow="Documentación del solicitante"
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
