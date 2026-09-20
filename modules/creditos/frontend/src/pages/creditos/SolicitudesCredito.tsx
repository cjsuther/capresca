import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../../api";
import { useNivelActual } from "../../permisos";
import { confirmar, avisar } from "../../ui/dialog";

// Formatea importes con la cantidad de decimales "para mostrar" configurada en Parámetros de créditos (H-198).
const fmtMoney = (n: number, dec: number) =>
  "$" + (n || 0).toLocaleString("es-AR", { minimumFractionDigits: dec, maximumFractionDigits: dec });
const ESTADO_CLASS: Record<string, string> = {
  BORRADOR: "", EN_EVALUACION: "warn", APROBADA: "ok", RECHAZADA: "crit", ORIGINADA: "brand", ANULADA: "",
};
const RELACIONES = ["ESTANDAR", "PREFERENCIAL", "PREMIUM"];
const TIPODOC: Record<string, string> = { DNI_FRENTE: "DNI (frente)", DNI_DORSO: "DNI (dorso)", RECIBO: "Recibo de sueldo", OTRO: "Otro" };
const DESTINO: Record<string, string> = {
  VIVIENDA: "Vivienda / refacción", VEHICULO: "Vehículo", CONSUMO: "Consumo / gastos personales",
  EDUCACION: "Educación", SALUD: "Salud", REFINANCIACION: "Refinanciación de deudas",
  EMPRENDIMIENTO: "Emprendimiento / negocio", OTRO: "Otro",
};
const kb = (n: number) => (n >= 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " KB");
// Deja sólo dígitos y acota a [min, max]; string vacío = sin valor (campo opcional). Mismos límites que el backend.
const clampNum = (v: string, min: number, max: number): string => {
  const d = String(v).replace(/\D/g, "");
  if (d === "") return "";
  return String(Math.max(min, Math.min(max, parseInt(d, 10))));
};

