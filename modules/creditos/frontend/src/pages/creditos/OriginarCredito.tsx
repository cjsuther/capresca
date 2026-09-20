import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import { useNivelActual } from "../../permisos";
import { avisar } from "../../ui/dialog";

// Originar Crédito — SÓLO el proceso guiado de originación:
// 1) Cliente (validar datos) · 2) Simular · 3) Datos adicionales · 4) Otorgar (instrumentar → A_LIQUIDAR).
// El DESEMBOLSO NO se hace acá: pasa por "Liquidación por lote" (control de liquidación diario).
// La cartera/tablero vive en "Tablero de cartera" y el servicing en "Situación del cliente".

const money = (n: number) =>
  isFinite(n) ? new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 }).format(n) : "—";
const fmtCuil = (c: string) => (c && c.length === 11 ? `${c.slice(0, 2)}-${c.slice(2, 10)}-${c.slice(10)}` : c || "");

const ESTADO_CTO: Record<string, string> = { ACTIVO: "pub", A_LIQUIDAR: "rev", CERRADO: "ret", CANCELADO: "ret" };
const PASOS = ["Cliente", "Simular", "Datos adicionales", "Otorgar", "Instrumentado"];
const DESTINOS = ["CONSUMO", "VIVIENDA", "REFACCIÓN", "VEHÍCULO", "LIBRE DISPONIBILIDAD", "CANCELACIÓN DE DEUDAS"];

// Arma el payload del cronograma para el backend (única fuente de verdad).
function previewPayload(cfg: any, comps: any[], tnaEff: number, monto: number, plazo: number) {
  const conf = (cod: string) => (comps?.find((c) => c.codigo === cod && c.activo)?.config || {}) as any;
  const ch = conf("CHARGE"), tx = conf("TAX"), rs = conf("REPAYMENT_SCHEDULE");
  return {
    sistema: cfg.sistema, monto, plazo, tna: tnaEff, cargoOtorg: cfg.cargoOtorg,
    gracia: cfg.graciaCapital || 0, frecuencia: cfg.frecuencia,
    cargos: (ch.items || []).map((it: any) => ({ porcentaje: it.porcentaje, momento: it.momento })),
    impuestos: (tx.items || []).map((it: any) => ({ base: it.base, porcentaje: it.porcentaje })),
    diaPago: rs.diaPago ?? 5, primerVencimientoDias: rs.primerVencimientoDias ?? 30,
    ajusteFinDeSemana: rs.ajusteFinDeSemana ?? "SIN_AJUSTE", tipoCuota: rs.tipoCuota ?? "VENCIDA",
    financiable: !!ch.financiable, cargoMomento: ch.momento ?? "PRORRATEADO",
  };
}

