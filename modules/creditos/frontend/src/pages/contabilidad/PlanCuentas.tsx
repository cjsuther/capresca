import { useEffect, useMemo, useRef, useState } from "react";
import { api, getEmpresaActiva, setEmpresaActiva } from "../../api";
import { confirmar, avisar, pedirTexto } from "../../ui/dialog";

type Empresa = { id: number; codigo: string; nombre: string; predeterminada: boolean };

// Plan de cuentas (moderno). Master-detail: árbol jerárquico a la izquierda + "Datos de la cuenta" a la
// derecha (código, nombre, descripción, alias, moneda, tipo, saldo normal, imputable/manual, entidades
// relacionadas). Editable/configurable y persistente. La versión previa (grilla-árbol simple) quedó como
// "Plan de cuentas 2".
// diseño-ok: master-detail con árbol jerárquico + panel de datos — DataTable es plano y no modela la
// jerarquía padre/hijo ni el detalle editable; UI custom scopeada `.pcm-*`, colores por tokens de tema.

type Ent = { tipo: string; entidad: string };
type Cuenta = {
  id: number; codigo: string; nombre: string; tipo: string; descripcion: string; alias: string;
  moneda: string; clasificacion: string; saldo_normal: string; imputable: boolean; manual: boolean;
  entidades: Ent[]; en_uso: boolean; base: boolean;
};
type Nodo = { codigo: string; cuenta: Cuenta | null; hijos: Nodo[] };

const RUBROS = ["activo", "pasivo", "patrimonio", "ingreso", "egreso"];
const RUBRO_LBL: Record<string, string> = { activo: "Activo", pasivo: "Pasivo", patrimonio: "Patrimonio", ingreso: "Ingreso", egreso: "Egreso" };
const CLASES = ["Sin clasificar", "Caja", "Banco", "Cliente / deudor", "Proveedor", "Impuesto", "Resultado", "Otra"];
const MONEDAS = ["ARS", "USD", "EUR"];
const cmpCod = (a: string, b: string) => a.localeCompare(b, undefined, { numeric: true });

function armarArbol(rows: Cuenta[]): Nodo[] {
  const byCod = new Map<string, Nodo>();
  const asegurar = (codigo: string): Nodo => {
    let n = byCod.get(codigo);
    if (!n) { n = { codigo, cuenta: null, hijos: [] }; byCod.set(codigo, n); }
    return n;
  };
  for (const c of rows) asegurar(c.codigo).cuenta = c;
  for (const cod of [...byCod.keys()]) {
    const segs = cod.split(".");
    for (let i = 1; i < segs.length; i++) asegurar(segs.slice(0, i).join("."));
  }
  const raices: Nodo[] = [];
  for (const n of byCod.values()) {
    const segs = n.codigo.split(".");
    const padre = segs.length > 1 ? byCod.get(segs.slice(0, -1).join(".")) : null;
    if (padre) padre.hijos.push(n); else raices.push(n);
  }
  const ordenar = (arr: Nodo[]) => { arr.sort((a, b) => cmpCod(a.codigo, b.codigo)); arr.forEach((x) => ordenar(x.hijos)); };
  ordenar(raices);
  return raices;
}

// Próximo código hijo (padre + siguiente sufijo de 2 dígitos).
function proxCodigoHijo(padre: string, hermanos: string[]): string {
  let max = 0;
  for (const h of hermanos) {
    const seg = h.split(".").pop() || "";
    const n = parseInt(seg, 10);
    if (!isNaN(n)) max = Math.max(max, n);
  }
  const suf = String(max + 1).padStart(2, "0");
  return padre ? `${padre}.${suf}` : suf;
}

const VACIO = (): Cuenta => ({ id: 0, codigo: "", nombre: "", tipo: "activo", descripcion: "", alias: "", moneda: "ARS", clasificacion: "Sin clasificar", saldo_normal: "deudor", imputable: true, manual: false, entidades: [], en_uso: false, base: false });

