import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";
import { confirmar, avisar } from "../../ui/dialog";

// Asientos (contabilidad general, doble partida). Como Odoo: cada asiento pertenece a un DIARIO y nace en
// BORRADOR (editable, no impacta el mayor) hasta PUBLICARLO. Un publicado es inmutable → se corrige por reversa.

const money = (v: any) => Number(v || 0).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const hoy = () => new Date().toISOString().slice(0, 10);
const fecha = (s?: string | null) => (s ? new Date(s + "T00:00:00").toLocaleDateString("es-AR") : "—");
type Cuenta = { codigo: string; nombre: string; imputable: boolean };
type Diario = { codigo: string; nombre: string; tipo: string };
type Centro = { codigo: string; nombre: string; activo: boolean };
type Linea = { cuenta_codigo: string; debe: string; haber: string; centro_codigo: string };

export default function Asientos() {
  const [rows, setRows] = useState<any[]>([]);
  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [diarios, setDiarios] = useState<Diario[]>([]);
  const [centros, setCentros] = useState<Centro[]>([]);
  const [error, setError] = useState("");
  const [editor, setEditor] = useState<null | { a?: any }>(null);   // {a} = editar borrador; {} = nuevo
  const [ver, setVer] = useState<any | null>(null);

  const cargar = () => api.asientosManuales().then(setRows).catch((e) => setError(e.message || String(e)));
  useEffect(() => {
    cargar();
    api.planCuentas().then((cs: Cuenta[]) => setCuentas(cs.filter((c) => c.imputable))).catch(() => {});
    api.diariosContables().then(setDiarios).catch(() => {});
    api.centrosCosto().then((cs: Centro[]) => setCentros(cs.filter((c) => c.activo))).catch(() => {});
  }, []);

  const diarioNom = useMemo(() => Object.fromEntries(diarios.map((d) => [d.codigo, d.nombre])), [diarios]);
  const totalAsiento = (a: any) => (a.lineas || []).reduce((s: number, l: any) => s + Number(l.debe || 0), 0);

  async function publicar(a: any) {
    if (!(await confirmar({ titulo: "Publicar asiento", confirmar: "Publicar", mensaje: `Publicar el asiento N° ${a.numero || a.id}. Recién publicado impacta el mayor y ya no se puede editar (se corrige por reversa). ¿Continuar?` }))) return;
    try { await api.publicarAsiento(a.id); cargar(); avisar("Asiento publicado."); }
    catch (e: any) { avisar({ tipo: "error", mensaje: e.message || String(e) }); }
  }
  async function eliminar(a: any) {
    if (!(await confirmar({ titulo: "Eliminar borrador", confirmar: "Eliminar", danger: true, mensaje: `Eliminar el borrador N° ${a.numero || a.id} (${a.concepto}). ¿Continuar?` }))) return;
    try { await api.eliminarAsientoManual(a.id); cargar(); }
    catch (e: any) { avisar({ tipo: "error", mensaje: e.message || String(e) }); }
  }
  async function reversar(a: any) {
    if (!(await confirmar({ titulo: "Reversar asiento", confirmar: "Reversar", danger: true, mensaje: `Se genera el contra-asiento de N° ${a.numero || a.id} (${a.concepto}). No se borra el original. ¿Continuar?` }))) return;
    try { await api.reversarAsiento(a.id); cargar(); avisar("Asiento reversado (contra-asiento generado)."); }
    catch (e: any) { avisar({ tipo: "error", mensaje: e.message || String(e) }); }
  }

  const estadoPill = (a: any) => a.origen === "reversa" ? <span className="pill brand">Reversa</span>
    : a.reversado ? <span className="pill" style={{ opacity: .8 }}>Reversado</span>
    : a.estado === "borrador" ? <span className="pill warn">Borrador</span> : <span className="pill ok">Publicado</span>;

  const cols: Col[] = [
    { key: "numero", label: "N°", align: "right", sortable: true, render: (a) => <span className="num"><b>{a.numero ?? a.id}</b></span> },
    { key: "fecha", label: "Fecha", sortable: true, render: (a) => fecha(a.fecha) },
    { key: "diario_codigo", label: "Diario", sortable: true, render: (a) => <span className="pill">{diarioNom[a.diario_codigo] || a.diario_codigo || "—"}</span> },
    { key: "concepto", label: "Concepto", sortable: true },
    { key: "importe", label: "Importe", align: "right", render: (a) => <span className="num">{money(totalAsiento(a))}</span> },
    { key: "estado", label: "Estado", render: estadoPill },
  ];
  const acciones = (a: any) => [
    { label: "Ver detalle", icon: "eye", onClick: () => setVer(a) },
    ...(a.origen === "manual" && a.estado === "borrador" ? [
      { label: "Editar", icon: "edit", onClick: () => setEditor({ a }) },
      { label: "Publicar", icon: "check", onClick: () => publicar(a) },
      { label: "Eliminar", icon: "trash", danger: true, onClick: () => eliminar(a) },
    ] : []),
    ...(a.origen === "manual" && a.estado === "publicado" && !a.reversado ? [{ label: "Reversar", icon: "rotate-ccw", danger: true, onClick: () => reversar(a) }] : []),
  ];

  return (
    <div className="asm">
      <div className="asm-head">
        <div>
          <h1 style={{ margin: 0 }}>Asientos</h1>
          <p className="muted" style={{ margin: "2px 0 0" }}>Contabilidad general por partida doble. Por diario, con borrador → publicado. Los automáticos están en el Libro diario. {rows.length} asientos.</p>
        </div>
        <span style={{ flex: 1 }} />
        <button onClick={() => setEditor({})}>＋ Nuevo asiento</button>
      </div>

      <div className="card" style={{ padding: "4px 14px 14px" }}>
        {error && <p className="error">{error}</p>}
        <DataTable columns={cols} rows={rows} rowKey={(a) => a.id} actions={acciones}
                   clientSort pageSize={25} defaultSort="numero" emptyText="Sin asientos" />
      </div>

      {editor && <EditorAsiento inicial={editor.a} cuentas={cuentas} diarios={diarios} centros={centros} onClose={() => setEditor(null)}
                  onGuardado={() => { setEditor(null); cargar(); }} />}
      {ver && <VerAsiento a={ver} diarioNom={diarioNom} onClose={() => setVer(null)} />}

      <style>{`
        .asm-head { display:flex; align-items:flex-start; gap:10px; margin-bottom:14px; flex-wrap:wrap; }
        .asm-ov { position:fixed; inset:0; background:rgba(16,24,40,.45); z-index:40; display:flex; align-items:center; justify-content:center; padding:16px; }
        .asm-modal { width:min(780px,96vw); max-height:92vh; overflow:hidden; background:var(--surface); border:1px solid var(--border); border-radius:14px; box-shadow:0 24px 70px -20px rgba(16,32,64,.55); display:flex; flex-direction:column; }
        .asm-mh { display:flex; align-items:center; gap:10px; padding:14px 18px; border-bottom:1px solid var(--border); }
        .asm-mh h2 { margin:0; font-size:16px; } .asm-mh .x { margin-left:auto; width:32px; height:32px; border-radius:8px; border:1px solid var(--border); background:var(--surface); cursor:pointer; color:var(--ink-soft); font-size:16px; }
        .asm-body { padding:14px 18px; overflow-y:auto; }
        .asm-grid { display:grid; grid-template-columns:160px 160px 1fr; gap:10px 14px; margin-bottom:8px; }
        .asm-fld { display:flex; flex-direction:column; gap:4px; }
        .asm-fld label { font-size:11.5px; color:var(--ink-soft); font-weight:600; }
        .asm-fld input, .asm-fld select { margin-bottom:0; }
        .asm-lin { width:100%; border-collapse:collapse; font-size:13px; margin-top:6px; }
        .asm-lin th { text-align:left; font-size:10.5px; text-transform:uppercase; letter-spacing:.03em; color:var(--ink-faint); font-weight:700; padding:6px 8px; border-bottom:1px solid var(--border); }
        .asm-lin td { padding:4px 8px; border-bottom:1px solid var(--border); }
        .asm-lin input, .asm-lin select { margin:0; width:100%; }
        .asm-tot { display:flex; gap:18px; align-items:center; justify-content:flex-end; margin-top:12px; font-size:13px; flex-wrap:wrap; }
        .asm-tot b { font-variant-numeric:tabular-nums; }
        .asm-bal { padding:4px 10px; border-radius:999px; font-size:12px; font-weight:700; }
        .asm-bal.ok { background:var(--ok-soft); color:var(--ok); } .asm-bal.no { background:var(--crit-soft); color:var(--crit); }
        .asm-mf { display:flex; gap:10px; align-items:center; padding:12px 18px; border-top:1px solid var(--border); background:var(--surface-2); }
      `}</style>
    </div>
  );
}