export default function OriginarCredito() {
  const nav = useNavigate();
  const { soloLectura } = useNivelActual();
  const [oferta, setOferta] = useState<any[]>([]);
  const [cargando, setCargando] = useState(true);
  const [cat, setCat] = useState<{ segmentos: string[]; canales: string[]; relaciones: { codigo: string; bonusTna: number }[] }>({ segmentos: [], canales: [], relaciones: [] });

  // ---- estado del wizard ----
  const [paso, setPaso] = useState(1);
  const [cliente, setCliente] = useState({ cliente_id: 0, nombre: "", cuil: "", dni: "", segmento: "", canal: "SUCURSAL", edad: "", antiguedad: "", relacion: "ESTANDAR", solicitud_id: 0, solicitud_pp_id: "" });
  const [cliQ, setCliQ] = useState("");            // buscador de clientes (typeahead)
  const [clis, setClis] = useState<any[]>([]);
  const [buscandoCli, setBuscandoCli] = useState(false);
  const [solQ, setSolQ] = useState("");
  const [sols, setSols] = useState<any[]>([]);
  const [sel, setSel] = useState<any>(null);
  const [form, setForm] = useState({ monto: 1200000, plazo: 24, tasa: 0 });
  const [prev, setPrev] = useState<{ rows: any[]; resumen: any } | null>(null);
  const [adic, setAdic] = useState({ destino: "CONSUMO", cbu: "", garante: "", observaciones: "" });
  const [nuevoCto, setNuevoCto] = useState<any>(null);

  const ctx = () => ({
    segmento: cliente.segmento || undefined, canal: cliente.canal || undefined,
    edad: cliente.edad ? Number(cliente.edad) : undefined,
    antiguedad_meses: cliente.antiguedad ? Number(cliente.antiguedad) : undefined,
  });
  const bonusRel = () => cat.relaciones.find((r) => r.codigo === cliente.relacion)?.bonusTna || 0;

  async function recargar() {
    const [of, sg] = await Promise.all([api.ppOferta(ctx()), api.ctoSegmentos()]);
    setOferta(of.items); setCat(sg);
  }
  useEffect(() => { recargar().catch((e) => avisar({ tipo: "error", mensaje: e.message })).finally(() => setCargando(false)); }, []);
  // Prefill desde una solicitud nueva APROBADA (botón "Originar" de Solicitudes de crédito).
  useEffect(() => {
    const raw = sessionStorage.getItem("originar_solicitud_pp");
    if (!raw) return;
    sessionStorage.removeItem("originar_solicitud_pp");
    try {
      const s = JSON.parse(raw);
      setCliente((c) => ({ ...c, nombre: s.clienteNombre || "", segmento: s.segmento || "", canal: s.canal || "SUCURSAL",
        edad: s.edad ? String(s.edad) : "", antiguedad: s.antiguedadMeses ? String(s.antiguedadMeses) : "",
        relacion: s.relacion || "ESTANDAR", solicitud_pp_id: s.id }));
      setForm((f) => ({ ...f, monto: s.monto || f.monto, plazo: s.plazo || f.plazo }));
    } catch { /* ignore */ }
  }, []);
  useEffect(() => { if (!cargando) api.ppOferta(ctx()).then((d) => setOferta(d.items)).catch(() => {}); }, [cliente.segmento, cliente.canal, cliente.edad, cliente.antiguedad]);

  // preview del cronograma en el paso 2 (backend = única fuente de verdad, debounced)
  // Para tasa VARIABLE, la base es cfg.tnaVigente (índice + margen), no cfg.tna (que es 0).
  const tnaBase = sel ? (sel.cfg.tnaVigente ?? sel.cfg.tna) : 0;
  const tnaEff = sel ? Math.max(0, ((negociableSel() ? form.tasa : tnaBase) + bonusRel())) : 0;
  function negociableSel() { return sel && sel.cfg.tnaNegociable && sel.cfg.modalidad === "FIJA"; }
  useEffect(() => {
    if (!sel) { setPrev(null); return; }
    const t = setTimeout(() => {
      api.ppPreview(previewPayload(sel.cfg, sel.componentes, tnaEff, form.monto, form.plazo))
        .then(setPrev).catch(() => {});
    }, 200);
    return () => clearTimeout(t);
  }, [sel, form.monto, form.plazo, form.tasa, cliente.relacion]);

  const fueraMonto = sel && (form.monto < sel.cfg.montoMin || form.monto > sel.cfg.montoMax);
  const fueraPlazo = sel && (form.plazo < sel.cfg.plazoMin || form.plazo > sel.cfg.plazoMax);
  const fueraTasa = negociableSel() && (form.tasa < sel.cfg.tnaMin || form.tasa > sel.cfg.tnaMax);

  // ---- pasos ----
  async function buscarSols() { try { const r = await api.ctoSolicitudes(solQ); setSols(r.items); } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); } }
  function elegirSol(s: any) {
    setCliente((c) => ({ ...c, cliente_id: s.cliente_id || 0, nombre: s.apellido_nombre, cuil: s.cuil || "", dni: s.dni || "", solicitud_id: s.id }));
    setSols([]); setSolQ("");
  }

  // Buscador de clientes (typeahead): el cliente se ELIGE del maestro, no se carga a mano (el alta está en
  // Clientes → Maestro). Busca por apellido/nombre, CUIL o DNI mientras se escribe (debounce).
  useEffect(() => {
    const q = cliQ.trim();
    if (cliente.cliente_id || q.length < 2) { setClis([]); return; }
    let vivo = true; setBuscandoCli(true);
    const t = setTimeout(async () => {
      try { const r = await api.clientes({ q, limit: 8 }); if (vivo) setClis(r.items); }
      catch { if (vivo) setClis([]); }
      finally { if (vivo) setBuscandoCli(false); }
    }, 300);
    return () => { vivo = false; clearTimeout(t); };
  }, [cliQ, cliente.cliente_id]);

  function elegirCliente(c: any) {
    setCliente((prev) => ({
      ...prev, cliente_id: c.id, nombre: c.apellido_nombre, cuil: c.cuil || "", dni: c.dni || "",
      solicitud_id: 0, solicitud_pp_id: "",
    }));
    setClis([]); setCliQ("");
  }
  function cambiarCliente() {
    setCliente((c) => ({ ...c, cliente_id: 0, nombre: "", cuil: "", dni: "", solicitud_id: 0, solicitud_pp_id: "" }));
    setCliQ(""); setClis([]);
  }
  function elegirProducto(p: any) {
    if (p.elegibilidad && !p.elegibilidad.elegible) return;
    setSel(p);
    setForm({ monto: Math.min(p.cfg.montoMax, Math.max(p.cfg.montoMin, form.monto || 1200000)), plazo: Math.min(p.cfg.plazoMax, Math.max(p.cfg.plazoMin, form.plazo || 24)), tasa: p.cfg.tnaVigente ?? p.cfg.tna });
  }
  const puedeAvanzar = () => {
    if (paso === 1) return !!(cliente.cliente_id || cliente.solicitud_id || cliente.solicitud_pp_id);
    if (paso === 2) return sel && !fueraMonto && !fueraPlazo && !fueraTasa;
    if (paso === 3) return adic.cbu.replace(/\D/g, "").length === 22;   // CBU de acreditación obligatorio (H-134)
    return true;
  };
  async function otorgar() {
    if (!sel) return;
    try {
      const c = await api.ctoOriginar({
        producto_id: sel.id, cliente_nombre: cliente.nombre, monto: form.monto, plazo: form.plazo,
        ...(negociableSel() ? { tasa: form.tasa } : {}), ...ctx(), relacion: cliente.relacion,
        ...(cliente.solicitud_id ? { solicitud_id: cliente.solicitud_id } : {}),
        ...(cliente.solicitud_pp_id ? { solicitud_pp_id: cliente.solicitud_pp_id } : {}),
        datos_adicionales: adic, desembolsar: false,
      });
      setNuevoCto(c); setPaso(5);
    } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); }
  }
  function nuevaOriginacion() {
    setPaso(1); setCliente({ cliente_id: 0, nombre: "", cuil: "", dni: "", segmento: "", canal: "SUCURSAL", edad: "", antiguedad: "", relacion: "ESTANDAR", solicitud_id: 0, solicitud_pp_id: "" });
    setSel(null); setForm({ monto: 1200000, plazo: 24, tasa: 0 }); setPrev(null);
    setAdic({ destino: "CONSUMO", cbu: "", garante: "", observaciones: "" }); setNuevoCto(null); setSols([]); setSolQ(""); setCliQ(""); setClis([]);
  }
  function verContrato() {
    // El servicing del contrato vive en "Situación del cliente": llevamos al usuario ahí, ya filtrado.
    if (nuevoCto?.cliente_nombre) sessionStorage.setItem("situacion_cliente_q", nuevoCto.cliente_nombre);
    nav("/creditos/situacion-linea");
  }

  const liq = nuevoCto?.liquidacion;

  return (
    <div className="cfgc">
      <div className="cfgc-cathead">
        <div>
          <h1>Originar Crédito</h1>
          <p>Proceso guiado: cliente → simulación → datos adicionales → otorgamiento (queda A liquidar). El desembolso se hace desde Liquidación por lote.</p>
        </div>
      </div>

      {/* WIZARD */}
      <div className="card" style={{ padding: 0, marginBottom: 16 }}>
        <div className="cfgc-steps">
          {PASOS.map((t, idx) => { const n = idx + 1; return (
            <div key={t} className={`cfgc-step ${n === paso ? "on" : n < paso ? "done" : ""}`} onClick={() => n < paso && setPaso(n)}>
              <span className="n">{n < paso ? "✓" : n}</span><span className="t">{t}</span>
              {idx < PASOS.length - 1 && <span className="sep" />}
            </div>
          ); })}
        </div>

        <div style={{ padding: 18 }}>
          {/* PASO 1 · CLIENTE — se ELIGE del maestro (el alta está en Clientes → Maestro), no se carga a mano */}
          {paso === 1 && (
            <div>
              {!cliente.nombre ? (
                <>
                  <div style={{ background: "var(--surface-2)", borderRadius: 11, padding: 12, marginBottom: 14 }}>
                    <b style={{ fontSize: 13 }}>🔎 Buscar cliente</b>
                    <span className="muted" style={{ fontSize: 11.5 }}> · elegí un cliente del maestro (para dar de alta uno nuevo, andá a Clientes → Maestro)</span>
                    <input style={{ width: "100%", marginTop: 8 }} value={cliQ} autoFocus
                           placeholder="Buscar por apellido y nombre, CUIL o DNI…" onChange={(e) => setCliQ(e.target.value)} />
                    {buscandoCli && <div className="hint" style={{ marginTop: 6 }}>Buscando…</div>}
                    {clis.length > 0 && (
                      <div style={{ marginTop: 8, maxHeight: 220, overflowY: "auto", display: "flex", flexDirection: "column", gap: 4 }}>
                        {clis.map((c) => (
                          <button key={c.id} className="cfgc-comp" style={{ borderRadius: 8, padding: "7px 10px", fontSize: 12, textAlign: "left" }} onClick={() => elegirCliente(c)}>
                            <span className="nm" style={{ flex: 1 }}><b>{c.apellido_nombre}</b><small>CUIL {fmtCuil(c.cuil)} · DNI {c.dni || "—"}</small></span>
                          </button>
                        ))}
                      </div>
                    )}
                    {cliQ.trim().length >= 2 && !buscandoCli && clis.length === 0 && (
                      <div className="hint" style={{ marginTop: 6 }}>Sin resultados. Si es un cliente nuevo, dalo de alta en <a href="/creditos/clientes/maestro">Clientes → Maestro</a>.</div>
                    )}
                  </div>
                  <div style={{ background: "var(--surface-2)", borderRadius: 11, padding: 12 }}>
                    <b style={{ fontSize: 13 }}>🗂️ …o traer de una solicitud aprobada</b>
                    <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                      <input style={{ flex: 1 }} value={solQ} placeholder="Apellido y nombre o CUIL…" onChange={(e) => setSolQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && buscarSols()} />
                      <button className="btn" onClick={buscarSols}>Buscar</button>
                    </div>
                    {sols.length > 0 && (
                      <div style={{ marginTop: 8, maxHeight: 150, overflowY: "auto", display: "flex", flexDirection: "column", gap: 4 }}>
                        {sols.map((s) => (
                          <button key={s.id} className="cfgc-comp" style={{ borderRadius: 8, padding: "6px 9px", fontSize: 12, textAlign: "left" }} onClick={() => elegirSol(s)}>
                            <span className="nm" style={{ flex: 1 }}><b>{s.apellido_nombre}</b><small>N° {s.id} · CUIL {s.cuil} · {money(s.monto)} · línea {s.linea}</small></span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="hint" style={{ color: "var(--crit)", marginTop: 10 }}>Buscá y elegí un cliente para continuar.</div>
                </>
              ) : (
                <>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 11, padding: "12px 14px" }}>
                    <div style={{ flex: 1 }}>
                      <div className="eyebrow">Cliente {cliente.solicitud_id ? `· 🗂️ Solicitud N° ${cliente.solicitud_id}` : ""}</div>
                      <b style={{ fontSize: 15 }}>{cliente.nombre}</b>
                      <div className="muted" style={{ fontSize: 12 }}>CUIL {fmtCuil(cliente.cuil) || "—"} · DNI {cliente.dni || "—"}</div>
                    </div>
                    <button className="btn ghost" onClick={cambiarCliente}>Cambiar cliente</button>
                  </div>
                  <h4 style={{ margin: "14px 0 10px" }}>Datos para la evaluación</h4>
                  <div className="cfgc-fgrid">
                    <label className="f"><span className="lbl">Segmento</span>
                      <select value={cliente.segmento} onChange={(e) => setCliente({ ...cliente, segmento: e.target.value })}>
                        <option value="">— sin especificar —</option>{cat.segmentos.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}</select></label>
                    <label className="f"><span className="lbl">Canal</span>
                      <select value={cliente.canal} onChange={(e) => setCliente({ ...cliente, canal: e.target.value })}>{cat.canales.map((s) => <option key={s} value={s}>{s}</option>)}</select></label>
                    <label className="f"><span className="lbl">Edad</span><input className="num" type="number" value={cliente.edad} onChange={(e) => setCliente({ ...cliente, edad: e.target.value })} /></label>
                    <label className="f"><span className="lbl">Antigüedad (meses)</span><input className="num" type="number" value={cliente.antiguedad} onChange={(e) => setCliente({ ...cliente, antiguedad: e.target.value })} /></label>
                    <label className="f"><span className="lbl">Relación <small className="muted">(pricing)</small></span>
                      <select value={cliente.relacion} onChange={(e) => setCliente({ ...cliente, relacion: e.target.value })}>
                        {cat.relaciones.map((r) => <option key={r.codigo} value={r.codigo}>{r.codigo}{r.bonusTna ? ` (${r.bonusTna} pts)` : ""}</option>)}</select></label>
                  </div>
                </>
              )}
            </div>
          )}

          {/* PASO 2 · SIMULAR */}
          {paso === 2 && (
            <div className="cfgc-grid" style={{ gridTemplateColumns: "1fr 1fr", alignItems: "start" }}>
              <div>
                <h4 style={{ margin: "0 0 10px" }}>Elegí la línea ({oferta.length})</h4>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(200px,1fr))", gap: 10 }}>
                  {oferta.map((p) => { const noElig = p.elegibilidad && !p.elegibilidad.elegible; return (
                    <button key={p.id} className="cfgc-comp" title={noElig ? p.elegibilidad.motivos.join(" ") : ""} style={{ border: sel?.id === p.id ? "1px solid var(--brand-2)" : "1px solid var(--border)", borderRadius: 11, padding: 12, alignItems: "flex-start", flexDirection: "column", gap: 4, opacity: noElig ? 0.55 : 1, cursor: noElig ? "not-allowed" : "pointer" }} onClick={() => elegirProducto(p)}>
                      <b style={{ fontSize: 13 }}>{p.nombre}</b>
                      <small style={{ color: "var(--ink-faint)" }}>{p.codigo} · {p.cfg.sistema} · {p.cfg.modalidad === "VARIABLE" ? `${p.cfg.tnaVigente}% (${p.cfg.indice})` : `${p.cfg.tna}%`}</small>
                      <small className="num" style={{ color: "var(--ink-soft)" }}>{money(p.cfg.montoMin)}–{money(p.cfg.montoMax)}</small>
                      {noElig ? <small style={{ color: "var(--crit)", fontWeight: 600 }}>⛔ {p.elegibilidad.motivos[0]}</small>
                        : (cliente.segmento || cliente.canal || cliente.edad) ? <small style={{ color: "var(--ok, #1a7f37)", fontWeight: 600 }}>✓ Elegible</small> : null}
                    </button>
                  ); })}
                </div>
                {sel && (
                  <div className="cfgc-fgrid" style={{ marginTop: 14 }}>
                    <label className="f"><span className="lbl">Monto</span><input className="num" type="number" value={form.monto} onChange={(e) => setForm({ ...form, monto: Number(e.target.value) || 0 })} />
                      {fueraMonto && <div className="hint" style={{ color: "var(--crit)" }}>Rango {money(sel.cfg.montoMin)}–{money(sel.cfg.montoMax)}</div>}</label>
                    <label className="f"><span className="lbl">Plazo (cuotas)</span><input className="num" type="number" value={form.plazo} onChange={(e) => setForm({ ...form, plazo: Number(e.target.value) || 1 })} />
                      {fueraPlazo && <div className="hint" style={{ color: "var(--crit)" }}>Rango {sel.cfg.plazoMin}–{sel.cfg.plazoMax}</div>}</label>
                    {negociableSel()
                      ? <label className="f"><span className="lbl">Tasa negociada (%)</span><input className="num" type="number" value={form.tasa} onChange={(e) => setForm({ ...form, tasa: Number(e.target.value) || 0 })} />
                          <div className="hint" style={fueraTasa ? { color: "var(--crit)" } : undefined}>Banda {sel.cfg.tnaMin}%–{sel.cfg.tnaMax}%</div></label>
                      : <label className="f"><span className="lbl">Tasa</span><input className="num" value={sel.cfg.modalidad === "VARIABLE" ? "variable" : sel.cfg.tna + "%"} disabled /></label>}
                  </div>
                )}
                {bonusRel() !== 0 && sel && <div className="hint" style={{ marginTop: 8, color: "var(--brand-2)" }}>🎁 Relación {cliente.relacion}: {bonusRel()} pts → TNA efectiva ≈ <b>{tnaEff.toFixed(2)}%</b></div>}
              </div>
              <div>
                {!sel && <p className="muted">Elegí una línea para simular el crédito.</p>}
                {sel && prev && (
                  <div>
                    <div className="cfgc-metrics">
                      <div className="cfgc-metric hl"><small>{sel.cfg.sistema === "FRANCES" ? "Cuota (aprox.)" : "1ª cuota"}</small><strong className="num">{money(prev.rows[0]?.total || 0)}</strong></div>
                      <div className="cfgc-metric"><small>Costo total</small><strong className="num">{money(prev.resumen.totalCuotas)}</strong></div>
                      <div className="cfgc-metric"><small>Intereses+cargos</small><strong className="num">{money(prev.resumen.totalInteres + prev.resumen.totalCargos)}</strong></div>
                      <div className="cfgc-metric"><small>CFT (TIR)</small><strong className="num">{prev.resumen.cft.toFixed(1)} %</strong></div>
                    </div>
                    <div className="cfgc-twrap" style={{ maxHeight: 240, marginTop: 12 }}>
                      <table>
                        <thead><tr><th>#</th><th>Vto</th><th>Capital</th><th>Interés</th><th>Cargos</th><th>Cuota</th></tr></thead>
                        <tbody>{prev.rows.map((r) => (<tr key={r.numero_cuota}><td><b>{r.numero_cuota}</b></td><td>{r.fecha_vencimiento}</td>
                          <td className="num">{money(r.capital)}</td><td className="num">{money(r.interes)}</td><td className="num">{money(r.cargos)}</td><td className="num"><b>{money(r.total)}</b></td></tr>))}</tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* PASO 3 · DATOS ADICIONALES */}
          {paso === 3 && (
            <div>
              <h4 style={{ margin: "0 0 10px" }}>Datos adicionales de la operación</h4>
              <div className="cfgc-fgrid">
                <label className="f"><span className="lbl">Destino del crédito</span>
                  <select value={adic.destino} onChange={(e) => setAdic({ ...adic, destino: e.target.value })}>{DESTINOS.map((d) => <option key={d} value={d}>{d}</option>)}</select></label>
                <label className="f"><span className="lbl">CBU de acreditación *</span>
                  <input className="num" inputMode="numeric" value={adic.cbu} placeholder="22 dígitos" maxLength={22}
                    onChange={(e) => setAdic({ ...adic, cbu: e.target.value.replace(/\D/g, "").slice(0, 22) })} />
                  {adic.cbu && adic.cbu.replace(/\D/g, "").length !== 22 && <span className="hint" style={{ color: "var(--warn)" }}>Faltan {22 - adic.cbu.replace(/\D/g, "").length} dígito(s).</span>}
                </label>
                <label className="f"><span className="lbl">Garante (opcional)</span><input value={adic.garante} onChange={(e) => setAdic({ ...adic, garante: e.target.value })} placeholder="Apellido y nombre" /></label>
                <label className="f" style={{ gridColumn: "1 / -1" }}><span className="lbl">Observaciones</span><input value={adic.observaciones} onChange={(e) => setAdic({ ...adic, observaciones: e.target.value })} /></label>
              </div>
            </div>
          )}

          {/* PASO 4 · OTORGAR (revisión) */}
          {paso === 4 && sel && (
            <div>
              <h4 style={{ margin: "0 0 10px" }}>Revisión final</h4>
              <div className="cfgc-condlist" style={{ marginBottom: 12 }}>
                <Fila k="Cliente" v={`${cliente.nombre}${cliente.cuil ? ` · CUIL ${cliente.cuil}` : ""}`} />
                <Fila k="Línea" v={`${sel.nombre} (${sel.codigo}) · ${sel.cfg.sistema}`} />
                <Fila k="Monto / plazo" v={`${money(form.monto)} · ${form.plazo} cuotas`} />
                <Fila k="TNA efectiva" v={`${tnaEff.toFixed(2)}%${bonusRel() ? ` (relación ${cliente.relacion})` : ""}`} />
                <Fila k="1ª cuota / Costo" v={prev ? `${money(prev.rows[0]?.total || 0)} · ${money(prev.resumen.totalCuotas)}` : "—"} />
                <Fila k="CFT (TIR)" v={prev ? `${prev.resumen.cft.toFixed(1)} %` : "—"} />
                <Fila k="Destino / CBU" v={`${adic.destino}${adic.cbu ? ` · CBU ${adic.cbu}` : ""}`} />
                {adic.garante && <Fila k="Garante" v={adic.garante} />}
              </div>
              <p className="muted" style={{ fontSize: 12 }}>Al otorgar, el contrato queda <b>pendiente de liquidación</b> (A_LIQUIDAR) y pasás al desembolso.</p>
            </div>
          )}

          {/* PASO 5 · INSTRUMENTADO — el contrato queda A_LIQUIDAR; el desembolso se hace por Liquidación por lote */}
          {paso === 5 && nuevoCto && (
            <div>
              <h4 style={{ margin: "0 0 10px" }}>Contrato originado · {nuevoCto.numero_contrato} <span className={`pill ${ESTADO_CTO[nuevoCto.estado] || "rev"}`} style={{ fontSize: 10 }}>{nuevoCto.estado}</span></h4>
              {liq && (
                <div className="cfgc-metrics" style={{ marginBottom: 12 }}>
                  <div className="cfgc-metric"><small>Monto del crédito</small><strong className="num">{money(liq.monto)}</strong></div>
                  <div className="cfgc-metric"><small>Cargos financiados (al capital)</small><strong className="num">{money(liq.cargosFinanciados || 0)}</strong></div>
                  <div className="cfgc-metric"><small>Cargos en cuotas</small><strong className="num">{money(liq.cargosEnCuotas || 0)}</strong></div>
                  <div className="cfgc-metric hl"><small>Neto a acreditar</small><strong className="num">{money(liq.neto)}</strong></div>
                </div>
              )}
              <div className="cfgc-condlist" style={{ marginBottom: 12 }}>
                <Fila k="Cliente" v={nuevoCto.cliente_nombre} />
                <Fila k="Acreditar en" v={adic.cbu ? `CBU ${adic.cbu}` : "(sin CBU cargado)"} />
                <Fila k="Destino" v={nuevoCto.datos_adicionales?.destino || adic.destino} />
              </div>
              <div className="hint" style={{ marginBottom: 12 }}>
                El contrato quedó <b>A liquidar</b>. El <b>desembolso</b> se hace desde <b>Liquidación por lote</b>
                {" "}(por día de originación), respetando el control de liquidación.
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button className="btn primary" onClick={() => nav("/creditos/liquidacion-lote")}>Ir a Liquidación por lote →</button>
                <button className="btn" onClick={nuevaOriginacion}>＋ Nueva originación</button>
                <button className="btn" onClick={verContrato}>Ver contrato →</button>
              </div>
            </div>
          )}
        </div>

        {/* navegación del wizard */}
        {paso < 5 && (
          <div style={{ display: "flex", gap: 8, padding: "12px 18px", borderTop: "1px solid var(--border)" }}>
            {paso > 1 && <button className="btn ghost" onClick={() => setPaso(paso - 1)}>← Anterior</button>}
            <span style={{ flex: 1 }} />
            {paso < 4 && <button className="btn primary" disabled={!puedeAvanzar()} onClick={() => setPaso(paso + 1)}>Siguiente →</button>}
            {paso === 4 && (soloLectura
              ? <span className="pill">🔒 Sólo lectura — no podés otorgar</span>
              : <button className="btn primary" onClick={otorgar}>✓ Otorgar crédito</button>)}
          </div>
        )}
      </div>
    </div>
  );
}

function Fila({ k, v }: { k: string; v: string }) {
  return <div className="cfgc-cond"><span className="k">{k}</span><span className="v">{v}</span></div>;
}
