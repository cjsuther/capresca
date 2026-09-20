import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { api } from "../../api";

type Col = { nombre: string; tipo: string; pk: boolean; fk: { tabla: string; columna: string } | null };
type Uso = { ruta: string; label: string };
type Tabla = { tabla: string; modulo: string; origen: string | null; usos: Uso[]; columnas: Col[] };
type Legacy = { clave: string; modulo: string; nombre: string; dbf: string; tabla_destino: string;
                campos: { origen: string; destino: string; tipo: string }[] };

type Vista = "actual" | "legacy" | "inventario";

export default function ModeloDatos() {
  const [data, setData] = useState<{ actual: Tabla[]; legacy: Legacy[] } | null>(null);
  const [inv, setInv] = useState<any>(null);
  const [vista, setVista] = useState<Vista>("actual");
  const [modulo, setModulo] = useState<string>("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.esquemaDatos().then((d: { actual: Tabla[]; legacy: Legacy[] }) => {
      setData(d);
      const mods = [...new Set(d.actual.map((t) => t.modulo))].sort();
      setModulo(mods[0] ?? "");
    }).catch((e: any) => setError(e.message));
  }, []);
  useEffect(() => {
    if (vista === "inventario" && !inv) api.inventarioDbfs().then(setInv).catch((e: any) => setError(e.message));
  }, [vista, inv]);

  if (error) return <div className="card"><p className="error">{error}</p></div>;
  if (!data) return <div className="card"><p className="muted">Cargando esquema…</p></div>;

  const modulos = [...new Set((vista === "actual" ? data.actual : data.legacy).map((t) => t.modulo))].sort();
  const modActivo = modulos.includes(modulo) ? modulo : modulos[0];

  return (
    <>
      <div className="card">
        <h1 style={{ marginTop: 0 }}>Modelo de datos — DER</h1>
        <p className="muted">Diagrama entidad-relación del <b>modelo actual</b> (con las claves foráneas reales), de los <b>DBFs legacy</b> de origen, y el <b>inventario</b> de todos los .dbf del backup por carpeta. {data.actual.length} tablas nuevas · {data.legacy.length} migradores.</p>
        <div style={{ display: "flex", gap: "0.4rem", marginBottom: vista === "inventario" ? 0 : "0.7rem", flexWrap: "wrap" }}>
          <button className={vista === "actual" ? "" : "btn-ghost"} onClick={() => setVista("actual")}>Modelo actual</button>
          <button className={vista === "legacy" ? "" : "btn-ghost"} onClick={() => setVista("legacy")}>DBFs legacy</button>
          <button className={vista === "inventario" ? "" : "btn-ghost"} onClick={() => setVista("inventario")}>Inventario de DBFs</button>
        </div>
        {vista !== "inventario" && (
          <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
            {modulos.map((m) => (
              <button key={m} onClick={() => setModulo(m)}
                      className={m === modActivo ? "" : "btn-ghost"}
                      style={{ padding: "5px 11px", fontSize: 12.5 }}>{m}</button>
            ))}
          </div>
        )}
      </div>

      {vista === "actual" && <DerActual tablas={data.actual.filter((t) => t.modulo === modActivo)} />}
      {vista === "legacy" && <LegacyCards items={data.legacy.filter((t) => t.modulo === modActivo)} />}
      {vista === "inventario" && (inv ? <Inventario carpetas={inv.carpetas} /> : <div className="card"><p className="muted">Escaneando carpetas del backup…</p></div>)}
    </>
  );
}

