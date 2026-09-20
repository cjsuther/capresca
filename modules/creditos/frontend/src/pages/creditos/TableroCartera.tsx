import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import { avisar } from "../../ui/dialog";

const money = (n: any) => "$" + Number(n || 0).toLocaleString("es-AR", { maximumFractionDigits: 0 });
const moneyK = (n: any) => {
  const v = Number(n || 0);
  if (Math.abs(v) >= 1_000_000) return "$" + (v / 1_000_000).toLocaleString("es-AR", { maximumFractionDigits: 2 }) + "M";
  if (Math.abs(v) >= 1_000) return "$" + Math.round(v / 1_000) + "k";
  return "$" + Math.round(v);
};
const num = (n: any) => Number(n || 0).toLocaleString("es-AR");

const ESTADO_CLR: Record<string, string> = {
  ACTIVO: "var(--dv-green)", A_LIQUIDAR: "var(--dv-amber)", EN_MORA: "var(--dv-orange)", CERRADO: "var(--dv-slate)",
  REFINANCIADO: "var(--dv-blue)", ANULADO: "var(--dv-red)", CANCELADO: "var(--dv-slate)", CASTIGADO: "var(--dv-red)",
};
const ESTADO_PILL: Record<string, string> = {
  ACTIVO: "ok", A_LIQUIDAR: "warn", CERRADO: "", REFINANCIADO: "brand", CANCELADO: "", CASTIGADO: "crit", ANULADO: "",
};
const BUCKET_CLR: Record<string, string> = {
  "Al día": "var(--dv-green)", "1–30": "var(--dv-amber)", "31–60": "var(--dv-orange)", "61–90": "var(--dv-red)", "90+": "var(--crit)",
};

type Drill = { tipo: "estado" | "producto" | "mora" | "todos"; valor: string; label: string } | null;

