import { Fragment, useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import { useNivelActual } from "../../permisos";
import { confirmar, avisar, pedirTexto } from "../../ui/dialog";

const money = (n: any) => "$" + Number(n || 0).toLocaleString("es-AR", { maximumFractionDigits: 0 });
const ESTADO_CLASS: Record<string, string> = {
  ACTIVO: "ok", A_LIQUIDAR: "warn", EN_MORA: "warn", CERRADO: "", CANCELADO: "",
  REFINANCIADO: "brand", ANULADO: "crit", CASTIGADO: "crit",
};

export default function SituacionClientePP() {
  const [q, setQ] = useState("");
  const [data, setData] = useState<{ items: any[]; resumen: any } | null>(null);
  const [err, setErr] = useState("");
  const [cargando, setCargando] = useState(false);
  const [detalle, setDetalle] = useState<Record<string, any>>({});
  const { soloLectura } = useNivelActual();

  const cargar = async (query = q) => {
    setErr(""); setCargando(true);
    try { setData(await api.ctoSituacion(query)); }
    catch (e: any) { setErr(e.message || String(e)); }
    finally { setCargando(false); }
  };
  useEffect(() => {
    // Prefill del buscador cuando se llega desde "Ver contrato" de Originar.
    const pre = sessionStorage.getItem("situacion_cliente_q");
    if (pre) { sessionStorage.removeItem("situacion_cliente_q"); setQ(pre); cargar(pre); }
    else cargar("");
  }, []);

  const toggle = async (id: string) => {
    if (detalle[id]) { setDetalle((d) => { const n = { ...d }; delete n[id]; return n; }); return; }
    try { const c = await api.ctoObtener(id); setDetalle((d) => ({ ...d, [id]: c })); }
    catch (e: any) { setErr(e.message || String(e)); }
  };
  // Callback desde el servicing: refresca el detalle abierto y la fila/resumen de la lista.
  const onChange = (c: any) => setDetalle((d) => ({ ...d, [c.id]: c }));
  const refrescar = async (id?: string) => {
    await cargar();
    if (id) { try { onChange(await api.ctoObtener(id)); } catch { /* pudo cambiar de estado */ } }
  };

  const r = data?.resumen;
  // Vista centrada en el cliente: los contratos se agrupan por cliente (uno puede tener varios préstamos)
  // y recién ahí se elige el contrato para operar.
  const grupos = useMemo(() => {
    const m = new Map<string, any[]>();
    (data?.items || []).forEach((c) => { const k = c.cliente || "—"; (m.get(k) || m.set(k, []).get(k)!).push(c); });
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0])).map(([cliente, ctos]) => ({
      cliente,
      ctos: [...ctos].sort((x, y) => String(x.numero).localeCompare(String(y.numero))),
      saldo: ctos.reduce((s, c) => s + (c.saldo || 0), 0),
      activos: ctos.filter((c) => c.estado === "ACTIVO").length,
      mora: ctos.filter((c) => c.enMora).length,
    }));
  }, [data]);
  return (
    <div className="sitc cfgc">
      <div className="sitc-head">
        <h2 style={{ margin: 0 }}>Situación del cliente <span className="sitc-sub">· línea nueva</span></h2>
        <span style={{ flex: 1 }} />
        <input className="inp" placeholder="Buscar por nombre de cliente…" value={q}
               onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && cargar()} style={{ width: 260 }} />
        <button className="btn sm" onClick={() => cargar()} disabled={cargando}>{cargando ? "…" : "🔍 Buscar"}</button>
        <button className="btn sm" title="Actualizar" onClick={() => cargar()}>↻</button>
        {data && data.items.length > 0 && <button className="btn sm" title="Exportar cartera a Excel" onClick={() => api.ctoCarteraExcel().catch((e: any) => avisar({ tipo: "error", mensaje: e.message }))}>⬇ Excel</button>}
      </div>
      {err && <div className="alert crit">{err}</div>}

      {r && (
        <div className="sitc-cards">
          <div className="sitc-kpi"><span className="k">Contratos</span><b>{r.contratos}</b></div>
          <div className="sitc-kpi"><span className="k">Activos</span><b className="ok">{r.activos}</b></div>
          <div className="sitc-kpi"><span className="k">En mora</span><b className={r.enMora ? "crit" : ""}>{r.enMora}</b></div>
          <div className="sitc-kpi"><span className="k">Capital colocado</span><b>{money(r.capitalColocado)}</b></div>
          <div className="sitc-kpi"><span className="k">Saldo vigente</span><b className="brand">{money(r.saldoVigente)}</b></div>
        </div>
      )}

      {grupos.length === 0 && <div className="card" style={{ marginTop: 12, textAlign: "center", opacity: .6, padding: 20 }}>Buscá un cliente para ver su situación y sus préstamos.</div>}

      {grupos.map((g) => (
        <div className="card sitc-cli" key={g.cliente} style={{ marginTop: 12, overflowX: "auto" }}>
          <div className="sitc-cli-head">
            <div>
              <b>{g.cliente}</b>
              <span className="muted"> · {g.ctos.length} préstamo{g.ctos.length !== 1 ? "s" : ""}</span>
            </div>
            <span style={{ flex: 1 }} />
            {g.mora > 0 && <span className="pill crit">{g.mora} en mora</span>}
            <span className="pill ok">{g.activos} activo{g.activos !== 1 ? "s" : ""}</span>
            <span className="sitc-cli-saldo">Saldo total <b className="sv-num">{money(g.saldo)}</b></span>
          </div>
          <table className="tbl">
            <thead>
              <tr>
                <th></th><th>Contrato</th><th>Sistema</th><th style={{ textAlign: "right" }}>Monto</th>
                <th style={{ textAlign: "right" }}>Saldo</th><th style={{ textAlign: "right" }}>Cuotas</th>
                <th>Próxima cuota</th><th style={{ textAlign: "right" }}>Mora</th><th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {g.ctos.map((c) => (
                <Fragment key={c.id}>
                  <tr className={"sitc-row" + (detalle[c.id] ? " open" : "")} onClick={() => toggle(c.id)}>
                    <td className="exp">{detalle[c.id] ? "▾" : "▸"}</td>
                    <td>{c.numero}</td>
                    <td>{c.sistema}</td>
                    <td style={{ textAlign: "right" }}>{money(c.monto)}</td>
                    <td style={{ textAlign: "right" }}>{money(c.saldo)}</td>
                    <td style={{ textAlign: "right" }}>{c.cuotasPagadas}/{c.cuotasPagadas + c.cuotasPendientes}</td>
                    <td>{c.proximaCuota ? `#${c.proximaCuota.numero} · ${c.proximaCuota.vencimiento} · ${money(c.proximaCuota.total)}` : "—"}</td>
                    <td style={{ textAlign: "right" }} className={c.enMora ? "crit" : ""}>{c.moraAlDia > 0 ? money(c.moraAlDia) : "—"}</td>
                    <td><span className={"pill " + (ESTADO_CLASS[c.estado] || "")}>{c.estado}</span></td>
                  </tr>
                  {detalle[c.id] && (
                    <tr className="sitc-detrow"><td colSpan={9}>
                      <ContratoServicing c={detalle[c.id]} onChange={onChange} onReload={refrescar} soloLectura={soloLectura} />
                    </td></tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      <style>{`
        .sitc-head { display:flex; align-items:center; gap:8px; margin-bottom:12px; }
        .sitc-sub { font-size:.7em; opacity:.55; font-weight:400; }
        .sitc-cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; }
        .sitc-kpi { background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:10px 14px; display:flex; flex-direction:column; gap:4px; }
        .sitc-kpi .k { font-size:.72rem; text-transform:uppercase; letter-spacing:.4px; color:var(--ink-soft); }
        .sitc-kpi b { font-size:1.25rem; font-variant-numeric:tabular-nums; color:var(--ink); }
        .sitc-kpi b.ok{color:var(--ok)} .sitc-kpi b.crit{color:var(--crit)} .sitc-kpi b.brand{color:var(--brand-2)}
        .sitc .tbl { width:100%; border-collapse:collapse; font-size:.86rem; color:var(--ink); }
        .sitc .tbl th, .sitc .tbl td { padding:7px 10px; border-bottom:1px solid var(--border); }
        .sitc .tbl th { text-align:left; font-size:.72rem; text-transform:uppercase; letter-spacing:.3px; color:var(--ink-soft); }
        .sitc-cli-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:12px 14px;border-bottom:1px solid var(--border);background:var(--surface-2)}
        .sitc-cli-head > div:first-child b{font-size:1rem;color:var(--ink)}
        .sitc-cli-head .muted{color:var(--ink-soft);font-size:.82rem}
        .sitc-cli-saldo{font-size:.78rem;color:var(--ink-soft);text-transform:uppercase;letter-spacing:.3px;display:flex;flex-direction:column;align-items:flex-end}
        .sitc-cli-saldo b{font-size:1rem;color:var(--brand-2)}
        .sitc-row { cursor:pointer; }
        .sitc-row:hover { background:var(--surface-2); }
        .sitc-row.open { background:var(--surface-2); }
        .sitc-row .exp { width:20px; opacity:.6; }
        .sitc-detrow > td { background:var(--surface-2); padding:0; }
        .sitc .pill{padding:2px 8px;border-radius:999px;font-size:.72rem;background:var(--surface-2);color:var(--ink-soft)}
        .sitc .pill.ok{background:var(--ok-soft);color:var(--ok)} .sitc .pill.warn{background:var(--warn-soft);color:var(--warn)}
        .sitc .pill.crit{background:var(--crit-soft);color:var(--crit)} .sitc .pill.brand{background:var(--accent-soft);color:var(--brand-2)}
        .sv-actions{display:flex;gap:8px;flex-wrap:wrap;align-items:end;padding:12px 16px;border-bottom:1px solid var(--border)}
        .sv-body{display:grid;grid-template-columns:2fr 1fr;gap:0}
        .sv-body>div{min-width:0}
        @media (max-width:900px){ .sv-body{grid-template-columns:1fr} .sv-body>div:first-child{border-right:none!important;border-bottom:1px solid var(--border)} }
        .sv-head{display:flex;gap:10px;align-items:center;padding:12px 16px 0}
        .sv-plan table,.sv-acts{width:100%;border-collapse:collapse;font-size:.8rem;color:var(--ink)}
        .sv-plan th,.sv-plan td{padding:5px 8px;border-bottom:1px solid var(--border);text-align:left}
        .sv-num{text-align:right;font-variant-numeric:tabular-nums}
        .refi-overlay{position:fixed;inset:0;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;z-index:1000}
        .refi-modal{background:var(--surface);color:var(--ink);border:1px solid var(--border);border-radius:12px;width:min(760px,94vw);max-height:90vh;overflow:auto;box-shadow:0 12px 40px rgba(0,0,0,.4)}
        .refi-head{display:flex;align-items:center;gap:8px;padding:14px 18px;border-bottom:1px solid var(--border)}
        .refi-body{padding:16px 18px;display:flex;flex-direction:column;gap:16px}
        .refi-form{display:flex;gap:14px;align-items:end;flex-wrap:wrap}
        .refi-fld{display:flex;flex-direction:column;gap:4px;font-size:.8rem;color:var(--ink)}
        .refi-fld span{color:var(--ink-soft);text-transform:uppercase;font-size:.68rem;letter-spacing:.3px}
        .refi-fld input{padding:6px 8px;border:1px solid var(--border);border-radius:6px;width:120px;background:var(--surface-2);color:var(--ink);font:inherit}
        .refi-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px}
        .refi-kpi{background:var(--surface-2);border:1px solid var(--border);border-radius:8px;padding:8px 10px;display:flex;flex-direction:column;gap:2px}
        .refi-kpi span{font-size:.66rem;color:var(--ink-soft);text-transform:uppercase;letter-spacing:.3px}
        .refi-kpi b{font-size:1.05rem;font-variant-numeric:tabular-nums;color:var(--ink)}
        .refi-kpi b.int{color:var(--crit)}
        .refi-twrap{max-height:280px;overflow:auto;border:1px solid var(--border);border-radius:8px}
        .refi-twrap table{width:100%;border-collapse:collapse;font-size:.82rem;color:var(--ink)}
        .refi-twrap th,.refi-twrap td{padding:5px 8px;border-bottom:1px solid var(--border)}
        .refi-twrap th{position:sticky;top:0;background:var(--surface-2);text-align:left;font-size:.7rem;color:var(--ink-soft);text-transform:uppercase}
        .refi-twrap .num{text-align:right;font-variant-numeric:tabular-nums}
        .refi-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
      `}</style>
    </div>
  );
}

// Detalle + servicing completo del contrato (migrado desde Originar Crédito).
function ContratoServicing({ c, onChange, onReload, soloLectura }: { c: any; onChange: (c: any) => void; onReload: (id?: string) => void; soloLectura: boolean }) {
  const [fechaValor, setFechaValor] = useState("");
  const [refi, setRefi] = useState<{ tasa: number; plazo: number; sim: any; cargando: boolean } | null>(null);
  const activo = c.estado === "ACTIVO";

  const aplicar = (nc: any) => { onChange(nc); onReload(); };
  async function act(tipo: string, importe = 0, modo?: string) {
    try { aplicar(await api.ctoActividad(c.id, tipo, importe, "", fechaValor || undefined, modo)); }
    catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); }
  }
  async function pagar() { await act("PAYMENT"); }
  async function pagarParcial() {
    const v = await pedirTexto({ titulo: "Pago parcial", mensaje: "Importe del pago parcial (abona la próxima cuota sin completarla):", tipo: "number", requerido: true });
    const imp = Number(v); if (!imp || imp <= 0) return; await act("PAYMENT", imp);
  }
  async function prepago() {
    const v = await pedirTexto({ titulo: "Prepago de capital", mensaje: "Prepago de capital — importe a aplicar:", tipo: "number", requerido: true });
    const imp = Number(v); if (!imp || imp <= 0) return;
    const modo = (await confirmar({ titulo: "Prepago de capital", mensaje: "¿Cómo aplicar el prepago?", confirmar: "Baja de CUOTA (mismo plazo, cuota menor)", cancelar: "Baja de PLAZO (misma cuota, menos plazo)" })) ? "BAJA_CUOTA" : "BAJA_PLAZO";
    await act("PARTIAL_PREPAYMENT", imp, modo);
  }
  async function diferir() {
    const v = await pedirTexto({ titulo: "Diferimiento de cuotas", mensaje: "¿Cuántas cuotas diferir? (el interés se capitaliza)", tipo: "number", requerido: true });
    const n = Number(v); if (!n || n <= 0) return; await act("PAYMENT_HOLIDAY", n);
  }
  async function payoff() {
    if (!(await confirmar({ titulo: "Cancelación total (payoff)", danger: true, confirmar: "Cancelar contrato", cancelar: "Volver", mensaje: "Cancelación total (payoff): salda el capital remanente y cierra el contrato. ¿Confirmás?" }))) return;
    await act("PAYOFF");
  }
  async function reprice() { await act("REPRICING"); }
  async function devengar() { try { aplicar(await api.ctoDevengar(c.id)); } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); } }
  async function desembolsar() { try { aplicar(await api.ctoDesembolsar(c.id)); } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); } }
  async function reversar(a: any) {
    if (!(await confirmar({ titulo: "Reversar actividad", danger: true, confirmar: "Reversar", mensaje: `Reversar la actividad ${a.tipo} del ${a.fecha}: deshace su efecto y recalcula el contrato. ¿Confirmás?` }))) return;
    try { aplicar(await api.ctoReversar(c.id, a.id)); } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); }
  }
  function abrirRefi() {
    const pendientes = (c.cuotas || []).filter((q: any) => q.estado === "PENDIENTE").length || c.plazo;
    setRefi({ tasa: Number(c.tasa) || 0, plazo: pendientes, sim: null, cargando: false });
  }
  async function simularRefi() {
    if (!refi) return;
    setRefi((r) => r && { ...r, cargando: true });
    try {
      const snap = c.snapshot || {};
      const sim = await api.ppPreview({ sistema: c.sistema, monto: Number(c.saldo_capital), plazo: refi.plazo, tna: refi.tasa,
        cargoOtorg: 0, frecuencia: snap.frecuencia || "MENSUAL", impuestos: snap.impuestos || [] });
      setRefi((r) => r && { ...r, sim, cargando: false });
    } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); setRefi((r) => r && { ...r, cargando: false }); }
  }
  async function confirmarRefi() {
    if (!refi) return;
    if (!(await confirmar({ titulo: "Refinanciar contrato", danger: true, confirmar: "Refinanciar", mensaje: `Refinanciar el saldo ${money(Number(c.saldo_capital))} a TNA ${refi.tasa}% en ${refi.plazo} cuotas: cierra este contrato y crea uno nuevo. ¿Confirmás?` }))) return;
    try {
      const r = await api.ctoRefinanciar(c.id, refi.tasa, refi.plazo);
      setRefi(null); onChange(r.anterior); onReload(c.id);
      avisar(`Refinanciado. Nuevo contrato ${r.nuevo.numero_contrato} (aparece en la lista).`);
    } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); }
  }

  return (
    <div>
      <div className="sv-head">
        <b>{c.numero_contrato} — {c.cliente_nombre}</b>
        <span className={"pill " + (ESTADO_CLASS[c.estado] || "")}>{c.estado}</span>
        {c.solicitud_origen && <span className="pill" title="Originado desde una solicitud legacy">🗂️ Solicitud N° {c.solicitud_origen}</span>}
        <span style={{ flex: 1 }} />
        <span style={{ fontSize: 11, color: "var(--ink-soft)" }}>Snapshot: {c.snapshot?.producto} v{c.snapshot?.version} · {c.sistema} · {c.snapshot?.tna}%</span>
        <button className="btn sm" onClick={() => api.ctoPdf(c.id, c.numero_contrato).catch((e: any) => avisar({ tipo: "error", mensaje: e.message }))}>⬇ PDF</button>
      </div>

      <div className="sv-actions">
        <div><small style={{ color: "var(--ink-soft)" }}>Saldo capital</small><div className="sv-num" style={{ fontWeight: 700 }}>{money(c.saldo_capital)}</div></div>
        <div><small style={{ color: "var(--ink-soft)" }}>Cuotas pagadas</small><div className="sv-num" style={{ fontWeight: 700 }}>{c.cuotas.filter((q: any) => q.estado === "PAGADA").length} / {c.cuotas.length}</div></div>
        {c.datos_adicionales?.destino && <div><small style={{ color: "var(--ink-soft)" }}>Destino</small><div style={{ fontWeight: 600, fontSize: 13 }}>{c.datos_adicionales.destino}</div></div>}
        <span style={{ flex: 1 }} />
        {soloLectura
          ? <span className="pill" title="Tu perfil sólo tiene consulta sobre esta pantalla">🔒 Sólo lectura</span>
          : c.estado === "A_LIQUIDAR"
          ? <button className="btn primary" onClick={desembolsar}>💸 Desembolsar (neto {money(c.liquidacion?.neto || 0)})</button>
          : <>
              <label className="f" style={{ minWidth: 150 }}><span className="lbl" style={{ fontSize: 11, color: "var(--ink-soft)" }}>Fecha valor <small>(backdating)</small></span>
                <input type="date" value={fechaValor} max={new Date().toISOString().slice(0, 10)} min={c.fecha_valor} onChange={(e) => setFechaValor(e.target.value)} /></label>
              {c.snapshot?.indice && <button className="btn" disabled={!activo} title={`Recalcular TNA desde ${c.snapshot.indice}`} onClick={reprice}>🔁 Repricing ({c.snapshot.indice})</button>}
              <button className="btn" disabled={!activo} title="Devengar el interés de la próxima cuota" onClick={devengar}>📈 Devengar interés</button>
              <button className="btn" disabled={!activo} onClick={pagar}>Pagar próxima cuota</button>
              <button className="btn" disabled={!activo} onClick={pagarParcial}>Pago parcial</button>
              <button className="btn" disabled={!activo} onClick={prepago}>Prepago capital</button>
              <button className="btn" disabled={!activo} onClick={diferir}>Diferir cuotas</button>
              <button className="btn" disabled={!activo} onClick={abrirRefi}>Refinanciar…</button>
              <button className="btn primary" disabled={!activo} onClick={payoff}>Cancelación total</button>
            </>}
      </div>

      <div className="sv-body">
        <div className="sv-plan" style={{ maxHeight: 320, overflow: "auto", borderRight: "1px solid var(--border)", padding: "8px 12px" }}>
          <table>
            <thead><tr><th>#</th><th>Vto</th><th className="sv-num">Capital</th><th className="sv-num">Interés</th><th className="sv-num">Cuota</th><th className="sv-num">Saldo</th><th>Estado</th></tr></thead>
            <tbody>
              {c.cuotas.map((q: any) => (
                <tr key={q.numero_cuota} style={q.estado === "PAGADA" ? { opacity: 0.55 } : undefined}>
                  <td><b>{q.numero_cuota}</b></td><td>{q.fecha_vencimiento}</td>
                  <td className="sv-num">{money(q.capital)}</td><td className="sv-num">{money(q.interes)}</td>
                  <td className="sv-num"><b>{money(q.total)}</b></td><td className="sv-num">{money(q.saldo_final)}</td>
                  <td>{q.estado === "PAGADA" ? "✓ pagada" : q.devengada ? "📈 devengada" : "pendiente"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ padding: "10px 14px", maxHeight: 320, overflow: "auto" }}>
          <h4 style={{ margin: "0 0 8px", fontSize: 13 }}>Actividades (servicing)</h4>
          {!c.actividades.length && <p className="muted" style={{ fontSize: 12 }}>Sin actividades (pendiente de desembolso).</p>}
          {c.actividades.map((a: any, i: number) => {
            const rev = a.estado === "REVERSADA";
            const puedeReversar = a.estado !== "REVERSADA" && !["DISBURSEMENT", "REVERSAL", "RENEGOTIATION"].includes(a.tipo);
            return (
              <div key={a.id || i} style={{ fontSize: 12, padding: "6px 0", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "flex-start", gap: 8, opacity: rev ? 0.55 : 1 }}>
                <div style={{ flex: 1 }}>
                  <b style={rev ? { textDecoration: "line-through" } : a.tipo === "REVERSAL" ? { color: "var(--crit)" } : undefined}>{a.tipo}</b> · <span className="sv-num">{money(a.importe)}</span>
                  {rev && <span className="pill" style={{ marginLeft: 6, fontSize: 10 }}>REVERSADA</span>}
                  {a.dato?.interes_punitorio > 0 && <span className="pill crit" style={{ marginLeft: 6, fontSize: 10 }}>⚠ mora {a.dato.mora_dias}d · {money(a.dato.interes_punitorio + (a.dato.iva_punitorio || 0))}</span>}<br />
                  <small style={{ color: "var(--ink-faint)" }}>{a.fecha} · {a.detalle} · {a.por}</small>
                </div>
                {puedeReversar && <button className="btn sm" title="Reversar actividad" style={{ color: "var(--crit)", borderColor: "var(--crit)" }} onClick={() => reversar(a)}>↩</button>}
              </div>
            );
          })}
        </div>
      </div>

      {c.asientos?.length > 0 && (
        <div style={{ borderTop: "1px solid var(--border)", padding: "12px 15px" }}>
          <h4 style={{ margin: "0 0 8px", fontSize: 13 }}>📚 Asientos contables ({c.asientos.length}) <small className="muted" style={{ fontWeight: 400 }}>— también en Contabilidad → Libro Diario</small></h4>
          <div className="sv-plan" style={{ maxHeight: 240, overflow: "auto" }}>
            <table>
              <thead><tr><th>N°</th><th>Fecha</th><th>Concepto</th><th>Cuenta</th><th className="sv-num">Debe</th><th className="sv-num">Haber</th></tr></thead>
              <tbody>
                {c.asientos.map((as: any) => as.lineas.map((l: any, j: number) => (
                  <tr key={`${as.id}-${j}`} style={as.origen === "pp_reversa" ? { color: "var(--crit)" } : undefined}>
                    <td>{j === 0 ? as.id : ""}</td><td>{j === 0 ? as.fecha : ""}</td>
                    <td style={{ maxWidth: 220, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }} title={as.concepto}>{j === 0 ? as.concepto : ""}</td>
                    <td>{l.cuenta} · {l.nombre}</td>
                    <td className="sv-num">{l.debe ? money(l.debe) : ""}</td><td className="sv-num">{l.haber ? money(l.haber) : ""}</td>
                  </tr>
                )))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {refi && (
        <div className="refi-overlay" onClick={() => setRefi(null)}>
          <div className="refi-modal" onClick={(e) => e.stopPropagation()}>
            <div className="refi-head">
              <b>Simular refinanciación — {c.numero_contrato}</b>
              <span style={{ flex: 1 }} />
              <button className="btn sm" onClick={() => setRefi(null)}>✕</button>
            </div>
            <div className="refi-body">
              <div className="refi-form">
                <div className="refi-fld"><span>Saldo a refinanciar</span><b>{money(Number(c.saldo_capital))}</b></div>
                <div className="refi-fld"><span>Sistema</span><b>{c.sistema}</b></div>
                <label className="refi-fld"><span>Nueva TNA %</span>
                  <input type="number" step="0.1" value={refi.tasa} onChange={(e) => setRefi((r) => r && { ...r, tasa: Number(e.target.value), sim: null })} /></label>
                <label className="refi-fld"><span>Nuevo plazo (cuotas)</span>
                  <input type="number" min={1} value={refi.plazo} onChange={(e) => setRefi((r) => r && { ...r, plazo: Number(e.target.value), sim: null })} /></label>
                <button className="btn" onClick={simularRefi} disabled={refi.cargando || !refi.plazo}>{refi.cargando ? "Simulando…" : "🔎 Simular"}</button>
              </div>
              {refi.sim && (() => {
                const rr = refi.sim.resumen; const saldo = Number(c.saldo_capital);
                const totalCap = refi.sim.rows.reduce((a: number, x: any) => a + x.capital, 0);
                return (
                  <div>
                    <div className="refi-kpis">
                      <div className="refi-kpi"><span>Primera cuota</span><b>{money(rr.primeraCuota)}</b></div>
                      <div className="refi-kpi"><span>Total a pagar</span><b>{money(rr.totalCuotas)}</b></div>
                      <div className="refi-kpi"><span>Capital</span><b>{money(totalCap)}</b></div>
                      <div className="refi-kpi"><span>Interés total</span><b className="int">{money(rr.totalInteres)}</b></div>
                      <div className="refi-kpi"><span>Costo financiero (Int/Saldo)</span><b>{saldo ? (rr.totalInteres / saldo * 100).toFixed(1) : "—"}%</b></div>
                      <div className="refi-kpi"><span>TEA</span><b>{rr.tea}%</b></div>
                      <div className="refi-kpi"><span>CFT</span><b>{rr.cft}%</b></div>
                    </div>
                    <div className="refi-twrap" style={{ marginTop: 12 }}>
                      <table>
                        <thead><tr><th>#</th><th>Vto</th><th>Capital</th><th>Interés</th><th>Cuota</th><th>Saldo</th></tr></thead>
                        <tbody>
                          {refi.sim.rows.map((q: any) => (
                            <tr key={q.numero_cuota}>
                              <td><b>{q.numero_cuota}</b></td><td>{q.fecha_vencimiento}</td>
                              <td className="num">{money(q.capital)}</td><td className="num">{money(q.interes)}</td>
                              <td className="num"><b>{money(q.total)}</b></td><td className="num">{money(q.saldo_final)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="refi-actions" style={{ marginTop: 12 }}>
                      <span className="muted">Cierra {c.numero_contrato} (REFINANCIADO) y crea un contrato nuevo sobre el saldo.</span>
                      <span style={{ flex: 1 }} />
                      <button className="btn" onClick={() => setRefi(null)}>Cancelar</button>
                      <button className="btn primary" onClick={confirmarRefi}>✓ Confirmar refinanciación</button>
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
