import { useEffect, useMemo, useState } from "react";
import { creditos } from "../../../../api/creditos";
import { PageHeader, Card, Boton, Alerta } from "../../components/ui";
import { Pill } from "../../components/Pill";
import { fecha, num } from "../../components/format";
import { usePaletaGraficos } from "../../graficos";

/**
 * Tablero de la cartera de créditos originados. Cada segmento es clickeable y abre el detalle de
 * contratos de ese corte (drill-down). Los colores salen de la paleta del tema activo
 * (claro/oscuro), validada en `graficos.js`; los estados de cola se agrupan en "Otros".
 */
const DESTACADOS = ["ACTIVO", "A_LIQUIDAR", "REFINANCIADO"];
const colorDeEstado = (paleta) => (e) => ({
  ACTIVO: paleta.verde, A_LIQUIDAR: paleta.ambar, REFINANCIADO: paleta.azul,
}[e] || paleta.gris);

const PILL_ESTADO = {
  ACTIVO: "ok", A_LIQUIDAR: "warn", REFINANCIADO: "brand", CASTIGADO: "crit",
  CERRADO: "neutral", CANCELADO: "neutral", ANULADO: "neutral",
};

const money = (n) => "$" + Number(n || 0).toLocaleString("es-AR", { maximumFractionDigits: 0 });
const moneyCorto = (n) => {
  const v = Number(n || 0);
  if (Math.abs(v) >= 1_000_000) return "$" + (v / 1_000_000).toLocaleString("es-AR", { maximumFractionDigits: 1 }) + "M";
  if (Math.abs(v) >= 1_000) return "$" + Math.round(v / 1_000) + "k";
  return "$" + Math.round(v);
};

function Kpi({ label, valor, sub, destacado, critico, onClick }) {
  const Etiqueta = onClick ? "button" : "div";
  return (
    <Etiqueta
      onClick={onClick}
      className={`text-left bg-surface border rounded-xl px-4 py-3 flex flex-col gap-0.5 ${
        destacado ? "border-blue-400" : "border-gray-200"} ${onClick ? "hover:border-blue-400" : ""}`}
    >
      <span className="text-[11px] uppercase tracking-wide text-gray-500">{label}</span>
      <span className={`text-xl font-semibold tabular-nums ${critico ? "text-red-600" : "text-gray-800"}`}>{valor}</span>
      {sub && <span className="text-xs text-gray-500">{sub}</span>}
    </Etiqueta>
  );
}

/** Donut de composición. Los segmentos se separan 2px (encoding secundario del color). */
function Donut({ segmentos, total, paleta }) {
  const R = 52, C = 2 * Math.PI * R, SZ = 130, HUECO = 2;
  let acumulado = 0;
  const arcos = segmentos.filter((s) => s.valor > 0).map((s) => {
    const frac = total > 0 ? s.valor / total : 0;
    const arco = { ...s, dash: Math.max(0, frac * C - HUECO), off: -acumulado * C };
    acumulado += frac;
    return arco;
  });
  return (
    <svg width={SZ} height={SZ} viewBox={`0 0 ${SZ} ${SZ}`} role="img"
         aria-label={`Composición de la cartera: ${segmentos.map((s) => `${s.label} ${moneyCorto(s.valor)}`).join(", ")}`}
         className="shrink-0">
      <g transform={`translate(${SZ / 2},${SZ / 2}) rotate(-90)`}>
        <circle r={R} fill="none" stroke={paleta.pista} strokeWidth={16} />
        {arcos.map((s) => (
          <circle key={s.label} r={R} fill="none" stroke={s.color} strokeWidth={16}
                  strokeDasharray={`${s.dash} ${C - s.dash}`} strokeDashoffset={s.off}>
            <title>{s.label}: {money(s.valor)}</title>
          </circle>
        ))}
      </g>
      <text x={SZ / 2} y={SZ / 2 - 1} textAnchor="middle" fontSize="15" fontWeight="700" fill={paleta.tinta}>
        {moneyCorto(total)}
      </text>
      <text x={SZ / 2} y={SZ / 2 + 13} textAnchor="middle" fontSize="9" fill={paleta.tintaSuave}>capital colocado</text>
    </svg>
  );
}