function EditorAsiento({ inicial, cuentas, diarios, centros, onClose, onGuardado }:
  { inicial?: any; cuentas: Cuenta[]; diarios: Diario[]; centros: Centro[]; onClose: () => void; onGuardado: () => void }) {
  const edicion = !!inicial;
  const [fechaV, setFechaV] = useState(inicial?.fecha || hoy());
  const [concepto, setConcepto] = useState(inicial?.concepto || "");
  const [diario, setDiario] = useState(inicial?.diario_codigo || "VAR");
  const [lineas, setLineas] = useState<Linea[]>(inicial
    ? (inicial.lineas || []).map((l: any) => ({ cuenta_codigo: l.cuenta_codigo, debe: Number(l.debe) ? String(Number(l.debe)) : "", haber: Number(l.haber) ? String(Number(l.haber)) : "", centro_codigo: l.centro_codigo || "" }))
    : [{ cuenta_codigo: "", debe: "", haber: "", centro_codigo: "" }, { cuenta_codigo: "", debe: "", haber: "", centro_codigo: "" }]);
  const [guardando, setGuardando] = useState(false);
  const [err, setErr] = useState("");

  const setL = (i: number, patch: Partial<Linea>) => setLineas((ls) => ls.map((l, idx) => idx === i ? { ...l, ...patch } : l));
  const addL = () => setLineas((ls) => [...ls, { cuenta_codigo: "", debe: "", haber: "", centro_codigo: "" }]);
  const delL = (i: number) => setLineas((ls) => ls.length > 2 ? ls.filter((_, idx) => idx !== i) : ls);

  const totDebe = useMemo(() => lineas.reduce((s, l) => s + (Number(l.debe) || 0), 0), [lineas]);
  const totHaber = useMemo(() => lineas.reduce((s, l) => s + (Number(l.haber) || 0), 0), [lineas]);
  const dif = Math.round((totDebe - totHaber) * 100) / 100;
  const balanceado = totDebe > 0 && dif === 0;
  const puede = !!concepto.trim() && balanceado && lineas.filter((l) => l.cuenta_codigo && (Number(l.debe) || Number(l.haber))).length >= 2;

  async function guardar() {
    setErr("");
    if (!puede) { setErr("Cargá concepto, al menos 2 líneas con cuenta e importe, y que Σdebe = Σhaber (≠ 0)."); return; }
    setGuardando(true);
    const payload = {
      fecha: fechaV, concepto: concepto.trim(), diario_codigo: diario,
      lineas: lineas.filter((l) => l.cuenta_codigo && (Number(l.debe) || Number(l.haber)))
        .map((l) => ({ cuenta_codigo: l.cuenta_codigo, debe: Number(l.debe) || 0, haber: Number(l.haber) || 0, centro_codigo: l.centro_codigo || "" })),
    };
    try {
      if (edicion) await api.editarAsientoManual(inicial.id, payload); else await api.crearAsientoManual(payload);
      onGuardado();
    } catch (e: any) { setErr(e.message || String(e)); }
    finally { setGuardando(false); }
  }

  return (
    <div className="asm-ov" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="asm-modal">
        <div className="asm-mh"><div><div className="eyebrow">{edicion ? `Editar borrador · N° ${inicial.numero || inicial.id}` : "Nuevo"}</div><h2>Asiento contable</h2></div>
          <button className="x" onClick={onClose} aria-label="Cerrar">✕</button></div>
        <div className="asm-body">
          <div className="asm-grid">
            <div className="asm-fld"><label>Fecha</label><input type="date" value={fechaV} onChange={(e) => setFechaV(e.target.value)} /></div>
            <div className="asm-fld"><label>Diario</label>
              <select value={diario} onChange={(e) => setDiario(e.target.value)}>
                {diarios.map((d) => <option key={d.codigo} value={d.codigo}>{d.nombre}</option>)}
              </select></div>
            <div className="asm-fld"><label>Concepto <span style={{ color: "var(--crit)" }}>*</span></label>
              <input value={concepto} maxLength={120} placeholder="ej. Ajuste de caja / provisión de gastos" onChange={(e) => setConcepto(e.target.value)} /></div>
          </div>
          <table className="asm-lin">
            <thead><tr><th style={{ width: "34%" }}>Cuenta</th><th style={{ width: "22%" }}>Centro de costo</th><th style={{ width: "18%", textAlign: "right" }}>Debe</th><th style={{ width: "18%", textAlign: "right" }}>Haber</th><th style={{ width: 32 }} /></tr></thead>
            <tbody>
              {lineas.map((l, i) => (
                <tr key={i}>
                  <td>
                    <select value={l.cuenta_codigo} onChange={(e) => setL(i, { cuenta_codigo: e.target.value })}>
                      <option value="">— elegí una cuenta —</option>
                      {cuentas.map((c) => <option key={c.codigo} value={c.codigo}>{c.codigo} · {c.nombre}</option>)}
                    </select>
                  </td>
                  <td>
                    <select value={l.centro_codigo} onChange={(e) => setL(i, { centro_codigo: e.target.value })}>
                      <option value="">— sin centro —</option>
                      {centros.map((c) => <option key={c.codigo} value={c.codigo}>{c.codigo} · {c.nombre}</option>)}
                    </select>
                  </td>
                  <td><input className="num" style={{ textAlign: "right" }} inputMode="decimal" value={l.debe} placeholder="0,00"
                    onChange={(e) => setL(i, { debe: e.target.value.replace(/[^\d.]/g, ""), haber: "" })} /></td>
                  <td><input className="num" style={{ textAlign: "right" }} inputMode="decimal" value={l.haber} placeholder="0,00"
                    onChange={(e) => setL(i, { haber: e.target.value.replace(/[^\d.]/g, ""), debe: "" })} /></td>
                  <td><button className="btn-ghost" onClick={() => delL(i)} disabled={lineas.length <= 2} aria-label="Quitar">✕</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: 8 }}><button className="btn sm" onClick={addL}>＋ Agregar línea</button></div>
          <div className="asm-tot">
            <span>Debe: <b className="num">{money(totDebe)}</b></span>
            <span>Haber: <b className="num">{money(totHaber)}</b></span>
            <span className={`asm-bal ${balanceado ? "ok" : "no"}`}>{balanceado ? "✓ Balanceado" : dif === 0 ? "Cargá importes" : `Descuadre ${money(Math.abs(dif))}`}</span>
          </div>
          {err && <div className="alert crit" style={{ marginTop: 12 }}>{err}</div>}
        </div>
        <div className="asm-mf"><span className="muted" style={{ fontSize: 12 }}>Se guarda en borrador; después lo publicás.</span><span style={{ flex: 1 }} />
          <button className="btn-ghost" onClick={onClose}>Cancelar</button>
          <button className="btn primary" disabled={guardando || !puede} onClick={guardar}>{guardando ? "Guardando…" : (edicion ? "Guardar borrador" : "Crear borrador")}</button>
        </div>
      </div>
    </div>
  );
}

function VerAsiento({ a, diarioNom, onClose }: { a: any; diarioNom: Record<string, string>; onClose: () => void }) {
  const totD = (a.lineas || []).reduce((s: number, l: any) => s + Number(l.debe || 0), 0);
  const estado = a.origen === "reversa" ? "reversa" : a.estado;
  return (
    <div className="asm-ov" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="asm-modal" style={{ maxWidth: 640 }}>
        <div className="asm-mh"><div><div className="eyebrow">Asiento N° {a.numero ?? a.id} · {fecha(a.fecha)} · {diarioNom[a.diario_codigo] || a.diario_codigo || "—"} · {estado}</div><h2>{a.concepto}</h2></div>
          <button className="x" onClick={onClose} aria-label="Cerrar">✕</button></div>
        <div className="asm-body">
          <table className="asm-lin">
            <thead><tr><th style={{ width: "56%" }}>Cuenta</th><th style={{ textAlign: "right" }}>Debe</th><th style={{ textAlign: "right" }}>Haber</th></tr></thead>
            <tbody>
              {(a.lineas || []).map((l: any, i: number) => (
                <tr key={i}><td>{l.cuenta_codigo} · {l.cuenta_nombre}</td>
                  <td className="num" style={{ textAlign: "right" }}>{Number(l.debe) ? money(l.debe) : ""}</td>
                  <td className="num" style={{ textAlign: "right" }}>{Number(l.haber) ? money(l.haber) : ""}</td></tr>
              ))}
            </tbody>
          </table>
          <div className="asm-tot"><span>Total: <b className="num">{money(totD)}</b></span>
            {a.usuario && <span className="muted">Cargado por {a.usuario}</span>}</div>
        </div>
        <div className="asm-mf"><span style={{ flex: 1 }} /><button className="btn" onClick={onClose}>Cerrar</button></div>
      </div>
    </div>
  );
}
