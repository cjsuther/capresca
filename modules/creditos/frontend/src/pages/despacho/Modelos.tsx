import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";
import RichText from "../../components/RichText";
import { avisar } from "../../ui/dialog";

type Modelo = { id: number; codigo: number; descripcion: string; tipo: string; seguros: boolean; tiene_plantilla: boolean };

const COLS: Col[] = [
  { key: "codigo", label: "Código", sortable: true, align: "right", render: (m) => <span className="num">{m.codigo}</span> },
  { key: "descripcion", label: "Descripción", sortable: true },
  { key: "tipo", label: "Tipo", sortable: true, render: (m) => <span className="pill brand">{m.tipo}</span> },
  { key: "seguros", label: "Seguros", sortable: true, render: (m) => (m.seguros ? "Sí" : "—") },
  { key: "tiene_plantilla", label: "Plantilla", sortable: true, render: (m) => (m.tiene_plantilla ? "Sí" : "—") },
];

export default function Modelos() {
  const [rows, setRows] = useState<Modelo[]>([]);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [editor, setEditor] = useState<null | { id?: number }>(null);   // {id} = editar; {} = nuevo

  const cargar = () => api.modelosResolucion().then(setRows).catch((e) => setError(e.message || String(e)));
  useEffect(() => { cargar(); }, []);

  const filtradas = rows.filter((m) => !q || m.descripcion.toLowerCase().includes(q.toLowerCase()) || String(m.codigo).includes(q));

  return (
    <div className="mdl">
      <div className="mdl-head">
        <div>
          <h1 style={{ margin: 0 }}>Modelos de resoluciones / disposiciones</h1>
          <p className="muted" style={{ margin: "2px 0 0" }}>Plantillas base para generar resoluciones (editor tipo Word). {rows.length} modelos.</p>
        </div>
        <span style={{ flex: 1 }} />
        <button onClick={() => setEditor({})}>＋ Nuevo modelo</button>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div className="mdl-toolbar">
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por descripción o código…" style={{ marginBottom: 0, flex: 1, minWidth: 220 }} />
          {q && <button className="btn-ghost" onClick={() => setQ("")}>Limpiar</button>}
        </div>
        {error && <p className="error" style={{ margin: "10px 14px" }}>{error}</p>}
        <div style={{ padding: "4px 14px 14px" }}>
          <DataTable columns={COLS} rows={filtradas} rowKey={(m) => m.id}
                     actions={(m) => [{ label: "Editar plantilla", icon: "edit", onClick: () => setEditor({ id: m.id }) }]}
                     clientSort pageSize={25} defaultSort="descripcion" emptyText="Sin modelos" />
        </div>
      </div>

      {editor && <EditorModelo id={editor.id} onClose={() => setEditor(null)}
                   onGuardado={() => { setEditor(null); cargar(); }} />}
    </div>
  );
}

