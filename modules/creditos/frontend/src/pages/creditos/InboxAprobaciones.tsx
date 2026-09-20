import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import Icon from "../../components/Icon";
import { avisar, pedirTexto } from "../../ui/dialog";

// Inbox = cuadro de control: primero se ven las AGRUPACIONES (por tipo) con su cantidad; al entrar en una,
// se ve la lista de lo que hay que aprobar/resolver de ese grupo.
type Tarea = {
  tipo: string; id: string; titulo: string; estado: string; accion: string;
  solicitante: string; fecha: string; detalle: string; ruta: string;
  deepLink?: { clave: string; valor: string };
};

// Grupos conocidos (orden + presentación). Los tipos no listados se agrupan como "Otros".
const GRUPOS: { tipo: string; label: string; icon: string; desc: string }[] = [
  { tipo: "SOLICITUD", label: "Solicitudes de crédito", icon: "file-text", desc: "Solicitudes que esperan evaluación / aprobación." },
  { tipo: "LINEA", label: "Líneas de crédito", icon: "creditos", desc: "Publicación de líneas (Configurar Créditos)." },
  { tipo: "DESEMBOLSO", label: "Desembolsos", icon: "banknote", desc: "Liquidaciones y desembolsos por aprobar." },
  { tipo: "REFINANCIACION", label: "Refinanciaciones", icon: "refresh", desc: "Refinanciaciones por aprobar." },
];
const ACCION_LBL: Record<string, string> = { aprobar: "Aprobar", publicar: "Publicar", resolver: "Resolver" };

