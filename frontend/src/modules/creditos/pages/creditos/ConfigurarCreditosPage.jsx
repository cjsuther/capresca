import { useEffect, useMemo, useState } from "react";
import { creditos } from "../../../../api/creditos";
import { PageHeader, Card, Field, Boton, Alerta, Modal } from "../../components/ui";
import { Pill } from "../../components/Pill";
import { Confirmacion } from "../../components/Confirmacion";
import { DataTable } from "../../components/DataTable";
import { MenuAcciones } from "../../components/MenuAcciones";
import { useSoloLectura } from "../../permisos";
import { fecha } from "../../components/format";
import { EditorComponente } from "./configurar/EditorComponente";
import {
  CFG_DEFAULT, ESTADO_LABEL, ESTADO_TONO, ICONOS, LIFECYCLE, SEGMENTOS, CANALES,
  diffVersiones, esDefault, previewPayload, toFilas, valida,
} from "./configurar/esquemas";

const money = (n) => (isFinite(n)
  ? new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 }).format(n)
  : "—");

/**
 * Configurar Créditos — product builder por componentes (Property Classes): catálogo de líneas,
 * editor por componente con prueba en vivo contra el motor del backend, ciclo de vida con
 * cuatro-ojos, versionado y comparación.
 */
export default function ConfigurarCreditosPage() {
  const soloLectura = useSoloLectura();
  const [productos, setProductos] = useState([]);
  const [permisos, setPermisos] = useState({ edita: false, aprueba: false });
  const [usuario, setUsuario] = useState("");
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const [vista, setVista] = useState("catalogo");
  // Vista del catálogo: tarjetas (como el sistema anterior) o en línea. Se recuerda por usuario/navegador.
  const [catVista, setCatVista] = useState(() => {
    try { return localStorage.getItem("creditos_cfg_vista") || "tarjetas"; } catch { return "tarjetas"; }
  });
  const cambiarVista = (v) => { setCatVista(v); try { localStorage.setItem("creditos_cfg_vista", v); } catch { /* ignore */ } };
  const [activoId, setActivoId] = useState(null);
  const [nuevaVerDe, setNuevaVerDe] = useState(null);
  const [filtro, setFiltro] = useState("TODOS");

  const [monto, setMonto] = useState(1200000);
  const [plazo, setPlazo] = useState(24);
  const [sel, setSel] = useState("TERM_AMOUNT");
  const [visitados, setVisitados] = useState(new Set(["TERM_AMOUNT"]));
  const [probar, setProbar] = useState(false);
  const [sims, setSims] = useState([]);
  const [simEtiq, setSimEtiq] = useState("");
  const [baseline, setBaseline] = useState(null);

  const [nuevoOpen, setNuevoOpen] = useState(false);
  const [familias, setFamilias] = useState([]);
  const [nuevo, setNuevo] = useState({ nombre: "", familia_id: "", copiar_de: "", heredar: false });

  const [inspOpen, setInspOpen] = useState(false);
  const [raw, setRaw] = useState(null);
  const [cmpOpen, setCmpOpen] = useState(false);
  const [versiones, setVersiones] = useState([]);
  const [cmpA, setCmpA] = useState(0);
  const [cmpB, setCmpB] = useState(0);
  const [confirmando, setConfirmando] = useState(null);
  const [duplicando, setDuplicando] = useState(null);
  const [nombreCopia, setNombreCopia] = useState("");

  const [impuestos, setImpuestos] = useState([]);
  const [indices, setIndices] = useState([]);
  const [catSegmentos, setCatSegmentos] = useState(SEGMENTOS);
  const [catCanales, setCatCanales] = useState(CANALES);

  const [filas, setFilas] = useState([]);
  const [res, setRes] = useState({ totalCuotas: 0, totalInteres: 0, totalCargos: 0, tea: 0, cft: 0 });
  const [filasBase, setFilasBase] = useState([]);

  useEffect(() => {
    creditos.ppCatalogo().then((d) => {
      setProductos(d.items);
      if (d.permisos) setPermisos(d.permisos);
      if (d.usuario) setUsuario(d.usuario);
      // Deep-link desde el Inbox de aprobaciones: abre directo la línea a revisar.
      const abrirId = sessionStorage.getItem("configurar_abrir_producto");
      if (abrirId) {
        sessionStorage.removeItem("configurar_abrir_producto");
        const p = d.items.find((x) => x.id === abrirId);
        if (p) abrir(p);
      }
    }).catch((e) => setError(e.message)).finally(() => setCargando(false));
    creditos.ppFamilias().then((d) => setFamilias(d.items)).catch(() => {});
    creditos.impuestos("activos").then((d) => setImpuestos(d.items)).catch(() => {});
    creditos.indices().then((d) => setIndices(d.items)).catch(() => {});
    creditos.ctoSegmentos().then((d) => {
      if (Array.isArray(d?.segmentos)) setCatSegmentos(d.segmentos);
      if (Array.isArray(d?.canales)) setCatCanales(d.canales);
    }).catch(() => {});
  }, []); // eslint-disable-line

  const activo = productos.find((p) => p.id === activoId) || null;
  const cfg = activo?.cfg || CFG_DEFAULT;
  const comps = activo?.componentes || [];

  const upsert = (p) => setProductos((ps) => (ps.some((x) => x.id === p.id)
    ? ps.map((x) => (x.id === p.id ? p : x)) : [p, ...ps]));

  // Editar una condición núcleo rompe su herencia (pasa a "propia").
  const setCfg = (patch) => activo && setProductos((ps) => ps.map((p) => (p.id === activoId
    ? { ...p, cfg: { ...p.cfg, ...patch }, cfgHeredada: false } : p)));
  const setCompCfg = (cod, patch) => setProductos((ps) => ps.map((p) => (p.id === activoId
    ? { ...p, componentes: p.componentes.map((c) => (c.codigo === cod
        ? { ...c, config: { ...c.config, ...patch }, heredado: false } : c)) } : p)));
  const toggleComp = (cod, on) => setProductos((ps) => ps.map((p) => (p.id === activoId
    ? { ...p, componentes: p.componentes.map((c) => (c.codigo === cod ? { ...c, activo: on, heredado: false } : c)) } : p)));

  const payload = (p) => ({
    ...p.cfg, cfgHeredada: !!p.cfgHeredada,
    componentes: p.componentes.map((c) => ({ codigo: c.codigo, activo: c.activo, config: c.config, heredado: !!c.heredado })),
  });

  const conError = (fn) => async (...args) => {
    setError(""); setOk("");
    try { await fn(...args); } catch (e) { setError(e.message); }
  };

  function abrir(p, verDe = null) {
    setActivoId(p.id); setNuevaVerDe(verDe); setSel("TERM_AMOUNT");
    setVisitados(new Set(["TERM_AMOUNT"])); setProbar(false); setVista("builder");
    setSims([]); setSimEtiq("");
    setBaseline({ cfg: structuredClone(p.cfg), comps: structuredClone(p.componentes) });
    creditos.ppSimListar(p.id).then((d) => setSims(d.items)).catch(() => {});
  }

  const reheredarCfg = conError(async () => upsert(await creditos.ppGuardarConfig(activo.id, payload({ ...activo, cfgHeredada: true }))));
  const reheredarComp = conError(async (cod) => upsert(await creditos.ppGuardarConfig(activo.id,
    payload({ ...activo, componentes: activo.componentes.map((c) => (c.codigo === cod ? { ...c, heredado: true } : c)) }))));
  const guardarBorrador = conError(async () => {
    upsert(await creditos.ppGuardarConfig(activo.id, payload(activo)));
    setOk("Borrador guardado.");
  });
  const publicar = conError(async () => upsert(await creditos.ppEstado(activo.id, "publicar")));
  const aprobar = conError(async () => upsert(await creditos.ppEstado(activo.id, "aprobar")));
  const rechazar = conError(async () => upsert(await creditos.ppEstado(activo.id, "rechazar")));
  const reactivar = conError(async (p) => upsert(await creditos.ppEstado(p.id, "reactivar")));
  const retirar = conError(async (p) => { upsert(await creditos.ppEstado(p.id, "retirar")); setConfirmando(null); });
  const borrar = conError(async (p) => {
    await creditos.ppBorrar(p.id);
    const d = await creditos.ppCatalogo();
    setProductos(d.items);
    if (activoId === p.id) { setActivoId(null); setVista("catalogo"); }
    setConfirmando(null);
  });
  const guardarSim = conError(async () => {
    const s = await creditos.ppSimGuardar(activo.id, { monto, plazo, tna: tnaEfectiva, etiqueta: simEtiq });
    setSims((xs) => [s, ...xs]); setSimEtiq("");
  });
  const borrarSim = conError(async (id) => {
    await creditos.ppSimBorrar(activo.id, id);
    setSims((xs) => xs.filter((s) => s.id !== id));
  });
  const guardarDisponibilidad = conError(async () => {
    upsert(await creditos.editarDisponibilidad(activo.id, { activo: true, ...comps.find((c) => c.codigo === sel).config }));
    setOk("Disponibilidad guardada (canales/segmentos).");
  });
  const crearLinea = conError(async () => {
    const base = { nombre: nuevo.nombre || undefined, familia_id: nuevo.familia_id || undefined };
    if (nuevo.copiar_de && nuevo.heredar) base.padre_id = nuevo.copiar_de;
    else if (nuevo.copiar_de) base.copiar_de = nuevo.copiar_de;
    const p = await creditos.ppCrear(base);
    setNuevoOpen(false); upsert(p); abrir(p);
  });
  // H-190: duplicar = préstamo NUEVO e independiente (copia de la config), con su ciclo propio.
  const duplicar = conError(async () => {
    const p = await creditos.ppCrear({ copiar_de: duplicando.id, nombre: nombreCopia });
    setDuplicando(null); upsert(p); abrir(p);
    setOk(`Se creó "${nombreCopia}" como préstamo independiente. Editalo y publicalo.`);
  });
  // Publicar en un paso (revisar→aprobar→publicar si el cuatro-ojos está apagado).
  const publicarCambios = conError(async () => {
    if (activo.estado === "BORRADOR") await creditos.ppGuardarConfig(activo.id, payload(activo));
    const r = await creditos.ppPublicarDirecto(activo.id);
    if (r.producto) upsert(r.producto);
    setOk(r.needs_approval
      ? "Enviado a revisión: requiere la aprobación de otra persona (cuatro-ojos)."
      : activo.copiadoDe ? "Préstamo publicado. El original queda intacto (son independientes)." : "Préstamo publicado.");
  });
  const abrirInspector = conError(async () => {
    setInspOpen(true);
    setRaw(await creditos.ppRaw(activo.id));
  });
  const abrirComparar = conError(async () => {
    const d = await creditos.ppVersiones(activo.id);
    setVersiones(d.items);
    const nums = d.items.map((x) => x.version);
    setCmpB(nums[nums.length - 1]);
    setCmpA(nums.length > 1 ? nums[nums.length - 2] : nums[nums.length - 1]);
    setCmpOpen(true);
  });

  const indiceVal = indices.find((x) => x.codigo === cfg.indice)?.valor || 0;
  const tnaEfectiva = cfg.modalidad === "VARIABLE" ? indiceVal + (cfg.margen || 0) : cfg.tna;

  const compErrores = {};
  comps.forEach((c) => { if (c.activo) compErrores[c.codigo] = valida(c.codigo, c.config, cfg); });
  const totalCompErr = Object.values(compErrores).reduce((a, e) => a + e.length, 0);

  // El cronograma y las métricas los calcula el BACKEND: el mismo motor que la originación.
  useEffect(() => {
    if (!activo) return;
    const t = setTimeout(() => {
      creditos.ppPreview(previewPayload(cfg, comps, tnaEfectiva, monto, plazo))
        .then((d) => { setFilas(toFilas(d.rows)); setRes(d.resumen); })
        .catch(() => {});
    }, 220);
    return () => clearTimeout(t);
  }, [cfg, comps, monto, plazo, tnaEfectiva, activoId]); // eslint-disable-line

  useEffect(() => {
    if (!baseline) { setFilasBase([]); return; }
    const btna = baseline.cfg.modalidad === "VARIABLE"
      ? (indices.find((x) => x.codigo === baseline.cfg.indice)?.valor || 0) + (baseline.cfg.margen || 0)
      : baseline.cfg.tna;
    creditos.ppPreview(previewPayload(baseline.cfg, baseline.comps, btna, monto, plazo))
      .then((d) => setFilasBase(toFilas(d.rows))).catch(() => {});
  }, [baseline, monto, plazo]); // eslint-disable-line

  const totalCapital = filas.reduce((a, r) => a + r.capital, 0);
  const costo = res.totalCuotas || monto + res.totalInteres + res.totalCargos;
  const saldoFinal = filas.length ? filas[filas.length - 1].cierre : 0;

  const checks = [
    { ok: cfg.montoMin <= cfg.montoMax, t: "monto mínimo ≤ máximo", s: `${money(cfg.montoMin)} ≤ ${money(cfg.montoMax)}` },
    { ok: cfg.plazoMin <= cfg.plazoMax, t: "plazo mínimo ≤ máximo", s: `${cfg.plazoMin} ≤ ${cfg.plazoMax}` },
    { ok: monto >= cfg.montoMin && monto <= cfg.montoMax, t: "Monto simulado en rango", s: money(monto) },
    { ok: plazo >= cfg.plazoMin && plazo <= cfg.plazoMax, t: "Plazo simulado en rango", s: `${plazo} cuotas` },
    { ok: Math.abs(totalCapital - monto) < 1, t: "Σ capital = monto", s: `${money(totalCapital)} vs ${money(monto)}` },
    { ok: Math.abs(saldoFinal) < 1, t: "Saldo final = 0", s: money(saldoFinal) },
    { ok: comps.filter((c) => c.requerido).every((c) => c.activo), t: "Componentes requeridos activos", s: "TERM_AMOUNT · INTEREST · REPAYMENT_SCHEDULE" },
  ];
  const errs = checks.filter((c) => !c.ok).length + totalCompErr;

  const impacto = useMemo(() => {
    if (!baseline) return [];
    const out = [];
    for (const [k, l] of [["sistema", "Sistema"], ["modalidad", "Modalidad"], ["tna", "TNA %"],
                          ["montoMin", "Monto mín."], ["montoMax", "Monto máx."],
                          ["plazoMin", "Plazo mín."], ["plazoMax", "Plazo máx."],
                          ["cargoOtorg", "Cargo otorg. %"], ["moraTNA", "Mora TNA %"]]) {
      if (String(baseline.cfg[k] ?? "") !== String(cfg[k] ?? ""))
        out.push({ campo: l, antes: String(baseline.cfg[k] ?? ""), ahora: String(cfg[k] ?? "") });
    }
    const base = Object.fromEntries(baseline.comps.map((c) => [c.codigo, c]));
    for (const c of comps) {
      const b = base[c.codigo];
      if (!b) continue;
      if (b.activo !== c.activo)
        out.push({ campo: `${c.nombre} · activo`, antes: b.activo ? "Sí" : "No", ahora: c.activo ? "Sí" : "No" });
      else if (c.activo && JSON.stringify(b.config) !== JSON.stringify(c.config))
        out.push({ campo: `${c.nombre} · condiciones`, antes: "—", ahora: "modificado" });
    }
    return out;
  }, [baseline, cfg, comps]);

  const comp = comps.find((c) => c.codigo === sel);
  const activos = comps.filter((c) => c.activo).sort((a, b) => a.orden - b.orden);
  const idxGuia = comp ? activos.findIndex((c) => c.codigo === sel) : -1;
  const siguiente = idxGuia >= 0 && idxGuia < activos.length - 1 ? activos[idxGuia + 1].codigo : null;
  const puedeEditar = permisos.edita && !soloLectura;
  const editable = !!activo && activo.estado === "BORRADOR" && puedeEditar;
  // La disponibilidad es metadata de distribución, no términos financieros: se edita aunque la
  // versión esté publicada, sin crear versión nueva (H-189).
  const editableDisp = !!activo && puedeEditar;

  const verComp = (cod) => { setSel(cod); setVisitados((s) => new Set(s).add(cod)); };
  const estadoComp = (c) => {
    if (!c.activo) return "add";
    if ((compErrores[c.codigo] || []).length) return "error";
    if (visitados.has(c.codigo) || !esDefault(c.codigo, c.config, cfg)) return "ok";
    return "pend";
  };

  /** Acciones de una línea, para el menú "⋯" de la grilla y de las tarjetas. */
  function accionesDe(p) {
    const edita = permisos.edita && !soloLectura;
    return [
      { label: "Abrir", onClick: () => abrir(p) },
      { label: "Continuar edición", onClick: () => abrir(p), oculta: !edita || p.estado !== "BORRADOR" },
      { label: "⧉ Duplicar (préstamo nuevo)", oculta: !edita,
        onClick: () => { setDuplicando(p); setNombreCopia(`${p.nombre} — copia`); } },
      { label: "Crear derivado (hereda)", oculta: !edita,
        onClick: () => { setNuevo({ nombre: `${p.nombre} (derivado)`, familia_id: "", copiar_de: p.id, heredar: true }); setNuevoOpen(true); } },
      { label: "Retirar línea", danger: true, oculta: !permisos.aprueba || p.estado !== "PUBLICADO",
        onClick: () => setConfirmando({
          titulo: "Retirar línea",
          mensaje: `Retirar "${p.nombre}". Deja de ofrecerse a clientes nuevos; los contratos ya originados no se afectan.`,
          confirmar: "Retirar", onSi: () => retirar(p) }) },
      { label: "Reactivar línea", oculta: !permisos.aprueba || p.estado !== "RETIRADO", onClick: () => reactivar(p) },
      { label: p.publicadas?.length ? "Borrar esta versión" : "Borrar línea", danger: true,
        oculta: !edita || !["BORRADOR", "EN_REVISION"].includes(p.estado),
        onClick: () => setConfirmando({
          titulo: "Descartar la línea",
          mensaje: p.publicadas?.length
            ? `Borrar la versión v${p.version} (borrador). La versión publicada anterior queda intacta.`
            : `Borrar definitivamente la línea "${p.nombre}" (nunca se publicó).`,
          confirmar: "Borrar", onSi: () => borrar(p) }) },
    ];
  }

  // ───────────────────────── Catálogo ─────────────────────────
  if (vista === "catalogo" || !activo) {
    const lista = productos.filter((p) => filtro === "TODOS" || p.estado === filtro);
    const COLS = [
      { key: "nombre", label: "Línea", sortable: true, render: (p) => (
        <div><b>{p.nombre}</b><p className="text-xs text-gray-400">{p.codigo} · v{p.version}</p></div>) },
      { key: "estado", label: "Estado", sortable: true, render: (p) => (
        <span className="flex gap-1">
          <Pill tono={ESTADO_TONO[p.estado]}>{ESTADO_LABEL[p.estado]}</Pill>
          {p.vigentePortal == null && p.estado !== "RETIRADO" && <Pill>no ofrecido</Pill>}
        </span>) },
      { key: "sistema", label: "Sistema", sortable: true, render: (p) => p.cfg.sistema },
      { key: "tna", label: "TNA", align: "right", sortable: true, sortValue: (p) => p.cfg.tna, render: (p) => `${p.cfg.tna}%` },
      { key: "monto", label: "Monto", align: "right", render: (p) => `${money(p.cfg.montoMin)}–${money(p.cfg.montoMax)}` },
      { key: "plazo", label: "Plazo", align: "right", render: (p) => `${p.cfg.plazoMin}–${p.cfg.plazoMax}` },
    ];

    return (
      <>
        <PageHeader
          titulo="Configurar Créditos — Catálogo de líneas"
          descripcion="Diseñá, versioná y publicá las líneas de crédito que se ofrecen a los clientes."
        >
          {puedeEditar && (
            <Boton onClick={() => { setNuevo({ nombre: "", familia_id: familias[0]?.id || "", copiar_de: "", heredar: false }); setNuevoOpen(true); }}>
              ＋ Nueva línea
            </Boton>
          )}
        </PageHeader>

        {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}
        {ok && <div className="mb-4"><Alerta tipo="ok">{ok}</Alerta></div>}

        <Card padding={false}>
          <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b border-gray-200">
            <Field label="Estado">
              <select className="input" value={filtro} onChange={(e) => setFiltro(e.target.value)}>
                <option value="TODOS">Todos</option>
                {LIFECYCLE.map((s) => <option key={s} value={s}>{ESTADO_LABEL[s]}</option>)}
              </select>
            </Field>
            <span className="ml-auto text-sm text-gray-500">{lista.length} de {productos.length} líneas</span>
            <div className="flex rounded-lg border border-gray-300 overflow-hidden" role="group" aria-label="Vista">
              {[["tarjetas", "▦ Tarjetas"], ["lista", "≣ En línea"]].map(([v, t]) => (
                <button key={v} type="button" aria-pressed={catVista === v} onClick={() => cambiarVista(v)}
                        className={`px-3 py-1.5 text-sm ${catVista === v
                          ? "bg-blue-50 text-blue-700 font-medium" : "text-gray-600 hover:bg-gray-50"}`}>{t}</button>
              ))}
            </div>
          </div>
          <div className="p-4">
            {cargando && <p className="text-gray-500">Cargando catálogo…</p>}
            {!cargando && catVista === "lista" && (
              <DataTable columns={COLS} rows={lista} rowKey={(p) => p.id} onRowClick={(p) => abrir(p)}
                         rowClass={(p) => (p.estado === "RETIRADO" ? "opacity-60" : "")}
                         acciones={accionesDe}
                         clientSort pageSize={50} defaultSort="nombre"
                         emptyText="Sin líneas. Creá la primera con “＋ Nueva línea”." />
            )}
            {!cargando && catVista === "tarjetas" && (
              lista.length === 0
                ? <p className="py-8 text-center text-sm text-gray-400">Sin líneas. Creá la primera con “＋ Nueva línea”.</p>
                : <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    {lista.map((p) => (
                      <div key={p.id}
                           className={`border border-gray-200 rounded-xl p-4 hover:border-blue-300 transition-colors ${
                             p.estado === "RETIRADO" ? "opacity-60" : ""}`}>
                        <div className="flex items-start gap-2">
                          <button onClick={() => abrir(p)} className="text-left min-w-0 flex-1">
                            <h3 className="font-semibold text-gray-800 truncate">{p.nombre}</h3>
                            <p className="text-xs text-gray-400">{p.codigo} · v{p.version}</p>
                          </button>
                          <div className="flex flex-col items-end gap-1 shrink-0">
                            <Pill tono={ESTADO_TONO[p.estado]}>{ESTADO_LABEL[p.estado]}</Pill>
                            {p.vigentePortal == null && p.estado !== "RETIRADO" && (
                              <span title="Ninguna versión publicada y vigente: no se ofrece en el portal"><Pill>no ofrecido</Pill></span>
                            )}
                          </div>
                          <MenuAcciones acciones={accionesDe(p)} etiqueta={`Acciones de ${p.nombre}`} />
                        </div>
                        <p className="text-xs text-gray-500 mt-2">
                          Familia <b>{p.familia}</b> · {p.componentes.filter((c) => c.activo).length} componentes
                        </p>
                        {p.padre && <p className="text-xs text-blue-700 mt-0.5">Deriva de <b>{p.padre.nombre}</b></p>}
                        <dl className="grid grid-cols-2 gap-2 mt-3 text-sm">
                          <div><dt className="text-xs text-gray-500">Sistema</dt><dd className="font-medium">{p.cfg.sistema}</dd></div>
                          <div><dt className="text-xs text-gray-500">TNA</dt><dd className="font-medium tabular-nums">{p.cfg.tna}%</dd></div>
                          <div><dt className="text-xs text-gray-500">Monto</dt>
                            <dd className="font-medium tabular-nums">{money(p.cfg.montoMin)}–{money(p.cfg.montoMax)}</dd></div>
                          <div><dt className="text-xs text-gray-500">Plazo</dt>
                            <dd className="font-medium tabular-nums">{p.cfg.plazoMin}–{p.cfg.plazoMax}</dd></div>
                        </dl>
                        <div className="flex justify-end gap-2 mt-3">
                          <Boton variante="secundario" className="!px-3 !py-1.5 text-xs" onClick={() => abrir(p)}>Abrir</Boton>
                          {p.estado === "BORRADOR" && puedeEditar && (
                            <Boton className="!px-3 !py-1.5 text-xs" onClick={() => abrir(p)}>Continuar edición</Boton>
                          )}
                          {p.estado === "RETIRADO" && permisos.aprueba && (
                            <Boton className="!px-3 !py-1.5 text-xs" onClick={() => reactivar(p)}>Reactivar</Boton>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
            )}
          </div>
        </Card>

        {nuevoOpen && (
          <Modal
            titulo="Nueva línea de crédito"
            ancho="max-w-lg"
            onClose={() => setNuevoOpen(false)}
            footer={
              <>
                <span className="flex-1" />
                <Boton variante="secundario" onClick={() => setNuevoOpen(false)}>Cancelar</Boton>
                <Boton onClick={crearLinea}>Crear y diseñar</Boton>
              </>
            }
          >
            <p className="text-sm text-gray-500 mb-3">
              Poné un nombre, elegí la familia y, si querés, partí de una línea existente.
            </p>
            <div className="space-y-3">
              <Field label="Nombre">
                <input className="input w-full" value={nuevo.nombre} placeholder="Ej.: Préstamo Personal 2026"
                       onChange={(e) => setNuevo({ ...nuevo, nombre: e.target.value })} />
              </Field>
              <Field label="Familia">
                <select className="input w-full" value={nuevo.familia_id}
                        onChange={(e) => setNuevo({ ...nuevo, familia_id: e.target.value })}>
                  {familias.map((f) => <option key={f.id} value={f.id}>{f.grupo} · {f.nombre}</option>)}
                </select>
              </Field>
              <Field label="Basar en">
                <select className="input w-full" value={nuevo.copiar_de}
                        onChange={(e) => setNuevo({ ...nuevo, copiar_de: e.target.value, heredar: e.target.value ? nuevo.heredar : false })}>
                  <option value="">— En blanco (valores por defecto) —</option>
                  {productos.map((p) => <option key={p.id} value={p.id}>{p.nombre} (v{p.version})</option>)}
                </select>
              </Field>
              {nuevo.copiar_de && (
                <div className="space-y-2">
                  <label className="flex gap-2 items-start text-sm">
                    <input type="radio" checked={!nuevo.heredar} onChange={() => setNuevo({ ...nuevo, heredar: false })} />
                    <span><b>Copia independiente</b>
                      <small className="block text-gray-500">Se copian los valores una vez; después evoluciona sola.</small></span>
                  </label>
                  <label className="flex gap-2 items-start text-sm">
                    <input type="radio" checked={nuevo.heredar} onChange={() => setNuevo({ ...nuevo, heredar: true })} />
                    <span><b>Derivar (hereda del padre)</b>
                      <small className="block text-gray-500">Sólo guarda lo que cambies; el resto sigue al padre.</small></span>
                  </label>
                </div>
              )}
            </div>
          </Modal>
        )}

        {duplicando && (
          <Modal titulo="Duplicar como préstamo nuevo" ancho="max-w-md" onClose={() => setDuplicando(null)}
                 footer={<>
                   <span className="flex-1" />
                   <Boton variante="secundario" onClick={() => setDuplicando(null)}>Cancelar</Boton>
                   <Boton disabled={!nombreCopia.trim()} onClick={duplicar}>Crear copia</Boton>
                 </>}>
            <p className="text-sm text-gray-500 mb-3">
              Se crea un préstamo independiente con la configuración de “{duplicando.nombre}”. El original queda intacto.
            </p>
            <Field label="Nombre del préstamo nuevo">
              <input className="input w-full" value={nombreCopia} autoFocus
                     onChange={(e) => setNombreCopia(e.target.value)} />
            </Field>
          </Modal>
        )}

        {confirmando && (
          <Confirmacion
            titulo={confirmando.titulo} mensaje={confirmando.mensaje} confirmar={confirmando.confirmar}
            onConfirmar={confirmando.onSi} onCancelar={() => setConfirmando(null)}
          />
        )}
      </>
    );
  }

  // ───────────────────────── Builder ─────────────────────────
  const pasoActual = LIFECYCLE.indexOf(activo.estado);

  return (
    <>
      <button onClick={() => setVista("catalogo")} className="text-sm text-gray-600 hover:text-gray-900 mb-3">
        ← Volver al catálogo de líneas
      </button>

      <PageHeader
        titulo={activo.nombre}
        descripcion={`${activo.codigo} · Grupo ${activo.grupo} › Familia ${activo.familia} · versión v${activo.version}`}
      >
        <Boton variante="secundario" onClick={() => setProbar((v) => !v)}>
          {probar ? "Ocultar prueba" : "▶ Probar en vivo"}
        </Boton>
        <Boton variante="secundario" onClick={abrirComparar}>⇄ Comparar</Boton>
        <Boton variante="secundario" onClick={abrirInspector}>Datos</Boton>
      </PageHeader>

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}
      {ok && <div className="mb-4"><Alerta tipo="ok">{ok}</Alerta></div>}

      <Card className="mb-4">
        <div className="flex flex-wrap items-center gap-2">
          <Pill tono={ESTADO_TONO[activo.estado]}>{ESTADO_LABEL[activo.estado]}</Pill>
          {(activo.enviadoPor || activo.aprobadoPor || activo.publicadoPor) && (
            <span className="text-xs text-gray-400">
              {activo.enviadoPor && `Enviada por ${activo.enviadoPor}`}
              {activo.aprobadoPor && ` · Aprobada por ${activo.aprobadoPor}`}
              {activo.publicadoPor && ` · Publicada por ${activo.publicadoPor}`}
            </span>
          )}
          <span className="flex-1" />
          {activo.estado === "BORRADOR" && (
            <>
              <Boton variante="secundario" disabled={!puedeEditar} onClick={guardarBorrador}>Guardar y seguir después</Boton>
              <Boton variante="secundario" disabled={!puedeEditar}
                     onClick={() => setConfirmando({
                       titulo: "Descartar la línea",
                       mensaje: activo.publicadas.length
                         ? `Borrar la versión v${activo.version} (borrador). La versión publicada anterior queda intacta.`
                         : `Borrar definitivamente la línea "${activo.nombre}" (nunca se publicó).`,
                       confirmar: "Borrar",
                       onSi: () => borrar(activo),
                     })}>Descartar</Boton>
              <Boton disabled={!puedeEditar || errs > 0}
                     title={errs ? "Resolvé las validaciones antes de publicar" : "Publicar la línea"}
                     onClick={publicarCambios}>Publicar</Boton>
            </>
          )}
          {activo.estado === "EN_REVISION" && (
            <>
              <Boton variante="secundario" disabled={!permisos.aprueba} onClick={rechazar}>Rechazar</Boton>
              <Boton disabled={!permisos.aprueba || activo.enviadoPor === usuario}
                     title={activo.enviadoPor === usuario
                       ? "Separación de funciones: no podés aprobar lo que enviaste vos"
                       : "Aprobar"}
                     onClick={aprobar}>Aprobar</Boton>
            </>
          )}
          {activo.estado === "APROBADO" && (
            <Boton disabled={!permisos.aprueba || errs > 0} onClick={publicar}>Publicar</Boton>
          )}
          {activo.estado === "PUBLICADO" && puedeEditar && (
            <>
              <Boton variante="secundario"
                     onClick={() => { setDuplicando(activo); setNombreCopia(`${activo.nombre} — copia`); }}>
                ⧉ Duplicar
              </Boton>
              {permisos.aprueba && (
                <Boton variante="danger" onClick={() => setConfirmando({
                  titulo: "Retirar línea",
                  mensaje: `Retirar "${activo.nombre}". Deja de ofrecerse a clientes nuevos; los contratos ya originados no se afectan (conservan su snapshot).`,
                  confirmar: "Retirar",
                  onSi: () => retirar(activo),
                })}>Retirar línea</Boton>
              )}
            </>
          )}
          {activo.estado === "RETIRADO" && permisos.aprueba && (
            <Boton onClick={() => reactivar(activo)}>Reactivar</Boton>
          )}
        </div>

        <ol className="flex flex-wrap items-center gap-2 mt-3">
          {LIFECYCLE.map((s, i) => (
            <li key={s} className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-full ${
              i < pasoActual ? "text-green-700 bg-green-50"
                : i === pasoActual ? "text-blue-700 bg-blue-50 font-medium" : "text-gray-400"}`}>
              <span>{i < pasoActual ? "✓" : i + 1}</span>{ESTADO_LABEL[s]}
            </li>
          ))}
        </ol>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
          {[
            { l: "TNA", v: `${tnaEfectiva.toFixed(2)}%`, h: cfg.modalidad === "VARIABLE" ? `${cfg.indice}+${cfg.margen}` : "nominal anual" },
            { l: "TEA", v: `${(res.tea || 0).toFixed(2)}%`, h: "efectiva anual" },
            { l: "CFT", v: `${(res.cft || 0).toFixed(2)}%`, h: "costo financiero total" },
            { l: "Cuota", v: money(filas[0]?.total || 0), h: `${money(monto)} · ${plazo} cuotas` },
          ].map((k) => (
            <div key={k.l} className="border border-gray-200 rounded-lg px-3 py-2">
              <p className="text-xs text-gray-500">{k.l}</p>
              <p className="font-semibold text-gray-800 tabular-nums">{k.v}</p>
              <p className="text-[11px] text-gray-400">{k.h}</p>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-end gap-3 mt-4 border-t border-gray-200 pt-3">
          <span className="text-sm text-gray-500">Vigencia de la versión v{activo.version}:</span>
          {editable ? (
            <>
              <Field label="Desde">
                <input type="date" className="input" value={cfg.vigenciaDesde || ""}
                       onChange={(e) => setCfg({ vigenciaDesde: e.target.value })} />
              </Field>
              <Field label="Hasta">
                <input type="date" className="input" value={cfg.vigenciaHasta || ""}
                       onChange={(e) => setCfg({ vigenciaHasta: e.target.value })} />
              </Field>
              <span className="text-xs text-gray-400">si no fijás “Desde”, entra en vigencia al publicar</span>
            </>
          ) : (
            <b className="text-sm">{fecha(cfg.vigenciaDesde) } → {cfg.vigenciaHasta ? fecha(cfg.vigenciaHasta) : "sin límite"}</b>
          )}
        </div>

        {nuevaVerDe != null && (
          <p className="mt-3 text-sm text-gray-600">
            Versión nueva (v{activo.version}) derivada de la v{nuevaVerDe} publicada, que sigue vigente hasta publicar ésta.
          </p>
        )}
        {activo.padre && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-gray-600">
            <span>
              Deriva de <b>{activo.padre.nombre}</b> ({activo.padre.codigo}). Lo que no personalices se hereda del padre.
              Condiciones generales: <b>{activo.cfgHeredada ? "heredadas" : "propias"}</b>.
            </span>
            {!activo.cfgHeredada && editable && (
              <Boton variante="secundario" onClick={reheredarCfg}>↩ Volver a heredar generales</Boton>
            )}
          </div>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-[260px,1fr]">
        <Card padding={false}>
          <p className="px-4 py-3 text-sm font-semibold text-gray-800 border-b border-gray-200">Componentes</p>
          <div className="p-2">
            {[...comps].sort((a, b) => a.orden - b.orden).map((c) => {
              const st = estadoComp(c);
              const marca = { ok: "✓", pend: "○", error: "!", add: "＋" }[st];
              const tono = { ok: "text-green-600", pend: "text-gray-400", error: "text-red-600", add: "text-gray-300" }[st];
              return (
                <button key={c.codigo} onClick={() => verComp(c.codigo)}
                        title={st === "error" ? (compErrores[c.codigo] || []).join(" · ") : undefined}
                        className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-sm ${
                          c.codigo === sel ? "bg-blue-50" : "hover:bg-gray-50"} ${!c.activo ? "opacity-60" : ""}`}>
                  <span aria-hidden>{ICONOS[c.codigo] || "▫"}</span>
                  <span className="flex-1 min-w-0">
                    <b className="block truncate text-gray-800">{c.nombre}</b>
                    <small className="text-gray-400">{c.requerido ? "Requerido" : c.categoria}{c.multiple ? " · multi" : ""}</small>
                  </span>
                  {activo.padre && c.heredado && <span title="Heredado del padre">🧬</span>}
                  <span className={`font-bold ${tono}`}>{marca}</span>
                </button>
              );
            })}
          </div>
        </Card>

        <Card>
          <EditorComponente
            comp={comp} cfg={cfg} errores={compErrores[comp?.codigo] || []}
            editable={editable} editableDisp={editableDisp} tienePadre={!!activo.padre}
            indices={indices} impuestos={impuestos} catSegmentos={catSegmentos} catCanales={catCanales}
            setCfg={setCfg} setCompCfg={setCompCfg} toggleComp={toggleComp}
            reheredarComp={reheredarComp} guardarDisponibilidad={guardarDisponibilidad}
          />

          {comp?.activo && (
            <div className="flex items-center gap-3 mt-5 pt-4 border-t border-gray-200">
              {!comp.requerido && editable && (
                <Boton variante="secundario" onClick={() => toggleComp(comp.codigo, false)}>Quitar componente</Boton>
              )}
              {idxGuia >= 0 && (
                <span className="text-sm text-gray-500">
                  Revisados {activos.filter((c) => estadoComp(c) === "ok").length} de {activos.length}
                </span>
              )}
              <span className="flex-1" />
              {siguiente && <Boton onClick={() => verComp(siguiente)}>Siguiente componente →</Boton>}
            </div>
          )}
        </Card>
      </div>

      {probar && (
        <Card className="mt-4">
          <div className="flex items-center gap-2 mb-3">
            <b className="text-gray-800">Prueba en vivo</b>
            <Pill tono="brand">no modifica el producto</Pill>
            <span className="flex-1" />
            <Boton variante="secundario" onClick={() => setProbar(false)}>Cerrar</Boton>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 max-w-md">
            <Field label="Monto">
              <input type="number" className="input w-full" value={monto}
                     onChange={(e) => setMonto(Number(e.target.value) || 0)} />
            </Field>
            <Field label="Plazo (cuotas)">
              <input type="number" className="input w-full" value={plazo}
                     onChange={(e) => setPlazo(Math.max(1, Number(e.target.value) || 1))} />
            </Field>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-3">
            <div className="border border-gray-200 rounded-lg px-3 py-2">
              <p className="text-xs text-gray-500">{cfg.sistema === "FRANCES" ? "Cuota" : "1ª cuota"}</p>
              <p className="font-semibold tabular-nums">{money(filas[0]?.total || 0)}</p>
            </div>
            <div className="border border-gray-200 rounded-lg px-3 py-2">
              <p className="text-xs text-gray-500">Costo total</p>
              <p className="font-semibold tabular-nums">{money(costo)}</p>
            </div>
            <div className="border border-gray-200 rounded-lg px-3 py-2">
              <p className="text-xs text-gray-500">Intereses + cargos</p>
              <p className="font-semibold tabular-nums">{money((res.totalInteres || 0) + (res.totalCargos || 0))}</p>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2 mt-4">
            <div>
              <p className="text-sm font-semibold text-gray-800 mb-1">
                Impacto de tus cambios {impacto.length > 0 && <Pill tono="brand">{impacto.length}</Pill>}
              </p>
              {!impacto.length ? (
                <p className="text-sm text-gray-400">Sin cambios respecto del estado inicial.</p>
              ) : (
                <ul className="text-sm space-y-1">
                  {impacto.map((d, i) => (
                    <li key={i} className="flex justify-between gap-2 border-b border-gray-100 py-1">
                      <span className="text-gray-700">{d.campo}</span>
                      <span className="text-gray-500">{d.antes} → <b className="text-gray-800">{d.ahora}</b></span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <p className="text-sm font-semibold text-gray-800 mb-1">
                Validación <Pill tono={errs ? "crit" : "ok"}>{errs ? errs : "OK"}</Pill>
              </p>
              <ul className="text-sm space-y-1">
                {checks.map((c, i) => (
                  <li key={i} className="flex gap-2">
                    <span className={c.ok ? "text-green-600" : "text-red-600"}>{c.ok ? "✓" : "✕"}</span>
                    <span className="flex-1">{c.t}<small className="block text-gray-400">{c.s}</small></span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="flex items-end gap-2 mt-4">
            <Field label="Etiqueta de la simulación" className="flex-1 max-w-xs">
              <input className="input w-full" value={simEtiq} onChange={(e) => setSimEtiq(e.target.value)} />
            </Field>
            <Boton onClick={guardarSim}>Guardar simulación</Boton>
          </div>
          {sims.length > 0 && (
            <ul className="mt-2 space-y-1 max-h-32 overflow-auto">
              {sims.map((s) => (
                <li key={s.id} className="flex items-center gap-2 text-sm bg-gray-50 rounded-lg px-3 py-1.5">
                  <button onClick={() => { setMonto(s.monto); setPlazo(s.plazo); }} className="flex-1 text-left">
                    <b>{s.etiqueta || `${money(s.monto)} · ${s.plazo}c`}</b>
                    <span className="text-gray-500"> · {money(s.monto)} · {s.plazo}c · {s.tna}% · cuota {money(s.primeraCuota)}</span>
                  </button>
                  <button onClick={() => borrarSim(s.id)} aria-label={`Borrar simulación ${s.etiqueta || s.id}`}
                          className="px-2 text-red-600 border border-red-300 rounded-lg">✕</button>
                </li>
              ))}
            </ul>
          )}

          <details className="mt-4" open>
            <summary className="text-sm text-gray-600 cursor-pointer">
              Cronograma proyectado · sistema {cfg.sistema.toLowerCase()}
              {cfg.graciaCapital ? ` · ${cfg.graciaCapital} en gracia` : ""} · {String(cfg.frecuencia).toLowerCase()}
            </summary>
            <div className="mt-2 max-h-60 overflow-auto border border-gray-200 rounded-lg">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                    <th className="px-3 py-2 text-left">#</th><th className="px-3 py-2 text-left">Vto</th>
                    <th className="px-3 py-2 text-right">Capital</th><th className="px-3 py-2 text-right">Interés</th>
                    <th className="px-3 py-2 text-right">Cargos</th><th className="px-3 py-2 text-right">Cuota</th>
                    <th className="px-3 py-2 text-right">Saldo</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filas.map((r) => {
                    const b = filasBase[r.k - 1];
                    const cambio = !!b && (Math.abs((b.total || 0) - r.total) > 0.005 || b.fecha !== r.fecha);
                    return (
                      <tr key={r.k} className={cambio ? "bg-amber-50" : ""}>
                        <td className="px-3 py-1.5 font-medium">{r.k}</td>
                        <td className="px-3 py-1.5">{fecha(r.fecha)}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{money(r.capital)}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{money(r.interes)}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{money(r.cargos)}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums font-semibold">{money(r.total)}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{money(r.cierre)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </details>
        </Card>
      )}

      {cmpOpen && (
        <Modal titulo="Comparar versiones" onClose={() => setCmpOpen(false)}
               footer={<><span className="flex-1" /><Boton variante="secundario" onClick={() => setCmpOpen(false)}>Cerrar</Boton></>}>
          <div className="flex gap-3 mb-3">
            <Field label="Versión A">
              <select className="input" value={cmpA} onChange={(e) => setCmpA(Number(e.target.value))}>
                {versiones.map((v) => <option key={v.version} value={v.version}>v{v.version}</option>)}
              </select>
            </Field>
            <Field label="Versión B">
              <select className="input" value={cmpB} onChange={(e) => setCmpB(Number(e.target.value))}>
                {versiones.map((v) => <option key={v.version} value={v.version}>v{v.version}</option>)}
              </select>
            </Field>
          </div>
          {(() => {
            const A = versiones.find((v) => v.version === cmpA);
            const B = versiones.find((v) => v.version === cmpB);
            if (!A || !B) return <p className="text-sm text-gray-500">Elegí dos versiones.</p>;
            const filasDiff = diffVersiones(A, B);
            if (!filasDiff.length) return <p className="text-sm text-gray-500">Las dos versiones son iguales.</p>;
            return (
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                    <th className="px-3 py-2 text-left">Grupo</th><th className="px-3 py-2 text-left">Campo</th>
                    <th className="px-3 py-2 text-left">v{cmpA}</th><th className="px-3 py-2 text-left">v{cmpB}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filasDiff.map((f, i) => (
                    <tr key={i}>
                      <td className="px-3 py-1.5 text-gray-500">{f.grupo}</td>
                      <td className="px-3 py-1.5">{f.campo}</td>
                      <td className="px-3 py-1.5 text-gray-500">{String(f.a)}</td>
                      <td className="px-3 py-1.5 font-medium">{String(f.b)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            );
          })()}
        </Modal>
      )}

      {inspOpen && (
        <Modal titulo="Datos de la línea (inspector)" onClose={() => setInspOpen(false)}
               footer={<><span className="flex-1" /><Boton variante="secundario" onClick={() => setInspOpen(false)}>Cerrar</Boton></>}>
          <pre className="text-xs bg-gray-50 border border-gray-200 rounded-lg p-3 overflow-auto max-h-96">
            {JSON.stringify(raw, null, 2)}
          </pre>
        </Modal>
      )}

      {duplicando && (
        <Modal titulo="Duplicar como préstamo nuevo" ancho="max-w-md" onClose={() => setDuplicando(null)}
               footer={<>
                 <span className="flex-1" />
                 <Boton variante="secundario" onClick={() => setDuplicando(null)}>Cancelar</Boton>
                 <Boton disabled={!nombreCopia.trim()} onClick={duplicar}>Crear copia</Boton>
               </>}>
          <p className="text-sm text-gray-500 mb-3">
            Se crea un préstamo independiente con la configuración de “{duplicando.nombre}”. El original queda intacto.
          </p>
          <Field label="Nombre del préstamo nuevo">
            <input className="input w-full" value={nombreCopia} autoFocus
                   onChange={(e) => setNombreCopia(e.target.value)} />
          </Field>
        </Modal>
      )}

      {confirmando && (
        <Confirmacion
          titulo={confirmando.titulo} mensaje={confirmando.mensaje} confirmar={confirmando.confirmar}
          onConfirmar={confirmando.onSi} onCancelar={() => setConfirmando(null)}
        />
      )}
    </>
  );
}
