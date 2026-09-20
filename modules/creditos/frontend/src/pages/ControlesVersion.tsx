import { useEffect, useState } from "react";
import { api } from "../api";
import { avisar } from "../ui/dialog";

// Controles de Versión — documentación viva del módulo Configurar Créditos:
// registro de cambios, modelo de datos (tablas) y APIs, introspectados del backend.

const METODO_CLS: Record<string, string> = { GET: "pub", POST: "apr", PUT: "rev", DELETE: "ret", PATCH: "draft" };

type Tab = "modelo" | "diagrama" | "apis" | "casos" | "cambios";
const GRUPO_COL = ["var(--dv-blue)", "var(--dv-purple)", "var(--dv-green)", "var(--dv-orange)", "var(--dv-teal)", "var(--dv-red)", "var(--dv-amber)"];

export default function ControlesVersion() {
  const [d, setD] = useState<any>(null);
  const [tab, setTab] = useState<Tab>("modelo");
  const [q, setQ] = useState("");
  const [casos, setCasos] = useState<any[] | null>(null);
  const [corriendo, setCorriendo] = useState(false);

  useEffect(() => { api.controlesVersion().then(setD).catch(() => {}); }, []);
  if (!d) return <div className="cfgc"><p className="muted">Cargando…</p></div>;

  async function correr() {
    setCorriendo(true);
    try { const r = await api.correrCasos(); setCasos(r.resultados); }
    catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); } finally { setCorriendo(false); }
  }
  const resMap: Record<string, any> = Object.fromEntries((casos || []).map((r) => [r.id, r]));
  const casosPorPantalla: Record<string, any[]> = {};
  for (const c of d.casos || []) (casosPorPantalla[c.pantalla] ||= []).push(c);

  // Layout del diagrama de relaciones (por capas según FK).
  const tablas = d.grupos.flatMap((g: any, gi: number) => g.tablas.map((t: any) => ({ ...t, gi })));
  const nombres = new Set(tablas.map((t: any) => t.nombre));
  const memo: Record<string, number> = {};
  const layerOf = (name: string, stack: Set<string> = new Set()): number => {
    if (name in memo) return memo[name];
    if (stack.has(name)) return 0;
    const t = tablas.find((x: any) => x.nombre === name);
    const refs = (t?.relaciones || []).map((r: any) => r.haciaTabla).filter((h: string) => h !== name && nombres.has(h));
    const l = refs.length ? 1 + Math.max(...refs.map((r: string) => layerOf(r, new Set([...stack, name])))) : 0;
    memo[name] = l; return l;
  };
  tablas.forEach((t: any) => layerOf(t.nombre));
  const byLayer: Record<number, any[]> = {};
  tablas.forEach((t: any) => { (byLayer[memo[t.nombre]] ||= []).push(t); });
  const W = 168, H = 30, GX = 78, GY = 16, PAD = 18;
  const pos: Record<string, { x: number; y: number; gi: number }> = {};
  Object.entries(byLayer).forEach(([layer, ts]) => ts.forEach((t: any, i: number) => { pos[t.nombre] = { x: PAD + Number(layer) * (W + GX), y: PAD + i * (H + GY), gi: t.gi }; }));
  const maxLayer = Math.max(0, ...Object.values(memo));
  const maxRows = Math.max(1, ...Object.values(byLayer).map((a) => a.length));
  const svgW = PAD * 2 + (maxLayer + 1) * W + maxLayer * GX;
  const svgH = PAD * 2 + maxRows * (H + GY);
  const edges: any[] = [];
  const selfRefs = new Set<string>();
  tablas.forEach((t: any) => (t.relaciones || []).forEach((r: any) => {
    if (r.haciaTabla === t.nombre) { selfRefs.add(t.nombre); return; }
    if (pos[r.haciaTabla] && pos[t.nombre]) edges.push({ from: pos[t.nombre], to: pos[r.haciaTabla] });
  }));

  const rutasFiltradas = d.rutas.filter((r: any) => !q || (r.path + " " + r.doc).toLowerCase().includes(q.toLowerCase()));
  const rutasPorGrupo: Record<string, any[]> = {};
  for (const r of rutasFiltradas) (rutasPorGrupo[r.grupo] ||= []).push(r);

  return (
    <div className="cfgc">
      <div className="cfgc-cathead">
        <div>
          <h1>Controles de Versión</h1>
          <p>Documentación viva del módulo <b>Configurar Créditos</b>: modelo de datos, APIs y registro de cambios. Se genera introspectando el esquema y las rutas reales del backend.</p>
        </div>
      </div>

      {/* Resumen + opciones nuevas de menú */}
      <div className="card" style={{ padding: "12px 16px", marginBottom: 14 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(130px,1fr))", gap: 10, marginBottom: 12 }}>
          <div className="cfgc-metric hl"><small>Tablas de datos</small><strong className="num">{d.totales.tablas}</strong></div>
          <div className="cfgc-metric"><small>Endpoints de API</small><strong className="num">{d.totales.rutas}</strong></div>
          <div className="cfgc-metric"><small>Opciones de menú nuevas</small><strong className="num">{d.menuNuevo.length}</strong></div>
          <div className="cfgc-metric"><small>Hitos registrados</small><strong className="num">{d.changelog.length}</strong></div>
        </div>
        <b style={{ fontSize: 13 }}>Opciones de menú nuevas</b>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 8, marginTop: 8 }}>
          {d.menuNuevo.map((m: any) => (
            <div key={m.ruta} style={{ border: "1px solid var(--border)", borderRadius: 10, padding: "8px 11px" }}>
              <b style={{ fontSize: 12.5 }}>{m.label}</b>
              <div className="muted" style={{ fontSize: 11.5 }}>{m.detalle}</div>
              <code style={{ fontSize: 11, color: "var(--brand-2)" }}>{m.ruta}</code>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="cfgc-vtabs">
        {([["modelo", "🗂️ Modelo de datos"], ["diagrama", "🔗 Diagrama"], ["apis", "🔌 APIs"], ["casos", "✅ Casos de prueba"], ["cambios", "📜 Registro de cambios"]] as const).map(([k, t]) => (
          <button key={k} className={`cfgc-vtab ${tab === k ? "on" : ""}`} onClick={() => setTab(k)}>{t}</button>
        ))}
      </div>

      {/* MODELO DE DATOS */}
      {tab === "modelo" && (
        <div>
          <p className="muted" style={{ fontSize: 12, margin: "0 0 12px" }}>Cada tabla es una entidad; <span className="cvk pk">PK</span> clave primaria, <span className="cvk fk">FK → tabla</span> relación. Prefijo <code>pp_</code> = plataforma de productos de préstamo (aislada del legacy).</p>
          {d.grupos.map((g: any) => (
            <div key={g.titulo} style={{ marginBottom: 18 }}>
              <h3 style={{ fontSize: 14, margin: "0 0 10px" }}>{g.titulo} <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>({g.tablas.length})</span></h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(260px,1fr))", gap: 12, alignItems: "start" }}>
                {g.tablas.map((t: any) => (
                  <div key={t.nombre} className="cv-ent">
                    <div className="cv-ent-h">{t.nombre}</div>
                    <div className="cv-ent-b">
                      {t.columnas.map((c: any) => (
                        <div key={c.nombre} className="cv-col">
                          <span className="cv-cn">{c.nombre}{c.pk && <span className="cvk pk">PK</span>}{c.fk && <span className="cvk fk">FK</span>}</span>
                          <span className="cv-ct">{c.tipo.replace(/VARCHAR/i, "str").replace(/NUMERIC/i, "num").replace(/INTEGER/i, "int").replace(/BOOLEAN/i, "bool").replace(/DATETIME/i, "datetime").replace(/DATE/i, "date")}</span>
                        </div>
                      ))}
                    </div>
                    {t.relaciones.length > 0 && (
                      <div className="cv-ent-f">{t.relaciones.map((r: any, i: number) => (
                        <span key={i} className="cv-rel">{r.columna} → <b>{r.haciaTabla}</b></span>
                      ))}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* DIAGRAMA DE RELACIONES */}
      {tab === "diagrama" && (
        <div className="card" style={{ padding: 12 }}>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginBottom: 8, fontSize: 11 }}>
            {d.grupos.map((g: any, i: number) => (
              <span key={g.titulo} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 10, height: 10, borderRadius: 3, background: GRUPO_COL[i % GRUPO_COL.length] }} />{g.titulo}
              </span>
            ))}
            <span className="muted">· la flecha apunta a la tabla referenciada (FK) · ↻ auto-referencia</span>
          </div>
          <div style={{ overflow: "auto", border: "1px solid var(--border)", borderRadius: 10, background: "var(--surface-2)" }}>
            <svg width={svgW} height={svgH} style={{ display: "block" }}>
              <defs>
                <marker id="cvarrow" markerWidth="9" markerHeight="9" refX="8" refY="3" orient="auto" markerUnits="userSpaceOnUse">
                  <path d="M0,0 L8,3 L0,6 Z" fill="var(--ink-faint)" />
                </marker>
              </defs>
              {edges.map((e: any, i: number) => {
                const x1 = e.from.x, y1 = e.from.y + H / 2, x2 = e.to.x + W, y2 = e.to.y + H / 2;
                const mx = (x1 + x2) / 2;
                return <path key={i} d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`} fill="none" stroke="var(--ink-faint)" strokeWidth={1.2} opacity={0.55} markerEnd="url(#cvarrow)" />;
              })}
              {tablas.map((t: any) => {
                const p = pos[t.nombre]; if (!p) return null;
                const col = GRUPO_COL[t.gi % GRUPO_COL.length];
                return (
                  <g key={t.nombre} transform={`translate(${p.x},${p.y})`}>
                    <rect width={W} height={H} rx={7} fill="var(--surface)" stroke="var(--border-strong)" />
                    <rect width={5} height={H} rx={2} fill={col} />
                    <text x={13} y={H / 2 + 4} fontFamily="var(--mono)" fontSize={11} fontWeight={600} fill="var(--ink)">{t.nombre}</text>
                    {selfRefs.has(t.nombre) && <text x={W - 14} y={H / 2 + 4} fontSize={12} fill="var(--ink-faint)">↻</text>}
                  </g>
                );
              })}
            </svg>
          </div>
        </div>
      )}

      {/* APIS */}
      {tab === "apis" && (
        <div className="card" style={{ padding: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
            <b style={{ fontSize: 13 }}>Endpoints ({rutasFiltradas.length})</b>
            <span style={{ flex: 1 }} />
            <input style={{ maxWidth: 240 }} value={q} placeholder="Filtrar por ruta…" onChange={(e) => setQ(e.target.value)} />
          </div>
          {Object.entries(rutasPorGrupo).map(([grupo, rutas]) => (
            <div key={grupo} style={{ marginBottom: 14 }}>
              <div className="muted" style={{ fontSize: 11.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 6 }}>/api/{grupo}</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {rutas.map((r: any, i: number) => (
                  <div key={i} className="cv-api">
                    <span className={`pill ${METODO_CLS[r.metodo] || "rev"}`} style={{ minWidth: 52, textAlign: "center" }}>{r.metodo}</span>
                    <code style={{ fontSize: 12 }}>{r.path}</code>
                    {r.doc && <span className="muted" style={{ fontSize: 11.5, flex: 1 }}>{r.doc}</span>}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* CASOS DE PRUEBA */}
      {tab === "casos" && (
        <div className="card" style={{ padding: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12, flexWrap: "wrap" }}>
            <b style={{ fontSize: 13 }}>Casos de prueba ({d.casos.length})</b>
            <span className="muted" style={{ fontSize: 11.5 }}>
              <span className="cvk fk">auto</span> cubierto por la suite pytest · <span className="cvk pk">live</span> corrible acá (read-only)
            </span>
            <span style={{ flex: 1 }} />
            {casos && <span style={{ fontSize: 12, fontWeight: 700, color: casos.every((r) => r.ok) ? "var(--ok, #1a7f37)" : "var(--crit)" }}>{casos.filter((r) => r.ok).length}/{casos.length} OK</span>}
            <button className="btn sm primary" disabled={corriendo} onClick={correr}>{corriendo ? "Corriendo…" : `▶ Correr ${d.totales.casosLive} pruebas en vivo`}</button>
          </div>
          {Object.entries(casosPorPantalla).map(([pantalla, cs]) => (
            <div key={pantalla} style={{ marginBottom: 14 }}>
              <div className="muted" style={{ fontSize: 11.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 6 }}>{pantalla}</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {cs.map((c: any) => {
                  const r = resMap[c.id];
                  return (
                    <div key={c.id} className="cv-caso">
                      <span className="cvk" style={c.tipo === "live" ? { background: "var(--accent-soft)", color: "var(--brand-2)" } : { background: "var(--calc-soft)", color: "var(--calc)" }}>{c.tipo}</span>
                      <span style={{ flex: 1, fontSize: 12.5 }}>{c.titulo}{c.ref && <code style={{ marginLeft: 6, fontSize: 10.5 }}>{c.ref}</code>}</span>
                      {c.tipo === "live" && r && <span style={{ fontSize: 11, color: r.ok ? "var(--ok, #1a7f37)" : "var(--crit)", fontWeight: 700 }} title={r.detalle}>{r.ok ? "✓" : "✗"} {r.detalle} <span className="muted">({r.ms}ms)</span></span>}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* CAMBIOS */}
      {tab === "cambios" && (
        <div className="card" style={{ padding: 16 }}>
          <div className="cv-timeline">
            {d.changelog.map((c: any, i: number) => (
              <div key={i} className="cv-ti">
                <span className="cv-dot" />
                <div><b style={{ fontSize: 13 }}>{c.hito}</b><div className="muted" style={{ fontSize: 12 }}>{c.detalle}</div></div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