export default function InboxAprobaciones() {
  const nav = useNavigate();
  const [items, setItems] = useState<Tarea[]>([]);
  const [err, setErr] = useState("");
  const [cargando, setCargando] = useState(true);
  const [grupoSel, setGrupoSel] = useState<string | null>(null);   // null = panel de agrupaciones

  const cargar = async () => {
    setErr(""); setCargando(true);
    try { setItems((await api.inboxAprobaciones()).items); }
    catch (e: any) { setErr(e.message || String(e)); }
    finally { setCargando(false); }
  };
  useEffect(() => { cargar(); }, []);

  // agrupaciones con cantidad (incluye un cajón "Otros" para tipos desconocidos)
  const grupos = useMemo(() => {
    const conteo: Record<string, number> = {};
    for (const t of items) conteo[t.tipo] = (conteo[t.tipo] || 0) + 1;
    const base = GRUPOS.map((g) => ({ ...g, count: conteo[g.tipo] || 0 }));
    const otros = items.filter((t) => !GRUPOS.some((g) => g.tipo === t.tipo));
    if (otros.length) base.push({ tipo: "__OTROS__", label: "Otros", icon: "package", desc: "Otras tareas pendientes.", count: otros.length });
    return base;
  }, [items]);

  const itemsGrupo = useMemo(() => {
    if (!grupoSel) return [];
    if (grupoSel === "__OTROS__") return items.filter((t) => !GRUPOS.some((g) => g.tipo === t.tipo));
    return items.filter((t) => t.tipo === grupoSel);
  }, [items, grupoSel]);
  const grupoActual = grupos.find((g) => g.tipo === grupoSel);

  function abrir(t: Tarea) {
    if (t.deepLink) sessionStorage.setItem(t.deepLink.clave, t.deepLink.valor);
    nav(t.ruta);
  }
  async function aprobarInline(t: Tarea) {
    try {
      const r = await api.inboxAprobarPendiente(t.id);
      avisar(r.ejecutado ? "Aprobado y ejecutado." : `Aprobado. Falta${r.faltan === 1 ? "" : "n"} ${r.faltan} nivel(es).`);
      cargar();
    } catch (e: any) { avisar({ tipo: "error", mensaje: e.message || String(e) }); }
  }
  async function rechazarInline(t: Tarea) {
    const motivo = (await pedirTexto({ titulo: "Rechazar", mensaje: "Motivo del rechazo:" })) || "";
    try { await api.inboxRechazarPendiente(t.id, motivo); cargar(); }
    catch (e: any) { avisar({ tipo: "error", mensaje: e.message || String(e) }); }
  }

  return (
    <div className="inbx">
      <div className="inbx-head">
        <span className="inbx-ic"><Icon name="inbox" size={22} /></span>
        <div>
          <h1 style={{ margin: 0 }}>Inbox</h1>
          <p className="muted" style={{ margin: "2px 0 0" }}>
            {grupoSel ? grupoActual?.desc : "Tu cuadro de control: elegí una agrupación para ver lo pendiente."}
            {" "}Cuatro-ojos: no ves lo que vos mismo enviaste.
          </p>
        </div>
        <span style={{ flex: 1 }} />
        <span className="inbx-count">{items.length} pendiente{items.length === 1 ? "" : "s"}</span>
        <button className="btn sm" onClick={cargar} disabled={cargando}>{cargando ? "…" : "↻ Refrescar"}</button>
      </div>
      {err && <div className="alert crit">{err}</div>}

      {!cargando && items.length === 0 && (
        <div className="inbx-empty">✓ No tenés tareas pendientes.</div>
      )}

      {/* ── Panel de agrupaciones (cuadro de control) ── */}
      {!grupoSel && items.length > 0 && (
        <div className="inbx-panel">
          {grupos.map((g) => (
            <button key={g.tipo} className={`inbx-gcard ${g.count ? "" : "vacio"}`} disabled={!g.count}
              onClick={() => g.count && setGrupoSel(g.tipo)}>
              <span className="inbx-gicon"><Icon name={g.icon} size={22} /></span>
              <span className="inbx-gnum">{g.count}</span>
              <span className="inbx-glabel">{g.label}</span>
              <span className="inbx-gdesc">{g.desc}</span>
              {g.count > 0 && <span className="inbx-genter">Ver {g.count} →</span>}
            </button>
          ))}
        </div>
      )}

      {/* ── Lista del grupo seleccionado ── */}
      {grupoSel && (
        <>
          <div className="inbx-sub">
            <button className="btn sm ghost" onClick={() => setGrupoSel(null)}>← Panel</button>
            {grupoActual && <span className="inbx-subic"><Icon name={grupoActual.icon} size={16} /></span>}
            <b>{grupoActual?.label}</b>
            <span className="inbx-count">{itemsGrupo.length}</span>
          </div>
          <div className="inbx-list">
            {itemsGrupo.map((t) => (
              <div className="inbx-card" key={`${t.tipo}-${t.id}-${t.estado}`}>
                <div className="inbx-body">
                  <b className="inbx-titulo">{t.titulo}</b>
                  <div className="inbx-detalle">{t.detalle}</div>
                  <div className="inbx-meta">
                    <span title="Quién lo pidió">👤 Pedido por <b>{t.solicitante}</b></span>
                    {t.fecha && <span>· {t.fecha}</span>}
                    <span className="inbx-estado">{t.estado}</span>
                  </div>
                </div>
                {t.accion === "aprobar-inline" ? (
                  <div style={{ display: "flex", gap: 6 }}>
                    <button className="btn sm" style={{ color: "var(--crit)", borderColor: "var(--crit)" }} onClick={() => rechazarInline(t)}>Rechazar</button>
                    <button className="btn primary sm" onClick={() => aprobarInline(t)}>Aprobar</button>
                  </div>
                ) : (
                  <button className="btn primary sm" onClick={() => abrir(t)}>{ACCION_LBL[t.accion] || t.accion} →</button>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      <style>{`
        .inbx-head { display:flex; align-items:center; gap:12px; margin-bottom:18px; flex-wrap:wrap; }
        .inbx-ic { flex:none; width:42px; height:42px; border-radius:12px; display:grid; place-items:center;
          background:var(--brand-soft, var(--surface-2)); color:var(--brand-2); }
        .inbx-count { font-size:.72rem; text-transform:uppercase; letter-spacing:.4px; color:var(--ink-soft);
          border:1px solid var(--border); border-radius:999px; padding:3px 10px; }
        .inbx-empty { background:var(--surface); border:1px solid var(--border); border-radius:12px;
          padding:36px; text-align:center; color:var(--ink-soft); font-size:1rem; }
        .inbx-panel { display:grid; grid-template-columns:repeat(auto-fill, minmax(230px, 1fr)); gap:14px; }
        .inbx-gcard { position:relative; text-align:left; display:grid; gap:2px; background:var(--surface);
          border:1px solid var(--border); border-radius:14px; padding:16px 18px 18px; cursor:pointer;
          box-shadow:0 1px 2px rgba(16,32,64,.05); transition:border-color .12s, box-shadow .12s, transform .06s; }
        .inbx-gcard:hover:not(.vacio) { border-color:var(--brand-2); box-shadow:0 10px 28px -16px rgba(16,32,64,.4); }
        .inbx-gcard:active:not(.vacio) { transform:translateY(1px); }
        .inbx-gcard.vacio { opacity:.5; cursor:default; }
        .inbx-gicon { width:44px; height:44px; border-radius:12px; display:grid; place-items:center;
          background:var(--brand-soft, var(--surface-2)); color:var(--brand-2); }
        .inbx-gcard.vacio .inbx-gicon { background:var(--surface-2); color:var(--ink-faint); }
        .inbx-gnum { position:absolute; top:16px; right:18px; font-size:1.6rem; font-weight:800; font-variant-numeric:tabular-nums;
          color:var(--brand-2); }
        .inbx-subic { display:inline-grid; place-items:center; width:28px; height:28px; border-radius:8px;
          background:var(--brand-soft, var(--surface-2)); color:var(--brand-2); }
        .inbx-gcard.vacio .inbx-gnum { color:var(--ink-faint); }
        .inbx-glabel { font-size:1rem; font-weight:700; margin-top:8px; }
        .inbx-gdesc { font-size:.8rem; color:var(--ink-soft); }
        .inbx-genter { font-size:.78rem; font-weight:700; color:var(--brand-2); margin-top:8px; }
        .inbx-sub { display:flex; align-items:center; gap:12px; margin-bottom:12px; font-size:1rem; }
        .inbx-sub .inbx-count { margin-left:auto; }
        .inbx-list { display:flex; flex-direction:column; gap:10px; }
        .inbx-card { display:flex; align-items:center; gap:14px; background:var(--surface); border:1px solid var(--border);
          border-radius:12px; padding:12px 16px; }
        .inbx-body { flex:1; min-width:0; }
        .inbx-titulo { font-size:.95rem; }
        .inbx-detalle { color:var(--ink-soft); font-size:.85rem; margin-top:2px; }
        .inbx-meta { display:flex; gap:8px; flex-wrap:wrap; align-items:center; font-size:.78rem; color:var(--ink-faint); margin-top:5px; }
        .inbx-estado { border:1px solid var(--border); border-radius:999px; padding:1px 8px; color:var(--ink-soft); }
      `}</style>
    </div>
  );
}
