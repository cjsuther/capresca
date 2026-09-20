import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";
import { confirmar, avisar } from "../../ui/dialog";

// Ejercicios contables (períodos fiscales). Abierto/cerrado; al cerrar se genera el asiento de cierre
// (refundición de resultados en 'Resultado del ejercicio') y se bloquea la carga de asientos del período.

const money = (v: any) => Number(v || 0).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const fecha = (s?: string | null) => (s ? new Date(s + "T00:00:00").toLocaleDateString("es-AR") : "—");
const hoy = () => new Date().toISOString().slice(0, 10);

export default function Ejercicios() {
  const [rows, setRows] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState(false);

  const cargar = () => api.ejercicios().then(setRows).catch((e) => setError(e.message || String(e)));
  useEffect(() => { cargar(); }, []);

  async function cerrar(e: any) {
    if (!(await confirmar({ titulo: "Cerrar ejercicio", confirmar: "Cerrar", danger: true, mensaje: `Cerrar "${e.nombre}" (${fecha(e.fecha_desde)}–${fecha(e.fecha_hasta)}). Se genera el asiento de cierre (refunde resultados en "Resultado del ejercicio") y se BLOQUEA la carga de asientos del período. ¿Continuar?` }))) return;
    try { const r = await api.cerrarEjercicio(e.id); cargar(); avisar(`Ejercicio cerrado. Resultado: ${money(r.resultado)} (${Number(r.resultado) >= 0 ? "ganancia" : "pérdida"}).`); }
    catch (ex: any) { avisar({ tipo: "error", mensaje: ex.message || String(ex) }); }
  }
  async function reabrir(e: any) {
    if (!(await confirmar({ titulo: "Reabrir ejercicio", confirmar: "Reabrir", mensaje: `Reabrir "${e.nombre}". Se elimina el asiento de cierre y se libera el período. ¿Continuar?` }))) return;
    try { await api.reabrirEjercicio(e.id); cargar(); avisar("Ejercicio reabierto."); }
    catch (ex: any) { avisar({ tipo: "error", mensaje: ex.message || String(ex) }); }
  }
  async function apertura(e: any) {
    if (!(await confirmar({ titulo: "Generar apertura", confirmar: "Generar", mensaje: `Genera el asiento de apertura de "${e.nombre}" con los saldos patrimoniales al inicio (del período anterior). ¿Continuar?` }))) return;
    try { await api.aperturaEjercicio(e.id); cargar(); avisar("Asiento de apertura generado."); }
    catch (ex: any) { avisar({ tipo: "error", mensaje: ex.message || String(ex) }); }
  }

  const cols: Col[] = [
    { key: "nombre", label: "Ejercicio", sortable: true, render: (e) => <b>{e.nombre}</b> },
    { key: "fecha_desde", label: "Desde", sortable: true, render: (e) => fecha(e.fecha_desde) },
    { key: "fecha_hasta", label: "Hasta", sortable: true, render: (e) => fecha(e.fecha_hasta) },
    { key: "estado", label: "Estado", render: (e) => e.estado === "cerrado" ? <span className="pill crit">Cerrado</span> : <span className="pill ok">Abierto</span> },
    { key: "resultado", label: "Resultado", align: "right", render: (e) => e.estado === "cerrado" ? <span className="num" style={{ color: Number(e.resultado) >= 0 ? "var(--ok)" : "var(--crit)" }}>{money(e.resultado)}</span> : "—" },
  ];
  const acciones = (e: any) => [
    ...(e.estado === "abierto" ? [
      { label: "Generar apertura", icon: "rotate-ccw", onClick: () => apertura(e), hidden: !!e.asiento_apertura_id },
      { label: "Cerrar ejercicio", icon: "check", danger: true, onClick: () => cerrar(e) },
    ] : [
      { label: "Reabrir ejercicio", icon: "edit", onClick: () => reabrir(e) },
    ]),
  ];

  return (
    <div className="ejc">
      <div className="ejc-head">
        <div>
          <h1 style={{ margin: 0 }}>Ejercicios contables</h1>
          <p className="muted" style={{ margin: "2px 0 0" }}>Períodos fiscales con apertura/cierre. Al cerrar se refunden los resultados y se bloquea la carga de asientos del período. {rows.length} ejercicios.</p>
        </div>
        <span style={{ flex: 1 }} />
        <button onClick={() => setNuevo(true)}>＋ Nuevo ejercicio</button>
      </div>

      <div className="card" style={{ padding: "4px 14px 14px" }}>
        {error && <p className="error">{error}</p>}
        <DataTable columns={cols} rows={rows} rowKey={(e) => e.id} actions={acciones}
                   clientSort pageSize={25} defaultSort="fecha_desde" emptyText="Sin ejercicios" />
      </div>

      {nuevo && <EditorEjercicio onClose={() => setNuevo(false)} onCreado={() => { setNuevo(false); cargar(); }} />}

      <style>{`
        .ejc-head { display:flex; align-items:flex-start; gap:10px; margin-bottom:14px; flex-wrap:wrap; }
        .ejc-ov { position:fixed; inset:0; background:rgba(16,24,40,.45); z-index:40; display:flex; align-items:center; justify-content:center; padding:16px; }
        .ejc-modal { width:min(460px,96vw); background:var(--surface); border:1px solid var(--border); border-radius:14px; box-shadow:0 24px 70px -20px rgba(16,32,64,.55); }
        .ejc-mh { display:flex; align-items:center; gap:10px; padding:14px 18px; border-bottom:1px solid var(--border); }
        .ejc-mh h2 { margin:0; font-size:16px; } .ejc-mh .x { margin-left:auto; width:32px; height:32px; border-radius:8px; border:1px solid var(--border); background:var(--surface); cursor:pointer; color:var(--ink-soft); font-size:16px; }
        .ejc-body { padding:14px 18px; display:flex; flex-direction:column; gap:12px; }
        .ejc-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
        .ejc-fld { display:flex; flex-direction:column; gap:4px; } .ejc-fld.col2 { grid-column:span 2; }
        .ejc-fld label { font-size:11.5px; color:var(--ink-soft); font-weight:600; }
        .ejc-fld input { margin:0; }
        .ejc-mf { display:flex; gap:10px; align-items:center; padding:12px 18px; border-top:1px solid var(--border); background:var(--surface-2); }
      `}</style>
    </div>
  );
}

