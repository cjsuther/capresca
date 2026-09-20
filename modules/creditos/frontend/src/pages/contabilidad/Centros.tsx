import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";
import { avisar } from "../../ui/dialog";

// Centros de costo (dimensión analítica). Se asignan a las líneas de asiento para analizar por área.
type Centro = { id: number; codigo: string; nombre: string; activo: boolean };

export default function Centros() {
  const [rows, setRows] = useState<Centro[]>([]);
  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState(false);
  const cargar = () => api.centrosCosto().then(setRows).catch((e) => setError(e.message || String(e)));
  useEffect(() => { cargar(); }, []);

  async function toggle(c: Centro) {
    try { await api.editarCentro(c.id, { codigo: c.codigo, nombre: c.nombre, activo: !c.activo }); cargar(); }
    catch (e: any) { avisar({ tipo: "error", mensaje: e.message || String(e) }); }
  }

  const cols: Col[] = [
    { key: "codigo", label: "Código", sortable: true, render: (c) => <span className="num"><b>{c.codigo}</b></span> },
    { key: "nombre", label: "Nombre", sortable: true },
    { key: "activo", label: "Estado", render: (c) => c.activo ? <span className="pill ok">Activo</span> : <span className="pill">Inactivo</span> },
  ];
  const acciones = (c: Centro) => [{ label: c.activo ? "Desactivar" : "Activar", icon: c.activo ? "ban" : "rotate-ccw", onClick: () => toggle(c) }];

  return (
    <div className="cco">
      <div className="cco-head">
        <div><h1 style={{ margin: 0 }}>Centros de costo</h1>
          <p className="muted" style={{ margin: "2px 0 0" }}>Dimensión analítica para las líneas de asiento (por área/negocio). {rows.length} centros.</p></div>
        <span style={{ flex: 1 }} />
        <button onClick={() => setNuevo(true)}>＋ Nuevo centro</button>
      </div>
      <div className="card" style={{ padding: "4px 14px 14px" }}>
        {error && <p className="error">{error}</p>}
        <DataTable columns={cols} rows={rows} rowKey={(c) => c.id} actions={acciones} clientSort pageSize={25} defaultSort="codigo" emptyText="Sin centros" />
      </div>
      {nuevo && <EditorCentro onClose={() => setNuevo(false)} onCreado={() => { setNuevo(false); cargar(); }} />}
      <style>{`
        .cco-head { display:flex; align-items:flex-start; gap:10px; margin-bottom:14px; flex-wrap:wrap; }
        .cco-ov { position:fixed; inset:0; background:rgba(16,24,40,.45); z-index:40; display:flex; align-items:center; justify-content:center; padding:16px; }
        .cco-modal { width:min(440px,96vw); background:var(--surface); border:1px solid var(--border); border-radius:14px; box-shadow:0 24px 70px -20px rgba(16,32,64,.55); }
        .cco-mh { display:flex; align-items:center; gap:10px; padding:14px 18px; border-bottom:1px solid var(--border); }
        .cco-mh h2 { margin:0; font-size:16px; } .cco-mh .x { margin-left:auto; width:32px; height:32px; border-radius:8px; border:1px solid var(--border); background:var(--surface); cursor:pointer; color:var(--ink-soft); font-size:16px; }
        .cco-body { padding:14px 18px; display:flex; flex-direction:column; gap:12px; }
        .cco-fld { display:flex; flex-direction:column; gap:4px; } .cco-fld label { font-size:11.5px; color:var(--ink-soft); font-weight:600; } .cco-fld input { margin:0; }
        .cco-mf { display:flex; gap:10px; align-items:center; padding:12px 18px; border-top:1px solid var(--border); background:var(--surface-2); }
      `}</style>
    </div>
  );
}

function EditorCentro({ onClose, onCreado }: { onClose: () => void; onCreado: () => void }) {
  const [codigo, setCodigo] = useState("");
  const [nombre, setNombre] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [err, setErr] = useState("");
  const puede = codigo.trim().length > 0 && nombre.trim().length > 0;
  async function guardar() {
    setErr(""); if (!puede) { setErr("Completá código y nombre."); return; } setGuardando(true);
    try { await api.crearCentro({ codigo: codigo.trim().toUpperCase(), nombre: nombre.trim(), activo: true }); onCreado(); }
    catch (e: any) { setErr(e.message || String(e)); } finally { setGuardando(false); }
  }
  return (
    <div className="cco-ov" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="cco-modal">
        <div className="cco-mh"><div><div className="eyebrow">Nuevo</div><h2>Centro de costo</h2></div>
          <button className="x" onClick={onClose} aria-label="Cerrar">✕</button></div>
        <div className="cco-body">
          <div className="cco-fld"><label>Código</label><input className="num" value={codigo} maxLength={12} onChange={(e) => setCodigo(e.target.value.toUpperCase())} placeholder="COM" /></div>
          <div className="cco-fld"><label>Nombre</label><input value={nombre} maxLength={60} onChange={(e) => setNombre(e.target.value)} placeholder="Comercial / Créditos" /></div>
          {err && <div className="alert crit">{err}</div>}
        </div>
        <div className="cco-mf"><span style={{ flex: 1 }} />
          <button className="btn-ghost" onClick={onClose}>Cancelar</button>
          <button className="btn primary" disabled={guardando || !puede} onClick={guardar}>{guardando ? "Creando…" : "Crear centro"}</button>
        </div>
      </div>
    </div>
  );
}
