import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const LIMIT = 25;
const dt = (v: string | null) => (v ? new Date(v).toLocaleString("es-AR") : "—");

// Rastro de auditoría del sistema NUEVO: quién cambió qué, con antes/después + IP.
// Complementa el log VFP migrado (Seguridad → Auditoría), que sólo guarda el hecho.

const OPERACIONES = ["", "ALTA", "ORIGINAR", "PAGAR", "COBRAR", "APROBAR", "RECHAZAR", "BAJA", "ANULAR"];
const RESULTADOS = ["", "OK", "RECHAZADO", "ERROR"];
const pillResultado = (r: string) =>
  r === "OK" ? "ok" : r === "ERROR" ? "crit" : "warn";

export default function AuditoriaCambios() {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [texto, setTexto] = useState("");
  const [busq, setBusq] = useState("");
  const [operacion, setOperacion] = useState("");
  const [resultado, setResultado] = useState("");
  const [detalle, setDetalle] = useState<any>(null);
  const [err, setErr] = useState("");

  async function cargar(off: number) {
    try {
      const d = await api.auditoriaCambios({ texto: busq, operacion, resultado, limit: LIMIT, offset: off });
      setItems(d.items); setTotal(d.total); setOffset(off); setErr("");
    } catch (e) { setErr(String(e)); }
  }
  useEffect(() => { cargar(0); /* eslint-disable-next-line */ }, [busq, operacion, resultado]);

  const cols: Col[] = [
    { key: "fecha_hora", label: "Fecha/hora", render: (e) => dt(e.fecha_hora) },
    { key: "usuario", label: "Usuario", render: (e) => <span>{e.usuario}{e.perfil ? <span className="muted"> · {e.perfil}</span> : null}</span> },
    { key: "ip", label: "IP", render: (e) => <code className="audc-ip">{e.ip || "—"}</code> },
    { key: "entidad", label: "Entidad", render: (e) => <span>{e.entidad}{e.entidad_id ? <span className="muted"> #{e.entidad_id}</span> : null}</span> },
    { key: "operacion", label: "Operación", render: (e) => <span className="pill brand">{e.operacion}</span> },
    { key: "resultado", label: "Resultado", render: (e) => <span className={`pill ${pillResultado(e.resultado)}`}>{e.resultado}</span> },
    { key: "detalle", label: "Detalle" },
  ];

  async function verDetalle(id: number) {
    try { setDetalle(await api.auditoriaCambioDetalle(id)); }
    catch (e) { setErr(String(e)); }
  }

  return (
    <div className="audc">
      <div className="audc-head">
        <h1>Auditoría de cambios</h1>
        <p className="muted">Rastro de las mutaciones del sistema nuevo — quién cambió qué, desde qué IP,
          con el estado <b>antes</b> y <b>después</b>. Distinto del log histórico migrado del VFP
          (<i>Seguridad → Auditoría</i>), que registra sólo el hecho.</p>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div className="audc-toolbar">
          <form onSubmit={(e) => { e.preventDefault(); setBusq(texto); }} className="audc-search">
            <input value={texto} onChange={(e) => setTexto(e.target.value)}
                   placeholder="Buscar usuario, entidad, id, detalle…" />
            <button type="submit">Buscar</button>
          </form>
          <label className="audc-fld"><span>Operación</span>
            <select value={operacion} onChange={(e) => setOperacion(e.target.value)}>
              {OPERACIONES.map((o) => <option key={o} value={o}>{o || "Todas"}</option>)}
            </select></label>
          <label className="audc-fld"><span>Resultado</span>
            <select value={resultado} onChange={(e) => setResultado(e.target.value)}>
              {RESULTADOS.map((r) => <option key={r} value={r}>{r || "Todos"}</option>)}
            </select></label>
        </div>
        {err && <div className="alert crit" style={{ margin: 12 }}>{err}</div>}
        <DataTable columns={cols} rows={items} total={total} limit={LIMIT} offset={offset}
                   onPage={cargar} emptyText="Sin cambios registrados"
                   actions={(e) => [{ label: "Ver diff", onClick: () => verDetalle(e.id) }]} />
      </div>

      {detalle && (
        <div className="audc-overlay" onClick={() => setDetalle(null)}>
          <div className="audc-modal" onClick={(e) => e.stopPropagation()}>
            <div className="audc-modal-head">
              <span className="pill brand">{detalle.operacion}</span>
              <span className={`pill ${pillResultado(detalle.resultado)}`}>{detalle.resultado}</span>
              <b>{detalle.entidad}{detalle.entidad_id ? ` #${detalle.entidad_id}` : ""}</b>
              <button className="audc-x" onClick={() => setDetalle(null)}>✕</button>
            </div>
            <div className="audc-modal-body">
              <div className="audc-meta">
                <div><span>Fecha/hora</span> {dt(detalle.fecha_hora)}</div>
                <div><span>Usuario</span> {detalle.usuario}{detalle.perfil ? ` · ${detalle.perfil}` : ""}</div>
                <div><span>IP</span> <code className="audc-ip">{detalle.ip || "—"}</code></div>
              </div>
              {detalle.detalle && <p className="audc-detalle">{detalle.detalle}</p>}

              {detalle.cambios && Object.keys(detalle.cambios).length > 0 && (
                <div>
                  <div className="audc-lbl">Cambios</div>
                  <div className="audc-diff">
                    {Object.entries(detalle.cambios).map(([campo, par]: any) => (
                      <div className="audc-diff-row" key={campo}>
                        <code className="audc-campo">{campo}</code>
                        <span className="audc-antes">{JSON.stringify(par[0]) ?? "—"}</span>
                        <span className="audc-flecha">→</span>
                        <span className="audc-despues">{JSON.stringify(par[1]) ?? "—"}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="audc-json2">
                <div>
                  <div className="audc-lbl">Antes</div>
                  <pre className="audc-json">{detalle.datos_anteriores ? JSON.stringify(detalle.datos_anteriores, null, 2) : "—"}</pre>
                </div>
                <div>
                  <div className="audc-lbl">Después</div>
                  <pre className="audc-json">{detalle.datos_nuevos ? JSON.stringify(detalle.datos_nuevos, null, 2) : "—"}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .audc { max-width: 1100px; }
        .audc-head h1 { margin: 0 0 4px; }
        .audc-head p { max-width: 78ch; line-height: 1.5; margin: 0 0 16px; }
        .audc-toolbar { display: flex; gap: 14px; align-items: end; flex-wrap: wrap; padding: 12px 14px; border-bottom: 1px solid var(--border); }
        .audc-search { display: flex; gap: 8px; flex: 1; min-width: 260px; }
        .audc-search input { margin: 0; flex: 1; }
        .audc-fld { display: flex; flex-direction: column; gap: 4px; font-size: .8rem; }
        .audc-fld span { color: var(--ink-soft); text-transform: uppercase; font-size: .66rem; letter-spacing: .3px; }
        .audc-fld select { margin: 0; }
        .audc-ip { font-family: var(--font-mono, monospace); font-size: .78rem; color: var(--ink-soft); }
        .audc-link { background: transparent; border: 1px solid var(--border); border-radius: 7px; padding: 3px 10px; font-size: .8rem; cursor: pointer; color: var(--brand-2); }
        .audc-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.55); display: flex; align-items: center; justify-content: center; z-index: 1000; }
        .audc-modal { background: var(--surface); color: var(--ink); border: 1px solid var(--border); border-radius: 12px; width: min(860px, 95vw); max-height: 90vh; overflow: auto; box-shadow: 0 12px 40px rgba(0,0,0,.4); }
        .audc-modal-head { display: flex; align-items: center; gap: 8px; padding: 14px 18px; border-bottom: 1px solid var(--border); position: sticky; top: 0; background: var(--surface); }
        .audc-x { margin-left: auto; background: transparent; border: none; font-size: 1.1rem; cursor: pointer; color: var(--ink-soft); }
        .audc-modal-body { padding: 16px 18px; display: flex; flex-direction: column; gap: 16px; }
        .audc-meta { display: flex; gap: 24px; flex-wrap: wrap; font-size: .85rem; }
        .audc-meta span { display: block; color: var(--ink-faint); text-transform: uppercase; font-size: .64rem; letter-spacing: .3px; }
        .audc-detalle { margin: 0; padding: 10px 12px; background: var(--surface-2); border-radius: 8px; font-size: .88rem; }
        .audc-lbl { font-size: .68rem; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; color: var(--ink-faint); margin-bottom: 6px; }
        .audc-diff { display: flex; flex-direction: column; gap: 4px; }
        .audc-diff-row { display: grid; grid-template-columns: minmax(120px, 1fr) 2fr auto 2fr; gap: 8px; align-items: center; font-size: .82rem; padding: 4px 8px; border-radius: 6px; background: var(--surface-2); }
        .audc-campo { font-family: var(--font-mono, monospace); color: var(--ink); }
        .audc-antes { color: var(--crit); overflow-wrap: anywhere; }
        .audc-despues { color: var(--ok); overflow-wrap: anywhere; }
        .audc-flecha { color: var(--ink-faint); }
        .audc-json2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
        .audc-json { margin: 0; padding: 10px 12px; background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; font-size: .76rem; line-height: 1.45; overflow: auto; max-height: 320px; }
        @media (max-width: 700px) { .audc-json2 { grid-template-columns: 1fr; } .audc-diff-row { grid-template-columns: 1fr; } }
      `}</style>
    </div>
  );
}