/** Barras agrupadas: originado vs cobrado por mes (azul/verde, paleta validada). */
function BarrasEvolucion({ data, paleta }) {
  const H = 120;
  const max = Math.max(1, ...data.map((m) => Math.max(Number(m.originadoMonto), Number(m.cobradoMonto))));
  const ancho = 100 / Math.max(1, data.length);
  return (
    <div>
      <svg width="100%" height={H} viewBox={`0 0 100 ${H}`} preserveAspectRatio="none" className="block" role="img"
           aria-label="Originado y cobrado por mes, últimos seis meses">
        {[0.25, 0.5, 0.75, 1].map((g) => (
          <line key={g} x1="0" x2="100" y1={H - g * H} y2={H - g * H} stroke={paleta.grilla} strokeWidth="0.3" />
        ))}
        {data.map((m, i) => {
          const x = i * ancho, o = Number(m.originadoMonto), c = Number(m.cobradoMonto);
          const w = ancho * 0.32;
          return (
            <g key={m.mes}>
              <rect x={x + ancho * 0.14} y={H - (o / max) * H} width={w} height={(o / max) * H} fill={paleta.azul}>
                <title>{m.mes} · Originado {money(o)} ({m.originadoN})</title>
              </rect>
              <rect x={x + ancho * 0.52} y={H - (c / max) * H} width={w} height={(c / max) * H} fill={paleta.verde}>
                <title>{m.mes} · Cobrado {money(c)}</title>
              </rect>
            </g>
          );
        })}
      </svg>
      <div className="flex mt-1">
        {data.map((m) => (
          <span key={m.mes} className="flex-1 text-center text-[11px] text-gray-400 tabular-nums">
            {m.mes.slice(5)}/{m.mes.slice(2, 4)}
          </span>
        ))}
      </div>
      <div className="flex gap-4 mt-2 text-xs text-gray-500">
        <span className="flex items-center gap-1.5"><i className="w-2.5 h-2.5 rounded-sm" style={{ background: paleta.azul }} /> Originado</span>
        <span className="flex items-center gap-1.5"><i className="w-2.5 h-2.5 rounded-sm" style={{ background: paleta.verde }} /> Cobrado</span>
      </div>
    </div>
  );
}

