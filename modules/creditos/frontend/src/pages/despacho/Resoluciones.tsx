import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";
import RichText, { esHtml, plainAHtml, htmlTieneContenido } from "../../components/RichText";
import { confirmar, avisar } from "../../ui/dialog";

const LIMIT = 25;
const hoy = () => new Date().toISOString().slice(0, 10);
const money = (v: any) => (v == null ? "—" : Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" }));
const fecha = (s?: string | null) => (s ? new Date(s + "T00:00:00").toLocaleDateString("es-AR") : "—");
const TIPO_LBL: Record<string, string> = { RES: "Resolución", DIS: "Disposición" };
// Catálogos de la grilla de beneficiarios (códigos legacy; se muestran con etiqueta amigable).
const TIPO_DOC: Record<number, string> = { 0: "—", 1: "DNI", 2: "LC", 3: "LE", 4: "CI", 5: "Pasaporte" };
const TIPO_BENE: Record<number, string> = { 0: "—", 1: "Titular", 2: "Beneficiario", 3: "Apoderado" };

type Bene = { tipo_doc: number; nro_doc: string; nombre: string; tipo_bene: number };
type Modelo = { id: number; codigo: number; descripcion: string; tipo: string };

export default function Resoluciones() {
  const [rows, setRows] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState("fecha");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [fTipo, setFTipo] = useState("");
  const [fAnio, setFAnio] = useState("");
  const [error, setError] = useState("");

  const [modelos, setModelos] = useState<Modelo[]>([]);
  const [editor, setEditor] = useState(false);          // modal de alta
  const [editar, setEditar] = useState<any | null>(null);    // modal de edición (borrador)
  const [detalle, setDetalle] = useState<any | null>(null);  // modal ver

  async function cargar(off = offset, s = sort, o = order) {
    setError("");
    try {
      const d = await api.resoluciones({ limit: LIMIT, offset: off, sort: s, order: o,
        ...(fTipo ? { tipo: fTipo } : {}), ...(fAnio ? { anio: Number(fAnio) } as any : {}) });
      setRows(d.items); setTotal(d.total); setOffset(off); setSort(s); setOrder(o);
    } catch (e: any) { setError(e.message || String(e)); }
  }
  useEffect(() => { cargar(0); api.modelosResolucion().then(setModelos).catch(() => {}); }, []);
  useEffect(() => { cargar(0); }, [fTipo, fAnio]);   // refiltra

  const onSort = (key: string) => cargar(0, key, sort === key && order === "asc" ? "desc" : "asc");

  const cols: Col[] = [
    { key: "tipo", label: "Tipo", sortable: true, render: (r) => <span className="pill brand">{TIPO_LBL[r.tipo] || r.tipo}</span> },
    { key: "numero", label: "N° correlativo", sortable: true, align: "right", render: (r) => <span className="num"><b>{r.numero}</b>/{r.anio}</span> },
    { key: "numero_real", label: "N° real", align: "right", render: (r) => <span className="num">{r.numero_real ? `${r.numero_real}/${r.anio}` : "—"}</span> },
    { key: "fecha", label: "Fecha", sortable: true, render: (r) => fecha(r.fecha) },
    { key: "motivo", label: "Motivo", render: (r) => r.motivo || `cod ${r.motivo_cod}` || "—" },
    { key: "importe", label: "Importe", align: "right", render: (r) => <span className="num">{Number(r.importe) ? money(r.importe) : "—"}</span> },
    { key: "estado", label: "Estado", render: (r) => r.anulada
        ? <span className="pill crit">Anulada</span>
        : <span className={`pill ${r.estado === "F" ? "ok" : "warn"}`}>{r.estado === "F" ? "Oficial" : "Borrador"}</span> },
  ];
  const esBorrador = (r: any) => !r.anulada && r.estado !== "F" && !r.numero_real;
  const acciones = (r: any) => [
    { label: "Ver / beneficiarios", icon: "eye", onClick: () => verDetalle(r.id) },
    ...(esBorrador(r) ? [{ label: "Editar", icon: "edit", onClick: () => abrirEditar(r.id) }] : []),
    ...(!r.numero_real ? [{ label: "Cargar N° Real", icon: "check", onClick: () => cargarNumeroReal(r.id) }] : []),
    { label: "Descargar Word", icon: "copy", onClick: () => api.descargarResolucionWord(r.id, `${r.tipo}_${r.numero}_${r.anio}.docx`) },
  ];

  async function verDetalle(id: number) {
    try { setDetalle(await api.resolucion(id)); } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); }
  }
  async function abrirEditar(id: number) {
    try { setEditar(await api.resolucion(id)); } catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); }
  }
  async function cargarNumeroReal(id: number) {
    if (!(await confirmar({ titulo: "Cargar N° Real", confirmar: "Asignar", mensaje: "Se asignará el próximo N° Real oficial (por tipo y año) a esta resolución. ¿Confirmás?" }))) return;
    try { await api.cargarNumeroReal(id); await cargar(); if (detalle?.id === id) verDetalle(id); }
    catch (e: any) { avisar({ tipo: "error", mensaje: e.message }); }
  }

  return (
    <div className="rsl">
      <div className="rsl-head">
        <div>
          <h1 style={{ margin: 0 }}>Resoluciones y disposiciones</h1>
          <p className="muted" style={{ margin: "2px 0 0" }}>Instrumentos legales de Despacho: N° correlativo y N° real, motivo (modelo), importe, texto y beneficiarios.</p>
        </div>
        <span style={{ flex: 1 }} />
        <button onClick={() => setEditor(true)}>＋ Nueva resolución</button>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div className="rsl-toolbar">
          <select value={fTipo} onChange={(e) => setFTipo(e.target.value)}>
            <option value="">Todos los tipos</option><option value="RES">Resoluciones</option><option value="DIS">Disposiciones</option>
          </select>
          <input className="num" inputMode="numeric" placeholder="Año" value={fAnio} maxLength={4}
                 onChange={(e) => setFAnio(e.target.value.replace(/\D/g, "").slice(0, 4))} style={{ width: 90 }} />
          {(fTipo || fAnio) && <button className="btn-ghost" onClick={() => { setFTipo(""); setFAnio(""); }}>Limpiar</button>}
        </div>
        {error && <p className="error" style={{ margin: "10px 14px" }}>{error}</p>}
        <div style={{ padding: "4px 14px 14px" }}>
          <DataTable columns={cols} rows={rows} total={total} limit={LIMIT} offset={offset}
                     sort={sort} order={order} onSort={onSort} onPage={(off) => cargar(off)}
                     rowKey={(r) => r.id} actions={acciones} emptyText="Sin resoluciones" />
        </div>
      </div>

      {editor && <EditorResolucion modelos={modelos} onClose={() => setEditor(false)}
                    onGuardada={(r) => { setEditor(false); cargar(0); setDetalle(r); }} />}
      {editar && <EditorResolucion modelos={modelos} inicial={editar} onClose={() => setEditar(null)}
                    onGuardada={(r) => { setEditar(null); cargar(offset); setDetalle(r); }} />}
      {detalle && <DetalleResolucion r={detalle} onClose={() => setDetalle(null)}
                    onEditar={esBorrador(detalle) ? () => { setDetalle(null); abrirEditar(detalle.id); } : undefined}
                    onNumeroReal={() => cargarNumeroReal(detalle.id)} />}

      <style>{`
        .rsl-head { display:flex; align-items:flex-start; gap:10px; margin-bottom:14px; }
        .rsl-toolbar { display:flex; gap:10px; padding:12px 14px; border-bottom:1px solid var(--border); flex-wrap:wrap; align-items:center; }
        .rsl-ov { position:fixed; inset:0; background:rgba(16,24,40,.45); z-index:40; display:flex; align-items:center; justify-content:center; padding:16px; }
        .rsl-modal { width:min(860px,96vw); max-height:92vh; overflow:hidden; background:var(--surface); border:1px solid var(--border); border-radius:14px; box-shadow:0 24px 70px -20px rgba(16,32,64,.55); display:flex; flex-direction:column; }
        .rsl-mh { display:flex; align-items:center; gap:10px; padding:14px 18px; border-bottom:1px solid var(--border); }
        .rsl-mh h2 { margin:0; font-size:16px; } .rsl-mh .x { margin-left:auto; width:32px; height:32px; border-radius:8px; border:1px solid var(--border); background:var(--surface); cursor:pointer; color:var(--ink-soft); font-size:16px; }
        .rsl-body { padding:14px 18px; overflow-y:auto; }
        .rsl-grid { display:grid; grid-template-columns:repeat(4, 1fr); gap:10px 14px; }
        .rsl-fld { display:flex; flex-direction:column; gap:4px; }
        .rsl-fld.col2 { grid-column:span 2; } .rsl-fld.col4 { grid-column:span 4; }
        .rsl-fld label { font-size:11.5px; color:var(--ink-soft); font-weight:600; }
        .rsl-fld input, .rsl-fld select, .rsl-fld textarea { margin-bottom:0; }
        .rsl-fld .ro { font-size:13px; color:var(--ink-faint); padding:8px 0; }
        .rsl-legal { width:100%; min-height:200px; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:12.5px; line-height:1.5; }
        .rsl-legal-view { border:1px solid var(--border); border-radius:10px; padding:12px 14px; max-height:340px; overflow:auto; font-size:13.5px; line-height:1.55; background:var(--surface); }
        .rsl-legal-view h1,.rsl-legal-view h2 { font-size:15px; text-align:center; margin:.4em 0; }
        .rsl-legal-view h3,.rsl-legal-view h4 { font-size:13.5px; margin:.4em 0; }
        .rsl-legal-view p { margin:.4em 0; text-align:justify; }
        .rsl-sect { font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:var(--brand-2); font-weight:700; margin:16px 0 8px; padding-bottom:6px; border-bottom:1px solid var(--border); }
        .rsl-ben { width:100%; border-collapse:collapse; font-size:13px; }
        .rsl-ben th, .rsl-ben td { padding:6px 8px; border-bottom:1px solid var(--border); text-align:left; }
        .rsl-ben th { font-size:11px; text-transform:uppercase; color:var(--ink-soft); }
        .rsl-ben input, .rsl-ben select { margin:0; width:100%; }
        .rsl-mf { display:flex; gap:10px; align-items:center; padding:12px 18px; border-top:1px solid var(--border); background:var(--surface-2); }
        .rsl-imp { text-align:right; font-variant-numeric:tabular-nums; }
        @media (max-width:640px){ .rsl-grid { grid-template-columns:1fr 1fr; } .rsl-fld.col2,.rsl-fld.col4 { grid-column:span 2; } }
      `}</style>
    </div>
  );
}