function EditorModelo({ id, onClose, onGuardado }: { id?: number; onClose: () => void; onGuardado: () => void }) {
  const [descripcion, setDescripcion] = useState("");
  const [tipo, setTipo] = useState("RES");
  const [seguros, setSeguros] = useState(false);
  const [plantilla, setPlantilla] = useState("");
  const [cargando, setCargando] = useState(!!id);
  const [guardando, setGuardando] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!id) return;
    api.modeloResolucion(id).then((m) => {
      setDescripcion(m.descripcion || ""); setTipo(m.tipo === "Disposición" ? "DIS" : "RES");
      setSeguros(!!m.es_seguros); setPlantilla(m.plantilla || "");
    }).catch((e) => setErr(e.message || String(e))).finally(() => setCargando(false));
  }, [id]);

  const puede = descripcion.trim().length > 0;

  async function guardar() {
    setErr("");
    if (!puede) { setErr("La descripción es obligatoria."); return; }
    setGuardando(true);
    const payload = { descripcion: descripcion.trim(), tipo, seguros, plantilla };
    try {
      if (id) await api.editarModeloResolucion(id, payload);
      else await api.crearModeloResolucion(payload);
      onGuardado();
    } catch (e: any) { setErr(e.message || String(e)); }
    finally { setGuardando(false); }
  }

  return (
    <div className="mdl-ov" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="mdl-modal">
        <div className="mdl-mh">
          <div><div className="eyebrow">{id ? "Editar" : "Nuevo"} modelo</div>
            <h2>{id ? descripcion || "Modelo de resolución" : "Modelo de resolución"}</h2></div>
          <button className="x" onClick={onClose} aria-label="Cerrar">✕</button>
        </div>
        <div className="mdl-body">
          {cargando ? <p className="muted">Cargando…</p> : (
            <>
              <div className="mdl-grid">
                <div className="mdl-fld col2"><label>Descripción <span className="req">*</span></label>
                  <input value={descripcion} maxLength={120} onChange={(e) => setDescripcion(e.target.value)}
                         placeholder="ej. TRANSFERENCIA / ACTA VOLANTE" /></div>
                <div className="mdl-fld"><label>Tipo</label>
                  <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
                    <option value="RES">Resolución</option><option value="DIS">Disposición</option></select></div>
                <div className="mdl-fld"><label>&nbsp;</label>
                  <label className="mdl-chk"><input type="checkbox" checked={seguros} onChange={(e) => setSeguros(e.target.checked)} /> Es de seguros</label></div>
              </div>
              <div className="mdl-sect">Plantilla (texto base del instrumento)</div>
              <RichText value={plantilla} onChange={setPlantilla}
                        placeholder="Cuerpo base que se copiará al elegir este modelo en una resolución." />
              {err && <div className="alert crit" style={{ marginTop: 12 }}>{err}</div>}
            </>
          )}
        </div>
        <div className="mdl-mf">
          <span style={{ flex: 1 }} />
          <button className="btn-ghost" onClick={onClose}>Cancelar</button>
          <button disabled={guardando || cargando || !puede} onClick={guardar}>{guardando ? "Guardando…" : "Guardar"}</button>
        </div>
      </div>
      <style>{`
        .mdl-head { display:flex; align-items:flex-start; gap:10px; margin-bottom:14px; }
        .mdl-toolbar { display:flex; gap:10px; padding:12px 14px; border-bottom:1px solid var(--border); align-items:center; }
        .mdl-ov { position:fixed; inset:0; background:rgba(16,24,40,.45); z-index:40; display:flex; align-items:center; justify-content:center; padding:16px; }
        .mdl-modal { width:min(780px,96vw); max-height:92vh; overflow:hidden; background:var(--surface); border:1px solid var(--border); border-radius:14px; box-shadow:0 24px 70px -20px rgba(16,32,64,.55); display:flex; flex-direction:column; }
        .mdl-mh { display:flex; align-items:center; gap:10px; padding:14px 18px; border-bottom:1px solid var(--border); }
        .mdl-mh h2 { margin:0; font-size:16px; } .mdl-mh .x { margin-left:auto; width:32px; height:32px; border-radius:8px; border:1px solid var(--border); background:var(--surface); cursor:pointer; color:var(--ink-soft); font-size:16px; }
        .mdl-body { padding:14px 18px; overflow-y:auto; }
        .mdl-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px 14px; }
        .mdl-fld { display:flex; flex-direction:column; gap:4px; } .mdl-fld.col2 { grid-column:span 2; }
        .mdl-fld label { font-size:11.5px; color:var(--ink-soft); font-weight:600; }
        .mdl-fld input, .mdl-fld select { margin-bottom:0; }
        .mdl-chk { flex-direction:row; align-items:center; gap:8px; font-size:13px; color:var(--ink); }
        .mdl-chk input { width:auto; margin:0; }
        .mdl-sect { font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:var(--brand-2); font-weight:700; margin:16px 0 8px; padding-bottom:6px; border-bottom:1px solid var(--border); }
        .mdl-mf { display:flex; gap:10px; align-items:center; padding:12px 18px; border-top:1px solid var(--border); background:var(--surface-2); }
        .req { color:var(--crit); }
      `}</style>
    </div>
  );
}