export default function TableroCarteraPage() {
  const paleta = usePaletaGraficos();
  const colorEstado = colorDeEstado(paleta);
  const [d, setD] = useState(null);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(true);
  const [drill, setDrill] = useState(null);       // { tipo, valor, label }

  async function cargar() {
    setError(""); setCargando(true);
    try { setD(await creditos.ctoTablero()); }
    catch (e) { setError(e.message); }
    finally { setCargando(false); }
  }
  useEffect(() => { cargar(); }, []);

  const k = d?.kpis;
  const contratos = d?.contratos || [];

  const filtrados = useMemo(() => {
    if (!drill) return [];
    return contratos.filter((c) =>
      drill.tipo === "todos" ? true
      : drill.tipo === "estado" ? c.estado === drill.valor
      : drill.tipo === "producto" ? c.productoId === drill.valor
      : drill.tipo === "mora" ? (drill.valor === "__mora__" ? c.diasAtraso > 0 : c.moraBucket === drill.valor)
      : false);
  }, [drill, contratos]);

  // Donut: los tres estados con color propio + "Otros" (no se inventan hues nuevos).
  const segmentos = useMemo(() => {
    const porEstado = d?.porEstado || [];
    const destacados = porEstado.filter((e) => DESTACADOS.includes(e.estado))
      .map((e) => ({ label: e.estado, valor: Number(e.capital), color: colorEstado(e.estado) }));
    const otros = porEstado.filter((e) => !DESTACADOS.includes(e.estado))
      .reduce((a, e) => a + Number(e.capital), 0);
    return otros > 0 ? [...destacados, { label: "Otros", valor: otros, color: paleta.gris }] : destacados;
  }, [d, paleta]);

  return (
    <>
      <PageHeader
        titulo="Tablero de cartera"
        descripcion={`Cartera de créditos originados · datos al ${d?.generadoEn || "—"}. Clickeá cualquier segmento para ver su detalle.`}
      >
        <Boton variante="secundario" onClick={cargar} disabled={cargando}>{cargando ? "…" : "↻ Refrescar"}</Boton>
        {contratos.length > 0 && (
          <Boton variante="ok" onClick={() => creditos.ctoCarteraExcel().catch((e) => setError(e.message))}>
            Exportar (Excel)
          </Boton>
        )}
      </PageHeader>

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}
      {cargando && !d && <Card>Cargando…</Card>}

      {k && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 mb-4">
            <Kpi label="Saldo vigente" valor={money(k.saldoVigente)} sub={`${num(k.activos)} contratos activos`} destacado />
            <Kpi label="Capital colocado" valor={money(k.capitalColocado)}
                 sub={`${num(k.contratos)} contratos · ticket ${moneyCorto(k.ticketPromedio)}`} />
            <Kpi label="Cobrado (histórico)" valor={money(k.cobrado)} sub={`${num(k.cuotasPagadas)} cuotas pagadas`} />
            <Kpi label="Mora" valor={money(k.moraMonto)} critico={Number(k.moraMonto) > 0}
                 sub={`${k.moraPct}% de la cartera · ${num(k.contratosEnMora)} contratos`}
                 onClick={k.contratosEnMora ? () => setDrill({ tipo: "mora", valor: "__mora__", label: "En mora" }) : undefined} />
            <Kpi label="Recaudado del mes" valor={money(k.recaudadoMes)} sub="pagos registrados este mes" />
            <Kpi label="Por liquidar" valor={money(k.aLiquidarMonto)} sub={`${num(k.aLiquidarN)} contratos a desembolsar`}
                 onClick={k.aLiquidarN ? () => setDrill({ tipo: "estado", valor: "A_LIQUIDAR", label: "Por liquidar" }) : undefined} />
            <Kpi label="Vencen en 30 días" valor={money(k.vencen30Monto)} sub={`${num(k.vencen30Cuotas)} cuotas próximas`} />
            <Kpi label="TNA prom. · Plazo prom." valor={`${k.tnaPromedioPond}% · ${k.plazoPromedio}`} sub="ponderada por saldo · cuotas" />
          </div>

          <div className="grid gap-4 lg:grid-cols-2 mb-4">
            <Card>
              <h2 className="font-semibold text-gray-800 mb-3">Cartera por estado</h2>
              <div className="flex flex-wrap items-center gap-4">
                <Donut segmentos={segmentos} total={Number(k.capitalColocado)} paleta={paleta} />
                <div className="flex-1 min-w-[190px]">
                  {(d.porEstado || []).map((e) => (
                    <button key={e.estado} onClick={() => setDrill({ tipo: "estado", valor: e.estado, label: e.estado })}
                            className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-50 text-left">
                      <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: colorEstado(e.estado) }} />
                      <span className="flex-1 text-sm text-gray-700">{e.estado}</span>
                      <span className="text-xs text-gray-400 tabular-nums w-10 text-right">{num(e.contratos)}</span>
                      <span className="text-sm text-gray-700 tabular-nums w-24 text-right">{money(e.capital)}</span>
                    </button>
                  ))}
                </div>
              </div>
            </Card>

            <Card>
              <h2 className="font-semibold text-gray-800 mb-3">Evolución (últimos 6 meses)</h2>
              <BarrasEvolucion data={d.evolucion || []} paleta={paleta} />
            </Card>
          </div>

          <Card padding={false} className="mb-4">
            <h2 className="px-4 py-3 font-semibold text-gray-800 border-b border-gray-200">Antigüedad de la mora (aging)</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500">
                  <th className="px-4 py-2 text-left">Tramo de atraso</th>
                  <th className="px-4 py-2 text-right">Contratos</th>
                  <th className="px-4 py-2 text-right">Saldo</th>
                  <th className="px-4 py-2 text-left w-2/5">Participación del saldo activo</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {(d.aging || []).map((a) => {
                  const pct = Number(k.saldoVigente) > 0 ? (Number(a.saldo) / Number(k.saldoVigente)) * 100 : 0;
                  return (
                    <tr key={a.bucket}
                        onClick={a.contratos ? () => setDrill({ tipo: "mora", valor: a.bucket, label: `Atraso ${a.bucket}` }) : undefined}
                        className={a.contratos ? "cursor-pointer hover:bg-gray-50" : ""}>
                      <td className="px-4 py-2">{a.bucket}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{num(a.contratos)}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{money(a.saldo)}</td>
                      <td className="px-4 py-2">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden">
                            <div className="h-full rounded-full bg-red-500" style={{ width: `${pct}%` }} />
                          </div>
                          <span className="text-xs text-gray-400 tabular-nums w-12 text-right">{pct.toFixed(1)}%</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>

          <Card padding={false} className="mb-4">
            <h2 className="px-4 py-3 font-semibold text-gray-800 border-b border-gray-200">Por línea de crédito</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500">
                    <th className="px-4 py-2 text-left">Línea</th>
                    <th className="px-4 py-2 text-right">Contratos</th>
                    <th className="px-4 py-2 text-right">Capital colocado</th>
                    <th className="px-4 py-2 text-right">Saldo vigente</th>
                    <th className="px-4 py-2 text-right">Mora</th>
                    <th className="px-4 py-2 text-left">Mora %</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {!(d.porProducto || []).length && (
                    <tr><td colSpan={6} className="px-4 py-6 text-center text-gray-400">Sin contratos.</td></tr>
                  )}
                  {(d.porProducto || []).map((p) => (
                    <tr key={p.id} onClick={() => setDrill({ tipo: "producto", valor: p.id, label: p.nombre || p.codigo })}
                        className="cursor-pointer hover:bg-gray-50">
                      <td className="px-4 py-2"><b>{p.nombre || p.codigo}</b>
                        {p.codigo && <span className="text-gray-400"> · {p.codigo}</span>}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{num(p.contratos)}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{money(p.capital)}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{money(p.saldo)}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{money(p.mora)}</td>
                      <td className="px-4 py-2">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden">
                            <div className={`h-full rounded-full ${p.moraPct > 0 ? "bg-red-500" : "bg-green-600"}`}
                                 style={{ width: `${Math.min(100, p.moraPct)}%` }} />
                          </div>
                          <span className="text-xs text-gray-400 tabular-nums w-10 text-right">{p.moraPct}%</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="flex flex-wrap items-center gap-2 mb-4">
            <span className="text-sm text-gray-500">Ver detalle:</span>
            <button onClick={() => setDrill({ tipo: "todos", valor: "", label: "Toda la cartera" })}
                    className="px-3 py-1 text-sm border rounded-full text-gray-600 hover:border-blue-400">
              Toda la cartera
            </button>
            {(d.porEstado || []).map((e) => (
              <button key={e.estado} onClick={() => setDrill({ tipo: "estado", valor: e.estado, label: e.estado })}
                      className="px-3 py-1 text-sm border rounded-full text-gray-600 hover:border-blue-400">
                {e.estado} ({e.contratos})
              </button>
            ))}
          </div>
        </>
      )}

      {drill && (
        <Card padding={false} className="border-blue-400">
          <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-200">
            <b className="text-gray-800">Detalle · {drill.label}</b>
            <span className="text-xs text-gray-500 bg-gray-100 rounded-full px-2 py-0.5">
              {filtrados.length} contrato(s)
            </span>
            <span className="flex-1" />
            <Boton variante="secundario" onClick={() => setDrill(null)}>✕ Cerrar detalle</Boton>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500">
                  <th className="px-4 py-2 text-left">N° contrato</th>
                  <th className="px-4 py-2 text-left">Cliente</th>
                  <th className="px-4 py-2 text-left">Línea</th>
                  <th className="px-4 py-2 text-left">Estado</th>
                  <th className="px-4 py-2 text-right">Monto</th>
                  <th className="px-4 py-2 text-right">Saldo</th>
                  <th className="px-4 py-2 text-right">Atraso</th>
                  <th className="px-4 py-2 text-left">Próx. venc.</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {!filtrados.length && (
                  <tr><td colSpan={8} className="px-4 py-6 text-center text-gray-400">Sin contratos en este segmento.</td></tr>
                )}
                {filtrados.map((c) => (
                  <tr key={c.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 font-medium tabular-nums">{c.numero}</td>
                    <td className="px-4 py-2">{c.cliente}</td>
                    <td className="px-4 py-2">{c.producto || c.codigo || "—"}</td>
                    <td className="px-4 py-2"><Pill tono={PILL_ESTADO[c.estado] || "neutral"}>{c.estado}</Pill></td>
                    <td className="px-4 py-2 text-right tabular-nums">{money(c.monto)}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{money(c.saldo)}</td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {c.diasAtraso > 0 ? <span className="text-red-600 font-medium">{c.diasAtraso} d</span> : "—"}
                    </td>
                    <td className="px-4 py-2">
                      {c.proxVenc ? fecha(c.proxVenc) : "—"}
                      {c.proxCuota ? <span className="text-gray-400"> (c.{c.proxCuota})</span> : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  );
}
