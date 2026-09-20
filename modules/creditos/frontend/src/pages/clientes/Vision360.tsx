import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../api";

const money = (v: any) =>
  v == null ? "—" : Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const num = (v: any) => (v == null ? "—" : Number(v).toLocaleString("es-AR"));
const fmtCuil = (c: string) => (c && c.length === 11 ? `${c.slice(0, 2)}-${c.slice(2, 10)}-${c.slice(10)}` : c || "—");
const fmtDni = (d: string) => (d ? Number(d).toLocaleString("es-AR") : "—");
const iniciales = (n: string) => (n || "").replace(",", " ").trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "—";
const ESTADO_CR: Record<string, string> = { A: "Activo", C: "Cancelado", B: "Baja", S: "Suspendido" };
const pillCr = (e: string) => (e === "A" ? "ok" : e === "B" ? "crit" : "info");

export default function Vision360() {
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState("");
  const [resultados, setResultados] = useState<any[]>([]);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const cid = params.get("cliente");
    if (cid) abrir(Number(cid), false);
  }, []); // eslint-disable-line

  async function buscar(e?: React.FormEvent) {
    e?.preventDefault(); setError(""); setData(null);
    try {
      const r = await api.clientes({ q, limit: 12 });
      setResultados(r.items || []);
      if (!r.items?.length) setError("Sin clientes para la búsqueda.");
    } catch (err: any) { setError(err.message); }
  }
  async function abrir(id: number, sync = true) {
    setError(""); setResultados([]);
    try {
      setData(await api.vision360(id));
      if (sync) setParams({ cliente: String(id) }, { replace: true });
    } catch (err: any) { setError(err.message); }
  }

  const c = data?.cliente;
  const cr = data?.credito;

  return (
    <>
      {!data && (
        <div className="card">
          <h1 style={{ marginTop: 0 }}>Visión 360° del cliente</h1>
          <p className="muted">Todo lo que el sistema sabe del cliente en una sola vista, con acceso directo a cada detalle.</p>
          <form onSubmit={buscar} style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
            <div style={{ flex: 1 }}><label>Cliente (CUIL, DNI o apellido y nombre)</label>
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ej.: 20305891119 o MONTENEGRO" style={{ marginBottom: 0 }} /></div>
            <button type="submit">Buscar</button>
          </form>
          {error && <p className="error">{error}</p>}
          {resultados.length > 0 && (
            <table style={{ marginTop: "1rem" }}>
              <thead><tr><th>Apellido y nombre</th><th>CUIL</th><th>DNI</th><th></th></tr></thead>
              <tbody>
                {resultados.map((r) => (
                  <tr key={r.id}>
                    <td>{r.apellido_nombre}</td><td>{r.cuil}</td><td>{r.dni}</td>
                    <td style={{ textAlign: "right" }}><button onClick={() => abrir(r.id)}>Ver 360°</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {c && (
        <div className="v360">
          {/* HERO */}
          <section className="v360-hero">
            <div className="v360-av">{iniciales(c.apellido_nombre)}</div>
            <div className="v360-who">
              <div className="eyebrow">Ficha del cliente</div>
              <h1>{c.apellido_nombre}</h1>
              <div className="v360-meta">
                <span className="num">CUIL {fmtCuil(c.cuil)}</span><span className="dot">·</span>
                <span className="num">DNI {fmtDni(c.dni)}</span><span className="dot">·</span>
                {c.organismo && <><Link to={`/general/organismos?volver=${c.id}`}>{c.organismo} ↗</Link><span className="dot">·</span></>}
                <span className={`pill ${c.baja ? "crit" : "ok"}`}>{c.baja ? "Baja" : "Activo"}</span>
              </div>
            </div>
            <div className="v360-actions">
              <button className="btn-ghost" onClick={() => { setData(null); setResultados([]); }}>← Otro cliente</button>
            </div>
          </section>

          {/* KPIs */}
          <section className="v360-kpis">
            <div className="v360-kpi"><div className="l">Créditos activos</div><div className="v">{num(cr.creditos_activos)}</div></div>
            <div className={`v360-kpi ${Number(cr.saldo_total) > 0 ? "bad" : ""}`}><div className="l">Deuda de capital</div><div className="v">{money(cr.saldo_total)}</div></div>
            <div className="v360-kpi good"><div className="l">Margen disponible</div><div className="v">{money(cr.margen_disponible)}</div></div>
            <div className="v360-kpi"><div className="l">Pólizas vigentes</div><div className="v">{num(data.seguros.vigentes)}</div></div>
            <div className="v360-kpi"><div className="l">Egresos históricos</div><div className="v">{money(data.egresos?.total)}</div></div>
          </section>

          <div className="v360-grid">
            {/* IZQUIERDA */}
            <div className="v360-col">
              <section className="v360-card">
                <div className="head"><h2>Identidad y contacto</h2></div>
                <div className="v360-dl">
                  <div className="row"><span className="k">Domicilio</span><span className="val">{[c.domicilio, c.barrio].filter(Boolean).join(", ") || "—"}</span></div>
                  <div className="row"><span className="k">Localidad</span><span className="val">{c.localidad || "—"}</span></div>
                  <div className="row"><span className="k">Teléfono</span><span className="val">{c.telefono ? <a href={`tel:${c.telefono}`}>{c.telefono}</a> : "—"}</span></div>
                  <div className="row"><span className="k">Email</span><span className="val">{c.email ? <a href={`mailto:${c.email}`}>{c.email}</a> : "—"}</span></div>
                  <div className="row"><span className="k">Sueldo</span><span className="val num">{money(c.sueldo)}</span></div>
                  <div className="row"><span className="k">Función</span><span className="val">{c.categoria_funcion || "—"}</span></div>
                  <div className="row"><span className="k">CBU</span><span className="val num">{c.cbu || "—"}</span></div>
                  <div className="row"><span className="k">Débito automático</span><span className="val"><span className={`pill ${c.debito_automatico ? "ok" : "warn"}`}>{c.debito_automatico ? "Sí" : "No"}</span></span></div>
                  <div className="row"><span className="k">Ingreso</span><span className="val">{c.fecha_ingreso || "—"}</span></div>
                </div>
              </section>

              <section className="v360-card">
                <div className="head"><h2>Situación crediticia</h2></div>
                <div className="v360-margen">
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5 }}>
                    <span style={{ color: "var(--ink-soft)" }}>Afectación del haber</span>
                    <span className="num" style={{ fontWeight: 700 }}>{cr.afectacion_pct != null ? `${cr.afectacion_pct}%` : "—"} · {money(cr.total_afectado)}</span>
                  </div>
                  <div className="v360-bar"><i style={{ width: `${Math.min(100, cr.afectacion_pct || 0)}%` }} /></div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, color: "var(--ink-faint)" }}>
                    <span>Tope {cr.por_afecta ? `${cr.por_afecta}%` : "—"} del sueldo</span>
                    <span className="num">Margen: {money(cr.margen_disponible)}</span>
                  </div>
                </div>
                {data.seguros_ctacte?.cantidad > 0 && (
                  <div className="v360-foot">Cta. cte. de seguros: {num(data.seguros_ctacte.cantidad)} cargos · {money(data.seguros_ctacte.total)}</div>
                )}
              </section>
            </div>

            {/* DERECHA */}
            <div className="v360-col">
              {/* Créditos */}
              <section className="v360-card">
                <div className="head"><h2>Créditos</h2><span className="cnt">{num(cr.creditos_activos)} activos · {num(cr.creditos_total)} en total</span>
                  <Link className="all" to={`/creditos/listado`}>Ver todos →</Link></div>
                <div>
                  {cr.items.map((x: any) => (
                    <div className="v360-r" key={x.id}>
                      <div className="main">
                        <div className="t">N° {x.id} <span className={`pill ${pillCr(x.estado)}`}>{ESTADO_CR[x.estado] || x.estado}</span></div>
                        <div className="s">{x.linea || "—"}{x.cuotas_pendientes ? ` · ${x.cuotas_pendientes} cuotas pendientes` : ""}</div>
                        <div className="v360-sublinks">
                          <Link to={`/creditos/cuenta-corriente?credito=${x.id}&volver=${c.id}`}>Cuenta corriente ›</Link>
                          <Link to={`/contabilidad/ctacte-credito?no_credito=${x.id}&volver=${c.id}`}>Cta. cte. contable ›</Link>
                        </div>
                      </div>
                      <div className="amt num">{money(x.saldo_capital)}<span className="sub">saldo</span></div>
                    </div>
                  ))}
                  {!cr.items.length && <div className="v360-foot">Sin créditos registrados.</div>}
                </div>
              </section>

              {/* Seguros */}
              <section className="v360-card">
                <div className="head"><h2>Seguros de vida</h2><span className="cnt">{num(data.seguros.vigentes)} vigentes de {num(data.seguros.cantidad)}</span>
                  <Link className="all" to={`/seguros/polizas?q=${c.cuil}&volver=${c.id}`}>Ver en Seguros →</Link></div>
                <div>
                  {data.seguros.items.map((p: any, i: number) => (
                    <Link className="v360-r" key={i} to={`/seguros/polizas?q=${c.cuil}&volver=${c.id}`}>
                      <div className="main">
                        <div className="t">{p.no_poliza ? `Póliza ${p.no_poliza}` : "Póliza s/n°"} <span className={`pill ${p.vigente ? "ok" : "crit"}`}>{p.vigente ? "Vigente" : p.estado}</span></div>
                        <div className="s">{p.tipo} · alta {p.fecha_alta || "—"}</div>
                      </div>
                      <span className="chev" aria-hidden="true">›</span>
                    </Link>
                  ))}
                  {!data.seguros.items.length && <div className="v360-foot">Sin pólizas.</div>}
                </div>
              </section>

              {/* Egresos */}
              <section className="v360-card">
                <div className="head"><h2>Movimientos y egresos</h2><span className="cnt">{num(data.egresos?.cantidad)} · {money(data.egresos?.total)}</span>
                  <Link className="all" to={`/tesoreria/egresos?modo=cuil&valor=${c.cuil}&volver=${c.id}`}>Buscar egresos →</Link></div>
                <div>
                  {(data.egresos?.items ?? []).map((e: any, i: number) => (
                    <Link className="v360-r" key={i} to={`/tesoreria/egresos?modo=cuil&valor=${c.cuil}&volver=${c.id}`} style={e.anulado ? { opacity: 0.55 } : undefined}>
                      <div className="main">
                        <div className="t">Liquidación {e.no_liquida || "—"}</div>
                        <div className="s">{e.fecha || "—"}{e.nro_res ? ` · Resolución ${e.nro_res}` : ""}{e.no_credito ? ` · crédito ${e.no_credito}` : ""}</div>
                      </div>
                      <div className="amt num">{money(e.total)}</div>
                      <span className="chev" aria-hidden="true">›</span>
                    </Link>
                  ))}
                  {!(data.egresos?.items?.length) && <div className="v360-foot">Sin egresos.</div>}
                </div>
              </section>

              {/* Trámites */}
              {data.tramites.cantidad > 0 && (
                <section className="v360-card">
                  <div className="head"><h2>Trámites en mesa de entradas</h2><span className="cnt">{num(data.tramites.cantidad)}</span>
                    <Link className="all" to={`/mesa/tramites?q=${c.dni || c.cuil}&volver=${c.id}`}>Ver en Mesa →</Link></div>
                  <div>
                    {data.tramites.items.map((t: any, i: number) => (
                      <Link className="v360-r" key={i} to={`/mesa/tramites?q=${c.dni || c.cuil}&volver=${c.id}`}>
                        <div className="main">
                          <div className="t">{t.numero || t.expediente || t.id || "Trámite"}</div>
                          <div className="s">{t.tipo || t.caratula || "—"}{t.oficina_actual ? ` · ${t.oficina_actual}` : ""}</div>
                        </div>
                        <span className="chev" aria-hidden="true">›</span>
                      </Link>
                    ))}
                  </div>
                </section>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