export default function TableroCartera() {
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState("");
  const [cargando, setCargando] = useState(true);
  const [drill, setDrill] = useState<Drill>(null);

  const cargar = async () => {
    setErr(""); setCargando(true);
    try { setD(await api.ctoTablero()); } catch (e: any) { setErr(e.message || String(e)); }
    finally { setCargando(false); }
  };
  useEffect(() => { cargar(); }, []);

  const k = d?.kpis;
  const contratos: any[] = d?.contratos || [];

  // Filtro del drill-down.
  const filtrados = useMemo(() => {
    if (!drill) return [];
    return contratos.filter((c) =>
      drill.tipo === "todos" ? true
      : drill.tipo === "estado" ? c.estado === drill.valor
      : drill.tipo === "producto" ? c.productoId === drill.valor
      : drill.tipo === "mora" ? (drill.valor === "__mora__" ? c.diasAtraso > 0 : c.moraBucket === drill.valor)
      : false);
  }, [drill, contratos]);

  const abrir = (dr: Drill) => setDrill(dr);

  return (
    <div className="tcar">
      <div className="tcar-head">
        <div>
          <h1 style={{ margin: 0 }}>Tablero de cartera</h1>
          <p className="muted" style={{ margin: "2px 0 0" }}>Cartera de créditos originados · datos al {d?.generadoEn || "—"}. Hacé clic en cualquier segmento para ver el detalle.</p>
        </div>
        <span style={{ flex: 1 }} />
        <button className="btn sm" onClick={cargar} disabled={cargando}>{cargando ? "…" : "↻ Refrescar"}</button>
        {contratos.length > 0 && <button className="btn sm" onClick={() => api.ctoCarteraExcel().catch((e: any) => avisar({ tipo: "error", mensaje: e.message }))}>⬇ Exportar (Excel)</button>}
      </div>
      {err && <div className="alert crit">{err}</div>}
      {cargando && !d ? <p className="muted">Cargando…</p> : k && (<>

        {/* KPIs */}
        <div className="tcar-kpis">
          <Kpi label="Saldo vigente" v={money(k.saldoVigente)} sub={`${num(k.activos)} contratos activos`} hl />
          <Kpi label="Capital colocado" v={money(k.capitalColocado)} sub={`${num(k.contratos)} contratos · ticket ${moneyK(k.ticketPromedio)}`} />
          <Kpi label="Cobrado (histórico)" v={money(k.cobrado)} sub={`${num(k.cuotasPagadas)} cuotas pagadas`} />
          <Kpi label="Mora" v={money(k.moraMonto)} sub={`${k.moraPct}% de la cartera · ${num(k.contratosEnMora)} contratos`} crit={Number(k.moraMonto) > 0} onClick={k.contratosEnMora ? () => abrir({ tipo: "mora", valor: "__mora__", label: "En mora" }) : undefined} />
          <Kpi label="Recaudado del mes" v={money(k.recaudadoMes)} sub="pagos registrados este mes" />
          <Kpi label="Por liquidar" v={money(k.aLiquidarMonto)} sub={`${num(k.aLiquidarN)} contratos a desembolsar`} onClick={k.aLiquidarN ? () => abrir({ tipo: "estado", valor: "A_LIQUIDAR", label: "Por liquidar" }) : undefined} />
          <Kpi label="Vencen en 30 días" v={money(k.vencen30Monto)} sub={`${num(k.vencen30Cuotas)} cuotas próximas`} />
          <Kpi label="TNA prom. · Plazo prom." v={`${k.tnaPromedioPond}% · ${k.plazoPromedio}`} sub="ponderada por saldo · cuotas" />
        </div>

        <div className="tcar-grid2">
          {/* Composición por estado (donut) */}
          <div className="card tcar-panel">
            <h3>Cartera por estado</h3>
            <div className="tcar-donutwrap">
              <Donut data={(d.porEstado || []).map((e: any) => ({ key: e.estado, val: Number(e.capital), clr: ESTADO_CLR[e.estado] || "var(--dv-slate)" }))} total={Number(k.capitalColocado)} />
              <div className="tcar-legend">
                {(d.porEstado || []).map((e: any) => (
                  <button key={e.estado} className="tcar-legrow" onClick={() => abrir({ tipo: "estado", valor: e.estado, label: e.estado })}>
                    <span className="tcar-dot" style={{ background: ESTADO_CLR[e.estado] || "var(--dv-slate)" }} />
                    <span className="tcar-legname">{e.estado}</span>
                    <span className="tcar-legn">{num(e.contratos)}</span>
                    <span className="tcar-legv">{money(e.capital)}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Evolución mensual */}
          <div className="card tcar-panel">
            <h3>Evolución (últimos 6 meses)</h3>
            <BarsEvol data={d.evolucion || []} />
            <div className="tcar-evleg"><span><i style={{ background: "var(--brand-2)" }} /> Originado</span><span><i style={{ background: "var(--dv-green)" }} /> Cobrado</span></div>
          </div>
        </div>

        {/* Aging de mora */}
        <div className="card tcar-panel">
          <h3>Antigüedad de la mora (aging)</h3>
          <table className="tcar-tbl">
            <thead><tr><th>Tramo de atraso</th><th className="n">Contratos</th><th className="n">Saldo</th><th style={{ width: "42%" }}>Participación del saldo activo</th></tr></thead>
            <tbody>
              {(d.aging || []).map((a: any) => {
                const pctS = Number(k.saldoVigente) > 0 ? (Number(a.saldo) / Number(k.saldoVigente)) * 100 : 0;
                return (
                  <tr key={a.bucket} className={a.contratos ? "tcar-clk" : ""} onClick={a.contratos ? () => abrir({ tipo: "mora", valor: a.bucket, label: `Atraso ${a.bucket}` }) : undefined}>
                    <td><span className="tcar-dot" style={{ background: BUCKET_CLR[a.bucket] }} />{a.bucket}</td>
                    <td className="n">{num(a.contratos)}</td>
                    <td className="n">{money(a.saldo)}</td>
                    <td><div className="tcar-bar"><div className="tcar-bar-fill" style={{ width: `${pctS}%`, background: BUCKET_CLR[a.bucket] }} /></div><small className="muted">{pctS.toFixed(1)}%</small></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Por producto */}
        <div className="card tcar-panel">
          <h3>Por línea de crédito</h3>
          <table className="tcar-tbl">
            <thead><tr><th>Línea</th><th className="n">Contratos</th><th className="n">Capital colocado</th><th className="n">Saldo vigente</th><th className="n">Mora</th><th style={{ width: "18%" }}>Mora %</th></tr></thead>
            <tbody>
              {(d.porProducto || []).length === 0 && <tr><td colSpan={6} style={{ textAlign: "center", opacity: .6, padding: 18 }}>Sin contratos.</td></tr>}
              {(d.porProducto || []).map((p: any) => (
                <tr key={p.id} className="tcar-clk" onClick={() => abrir({ tipo: "producto", valor: p.id, label: p.nombre || p.codigo })}>
                  <td><b>{p.nombre || p.codigo}</b>{p.codigo && <small className="muted"> · {p.codigo}</small>}</td>
                  <td className="n">{num(p.contratos)}</td>
                  <td className="n">{money(p.capital)}</td>
                  <td className="n">{money(p.saldo)}</td>
                  <td className="n">{money(p.mora)}</td>
                  <td><div className="tcar-bar"><div className="tcar-bar-fill" style={{ width: `${Math.min(100, p.moraPct)}%`, background: p.moraPct > 0 ? "var(--crit)" : "var(--dv-green)" }} /></div><small className="muted">{p.moraPct}%</small></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Accesos rápidos al detalle */}
        <div className="tcar-quick">
          <span className="muted">Ver detalle:</span>
          <button className="tcar-tab" onClick={() => abrir({ tipo: "todos", valor: "", label: "Toda la cartera" })}>Toda la cartera</button>
          {(d.porEstado || []).map((e: any) => <button key={e.estado} className="tcar-tab" onClick={() => abrir({ tipo: "estado", valor: e.estado, label: e.estado })}>{e.estado} ({e.contratos})</button>)}
        </div>
      </>)}

      {/* Drill-down */}
      {drill && (
        <div className="tcar-drill card">
          <div className="tcar-drillhead">
            <b>Detalle · {drill.label}</b>
            <span className="tcar-drilln">{filtrados.length} contrato(s)</span>
            <span style={{ flex: 1 }} />
            <button className="btn sm" onClick={() => setDrill(null)}>✕ Cerrar detalle</button>
          </div>
          <div className="tcar-scroll">
            <table className="tcar-tbl">
              <thead><tr><th>N° contrato</th><th>Cliente</th><th>Línea</th><th>Estado</th><th className="n">Monto</th><th className="n">Saldo</th><th className="n">Atraso</th><th>Próx. venc.</th></tr></thead>
              <tbody>
                {filtrados.length === 0 && <tr><td colSpan={8} style={{ textAlign: "center", opacity: .6, padding: 18 }}>Sin contratos en este segmento.</td></tr>}
                {filtrados.map((c) => (
                  <tr key={c.id}>
                    <td className="tcar-mono">{c.numero}</td>
                    <td>{c.cliente}</td>
                    <td>{c.producto || c.codigo || "—"}</td>
                    <td><span className={"pill " + (ESTADO_PILL[c.estado] || "")}>{c.estado}</span></td>
                    <td className="n">{money(c.monto)}</td>
                    <td className="n">{money(c.saldo)}</td>
                    <td className="n">{c.diasAtraso > 0 ? <span style={{ color: "var(--crit)", fontWeight: 600 }}>{c.diasAtraso} d</span> : "—"}</td>
                    <td>{c.proxVenc || "—"}{c.proxCuota ? <small className="muted"> (c.{c.proxCuota})</small> : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <style>{`
        .tcar-head{display:flex;align-items:center;gap:10px;margin-bottom:14px}
        .tcar-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:14px}
        .tcar-kpi{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 14px;display:flex;flex-direction:column;gap:3px}
        .tcar-kpi.hl{border-color:var(--brand-2);box-shadow:0 0 0 1px var(--brand-2) inset}
        .tcar-kpi.clk{cursor:pointer}.tcar-kpi.clk:hover{border-color:var(--brand-2)}
        .tcar-kpi small.l{font-size:.7rem;text-transform:uppercase;letter-spacing:.4px;color:var(--ink-soft)}
        .tcar-kpi b{font-size:1.35rem;font-variant-numeric:tabular-nums;color:var(--ink);line-height:1.1}
        .tcar-kpi b.crit{color:var(--crit)}
        .tcar-kpi small.s{font-size:.72rem;color:var(--ink-soft)}
        .tcar-grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}
        @media(max-width:820px){.tcar-grid2{grid-template-columns:1fr}}
        .tcar-panel{padding:14px 16px;margin-bottom:12px}
        .tcar-panel h3{margin:0 0 12px;font-size:14px}
        .tcar-donutwrap{display:flex;gap:16px;align-items:center;flex-wrap:wrap}
        .tcar-legend{display:flex;flex-direction:column;gap:2px;flex:1;min-width:190px}
        .tcar-legrow{display:flex;align-items:center;gap:8px;padding:5px 6px;border:0;background:transparent;border-radius:7px;cursor:pointer;color:var(--ink);font:inherit;text-align:left}
        .tcar-legrow:hover{background:var(--surface-2)}
        .tcar-legname{flex:1;font-size:.84rem}.tcar-legn{font-variant-numeric:tabular-nums;color:var(--ink-soft);font-size:.8rem;width:38px;text-align:right}
        .tcar-legv{font-variant-numeric:tabular-nums;font-size:.82rem;width:92px;text-align:right}
        .tcar-evx{display:flex;margin-top:4px}
        .tcar-evx span{flex:1;text-align:center;font-size:.68rem;color:var(--ink-soft);font-variant-numeric:tabular-nums}
        .tcar-evleg{display:flex;gap:16px;margin-top:8px;font-size:.75rem;color:var(--ink-soft)}
        .tcar-evleg i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:middle}
        .tcar-tbl{width:100%;border-collapse:collapse;font-size:.86rem;color:var(--ink)}
        .tcar-tbl th,.tcar-tbl td{padding:8px 10px;border-bottom:1px solid var(--border);text-align:left}
        .tcar-tbl th{font-size:.72rem;text-transform:uppercase;letter-spacing:.3px;color:var(--ink-soft);font-weight:600}
        .tcar-tbl .n{text-align:right;font-variant-numeric:tabular-nums}
        .tcar-clk{cursor:pointer}.tcar-clk:hover{background:var(--surface-2)}
        .tcar-mono{font-variant-numeric:tabular-nums;font-weight:600}
        .tcar-dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:8px;vertical-align:middle}
        .tcar-bar{height:8px;border-radius:999px;background:var(--surface-2);overflow:hidden;display:inline-block;width:calc(100% - 44px);vertical-align:middle;margin-right:6px}
        .tcar-bar-fill{height:100%;border-radius:999px;transition:width .3s}
        .tcar-quick{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:4px 0 12px}
        .tcar-tab{padding:5px 12px;border:1px solid var(--border);background:var(--surface);color:var(--ink-soft);border-radius:999px;font:inherit;font-size:12.5px;cursor:pointer}
        .tcar-tab:hover{border-color:var(--brand-2);color:var(--ink)}
        .tcar-drill{padding:12px 14px;border-color:var(--brand-2)}
        .tcar-drillhead{display:flex;align-items:center;gap:10px;margin-bottom:8px}
        .tcar-drilln{font-size:.78rem;color:var(--ink-soft);background:var(--surface-2);padding:2px 8px;border-radius:999px}
        .tcar-scroll{overflow-x:auto}
      `}</style>
    </div>
  );
}

function Kpi({ label, v, sub, hl, crit, onClick }: { label: string; v: any; sub?: string; hl?: boolean; crit?: boolean; onClick?: () => void }) {
  return (
    <div className={"tcar-kpi" + (hl ? " hl" : "") + (onClick ? " clk" : "")} onClick={onClick} title={onClick ? "Ver detalle" : undefined}>
      <small className="l">{label}</small>
      <b className={crit ? "crit" : ""}>{v}</b>
      {sub && <small className="s">{sub}</small>}
    </div>
  );
}

// Donut SVG por composición (capital por estado).
function Donut({ data, total }: { data: { key: string; val: number; clr: string }[]; total: number }) {
  const R = 52, C = 2 * Math.PI * R, sz = 130;
  let acc = 0;
  const segs = data.filter((s) => s.val > 0).map((s) => {
    const frac = total > 0 ? s.val / total : 0;
    const seg = { ...s, dash: frac * C, off: -acc * C };
    acc += frac; return seg;
  });
  return (
    <svg width={sz} height={sz} viewBox={`0 0 ${sz} ${sz}`} style={{ flexShrink: 0 }}>
      <g transform={`translate(${sz / 2},${sz / 2}) rotate(-90)`}>
        <circle r={R} fill="none" stroke="var(--surface-2)" strokeWidth={16} />
        {segs.map((s) => (
          <circle key={s.key} r={R} fill="none" stroke={s.clr} strokeWidth={16}
            strokeDasharray={`${s.dash} ${C - s.dash}`} strokeDashoffset={s.off} />
        ))}
      </g>
      <text x={sz / 2} y={sz / 2 - 1} textAnchor="middle" fontSize="15" fontWeight="700" fill="var(--ink)">{moneyKlocal(total)}</text>
      <text x={sz / 2} y={sz / 2 + 13} textAnchor="middle" fontSize="9" fill="var(--ink-soft)">capital colocado</text>
    </svg>
  );
}
const moneyKlocal = (n: any) => {
  const v = Number(n || 0);
  if (Math.abs(v) >= 1_000_000) return "$" + (v / 1_000_000).toLocaleString("es-AR", { maximumFractionDigits: 1 }) + "M";
  if (Math.abs(v) >= 1_000) return "$" + Math.round(v / 1_000) + "k";
  return "$" + Math.round(v);
};

// Barras agrupadas: originado vs cobrado por mes.
function BarsEvol({ data }: { data: any[] }) {
  const H = 120;
  const max = Math.max(1, ...data.map((m) => Math.max(Number(m.originadoMonto), Number(m.cobradoMonto))));
  const bw = 100 / Math.max(1, data.length);
  return (
    <div>
      <svg width="100%" height={H} viewBox={`0 0 100 ${H}`} preserveAspectRatio="none" style={{ display: "block" }}>
        {[0.25, 0.5, 0.75, 1].map((g) => <line key={g} x1="0" x2="100" y1={H - g * H} y2={H - g * H} stroke="var(--border)" strokeWidth="0.3" />)}
        {data.map((m, i) => {
          const x = i * bw, o = Number(m.originadoMonto), c = Number(m.cobradoMonto);
          const oh = (o / max) * H, ch = (c / max) * H, w = bw * 0.32;
          return (
            <g key={m.mes}>
              <rect x={x + bw * 0.14} y={H - oh} width={w} height={oh} fill="var(--brand-2)"><title>{m.mes} · Originado {money(o)} ({m.originadoN})</title></rect>
              <rect x={x + bw * 0.52} y={H - ch} width={w} height={ch} fill="var(--dv-green)"><title>{m.mes} · Cobrado {money(c)}</title></rect>
            </g>
          );
        })}
      </svg>
      <div className="tcar-evx">{data.map((m) => <span key={m.mes}>{m.mes.slice(5)}/{m.mes.slice(2, 4)}</span>)}</div>
    </div>
  );
}