/* ---------- Inventario de DBFs por carpeta ---------- */
const num = (v: any) => (v == null ? "—" : Number(v).toLocaleString("es-AR"));
const mb = (b: number) => (b >= 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${(b / 1024).toFixed(0)} KB`);

function Inventario({ carpetas }: { carpetas: any[] }) {
  const [campos, setCampos] = useState<string | null>(null);
  return (
    <>
      {carpetas.map((c) => (
        <div className="card" key={c.carpeta}>
          <h3 style={{ marginTop: 0 }}>
            {c.carpeta}
            <span className="muted" style={{ fontWeight: 400, fontSize: 12.5 }}> · {c.cantidad} DBFs · </span>
            <span className="pill ok">{c.usados} migrados</span>
            {c.cantidad - c.usados > 0 && <span className="pill warn" style={{ marginLeft: 6 }}>{c.cantidad - c.usados} sin migrar</span>}
          </h3>
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead><tr><th>Archivo .dbf</th><th style={{ textAlign: "right" }}>Registros</th><th style={{ textAlign: "right" }}>Campos</th><th style={{ textAlign: "right" }}>Tamaño</th><th>Estado</th></tr></thead>
              <tbody>
                {c.dbfs.map((d: any) => (
                  <>
                    <tr key={d.ruta}>
                      <td>
                        <code>{d.archivo}</code>
                        {d.proposito && <div className="muted" style={{ fontSize: 11 }}>{d.proposito}</div>}
                      </td>
                      <td style={{ textAlign: "right" }}>{num(d.registros)}</td>
                      <td style={{ textAlign: "right" }}>
                        <button className="btn-ghost" style={{ padding: "1px 8px", fontSize: 11 }}
                                onClick={() => setCampos(campos === d.ruta ? null : d.ruta)}>{d.campos.length} ▾</button>
                      </td>
                      <td style={{ textAlign: "right" }}>{mb(d.tamano)}</td>
                      <td>{d.usado
                        ? <span className="pill ok" title={d.migrador}>→ {d.tabla}</span>
                        : <span className="pill warn">sin migrar</span>}</td>
                    </tr>
                    {campos === d.ruta && (
                      <tr key={d.ruta + "-c"}><td colSpan={5} style={{ background: "var(--surface-2)", fontSize: 11.5, padding: "8px 12px" }}>
                        {d.usado ? (
                          <>
                            <div style={{ marginBottom: 4 }}>Migra a <code>{d.tabla}</code> — mapeo de campos:</div>
                            <div style={{ display: "flex", flexWrap: "wrap", gap: "3px 12px" }}>
                              {d.mapeo.map((m: any, i: number) => (
                                <span key={i}><code>{m.origen}</code> → {m.destino}</span>
                              ))}
                            </div>
                          </>
                        ) : (
                          <>
                            <div><b>No se migra:</b> {d.motivo}</div>
                            <div style={{ marginTop: 4 }}><b>Campos:</b> {d.campos.join(" · ") || "(no legibles)"}</div>
                          </>
                        )}
                      </td></tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </>
  );
}

/* ---------- DER del modelo actual: cards + líneas SVG de FK ---------- */
function DerActual({ tablas }: { tablas: Tabla[] }) {
  const cont = useRef<HTMLDivElement>(null);
  const cards = useRef<Record<string, HTMLDivElement | null>>({});
  const [edges, setEdges] = useState<{ x1: number; y1: number; x2: number; y2: number; label: string }[]>([]);
  const [size, setSize] = useState({ w: 0, h: 0 });

  const nombres = new Set(tablas.map((t) => t.tabla));

  function recalcular() {
    const c = cont.current;
    if (!c) return;
    const base = c.getBoundingClientRect();
    setSize({ w: c.scrollWidth, h: c.scrollHeight });
    const centro = (el: HTMLElement) => {
      const r = el.getBoundingClientRect();
      return { x: r.left - base.left + c.scrollLeft + r.width / 2,
               y: r.top - base.top + c.scrollTop + r.height / 2 };
    };
    const es: any[] = [];
    for (const t of tablas) {
      const src = cards.current[t.tabla];
      if (!src) continue;
      for (const col of t.columnas) {
        if (col.fk && nombres.has(col.fk.tabla) && col.fk.tabla !== t.tabla) {
          const dst = cards.current[col.fk.tabla];
          if (!dst) continue;
          const a = centro(src), b = centro(dst);
          es.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y, label: col.nombre });
        }
      }
    }
    setEdges(es);
  }

  useLayoutEffect(() => {
    const id = requestAnimationFrame(recalcular);
    return () => cancelAnimationFrame(id);
    // eslint-disable-next-line
  }, [tablas]);
  useEffect(() => {
    const onR = () => recalcular();
    window.addEventListener("resize", onR);
    return () => window.removeEventListener("resize", onR);
    // eslint-disable-next-line
  }, [tablas]);

  return (
    <div className="card">
      <div ref={cont} style={{ position: "relative", display: "flex", flexWrap: "wrap", gap: "26px", alignItems: "flex-start" }}>
        <svg width={size.w} height={size.h} style={{ position: "absolute", inset: 0, pointerEvents: "none", zIndex: 0, overflow: "visible" }}>
          <defs>
            <marker id="arrow" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">
              <path d="M0,0 L7,3 L0,6" fill="none" stroke="var(--brand-2)" strokeWidth="1.4" />
            </marker>
          </defs>
          {edges.map((e, i) => {
            const mx = (e.x1 + e.x2) / 2;
            return <path key={i} d={`M ${e.x1} ${e.y1} C ${mx} ${e.y1}, ${mx} ${e.y2}, ${e.x2} ${e.y2}`}
                         fill="none" stroke="var(--brand-2)" strokeWidth="1.6" opacity="0.55" markerEnd="url(#arrow)" />;
          })}
        </svg>
        {tablas.map((t) => (
          <div key={t.tabla} ref={(el) => (cards.current[t.tabla] = el)}
               style={{ position: "relative", zIndex: 1, minWidth: 210, maxWidth: 260,
                        border: "1px solid var(--border-strong)", borderRadius: 10,
                        background: "var(--surface)", boxShadow: "var(--shadow)", overflow: "hidden" }}>
            <div style={{ background: "var(--brand)", color: "#fff", padding: "7px 11px" }}>
              <div style={{ fontWeight: 700, fontSize: 13 }}>{t.tabla}</div>
              <div style={{ fontSize: 10, opacity: 0.9 }}>
                {t.origen ? `← ${t.origen.split("·")[0].split("(")[0].trim()}` : "sin origen legacy (la genera la app)"}
              </div>
            </div>
            <div>
              {t.columnas.map((c) => (
                <div key={c.nombre} style={{ display: "flex", gap: 8, alignItems: "baseline", justifyContent: "space-between",
                                             padding: "3px 11px", borderTop: "1px solid var(--border)", fontSize: 12 }}>
                  <span>
                    {c.pk && <b title="clave primaria" style={{ color: "var(--warn)" }}>🔑 </b>}
                    {c.fk && <span title={`FK → ${c.fk.tabla}`} style={{ color: "var(--brand)" }}>🔗 </span>}
                    {c.nombre}
                  </span>
                  <span className="muted" style={{ fontSize: 10.5 }}>
                    {c.fk && !nombres.has(c.fk.tabla) ? `→ ${c.fk.tabla}` : c.tipo}
                  </span>
                </div>
              ))}
            </div>
            <div style={{ borderTop: "1px solid var(--border)", padding: "6px 11px", fontSize: 10.5 }}>
              <div className="muted" style={{ fontWeight: 700, letterSpacing: ".04em" }}>USO EN MENÚ</div>
              {t.usos.length
                ? t.usos.map((u) => <div key={u.ruta} style={{ color: "var(--brand)" }}>· {u.label}</div>)
                : <div className="muted">— aún sin pantalla</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---------- DBFs legacy: cards de campos por migrador ---------- */
function LegacyCards({ items }: { items: Legacy[] }) {
  return (
    <div className="card">
      <div style={{ display: "flex", flexWrap: "wrap", gap: "18px", alignItems: "flex-start" }}>
        {items.map((m) => (
          <div key={m.clave} style={{ minWidth: 250, maxWidth: 320, border: "1px solid var(--border-strong)",
                                      borderRadius: 10, background: "var(--surface)", boxShadow: "var(--shadow)", overflow: "hidden" }}>
            <div style={{ background: "var(--ink-soft)", color: "#fff", padding: "7px 11px" }}>
              <div style={{ fontWeight: 700, fontSize: 13 }}>{m.dbf.split("·")[0].trim()}</div>
              <div style={{ fontSize: 10.5, opacity: 0.85 }}>→ {m.tabla_destino}</div>
            </div>
            <table style={{ margin: 0 }}>
              <tbody>
                {m.campos.map((c, i) => (
                  <tr key={i}>
                    <td style={{ textAlign: "left", fontSize: 11.5 }}><code>{c.origen}</code></td>
                    <td style={{ textAlign: "left", fontSize: 11.5 }} className="muted">{c.destino}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  );
}