export default function SolicitudesCredito() {
  const [items, setItems] = useState<any[]>([]);
  const [estados, setEstados] = useState<string[]>([]);
  const [permisos, setPermisos] = useState({ edita: false, aprueba: false });
  const { soloLectura } = useNivelActual();
  const [filtro, setFiltro] = useState("");
  const [q, setQ] = useState("");
  const [nueva, setNueva] = useState(false);
  const [paso, setPaso] = useState(1);          // wizard: 1 Solicitante · 2 Simulación · 3 Confirmación
  const [sim, setSim] = useState<any>(null);
  const [simulando, setSimulando] = useState(false);
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  // Detalle flotante de la solicitud (datos + cronograma + docs + revisión) con observación y acciones.
  const [crono, setCrono] = useState<any[]>([]);
  const [cargandoCrono, setCargandoCrono] = useState(false);
  const [cronoAbierto, setCronoAbierto] = useState(false);   // el cronograma arranca plegado (desplegable)
  const [obs, setObs] = useState("");
  const [detErr, setDetErr] = useState("");
  const [accionando, setAccionando] = useState(false);
  // Vincular un cliente ya existente del maestro a una solicitud express (typeahead).
  const [vincSol, setVincSol] = useState<any>(null);
  const [vincQ, setVincQ] = useState("");
  const [vincList, setVincList] = useState<any[]>([]);
  const [vincErr, setVincErr] = useState("");
  // Cliente de la solicitud: se ELIGE del maestro con un buscador (igual que Originar); no se carga a mano.
  const [cliQ, setCliQ] = useState("");
  const [clis, setClis] = useState<any[]>([]);
  const [buscandoCli, setBuscandoCli] = useState(false);
  const [cliSel, setCliSel] = useState<any>(null);
  const [sel, setSel] = useState<any>(null);
  const [docs, setDocs] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const [lineas, setLineas] = useState<any[]>([]);
  const [cat, setCat] = useState<{ segmentos: string[]; canales: string[]; decimalesMostrar?: number; canalBackoffice?: string }>({ segmentos: [], canales: [] });
  const money = (n: number) => fmtMoney(n, Math.max(0, Math.min(6, cat.decimalesMostrar ?? 2)));

  const [form, setForm] = useState<any>({
    solicitante_tipo: "REGISTRADO", cliente_id: 0,
    cliente_datos: { apellido_nombre: "", cuil: "", dni: "" },
    producto_id: "", monto_solicitado: 1000000, plazo_solicitado: 24,
    segmento: "", canal: "SUCURSAL", edad: "", antiguedad_meses: "", relacion: "ESTANDAR",
    datos_adicionales: { destino: "", cbu: "", observaciones: "" },
  });

  const cargar = () => api.ppSolicitudes({ estado: filtro, q }).then((d) => {
    setItems(d.items); setEstados(d.estados); setPermisos(d.permisos);
  }).catch((e) => setErr(String(e)));
  useEffect(() => { cargar(); }, [filtro, q]);
  // Al seleccionar una solicitud (panel flotante): documentación adjunta + cronograma + observación previa.
  useEffect(() => {
    if (!sel?.id) { setDocs([]); setCrono([]); return; }
    setObs((sel.datosAdicionales?.obs_revision as string) || ""); setDetErr(""); setCronoAbierto(false);
    api.ppSolicitudDocs(sel.id).then((d: any) => setDocs(d.items)).catch(() => setDocs([]));
    if (!sel.productoId) { setCrono([]); return; }
    setCargandoCrono(true);
    api.ppSimPreview(sel.productoId, {
      monto: sel.monto, plazo: sel.plazo, segmento: sel.segmento || undefined, canal: sel.canal || undefined,
      edad: sel.edad ?? undefined, antiguedad_meses: sel.antiguedadMeses ?? undefined,
    }).then((sim: any) => setCrono(sim.cuotas || [])).catch(() => setCrono([])).finally(() => setCargandoCrono(false));
  }, [sel?.id]);   // eslint-disable-line
  useEffect(() => {
    // La oferta del backoffice se filtra por el CANAL del backoffice (H-185/H-199): una línea "solo web"
    // no se puede originar por sucursal, así que no debe listarse en el asistente. El canal sale de cat.
    const cargarOferta = (canal?: string) =>
      api.ppOferta(canal ? { canal } : {}).then((d) => { setLineas(d.items); if (d.items[0]) setForm((f: any) => ({ ...f, producto_id: f.producto_id || d.items[0].id })); }).catch(() => {});
    api.ctoSegmentos().then((c: any) => { setCat(c); cargarOferta(c?.canalBackoffice); }).catch(() => { cargarOferta(); });
  }, []);

  // Vuelta de "Clientes → Maestro": vincula el cliente recién creado a la solicitud express.
  useEffect(() => {
    const sid = params.get("vincular"); const cid = params.get("cliente");
    if (!sid || !cid) return;
    (async () => {
      try {
        const r = await api.ppSolicitudPromover(sid, { cliente_id: Number(cid) });
        setSel(r.solicitud); avisar("Cliente vinculado a la solicitud.");
      } catch (e: any) { avisar({ tipo: "error", mensaje: e.message || String(e) }); }
      finally { setParams({}, { replace: true }); cargar(); }
    })();
  }, [params]);   // eslint-disable-line

  // Typeahead del modal "Vincular cliente" (express): elegir un cliente ya existente del maestro.
  useEffect(() => {
    const qq = vincQ.trim();
    if (!vincSol || qq.length < 2) { setVincList([]); return; }
    let vivo = true;
    const t = setTimeout(async () => {
      try { const r = await api.clientes({ q: qq, limit: 8 }); if (vivo) setVincList(r.items); }
      catch { if (vivo) setVincList([]); }
    }, 300);
    return () => { vivo = false; clearTimeout(t); };
  }, [vincQ, vincSol]);

  // Buscador de clientes (typeahead) del wizard: el cliente se elige del maestro, no se carga a mano.
  useEffect(() => {
    const qq = cliQ.trim();
    if (form.cliente_id || qq.length < 2) { setClis([]); return; }
    let vivo = true; setBuscandoCli(true);
    const t = setTimeout(async () => {
      try { const r = await api.clientes({ q: qq, limit: 8 }); if (vivo) setClis(r.items); }
      catch { if (vivo) setClis([]); }
      finally { if (vivo) setBuscandoCli(false); }
    }, 300);
    return () => { vivo = false; clearTimeout(t); };
  }, [cliQ, form.cliente_id]);
  const elegirCliente = (c: any) => { setForm((f: any) => ({ ...f, solicitante_tipo: "REGISTRADO", cliente_id: c.id })); setCliSel(c); setCliQ(""); setClis([]); };
  const cambiarCliente = () => { setForm((f: any) => ({ ...f, cliente_id: "" })); setCliSel(null); setCliQ(""); setClis([]); };

  const abrirNueva = () => { setNueva(true); setSel(null); setPaso(1); setSim(null); setErr(""); setCliSel(null); setCliQ(""); setClis([]); setForm((f: any) => ({ ...f, cliente_id: "" })); };
  const cerrarNueva = () => { setNueva(false); setPaso(1); setSim(null); };

  // Edad opcional, pero si se carga debe estar en el rango que valida el backend (18–99). Se bloquea
  // "Continuar" antes de llegar a un alta que el backend rechazaría (H-200).
  const edadInvalida = form.edad !== "" && form.edad != null && (Number(form.edad) < 18 || Number(form.edad) > 99);
  const paso1OK = !!form.cliente_id && !edadInvalida;   // solicitud para un cliente REGISTRADO (del maestro)
  const paso2OK = !!form.producto_id && Number(form.monto_solicitado) > 0 && Number(form.plazo_solicitado) > 0;

  const simular = async () => {
    if (!paso2OK) return;
    setSimulando(true); setErr("");
    try {
      setSim(await api.ppSimPreview(form.producto_id, {
        monto: Number(form.monto_solicitado), plazo: Number(form.plazo_solicitado),
        segmento: form.segmento || undefined, canal: form.canal || undefined,
        edad: form.edad ? Number(form.edad) : undefined,
        antiguedad_meses: form.antiguedad_meses ? Number(form.antiguedad_meses) : undefined,
      }));
    } catch (e: any) { setSim(null); setErr(e.message || String(e)); }
    finally { setSimulando(false); }
  };
  // Simulación EN VIVO (H-195): al entrar al paso 2 o cambiar línea/monto/plazo, recalcula solo (debounce).
  useEffect(() => {
    if (!nueva || paso !== 2 || !paso2OK) return;
    const t = setTimeout(() => { simular(); }, 450);
    return () => clearTimeout(t);
  }, [nueva, paso, form.producto_id, form.monto_solicitado, form.plazo_solicitado]);   // eslint-disable-line

  const [creando, setCreando] = useState(false);
  const crear = async (enviar = false) => {
    setErr(""); setCreando(true);
    try {
      const payload = {
        ...form,
        cliente_id: form.solicitante_tipo === "REGISTRADO" ? Number(form.cliente_id) || null : null,
        edad: form.edad ? Number(form.edad) : null,
        antiguedad_meses: form.antiguedad_meses ? Number(form.antiguedad_meses) : null,
      };
      let s = await api.ppSolicitudCrear(payload);
      if (enviar) {   // crear y mandar a evaluación en un paso (queda en el Inbox)
        try { const r: any = await api.ppSolicitudEstado(s.id, "enviar", "", ""); if (r?.id) s = r; } catch { /* si falla el envío, queda en borrador */ }
      }
      cerrarNueva(); setSel(s); cargar();
    } catch (e: any) { setErr(e.message || String(e)); }
    finally { setCreando(false); }
  };

  // Originación (núcleo, sin confirm): el contrato queda A_LIQUIDAR; el desembolso va por lote (H-135).
  const originarContrato = async (s: any, observacion = "") => {
    const c = await api.ctoOriginar({
      producto_id: s.productoId, cliente_nombre: s.clienteNombre, monto: s.monto, plazo: s.plazo,
      segmento: s.segmento || undefined, canal: s.canal || undefined,
      edad: s.edad ?? undefined, antiguedad_meses: s.antiguedadMeses ?? undefined,
      relacion: s.relacion || undefined, solicitud_pp_id: s.id,
      datos_adicionales: { destino: s.datosAdicionales?.destino || "", cbu: s.datosAdicionales?.cbu || "",
                           observaciones: observacion.trim() || s.datosAdicionales?.observaciones || "" },
      desembolsar: false,
    });
    const rec = await api.ppSolicitudes({ estado: filtro, q }).then((d) => d.items.find((x: any) => x.id === s.id)).catch(() => null);
    cargar(); setSel(rec || null);
    return c;
  };

  // Acción sobre la solicitud abierta (panel flotante), con la observación del asesor.
  const resolver = async (acc: string) => {
    const s = sel; if (!s) return;
    setDetErr("");
    if (acc === "rechazar" && !obs.trim()) { setDetErr("Para rechazar, escribí el motivo en Observación."); return; }
    if (acc === "anular" && !(await confirmar({ titulo: "Anular solicitud", confirmar: "Anular",
      mensaje: `¿Anular ${s.numero}? Es una baja administrativa del trámite (no una decisión crediticia).` }))) return;
    setAccionando(true);
    try {
      if (acc === "originar") {
        const c = await originarContrato(s, obs);
        avisar(`Contrato originado: ${c.numeroContrato || c.numero_contrato || ""} · quedó A LIQUIDAR para el desembolso por lote.`);
      } else {
        const motivo = (acc === "rechazar" || acc === "anular") ? obs.trim() : "";
        const r = await api.ppSolicitudEstado(s.id, acc, motivo, obs.trim());
        setSel(r); cargar();
      }
    } catch (e: any) { setDetErr(e.message || String(e)); }
    finally { setAccionando(false); }
  };

  // Alta al maestro: se hace en Clientes → Maestro (form completo). Vamos con los datos declarados precargados
  // y una marca para volver y vincular el cliente creado a esta solicitud.
  const irAltaMaestro = (s: any) => {
    const cd = s.clienteDatos || {};
    const qs = new URLSearchParams({ alta: "1", sid: String(s.id), sol: s.numero || "",
      nombre: cd.apellido_nombre || s.clienteNombre || "", dni: cd.dni || "", cuil: cd.cuil || "" });
    nav(`/clientes/maestro?${qs.toString()}`);
  };
  // Vincular un cliente existente del maestro a la solicitud express.
  const vincularCliente = async (c: any) => {
    if (!vincSol) return;
    setVincErr("");
    try {
      const r = await api.ppSolicitudPromover(vincSol.id, { cliente_id: c.id });
      setVincSol(null); setVincQ(""); setVincList([]); setSel(r.solicitud); cargar();
      avisar(`Cliente ${c.apellido_nombre} vinculado a la solicitud.`);
    } catch (e: any) { setVincErr(e.message || String(e)); }
  };

  const puedeEditar = permisos.edita && !soloLectura;
  const puedeAprobar = permisos.aprueba && !soloLectura;
  const filtrados = useMemo(() => items, [items]);

  return (
    <div className="sol cfgc">
      <div className="sol-head">
        <div>
          <h1>Solicitudes de crédito</h1>
          <p className="muted">Carga y evaluación de solicitudes de la línea nueva. Cliente registrado o alta express. Una solicitud aprobada se puede originar como contrato.</p>
        </div>
        {(permisos.edita && !soloLectura) && <button className="btn primary" onClick={abrirNueva}>+ Nueva solicitud</button>}
      </div>

      <div className="sol-filtros">
        <button className={filtro === "" ? "on" : ""} onClick={() => setFiltro("")}>Todas</button>
        {estados.map((e) => <button key={e} className={filtro === e ? "on" : ""} onClick={() => setFiltro(e)}>{e}</button>)}
        <input placeholder="Buscar cliente o N°…" value={q} onChange={(e) => setQ(e.target.value)} style={{ marginLeft: "auto" }} />
      </div>

      {err && <div className="cfgc-err" style={{ margin: "8px 0" }}>{err}</div>}

      {nueva && (
        <div className="sol-modal-scrim" onClick={cerrarNueva}>
          <div className="sol-modal" onClick={(e) => e.stopPropagation()}>
            <div className="sol-modal-head">
              <h3>Nueva solicitud</h3>
              <button className="sol-modal-x" onClick={cerrarNueva} title="Cerrar">✕</button>
            </div>
            <ol className="sol-steps">
              {["Solicitante", "Simulación", "Confirmación"].map((t, i) => {
                const n = i + 1;
                return <li key={t} className={`sol-step ${paso === n ? "on" : paso > n ? "done" : ""}`}>
                  <span className="sol-step-n">{paso > n ? "✓" : n}</span>{t}</li>;
              })}
            </ol>
            <div className="sol-modal-body">
              {err && <div className="cfgc-err" style={{ marginBottom: 10 }}>{err}</div>}

              {paso === 1 && (
                <>
                  {!form.cliente_id ? (
                    <div style={{ background: "var(--surface-2)", borderRadius: 11, padding: 12, marginBottom: 12 }}>
                      <b style={{ fontSize: 13 }}>🔎 Buscar cliente <span className="req">*</span></b>
                      <span className="muted" style={{ fontSize: 11.5 }}> · elegí un cliente del maestro (el alta está en Clientes → Maestro)</span>
                      <input style={{ width: "100%", marginTop: 8 }} value={cliQ} placeholder="Buscar por apellido y nombre, CUIL o DNI…" onChange={(e) => setCliQ(e.target.value)} />
                      {buscandoCli && <div className="hint" style={{ marginTop: 6 }}>Buscando…</div>}
                      {clis.length > 0 && (
                        <div style={{ marginTop: 8, maxHeight: 200, overflowY: "auto", display: "flex", flexDirection: "column", gap: 4 }}>
                          {clis.map((c) => (
                            <button type="button" key={c.id} className="btn" style={{ justifyContent: "flex-start", textAlign: "left", fontWeight: 400 }} onClick={() => elegirCliente(c)}>
                              <b>{c.apellido_nombre}</b>&nbsp;— CUIL {c.cuil || "—"} · DNI {c.dni || "—"}
                            </button>
                          ))}
                        </div>
                      )}
                      {cliQ.trim().length >= 2 && !buscandoCli && clis.length === 0 && (
                        <div className="hint" style={{ marginTop: 6 }}>Sin resultados. Si es un cliente nuevo, dalo de alta en <a href="/creditos/clientes/maestro">Clientes → Maestro</a>.</div>
                      )}
                    </div>
                  ) : (
                    <div style={{ display: "flex", alignItems: "center", gap: 12, background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 11, padding: "12px 14px", marginBottom: 12 }}>
                      <div style={{ flex: 1 }}>
                        <div className="eyebrow">Cliente</div>
                        <b style={{ fontSize: 15 }}>{cliSel?.apellido_nombre}</b>
                        <div className="muted" style={{ fontSize: 12 }}>CUIL {cliSel?.cuil || "—"} · DNI {cliSel?.dni || "—"}</div>
                      </div>
                      <button type="button" className="btn" onClick={cambiarCliente}>Cambiar cliente</button>
                    </div>
                  )}
                  <div className="sol-grid">
                  <label>Segmento
                    <select value={form.segmento} onChange={(e) => setForm({ ...form, segmento: e.target.value })}>
                      <option value="">(cualquiera)</option>
                      {cat.segmentos.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </label>
                  <label>Edad <small className="muted">(18–99)</small>
                    <input type="number" min={18} max={99} step={1} value={form.edad}
                      onChange={(e) => setForm({ ...form, edad: clampNum(e.target.value, 0, 99) })} />
                    {edadInvalida && <small className="cfgc-err" style={{ marginTop: 4 }}>La edad debe estar entre 18 y 99.</small>}</label>
                  <label>Antigüedad (meses) <small className="muted">(0–1200)</small>
                    <input type="number" min={0} max={1200} step={1} value={form.antiguedad_meses}
                      onChange={(e) => setForm({ ...form, antiguedad_meses: clampNum(e.target.value, 0, 1200) })} /></label>
                  <label>Relación
                    <select value={form.relacion} onChange={(e) => setForm({ ...form, relacion: e.target.value })}>
                      {RELACIONES.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </label>
                  </div>
                </>
              )}

              {paso === 2 && (
                <>
                  <div className="sol-grid">
                    <label>Línea <span className="req">*</span>
                      <select value={form.producto_id} onChange={(e) => { setForm({ ...form, producto_id: e.target.value }); setSim(null); }}>
                        {lineas.map((l) => <option key={l.id} value={l.id}>{l.nombre} ({l.codigo})</option>)}
                      </select>
                    </label>
                    <label>Monto <span className="req">*</span><input type="number" min={1} max={999999999} step={1} value={form.monto_solicitado} onChange={(e) => { setForm({ ...form, monto_solicitado: Math.max(0, Math.min(999999999, Math.floor(Number(e.target.value) || 0))) }); setSim(null); }} /></label>
                    <label>Plazo (cuotas) <span className="req">*</span> <small className="muted">(1–240)</small><input type="number" min={1} max={240} step={1} value={form.plazo_solicitado} onChange={(e) => { setForm({ ...form, plazo_solicitado: Math.max(0, Math.min(240, Math.floor(Number(e.target.value) || 0))) }); setSim(null); }} /></label>
                  </div>
                  <div className="muted" style={{ marginTop: 10, fontSize: 12 }}>
                    {simulando ? "Calculando…" : paso2OK ? "La simulación se recalcula automáticamente al cambiar los datos." : "Completá línea, monto y plazo para simular."}
                  </div>
                  {sim && (
                    <div className="sol-sim">
                      <div className="sol-sim-kpis">
                        <div><small>Cuota promedio</small><b>{money(sim.cuotaPromedio)}</b></div>
                        <div><small>Total a pagar</small><b>{money(sim.totalCuotas)}</b></div>
                        <div><small>Cuotas</small><b>{sim.cantidadCuotas}</b></div>
                        <div><small>TNA</small><b>{sim.tna}%</b></div>
                      </div>
                      {sim.elegible === false
                        ? <p className="cfgc-err" style={{ marginTop: 8 }}>No cumple las condiciones: {sim.motivos.join(" · ")}. Ajustá los datos o elegí otra línea para continuar.</p>
                        : <p className="muted" style={{ marginTop: 8 }}>✓ Elegible con estos datos.</p>}
                    </div>
                  )}
                </>
              )}

              {paso === 3 && (
                <>
                  <div className="sol-resumen">
                    <div><span>Cliente</span>{cliSel?.apellido_nombre || "—"}</div>
                    <div><span>Línea</span>{lineas.find((l) => l.id === form.producto_id)?.nombre || "—"}</div>
                    <div><span>Monto</span>{money(Number(form.monto_solicitado))}</div>
                    <div><span>Plazo</span>{form.plazo_solicitado} cuotas</div>
                    {sim && <div><span>Cuota estimada</span>{money(sim.cuotaPromedio)}</div>}
                    {sim && <div><span>Elegible</span>{sim.elegible === false ? "No (revisar)" : "Sí"}</div>}
                  </div>
                  <div className="sol-grid" style={{ marginTop: 12 }}>
                    <label>Destino
                      <select value={form.datos_adicionales.destino} onChange={(e) => setForm({ ...form, datos_adicionales: { ...form.datos_adicionales, destino: e.target.value } })}>
                        <option value="">(sin especificar)</option>
                        {Object.entries(DESTINO).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                      </select>
                    </label>
                    <label>Relación
                      <select value={form.relacion} onChange={(e) => setForm({ ...form, relacion: e.target.value })}>
                        {RELACIONES.map((r) => <option key={r} value={r}>{r}</option>)}
                      </select>
                    </label>
                  </div>
                  <label style={{ display: "block", marginTop: 10 }}>Observaciones
                    <textarea value={form.datos_adicionales.observaciones} rows={2} style={{ width: "100%" }}
                      onChange={(e) => setForm({ ...form, datos_adicionales: { ...form.datos_adicionales, observaciones: e.target.value } })} />
                  </label>
                </>
              )}
            </div>

            <div className="sol-modal-foot">
              <button className="btn" onClick={cerrarNueva}>Cancelar</button>
              <div style={{ flex: 1 }} />
              {paso > 1 && <button className="btn" onClick={() => setPaso(paso - 1)}>← Volver</button>}
              {paso === 1 && <button className="btn primary" disabled={!paso1OK} onClick={() => { setPaso(2); if (!sim) simular(); }}>Continuar →</button>}
              {paso === 2 && <button className="btn primary" disabled={!paso2OK || sim?.elegible === false} title={sim?.elegible === false ? "No cumple las condiciones de la línea" : ""} onClick={() => setPaso(3)}>Continuar →</button>}
              {paso === 3 && <>
                <button className="btn" disabled={creando || sim?.elegible === false} onClick={() => crear(false)}>Guardar borrador</button>
                <button className="btn primary" disabled={creando || sim?.elegible === false} onClick={() => crear(true)} title="Crea la solicitud y la manda a evaluación (queda en el Inbox para aprobar)">{creando ? "Creando…" : "Crear y enviar a evaluación"}</button>
              </>}
            </div>
          </div>
        </div>
      )}

      <table className="sol-table">
        <thead><tr><th>N°</th><th>Cliente</th><th>Monto</th><th>Plazo</th><th>Cuota est.</th><th>Estado</th><th>Elegible</th><th></th></tr></thead>
        <tbody>
          {filtrados.map((s) => (
            <tr key={s.id} className={sel?.id === s.id ? "on" : ""} onClick={() => { setSel(s); setNueva(false); }}>
              <td><b>{s.numero}</b></td>
              <td>{s.clienteNombre}{s.solicitanteTipo === "NO_REGISTRADO" && <span className="pill" style={{ marginLeft: 6, fontSize: 9 }}>express</span>}</td>
              <td className="num">{money(s.monto)}</td>
              <td className="num">{s.plazo}</td>
              <td className="num">{money(s.evaluacion?.cuota_estimada || 0)}</td>
              <td><span className={"pill " + (ESTADO_CLASS[s.estado] || "")}>{s.estado}</span></td>
              <td>{s.evaluacion?.elegible ? "✓" : "✕"}</td>
              <td>{s.estado === "APROBADA" && <span className="pill ok" style={{ fontSize: 9 }}>lista p/ originar</span>}</td>
            </tr>
          ))}
          {filtrados.length === 0 && <tr><td colSpan={8} className="muted" style={{ textAlign: "center", padding: 20 }}>Sin solicitudes.</td></tr>}
        </tbody>
      </table>

      {sel && (
        <div className="sol-modal-scrim" onClick={() => setSel(null)}>
          <div className="sol-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 760 }}>
            <div className="sol-modal-head">
              <h3>{sel.numero} · {sel.clienteNombre} <span className={"pill " + (ESTADO_CLASS[sel.estado] || "")}>{sel.estado}</span>
                {sel.solicitanteTipo === "NO_REGISTRADO" && <span className="pill" style={{ marginLeft: 6, fontSize: 9 }}>express</span>}</h3>
              <button className="sol-modal-x" onClick={() => setSel(null)} title="Cerrar">✕</button>
            </div>
            <div className="sol-modal-body">
              {detErr && <div className="cfgc-err" style={{ marginBottom: 10 }}>{detErr}</div>}
              <div className="sol-grid">
                <div><small>Línea</small><b>{lineas.find((l) => l.id === sel.productoId)?.nombre || sel.productoId}</b></div>
                <div><small>Monto</small><b>{money(sel.monto)}</b></div>
                <div><small>Plazo</small><b>{sel.plazo} cuotas</b></div>
                <div><small>TNA ofrecida</small><b>{sel.evaluacion?.tna_ofrecida ?? "—"}%</b></div>
                <div><small>Cuota estimada</small><b>{money(sel.evaluacion?.cuota_estimada || 0)}</b></div>
                <div><small>Relación</small><b>{sel.relacion}</b></div>
                {sel.datosAdicionales?.destino && <div><small>Destino</small><b>{DESTINO[sel.datosAdicionales.destino] || sel.datosAdicionales.destino}</b></div>}
                {sel.datosAdicionales?.cbu && <div><small>CBU</small><b>{sel.datosAdicionales.cbu}</b></div>}
                {sel.datosAdicionales?.sueldo_declarado && <div><small>Sueldo {sel.datosAdicionales.haberes_fuente === "micatamarca" ? "verificado" : "declarado"}</small><b>{money(sel.datosAdicionales.sueldo_declarado)}{sel.datosAdicionales.afectacion != null && ` · afect. ${sel.datosAdicionales.afectacion}%`}</b></div>}
              </div>
              {sel.evaluacion?.motivos?.length > 0 && <p className="cfgc-err" style={{ marginTop: 8 }}>No elegible: {sel.evaluacion.motivos.join(" · ")}</p>}
              {sel.motivoRechazo && <p className="muted" style={{ marginTop: 6 }}>Motivo: {sel.motivoRechazo}</p>}
              {sel.datosAdicionales?.observaciones && <p className="muted" style={{ marginTop: 6 }}>Nota del solicitante: {sel.datosAdicionales.observaciones}</p>}
              {docs.length > 0 && (
                <div className="sol-docs" style={{ marginTop: 10 }}>
                  <small>Documentación del solicitante</small>
                  {docs.map((d) => (
                    <div className="sol-doc" key={d.id}>
                      <span className="pill">{TIPODOC[d.tipo] || d.tipo}</span>
                      <button className="sol-doc-link" onClick={() => api.ppSolicitudDocAbrir(sel.id, d.id)}>{d.nombre}</button>
                      <span className="muted" style={{ fontSize: 12 }}>{kb(d.tamano)}</span>
                    </div>
                  ))}
                </div>
              )}
              {sel.datosLiquidacion?.aplica && (
                <div className="sol-revli">
                  <small>Revisión para liquidar {sel.datosLiquidacion.lista
                    ? <span className="pill ok" style={{ marginLeft: 6 }}>lista</span>
                    : <span className="pill warn" style={{ marginLeft: 6 }}>faltan datos</span>}</small>
                  <div className="sol-revli-items">
                    {sel.datosLiquidacion.items.map((it: any) => (
                      <div className={`sol-revli-item ${it.ok ? "ok" : it.requerido ? "crit" : "warn"}`} key={it.campo}>
                        <span className="sol-revli-ck">{it.ok ? "✓" : it.requerido ? "✕" : "○"}</span>
                        <div className="sol-revli-txt">
                          <span className="sol-revli-lbl">{it.label}{!it.requerido && <em> (opcional)</em>}</span>
                          <span className="sol-revli-val">{it.ok ? (it.valor || "—") : (it.requerido ? "falta" : "—")}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  {!sel.datosLiquidacion.lista && <p className="cfgc-err" style={{ marginTop: 6 }}>No se puede originar: completá {sel.datosLiquidacion.faltantes.join(", ")}.</p>}
                </div>
              )}
              <div style={{ marginTop: 14 }}>
                <button className={`sol-crono-toggle ${cronoAbierto ? "abierto" : ""}`} onClick={() => setCronoAbierto((v) => !v)}>
                  <span className="chev">▶</span>
                  <span>Cronograma estimado{crono.length > 0 ? ` · ${crono.length} cuotas` : ""}{cargandoCrono ? " · calculando…" : ""}</span>
                </button>
                {cronoAbierto && crono.length > 0 && (
                  <div className="sol-crono-wrap" style={{ marginTop: 8 }}>
                    <table className="sol-crono">
                      <thead><tr><th>Cuota</th><th>Vencimiento</th><th>Capital</th><th>Interés</th><th>Total</th></tr></thead>
                      <tbody>
                        {crono.map((q) => (
                          <tr key={q.numero_cuota}>
                            <td className="num">{q.numero_cuota}</td><td>{q.fecha_vencimiento}</td>
                            <td className="num">{money(q.capital)}</td><td className="num">{money(q.interes)}</td>
                            <td className="num"><b>{money(q.total)}</b></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {cronoAbierto && !cargandoCrono && crono.length === 0 && <p className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>Sin cronograma disponible.</p>}
              </div>
              {!["ORIGINADA", "ANULADA"].includes(sel.estado) && (
                <label style={{ display: "block", marginTop: 12 }}>Observación del asesor <span className="muted">(opcional; para rechazar es el motivo)</span>
                  <textarea value={obs} rows={2} style={{ width: "100%" }} maxLength={500}
                    onChange={(e) => setObs(e.target.value)} placeholder="Nota interna que queda registrada en la solicitud…" />
                </label>
              )}
              {sel.estado === "ORIGINADA" && sel.contratoId && <p style={{ marginTop: 12 }}><span className="pill brand">Originada · contrato {sel.contratoId.slice(0, 8)}</span></p>}
              {sel.estado === "EN_EVALUACION" && sel.solicitanteTipo === "NO_REGISTRADO" && (
                <p className="cfgc-err" style={{ marginTop: 12 }}>⚠ El cliente <b>no está registrado</b> en el maestro. Para aprobar, primero <b>Dar de alta en maestro</b> o <b>Vincular cliente</b>.</p>
              )}
            </div>
            <div className="sol-modal-foot" style={{ flexWrap: "wrap" }}>
              <button className="btn" onClick={() => setSel(null)}>Cerrar</button>
              <div style={{ flex: 1 }} />
              {sel.solicitanteTipo === "NO_REGISTRADO" && puedeEditar && <>
                <button className="btn" onClick={() => irAltaMaestro(sel)} title="Crea el cliente en Clientes → Maestro (formulario completo) y vuelve a vincularlo.">Dar de alta en maestro</button>
                <button className="btn" onClick={() => { setVincSol(sel); setVincQ(""); setVincList([]); setVincErr(""); }} title="Vincular un cliente que ya existe en el maestro.">Vincular cliente</button>
              </>}
              {sel.estado === "BORRADOR" && <button className="btn primary" disabled={accionando || !puedeEditar} onClick={() => resolver("enviar")}>Enviar a evaluación</button>}
              {!["ORIGINADA", "ANULADA"].includes(sel.estado) && <button className="btn" disabled={accionando || !puedeEditar} title="Baja administrativa del trámite (error de carga, duplicada o el cliente desistió). No es una decisión crediticia." onClick={() => resolver("anular")}>Anular</button>}
              {sel.estado === "EN_EVALUACION" && <>
                <button className="btn" disabled={accionando || !puedeAprobar} title="Decisión crediticia NEGATIVA: se evaluó y se deniega. Requiere rol aprobador y motivo (Observación)." onClick={() => resolver("rechazar")}>Rechazar</button>
                <button className="btn primary" disabled={accionando || !puedeAprobar || sel.solicitanteTipo === "NO_REGISTRADO"}
                  title={sel.solicitanteTipo === "NO_REGISTRADO" ? "El cliente no está registrado en el maestro: dalo de alta o vinculá uno existente antes de aprobar." : "Aprueba el crédito (decisión crediticia). Requiere rol aprobador."}
                  onClick={() => resolver("aprobar")}>Aprobar</button>
              </>}
              {sel.estado === "APROBADA" && <button className="btn primary" disabled={accionando || (sel.datosLiquidacion?.aplica && !sel.datosLiquidacion?.lista)}
                title={sel.datosLiquidacion?.aplica && !sel.datosLiquidacion?.lista ? "Faltan datos para liquidar" : ""}
                onClick={() => resolver("originar")}>💸 Originar contrato</button>}
            </div>
          </div>
        </div>
      )}

      {vincSol && (
        <div className="sol-modal-scrim" onClick={() => setVincSol(null)}>
          <div className="sol-modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 520 }}>
            <div className="sol-modal-head">
              <h3>Vincular cliente del maestro</h3>
              <button className="sol-modal-x" onClick={() => setVincSol(null)} title="Cerrar">✕</button>
            </div>
            <div className="sol-modal-body">
              <p className="muted" style={{ marginTop: 0 }}>Elegí el cliente ya existente para vincular a <b>{vincSol.numero}</b>. Si todavía no existe, usá <b>Dar de alta en maestro</b>.</p>
              {vincErr && <div className="cfgc-err" style={{ marginBottom: 10 }}>{vincErr}</div>}
              <input style={{ width: "100%" }} value={vincQ} placeholder="Buscar por apellido y nombre, CUIL o DNI…" onChange={(e) => setVincQ(e.target.value)} />
              {vincList.length > 0 && (
                <div style={{ marginTop: 8, maxHeight: 240, overflowY: "auto", display: "flex", flexDirection: "column", gap: 4 }}>
                  {vincList.map((c) => (
                    <button type="button" key={c.id} className="btn" style={{ justifyContent: "flex-start", textAlign: "left", fontWeight: 400 }} onClick={() => vincularCliente(c)}>
                      <b>{c.apellido_nombre}</b>&nbsp;— {c.id_cliente || c.id} · CUIL {c.cuil || "—"} · DNI {c.dni || "—"}
                    </button>
                  ))}
                </div>
              )}
              {vincQ.trim().length >= 2 && vincList.length === 0 && <p className="hint" style={{ marginTop: 6 }}>Sin resultados.</p>}
            </div>
            <div className="sol-modal-foot"><button className="btn" onClick={() => setVincSol(null)}>Cancelar</button></div>
          </div>
        </div>
      )}
    </div>
  );
}