// ---- Editor de alta / edición (parecido a la pantalla VFP). `inicial` = editar un borrador ----
function EditorResolucion({ modelos, inicial, onClose, onGuardada }:
  { modelos: Modelo[]; inicial?: any; onClose: () => void; onGuardada: (r: any) => void }) {
  const edicion = !!inicial;
  // El modelo se guarda por código en la resolución; acá se resuelve al id único (código repite entre tipos).
  const modeloIdInicial = inicial?.modelo_codigo
    ? String(modelos.find((m) => m.codigo === inicial.modelo_codigo
        && (inicial.tipo === "DIS") === (m.tipo === "Disposición"))?.id || "")
    : "";
  const [tipo, setTipo] = useState(inicial?.tipo || "RES");
  const [fecha, setFecha] = useState(inicial?.fecha || hoy());
  const [modeloId, setModeloId] = useState(modeloIdInicial);   // id único del modelo elegido
  const [importe, setImporte] = useState(Number(inicial?.importe) ? String(Number(inicial.importe)) : "");
  const [origen, setOrigen] = useState(inicial?.origen || "");
  const [texto, setTexto] = useState(inicial?.texto || "");    // HTML del editor mini-Word
  const [bene, setBene] = useState<Bene[]>((inicial?.beneficiarios || []).map((b: any) =>
    ({ tipo_doc: b.tipo_doc ?? 0, nro_doc: b.nro_doc || "", nombre: b.nombre || "", tipo_bene: b.tipo_bene ?? 0 })));
  const [guardando, setGuardando] = useState(false);
  const [err, setErr] = useState("");

  const modelosTipo = useMemo(() => modelos.filter((m) => (tipo === "DIS") === (m.tipo === "Disposición")), [modelos, tipo]);
  const motivo = modelos.find((m) => String(m.id) === modeloId)?.descripcion || (edicion ? inicial.motivo : "") || "";

  async function elegirModelo(id: string) {
    setModeloId(id);
    if (!id) return;
    // "Modelo a utilizar": carga el texto base (plantilla) si el cuerpo está vacío.
    try {
      const m = await api.modeloResolucion(Number(id));
      if (m.plantilla && !htmlTieneContenido(texto)) {
        setTexto(esHtml(m.plantilla) ? m.plantilla : plainAHtml(m.plantilla));
      }
    } catch { /* el modelo puede no tener plantilla */ }
  }
  const setB = (i: number, k: keyof Bene, v: any) => setBene((bs) => bs.map((b, idx) => idx === i ? { ...b, [k]: v } : b));
  const addB = () => setBene((bs) => [...bs, { tipo_doc: 1, nro_doc: "", nombre: "", tipo_bene: 1 }]);
  const delB = (i: number) => setBene((bs) => bs.filter((_, idx) => idx !== i));

  const impInvalido = importe !== "" && !(Number(importe) >= 0);
  const beneInvalido = bene.some((b) => !b.nombre.trim());
  const puede = !impInvalido && !beneInvalido && (!!modeloId || htmlTieneContenido(texto));

  async function grabar() {
    setErr("");
    if (!puede) { setErr("Elegí un modelo o cargá el texto; revisá importe y que cada beneficiario tenga nombre."); return; }
    setGuardando(true);
    const payload = {
      tipo, fecha, modelo_id: modeloId ? Number(modeloId) : null,
      importe: importe ? Number(importe) : 0, origen: origen.trim(),
      texto: htmlTieneContenido(texto) ? texto : "",
      beneficiarios: bene.map((b) => ({ ...b, nro_doc: b.nro_doc.replace(/\D/g, "") })),
    };
    try {
      const r = edicion ? await api.editarResolucion(inicial.id, payload) : await api.crearResolucion(payload);
      onGuardada(r);
    } catch (e: any) { setErr(e.message || String(e)); }
    finally { setGuardando(false); }
  }

  return (
    <div className="rsl-ov" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="rsl-modal">
        <div className="rsl-mh">
          <div><div className="eyebrow">{edicion ? `Editar borrador · N° ${inicial.numero}/${inicial.anio}` : "Nueva"}</div>
            <h2>Resolución / Disposición</h2></div>
          <button className="x" onClick={onClose} aria-label="Cerrar">✕</button>
        </div>
        <div className="rsl-body">
          <div className="rsl-grid">
            <div className="rsl-fld"><label>Tipo</label>
              {edicion
                ? <div className="ro">{TIPO_LBL[tipo] || tipo}</div>
                : <select value={tipo} onChange={(e) => { setTipo(e.target.value); setModeloId(""); }}>
                    <option value="RES">Resolución</option><option value="DIS">Disposición</option></select>}</div>
            <div className="rsl-fld"><label>N° Correlativo</label>
              <div className="ro">{edicion ? `${inicial.numero}/${inicial.anio}` : "se asigna al grabar"}</div></div>
            <div className="rsl-fld"><label>Fecha</label><input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} /></div>
            <div className="rsl-fld"><label>N° Real</label><div className="ro">se carga luego</div></div>
            <div className="rsl-fld col2"><label>Modelo a utilizar <span className="muted">(define el motivo)</span></label>
              <select value={modeloId} onChange={(e) => elegirModelo(e.target.value)}>
                <option value="">— elegí un modelo —</option>
                {modelosTipo.map((m) => <option key={m.id} value={m.id}>{m.codigo} · {m.descripcion}</option>)}
              </select></div>
            <div className={`rsl-fld ${impInvalido ? "err" : ""}`}><label>Importe</label>
              <input className="num rsl-imp" inputMode="decimal" value={importe} placeholder="0,00"
                     onChange={(e) => setImporte(e.target.value.replace(/[^\d.]/g, ""))} /></div>
            <div className="rsl-fld"><label>Motivo</label><div className="ro">{motivo || "—"}</div></div>
            <div className="rsl-fld col4"><label>Exp./Nota que origina el instrumento legal <span className="muted">(opcional)</span></label>
              <input value={origen} maxLength={40} placeholder="ej. E10 55/2026" onChange={(e) => setOrigen(e.target.value)} /></div>
          </div>

          <div className="rsl-sect">Texto del instrumento legal</div>
          <RichText value={texto} onChange={setTexto}
                    placeholder="Cuerpo de la resolución. Usá Título/Subtítulo, negrita, etc. Al elegir un modelo se carga su texto base." />

          <div className="rsl-sect" style={{ display: "flex", alignItems: "center" }}>Beneficiarios
            <span style={{ flex: 1 }} /><button type="button" className="btn sm" onClick={addB}>＋ Agregar</button></div>
          {bene.length === 0 && <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>Sin beneficiarios. Agregá si la resolución los requiere.</p>}
          {bene.length > 0 && (
            <table className="rsl-ben">
              <thead><tr><th style={{ width: 110 }}>Tipo Doc.</th><th style={{ width: 140 }}>N° documento</th><th>Nombres</th><th style={{ width: 150 }}>Tipo Benef.</th><th style={{ width: 34 }}></th></tr></thead>
              <tbody>
                {bene.map((b, i) => (
                  <tr key={i}>
                    <td><select value={b.tipo_doc} onChange={(e) => setB(i, "tipo_doc", Number(e.target.value))}>
                      {Object.entries(TIPO_DOC).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></td>
                    <td><input className="num" inputMode="numeric" value={b.nro_doc} maxLength={11}
                               onChange={(e) => setB(i, "nro_doc", e.target.value.replace(/\D/g, "").slice(0, 11))} /></td>
                    <td><input value={b.nombre} maxLength={80} onChange={(e) => setB(i, "nombre", e.target.value)} /></td>
                    <td><select value={b.tipo_bene} onChange={(e) => setB(i, "tipo_bene", Number(e.target.value))}>
                      {Object.entries(TIPO_BENE).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></td>
                    <td><button type="button" className="btn-ghost" onClick={() => delB(i)} aria-label="Quitar">✕</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {err && <div className="alert crit" style={{ marginTop: 12 }}>{err}</div>}
        </div>
        <div className="rsl-mf">
          <span style={{ flex: 1 }} />
          <button className="btn-ghost" onClick={onClose}>Cancelar</button>
          <button disabled={guardando || !puede} onClick={grabar}>{guardando ? "Grabando…" : (edicion ? "Guardar cambios" : "Grabar")}</button>
        </div>
      </div>
    </div>
  );
}

// ---- Detalle / ver (con beneficiarios y carga de N° Real) ----
function DetalleResolucion({ r, onClose, onNumeroReal, onEditar }: { r: any; onClose: () => void; onNumeroReal: () => void; onEditar?: () => void }) {
  return (
    <div className="rsl-ov" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="rsl-modal">
        <div className="rsl-mh">
          <div><div className="eyebrow">{TIPO_LBL[r.tipo] || r.tipo} · N° {r.numero}/{r.anio}</div>
            <h2>{r.motivo || r.asunto || "Instrumento legal"}</h2></div>
          <button className="x" onClick={onClose} aria-label="Cerrar">✕</button>
        </div>
        <div className="rsl-body">
          <div className="rsl-grid">
            <div className="rsl-fld"><label>N° Correlativo</label><div className="ro">{r.numero}/{r.anio}</div></div>
            <div className="rsl-fld"><label>Fecha</label><div className="ro">{fecha(r.fecha)}</div></div>
            <div className="rsl-fld"><label>N° Real</label><div className="ro">{r.numero_real ? `${r.numero_real}/${r.anio}` : "sin asignar"}</div></div>
            <div className="rsl-fld"><label>Fecha Real</label><div className="ro">{fecha(r.fecha_real)}</div></div>
            <div className="rsl-fld col2"><label>Motivo</label><div className="ro">{r.motivo || `cod ${r.motivo_cod}`}</div></div>
            <div className="rsl-fld"><label>Importe</label><div className="ro rsl-imp">{Number(r.importe) ? money(r.importe) : "—"}</div></div>
            <div className="rsl-fld"><label>Estado</label><div className="ro">{r.anulada ? "Anulada" : r.estado === "F" ? "Oficial" : "Borrador"}</div></div>
            {r.origen && <div className="rsl-fld col4"><label>Exp./Nota origen</label><div className="ro">{r.origen}</div></div>}
          </div>
          <div className="rsl-sect">Texto del instrumento legal</div>
          {!r.texto ? <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>(sin texto)</p>
            : esHtml(r.texto)
              ? <div className="rsl-legal-view" dangerouslySetInnerHTML={{ __html: r.texto }} />
              : <div className="rsl-legal-view" style={{ whiteSpace: "pre-wrap" }}>{r.texto}</div>}
          <div className="rsl-sect">Beneficiarios ({(r.beneficiarios || []).length})</div>
          {(r.beneficiarios || []).length === 0 ? <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>Sin beneficiarios.</p> : (
            <table className="rsl-ben">
              <thead><tr><th>Tipo Doc.</th><th>N° documento</th><th>Nombres</th><th>Tipo Benef.</th></tr></thead>
              <tbody>{r.beneficiarios.map((b: any) => (
                <tr key={b.id}><td>{TIPO_DOC[b.tipo_doc] || b.tipo_doc}</td><td className="num">{b.nro_doc || "—"}</td>
                  <td>{b.nombre}</td><td>{TIPO_BENE[b.tipo_bene] || b.tipo_bene}</td></tr>))}</tbody>
            </table>
          )}
        </div>
        <div className="rsl-mf">
          {onEditar && <button className="btn-ghost" onClick={onEditar}>Editar</button>}
          {!r.numero_real && <button className="btn-ghost" onClick={onNumeroReal}>Cargar N° Real</button>}
          <span style={{ flex: 1 }} />
          <button className="btn-ghost" onClick={() => api.descargarResolucionWord(r.id, `${r.tipo}_${r.numero}_${r.anio}.docx`)}>Descargar Word</button>
          <button onClick={onClose}>Cerrar</button>
        </div>
      </div>
    </div>
  );
}