function EditorEjercicio({ onClose, onCreado }: { onClose: () => void; onCreado: () => void }) {
  const y = new Date().getFullYear();
  const [nombre, setNombre] = useState(`Ejercicio ${y}`);
  const [desde, setDesde] = useState(`${y}-01-01`);
  const [hasta, setHasta] = useState(`${y}-12-31`);
  const [guardando, setGuardando] = useState(false);
  const [err, setErr] = useState("");
  const puede = !!nombre.trim() && !!desde && !!hasta && hasta >= desde;

  async function guardar() {
    setErr("");
    if (!puede) { setErr("Completá nombre y un rango de fechas válido."); return; }
    setGuardando(true);
    try { await api.crearEjercicio({ nombre: nombre.trim(), fecha_desde: desde, fecha_hasta: hasta }); onCreado(); }
    catch (e: any) { setErr(e.message || String(e)); }
    finally { setGuardando(false); }
  }

  return (
    <div className="ejc-ov" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="ejc-modal">
        <div className="ejc-mh"><div><div className="eyebrow">Nuevo</div><h2>Ejercicio contable</h2></div>
          <button className="x" onClick={onClose} aria-label="Cerrar">✕</button></div>
        <div className="ejc-body">
          <div className="ejc-fld"><label>Nombre</label><input value={nombre} maxLength={40} onChange={(e) => setNombre(e.target.value)} placeholder="Ejercicio 2026" /></div>
          <div className="ejc-grid">
            <div className="ejc-fld"><label>Desde</label><input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} /></div>
            <div className="ejc-fld"><label>Hasta</label><input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></div>
          </div>
          {err && <div className="alert crit">{err}</div>}
        </div>
        <div className="ejc-mf"><span style={{ flex: 1 }} />
          <button className="btn-ghost" onClick={onClose}>Cancelar</button>
          <button className="btn primary" disabled={guardando || !puede} onClick={guardar}>{guardando ? "Creando…" : "Crear ejercicio"}</button>
        </div>
      </div>
    </div>
  );
}