export default function PlanCuentas() {
  const [rows, setRows] = useState<Cuenta[]>([]);
  const [sel, setSel] = useState<string>("");        // código seleccionado
  const [draft, setDraft] = useState<Cuenta | null>(null);  // copia editable (o alta)
  const [esAlta, setEsAlta] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [colapsados, setColapsados] = useState<Set<string>>(new Set());
  const [q, setQ] = useState("");
  const [err, setErr] = useState("");
  const [guardando, setGuardando] = useState(false);
  const nombreRef = useRef<HTMLInputElement>(null);

  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const [empActiva, setEmpActiva] = useState<number | undefined>(getEmpresaActiva());
  const cargar = () => api.planCuentas().then((r: Cuenta[]) => setRows(r)).catch((e) => setErr(e.message || String(e)));
  const cargarEmpresas = () => api.empresas().then((es: Empresa[]) => {
    setEmpresas(es);
    // si no hay empresa activa persistida, usar la predeterminada
    if (!getEmpresaActiva()) { const pred = es.find((e) => e.predeterminada) || es[0]; if (pred) { setEmpresaActiva(pred.id); setEmpActiva(pred.id); } }
  }).catch(() => {});
  useEffect(() => { cargarEmpresas(); cargar(); }, []);   // eslint-disable-line

  function cambiarEmpresa(id: number) {
    setEmpresaActiva(id); setEmpActiva(id); setSel(""); setDraft(null); setEsAlta(false);
    api.planCuentas().then((r: Cuenta[]) => setRows(r)).catch((e) => setErr(e.message || String(e)));
  }
  async function nuevaEmpresa() {
    const codigo = await pedirTexto({ mensaje: "Código de la empresa (ej. JUEGOS):", requerido: true });
    if (!codigo) return;
    const nombre = await pedirTexto({ mensaje: "Nombre de la empresa:", requerido: true });
    if (!nombre) return;
    try { const e = await api.crearEmpresa({ codigo, nombre }); await cargarEmpresas(); cambiarEmpresa(e.id); avisar({ tipo: "ok", mensaje: `Empresa "${nombre}" creada. Cargá su plan de cuentas.` }); }
    catch (x: any) { avisar({ tipo: "error", mensaje: x.message || String(x) }); }
  }

  const cuentaSel = rows.find((c) => c.codigo === sel) || null;
  // Mientras se da un alta, la cuenta en borrador aparece EN el árbol (fantasma) para ver dónde queda.
  const rowsView = useMemo(() => {
    if (esAlta && draft) {
      const otras = rows.filter((c) => c.codigo !== draft.codigo);
      return [...otras, { ...draft, id: draft.id || -1, nombre: draft.nombre || "Nueva cuenta…" }];
    }
    return rows;
  }, [rows, esAlta, draft]);
  const arbol = useMemo(() => armarArbol(rowsView), [rowsView]);
  const codigoActivo = esAlta && draft ? draft.codigo : sel;   // fila resaltada en el árbol

  // cargar el draft cuando cambia la selección (si no es alta en curso)
  useEffect(() => {
    if (esAlta) return;
    setDraft(cuentaSel ? { ...cuentaSel, entidades: (cuentaSel.entidades || []).map((e) => ({ ...e })) } : null);
    setDirty(false); setErr("");
  }, [sel, rows]);   // eslint-disable-line

  const ql = q.trim().toLowerCase();
  const matchNodo = (n: Nodo) => !!n.cuenta && (n.cuenta.codigo.toLowerCase().includes(ql) || n.cuenta.nombre.toLowerCase().includes(ql));
  const subMatch = (n: Nodo): boolean => matchNodo(n) || n.hijos.some(subMatch);

  const filas = useMemo(() => {
    const out: { n: Nodo; depth: number }[] = [];
    const rec = (ns: Nodo[], depth: number) => {
      for (const n of ns) {
        if (ql && !subMatch(n)) continue;
        out.push({ n, depth });
        const abierto = ql ? true : !colapsados.has(n.codigo);
        if (n.hijos.length && abierto) rec(n.hijos, depth + 1);
      }
    };
    rec(arbol, 0);
    return out;
  }, [arbol, colapsados, ql]);   // eslint-disable-line

  const toggle = (cod: string) => setColapsados((p) => { const s = new Set(p); s.has(cod) ? s.delete(cod) : s.add(cod); return s; });
  const path = (code: string) => { const arr: string[] = []; const segs = code.split("."); for (let i = 1; i <= segs.length; i++) arr.push(segs.slice(0, i).join(".")); return arr; };

  // Diálogo in-app (no window.confirm): confirma descartar cambios; true = seguir.
  const pedirDescartar = async () => !dirty || await confirmar({
    titulo: "Cambios sin guardar", confirmar: "Descartar", danger: true,
    mensaje: "Hay cambios sin guardar en la cuenta. ¿Descartarlos?" });

  async function seleccionar(codigo: string) {
    if (esAlta && draft && codigo === draft.codigo) return;   // ya estoy editando esta fila (fantasma)
    if (!(await pedirDescartar())) return;
    const real = rows.find((c) => c.codigo === codigo);
    if (real) { setEsAlta(false); setSel(codigo); return; }
    // Rama de agrupación sin cuenta propia → modo "nombrar/crear" (imputable off), el código queda fijo.
    const nuevo = VACIO();
    nuevo.codigo = codigo; nuevo.imputable = false; nuevo.tipo = rubroDeRaiz(codigo);
    nuevo.saldo_normal = ["pasivo", "patrimonio", "ingreso"].includes(nuevo.tipo) ? "acreedor" : "deudor";
    setEsAlta(true); setSel(codigo); setDraft(nuevo); setDirty(false); setErr("");
    setTimeout(() => nombreRef.current?.focus(), 30);
  }
  const setD = (patch: Partial<Cuenta>) => { setDraft((d) => (d ? { ...d, ...patch } : d)); setDirty(true); };

  async function nuevaBajo(padreCodigo: string) {
    if (!(await pedirDescartar())) return;
    const hermanos = rows.filter((c) => { const s = c.codigo.split("."); return s.slice(0, -1).join(".") === padreCodigo; }).map((c) => c.codigo);
    const padre = rows.find((c) => c.codigo === padreCodigo);
    const nuevo = VACIO();
    nuevo.codigo = proxCodigoHijo(padreCodigo, hermanos);
    nuevo.nombre = "";
    nuevo.tipo = padre?.tipo || rubroDeRaiz(nuevo.codigo);
    nuevo.saldo_normal = padre?.saldo_normal || (nuevo.tipo === "pasivo" || nuevo.tipo === "patrimonio" || nuevo.tipo === "ingreso" ? "acreedor" : "deudor");
    setColapsados((p) => { const s = new Set(p); s.delete(padreCodigo); return s; });
    setEsAlta(true); setSel(""); setDraft(nuevo); setDirty(true); setErr("");
    setTimeout(() => nombreRef.current?.focus(), 30);
  }
  async function nuevaRaiz() {
    if (!(await pedirDescartar())) return;
    const raices = rows.filter((c) => !c.codigo.includes(".")).map((c) => c.codigo);
    const nuevo = VACIO(); nuevo.codigo = proxCodigoHijo("", raices); nuevo.tipo = rubroDeRaiz(nuevo.codigo);
    setEsAlta(true); setSel(""); setDraft(nuevo); setDirty(true); setErr("");
    setTimeout(() => nombreRef.current?.focus(), 30);
  }
  function rubroDeRaiz(codigo: string): string {
    const raiz = codigo.split(".")[0];
    return ({ "1": "activo", "2": "pasivo", "3": "patrimonio", "4": "ingreso", "5": "egreso" } as Record<string, string>)[raiz] || "activo";
  }
  function nuevaHermana() {
    const padre = sel ? sel.split(".").slice(0, -1).join(".") : "";
    padre ? nuevaBajo(padre) : nuevaRaiz();
  }
  async function duplicar() {
    if (!cuentaSel) return;
    if (!(await pedirDescartar())) return;
    const padreCodigo = cuentaSel.codigo.split(".").slice(0, -1).join(".");
    const hermanos = rows.filter((c) => c.codigo.split(".").slice(0, -1).join(".") === padreCodigo).map((c) => c.codigo);
    const nuevo = { ...cuentaSel, entidades: (cuentaSel.entidades || []).map((e) => ({ ...e })) };
    nuevo.id = 0; nuevo.base = false; nuevo.en_uso = false;
    nuevo.codigo = proxCodigoHijo(padreCodigo, hermanos);
    nuevo.nombre = `${cuentaSel.nombre} (copia)`;
    setEsAlta(true); setSel(""); setDraft(nuevo); setDirty(true); setErr("");
    setTimeout(() => nombreRef.current?.focus(), 30);
  }

  async function guardar() {
    if (!draft) return;
    setErr("");
    if (!draft.codigo.trim() || !draft.nombre.trim()) { setErr("Código y nombre son obligatorios."); return; }
    setGuardando(true);
    const payload = {
      codigo: draft.codigo.trim(), nombre: draft.nombre.trim(), tipo: draft.tipo,
      descripcion: draft.descripcion, alias: draft.alias, moneda: draft.moneda,
      clasificacion: draft.clasificacion, saldo_normal: draft.saldo_normal,
      imputable: draft.imputable, manual: draft.manual,
      entidades: (draft.entidades || []).filter((e) => e.tipo || e.entidad),
    };
    try {
      const saved = esAlta ? await api.crearCuenta(payload) : await api.editarCuenta(draft.id, payload);
      await cargar();
      setEsAlta(false); setDirty(false); setSel(saved.codigo);
    } catch (e: any) { setErr(e.message || String(e)); }
    finally { setGuardando(false); }
  }
  function descartar() {
    setEsAlta(false); setDirty(false); setErr("");
    setDraft(cuentaSel ? { ...cuentaSel, entidades: (cuentaSel.entidades || []).map((e) => ({ ...e })) } : null);
  }
  async function borrar() {
    if (!cuentaSel) return;
    if (!(await confirmar({ titulo: "Borrar cuenta", confirmar: "Borrar", danger: true, mensaje: `¿Borrar la cuenta ${cuentaSel.codigo} · ${cuentaSel.nombre}?` }))) return;
    try { await api.borrarCuenta(cuentaSel.id); setSel(""); setDraft(null); await cargar(); }
    catch (e: any) { avisar({ tipo: "error", mensaje: e.message || String(e) }); }
  }
  async function restaurar() {
    if (!(await confirmar({ titulo: "Restaurar plantilla base", confirmar: "Restaurar", mensaje: "Agrega al plan las cuentas base que falten (no pisa ni duplica). ¿Continuar?" }))) return;
    try { const r = await api.restaurarPlanCuentas(); await cargar(); avisar(r.agregadas ? `Se agregaron ${r.agregadas} cuenta(s) base.` : "El plan ya tiene todas las cuentas base."); }
    catch (e: any) { avisar({ tipo: "error", mensaje: e.message || String(e) }); }
  }
  async function cargarEstandar() {
    if (!(await confirmar({ titulo: "Cargar plan estándar", confirmar: "Cargar", mensaje: "Puebla el plan con un chart de cuentas estándar (Activo, Pasivo, Patrimonio neto, Ingresos, Egresos y sus subcuentas). No pisa ni duplica lo existente. ¿Continuar?" }))) return;
    try { const r = await api.cargarPlanEstandar(); await cargar(); avisar(r.agregadas ? `Se agregaron ${r.agregadas} cuenta(s) del plan estándar.` : "El plan ya tiene todas las cuentas estándar."); }
    catch (e: any) { avisar({ tipo: "error", mensaje: e.message || String(e) }); }
  }

  // entidades relacionadas (en el draft)
  const addEnt = () => setD({ entidades: [...(draft?.entidades || []), { tipo: "", entidad: "" }] });
  const setEnt = (i: number, patch: Partial<Ent>) => setD({ entidades: (draft?.entidades || []).map((e, idx) => idx === i ? { ...e, ...patch } : e) });
  const delEnt = (i: number) => setD({ entidades: (draft?.entidades || []).filter((_, idx) => idx !== i) });

  // Render recursivo del árbol con conectores (ramas anidadas), respetando plegado y búsqueda.
  const ramas = (nodes: Nodo[], depth = 0): any[] => {
    const out: any[] = [];
    for (const n of nodes) {
      if (ql && !subMatch(n)) continue;
      const c = n.cuenta; const abierto = ql ? true : !colapsados.has(n.codigo);
      const grupo = !c || !c.imputable;      // rama de agrupación (sin cuenta, o cuenta no imputable)
      const fantasma = esAlta && draft && n.codigo === draft.codigo && !rows.some((r) => r.codigo === n.codigo);
      out.push(
        <div key={n.codigo} className={`pcm-row ${n.codigo === codigoActivo ? "sel" : ""} ${grupo ? "grp" : ""} ${depth === 0 ? "root" : ""} ${fantasma ? "ghost" : ""}`} onClick={() => seleccionar(n.codigo)}>
          <span className={`pcm-tog ${n.hijos.length ? (abierto ? "open" : "") : "leaf"}`}
                onClick={(e) => { if (n.hijos.length) { e.stopPropagation(); toggle(n.codigo); } }}>›</span>
          <span className={`pcm-dot ${(c?.tipo) || rubroDeRaiz(n.codigo)}`} />
          <span className="pcm-nm">{c ? c.nombre : <span className="muted">sin nombre</span>}</span>
          <button className="pcm-add" title="Agregar subcuenta" onClick={(e) => { e.stopPropagation(); nuevaBajo(n.codigo); }}>＋</button>
          <span className="pcm-code num">{n.codigo}</span>
        </div>
      );
      if (n.hijos.length && abierto) out.push(<div key={n.codigo + "-k"} className="pcm-kids">{ramas(n.hijos, depth + 1)}</div>);
    }
    return out;
  };

  const d = draft;
  const creandoGrupo = esAlta && !!sel && !rows.some((c) => c.codigo === sel);   // nombrando una rama del árbol

  return (
    <div className="pcm">
      <div className="pcm-head">
        <div>
          <h1 style={{ margin: 0 }}>Plan de cuentas</h1>
          <p className="muted" style={{ margin: "2px 0 0" }}>Árbol de cuentas con datos, imputación y saldos. {rows.length} cuentas.</p>
        </div>
        <span style={{ flex: 1 }} />
        <button className="btn-ghost" onClick={restaurar} title="Agrega sólo las cuentas base que usa el motor de asientos.">↺ Restaurar base</button>
        <button onClick={cargarEstandar} title="Puebla el plan con un chart de cuentas estándar.">＋ Cargar plan estándar</button>
      </div>

      <div className="pcm-tabs">
        <span className="pcm-emp-lbl">Empresa / plan:</span>
        {empresas.map((e) => (
          <button key={e.id} className={`pcm-tab ${empActiva === e.id ? "on" : ""}`} onClick={() => cambiarEmpresa(e.id)}
            title={e.predeterminada ? "Empresa predeterminada" : "Cambiar a esta empresa"}>
            {e.codigo}{e.predeterminada ? " ★" : ""}
          </button>
        ))}
        <button className="pcm-tab pcm-emp-nueva" onClick={nuevaEmpresa} title="Crear otra empresa con su propio plan">＋ empresa</button>
      </div>

      <div className="pcm-grid">
        {/* ── Árbol ── */}
        <div className="card" style={{ padding: 0 }}>
          <div className="pcm-tb">
            <label className="pcm-search">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></svg>
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por código o nombre…" />
            </label>
            <span className="pcm-tbg-lbl">Editar</span>
            <div className="pcm-tbg" role="group" aria-label="Editar">
              <button className="pcm-ic" title="Agregar cuenta (hermana)" onClick={nuevaHermana}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 6h10M4 12h10M4 18h6M18 15v6M15 18h6"/></svg>
              </button>
              <button className="pcm-ic" title="Agregar subcuenta" disabled={!sel} onClick={() => sel && nuevaBajo(sel)}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 6h16M8 12h12M8 18h8M4 12v7"/></svg>
              </button>
              <button className="pcm-ic danger" title="Eliminar cuenta" disabled={!cuentaSel || cuentaSel.base || cuentaSel.en_uso} onClick={borrar}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 7h16M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13"/></svg>
              </button>
              <button className="pcm-ic" title="Duplicar" disabled={!cuentaSel} onClick={duplicar}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/></svg>
              </button>
            </div>
          </div>
          <div className="pcm-tree">
            {filas.length ? ramas(arbol) : <p className="muted" style={{ padding: 16, textAlign: "center" }}>Sin cuentas.</p>}
          </div>
        </div>

        {/* ── Detalle ── */}
        <div className="card">
          {!d ? (
            <div className="pcm-detail">
              <div className="pcm-empty"><b>Elegí una cuenta</b><p className="muted">Seleccioná una cuenta del árbol para ver y editar sus datos, o creá una nueva con ＋.</p></div>
            </div>
          ) : (
            <>
              <div className="pcm-dh">
                <div><div className="eyebrow">{esAlta ? (creandoGrupo ? "Nombrar rama" : "Nueva cuenta") : "Datos de la cuenta"}</div>
                  <div className="pcm-crumb">{path(d.codigo).map((p, i, a) => <span key={p}>{i === a.length - 1 ? <b>{d.nombre || d.codigo}</b> : <>{rows.find((c) => c.codigo === p)?.nombre || p}<span className="sep"> › </span></>}</span>)}</div>
                </div>
                <span className={`pcm-chip ${d.tipo}`}>{RUBRO_LBL[d.tipo] || d.tipo}</span>
              </div>
              <div className="pcm-detail">
                {err && <div className="cfgc-err" style={{ marginBottom: 12 }}>{err}</div>}
                <div className="pcm-fgrid">
                  <div className="pcm-fld"><label>Código <span className="req">*</span></label>
                    <input className="num" value={d.codigo} maxLength={12} disabled={(!esAlta && d.base) || creandoGrupo}
                           onChange={(e) => setD({ codigo: e.target.value })} placeholder="1.1.1" />
                    {creandoGrupo ? <span className="hint">código de la rama (fijo)</span>
                      : (!esAlta && d.base && <span className="hint">cuenta base: el código no se cambia</span>)}</div>
                  <div className="pcm-fld"><label>Alias</label><input value={d.alias} maxLength={40} onChange={(e) => setD({ alias: e.target.value })} placeholder="opcional" /></div>
                  <div className="pcm-fld col2"><label>Nombre <span className="req">*</span></label>
                    <input ref={nombreRef} value={d.nombre} maxLength={80} onChange={(e) => setD({ nombre: e.target.value })} placeholder="ej. Caja y bancos" /></div>
                  <div className="pcm-fld col2"><label>Descripción</label>
                    <textarea value={d.descripcion} rows={2} onChange={(e) => setD({ descripcion: e.target.value })} placeholder="Detalle o uso de la cuenta…" /></div>
                  <div className="pcm-fld"><label>Rubro</label>
                    <select value={d.tipo} onChange={(e) => setD({ tipo: e.target.value })}>{RUBROS.map((t) => <option key={t} value={t}>{RUBRO_LBL[t]}</option>)}</select></div>
                  <div className="pcm-fld"><label>Tipo</label>
                    <select value={d.clasificacion} onChange={(e) => setD({ clasificacion: e.target.value })}>{CLASES.map((t) => <option key={t}>{t}</option>)}</select></div>
                  <div className="pcm-fld"><label>Moneda</label>
                    <select value={d.moneda} onChange={(e) => setD({ moneda: e.target.value })}>{MONEDAS.map((m) => <option key={m}>{m}</option>)}</select></div>
                  <div className="pcm-fld"><label>Saldo normal</label>
                    <div className="pcm-seg">
                      {["deudor", "acreedor"].map((s) => <button key={s} type="button" className={d.saldo_normal === s ? "on" : ""} onClick={() => setD({ saldo_normal: s })}>{s[0].toUpperCase() + s.slice(1)}</button>)}
                    </div></div>
                  <div className="pcm-fld col2">
                    <div className="pcm-switches">
                      <button type="button" className={`pcm-sw ${d.imputable ? "on" : ""}`} onClick={() => setD({ imputable: !d.imputable })}>
                        <span className="tr" /><span className="tx">Imputable<small>Recibe asientos</small></span></button>
                      <button type="button" className={`pcm-sw ${d.manual ? "on" : ""}`} onClick={() => setD({ manual: !d.manual })}>
                        <span className="tr" /><span className="tx">Carga manual<small>Editable a mano</small></span></button>
                    </div></div>
                </div>

                <div className="pcm-sec"><span className="t">Entidades relacionadas</span><span className="line" /><button className="pcm-btnsm" onClick={addEnt}>＋ Agregar</button></div>
                {(d.entidades || []).length === 0
                  ? <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>Sin entidades vinculadas a esta cuenta.</p>
                  : <table className="pcm-ent">
                      <thead><tr><th style={{ width: "38%" }}>Tipo</th><th>Entidad</th><th style={{ width: 34 }} /></tr></thead>
                      <tbody>{d.entidades.map((e, i) => (
                        <tr key={i}>
                          <td><input value={e.tipo} placeholder="Banco / Cliente…" onChange={(ev) => setEnt(i, { tipo: ev.target.value })} /></td>
                          <td><input value={e.entidad} placeholder="Nombre de la entidad" onChange={(ev) => setEnt(i, { entidad: ev.target.value })} /></td>
                          <td><button className="pcm-ic danger" onClick={() => delEnt(i)} aria-label="Quitar">✕</button></td>
                        </tr>))}</tbody>
                    </table>}
              </div>
              <div className="pcm-df">
                <span className="pcm-status">{esAlta ? (creandoGrupo ? "Nombrar rama" : "Nueva cuenta") : `${d.codigo} · ${d.imputable ? "imputable" : "agrupación"}`}{dirty ? " · sin guardar" : ""}</span>
                <span style={{ flex: 1 }} />
                {!esAlta && cuentaSel && <button className="btn-ghost" onClick={duplicar} title="Crear una copia de esta cuenta">Duplicar</button>}
                {!esAlta && cuentaSel && <button className="btn-ghost pcm-del" disabled={cuentaSel.base || cuentaSel.en_uso} onClick={borrar}
                  title={cuentaSel.base ? "Cuenta base del sistema" : cuentaSel.en_uso ? "Tiene asientos" : "Borrar cuenta"}>Eliminar</button>}
                <button className="btn-ghost" disabled={!dirty && !esAlta} onClick={descartar}>Descartar</button>
                <button className="btn primary" disabled={guardando || !dirty} onClick={guardar}>{guardando ? "Guardando…" : "Guardar cambios"}</button>
              </div>
            </>
          )}
        </div>
      </div>

      <style>{`
        .pcm-head { display:flex; align-items:flex-start; gap:10px; margin-bottom:14px; flex-wrap:wrap; }
        .pcm-tabs { display:inline-flex; gap:4px; background:var(--surface-2); border:1px solid var(--border); padding:4px; border-radius:11px; margin-bottom:14px; }
        .pcm-tab { border:0; background:transparent; color:var(--ink-soft); font:inherit; font-size:12.5px; font-weight:600; padding:7px 14px; border-radius:8px; cursor:pointer; white-space:nowrap; }
        .pcm-tab.on { background:var(--surface); color:var(--ink); box-shadow:0 1px 2px rgba(16,24,40,.14); }
        .pcm-tabs { flex-wrap:wrap; align-items:center; }
        .pcm-emp-lbl { font-size:11px; text-transform:uppercase; letter-spacing:.04em; color:var(--ink-faint); font-weight:700; padding:0 6px 0 4px; }
        .pcm-emp-nueva { color:var(--brand-2); }
        .pcm-grid { display:grid; grid-template-columns:minmax(300px,1fr) minmax(340px,1.05fr); gap:16px; align-items:start; }
        .pcm-tb { display:flex; align-items:center; gap:10px; padding:11px 13px; border-bottom:1px solid var(--border); }
        .pcm-search { flex:1; min-width:110px; display:flex; align-items:center; gap:8px; background:var(--surface-2); border:1px solid var(--border); border-radius:10px; padding:0 10px; }
        .pcm-search svg { width:15px; height:15px; color:var(--ink-faint); flex:none; }
        .pcm-search input { flex:1; border:0; background:transparent; color:var(--ink); font:inherit; font-size:13px; padding:9px 0; outline:none; }
        .pcm-tbg-lbl { font-size:11px; text-transform:uppercase; letter-spacing:.05em; color:var(--ink-faint); font-weight:700; }
        .pcm-tbg { display:flex; gap:3px; background:var(--surface-2); border:1px solid var(--border); border-radius:10px; padding:3px; }
        .pcm-ic { width:31px; height:31px; border:0; background:transparent; border-radius:7px; color:var(--ink-soft); cursor:pointer; display:grid; place-items:center; }
        .pcm-ic svg { width:17px; height:17px; }
        .pcm-ic:hover:not(:disabled) { background:var(--surface); color:var(--brand-2); }
        .pcm-ic.danger:hover:not(:disabled) { color:var(--crit); }
        .pcm-ic:disabled { opacity:.4; cursor:default; }
        .pcm-tree { padding:8px 6px 12px; max-height:600px; overflow:auto; }
        .pcm-kids { margin-left:16px; border-left:1px dashed var(--border-strong); padding-left:5px; }
        .pcm-row { display:flex; align-items:center; gap:7px; padding:6px 8px; border-radius:9px; cursor:pointer; position:relative; }
        .pcm-row:hover { background:var(--surface-2); }
        .pcm-row.sel { background:var(--accent-soft); }
        .pcm-row.sel::before { content:""; position:absolute; left:-1px; top:5px; bottom:5px; width:3px; border-radius:3px; background:var(--brand); }
        .pcm-tog { width:16px; flex:none; color:var(--ink-faint); cursor:pointer; font-size:12px; line-height:1; text-align:center; transition:transform .12s; user-select:none; }
        .pcm-tog.open { transform:rotate(90deg); }
        .pcm-tog.leaf { visibility:hidden; cursor:default; }
        .pcm-tog:hover:not(.leaf) { color:var(--ink); }
        .pcm-dot { width:9px; height:9px; border-radius:3px; flex:none; background:var(--ink-faint); }
        .pcm-dot.activo { background:var(--r-activo); } .pcm-dot.ingreso { background:var(--r-ingreso); }
        .pcm-dot.pasivo { background:var(--r-pasivo); } .pcm-dot.egreso { background:var(--r-egreso); } .pcm-dot.patrimonio { background:var(--r-patrimonio); }
        .pcm-nm { font-size:13.5px; color:var(--ink); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
        .pcm-row.grp .pcm-nm { font-weight:600; }
        .pcm-row.root .pcm-nm { font-weight:700; text-transform:uppercase; letter-spacing:.02em; }
        .pcm-row.ghost .pcm-nm { font-style:italic; color:var(--brand-2); }
        .pcm-add { margin-left:auto; width:21px; height:21px; flex:none; border:0; background:transparent; color:var(--ink-faint); cursor:pointer; border-radius:6px; font-size:13px; line-height:1; opacity:0; transition:opacity .1s; }
        .pcm-row:hover .pcm-add { opacity:1; } .pcm-add:hover { background:var(--surface); color:var(--brand-2); }
        .pcm-code { font-size:11.5px; color:var(--ink-faint); padding-left:10px; }
        .pcm-chip { display:inline-flex; align-items:center; font-size:10.5px; font-weight:700; padding:3px 9px; border-radius:999px; text-transform:uppercase; letter-spacing:.03em; }
        .pcm-chip.activo { background:var(--r-activo-soft); color:var(--r-activo); }
        .pcm-chip.pasivo { background:var(--r-pasivo-soft); color:var(--r-pasivo); }
        .pcm-chip.patrimonio { background:var(--r-patrimonio-soft); color:var(--r-patrimonio); }
        .pcm-chip.ingreso { background:var(--r-ingreso-soft); color:var(--r-ingreso); }
        .pcm-chip.egreso { background:var(--r-egreso-soft); color:var(--r-egreso); }
        .pcm-dh { display:flex; align-items:center; gap:10px; padding:14px 16px; border-bottom:1px solid var(--border); }
        .pcm-crumb { font-size:12px; color:var(--ink-faint); margin-top:2px; } .pcm-crumb b { color:var(--ink); } .pcm-crumb .sep { opacity:.5; }
        .pcm-detail { padding:16px; }
        .pcm-empty { text-align:center; padding:36px 20px; display:flex; flex-direction:column; align-items:center; gap:8px; }
        .pcm-empty b { font-size:15px; }
        .pcm-fgrid { display:grid; grid-template-columns:1fr 1fr; gap:12px 14px; }
        .pcm-fld { display:flex; flex-direction:column; gap:5px; min-width:0; } .pcm-fld.col2 { grid-column:span 2; }
        .pcm-fld label { font-size:11px; font-weight:600; color:var(--ink-soft); text-transform:uppercase; letter-spacing:.04em; }
        .pcm-fld input, .pcm-fld select, .pcm-fld textarea { margin-bottom:0; }
        .pcm-fld textarea { resize:vertical; }
        .pcm-seg { display:inline-flex; background:var(--surface-2); border:1px solid var(--border-strong); border-radius:9px; padding:3px; gap:2px; }
        .pcm-seg button { border:0; background:transparent; font:inherit; font-size:12.5px; font-weight:600; color:var(--ink-soft); padding:7px 14px; border-radius:7px; cursor:pointer; }
        .pcm-seg button.on { background:var(--surface); color:var(--brand-2); box-shadow:0 1px 2px rgba(16,24,40,.12); }
        .pcm-switches { display:flex; gap:28px; flex-wrap:wrap; padding-top:4px; }
        .pcm-sw { display:flex; align-items:center; gap:10px; cursor:pointer; border:0; background:transparent; padding:0; }
        .pcm-sw .tr { width:38px; height:22px; border-radius:999px; background:var(--border-strong); position:relative; transition:background .16s; flex:none; }
        .pcm-sw .tr::after { content:""; position:absolute; top:2px; left:2px; width:17px; height:17px; border-radius:50%; background:#fff; box-shadow:0 1px 2px rgba(0,0,0,.35); transition:transform .16s; }
        .pcm-sw.on .tr { background:var(--brand); } .pcm-sw.on .tr::after { transform:translateX(16px); }
        .pcm-sw .tx { font-size:12.5px; color:var(--ink); font-weight:600; text-align:left; } .pcm-sw .tx small { display:block; font-weight:400; color:var(--ink-faint); font-size:11px; }
        .pcm-sec { display:flex; align-items:center; gap:10px; margin:20px 0 10px; }
        .pcm-sec .t { font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:var(--brand-2); font-weight:700; }
        .pcm-sec .line { flex:1; height:1px; background:var(--border); }
        .pcm-btnsm { border:1px solid var(--border-strong); background:var(--surface); color:var(--ink-soft); font:inherit; font-size:12px; font-weight:600; padding:5px 11px; border-radius:8px; cursor:pointer; }
        .pcm-btnsm:hover { border-color:var(--brand-2); color:var(--brand-2); }
        .pcm-ent { width:100%; border-collapse:collapse; font-size:13px; }
        .pcm-ent th { text-align:left; font-size:10.5px; text-transform:uppercase; letter-spacing:.04em; color:var(--ink-faint); font-weight:700; padding:4px 6px; }
        .pcm-ent td { padding:3px 6px; } .pcm-ent input { margin:0; width:100%; }
        .pcm-df { display:flex; align-items:center; gap:10px; padding:12px 16px; border-top:1px solid var(--border); background:var(--surface-2); flex-wrap:wrap; }
        .pcm-status { font-size:12px; color:var(--ink-faint); }
        .req { color:var(--crit); }
        @media (max-width:820px){ .pcm-grid { grid-template-columns:1fr; } .pcm-fgrid { grid-template-columns:1fr; } .pcm-fld.col2 { grid-column:span 1; } }
      `}</style>
    </div>
  );
}
