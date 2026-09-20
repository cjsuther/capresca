import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";
import { avisar, confirmar } from "../../ui/dialog";

// Conciliación bancaria: coteja las líneas del extracto del banco contra los movimientos del mayor en la
// cuenta banco. Concilia manual (seleccionar extracto → vincular movimiento del mismo importe) o automática.
const money = (v: any) => Number(v || 0).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

type Ext = { id: number; fecha: string; descripcion: string; referencia: string; importe: number; conciliada: boolean };
type Mov = { asiento_linea_id: number; numero: number; fecha: string; concepto: string; importe: number; conciliada: boolean };

export default function Conciliacion() {
  const [cuenta, setCuenta] = useState("1.1.02");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [data, setData] = useState<any>(null);
  const [selExt, setSelExt] = useState<Ext | null>(null);
  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState({ fecha: "", descripcion: "", referencia: "", importe: "" });

  const cargar = () => {
    setError(""); setSelExt(null);
    api.conciliacion(cuenta, desde, hasta).then(setData).catch((e) => setError(e.message || String(e)));
  };
  useEffect(() => { cargar(); }, []);   // eslint-disable-line

  async function agregar() {
    if (!nuevo.fecha || !nuevo.importe) { avisar({ tipo: "error", mensaje: "Cargá al menos fecha e importe." }); return; }
    try {
      await api.crearExtracto({ cuenta_codigo: cuenta, fecha: nuevo.fecha, descripcion: nuevo.descripcion, referencia: nuevo.referencia, importe: Number(nuevo.importe) });
      setNuevo({ fecha: "", descripcion: "", referencia: "", importe: "" }); cargar();
    } catch (e: any) { avisar({ tipo: "error", mensaje: e.message || String(e) }); }
  }
  async function vincular(mov: Mov) {
    if (!selExt) { avisar("Primero seleccioná una línea del extracto."); return; }
    try { await api.conciliar(selExt.id, mov.asiento_linea_id); cargar(); }
    catch (e: any) { avisar({ tipo: "error", mensaje: e.message || String(e) }); }
  }
  async function desconciliar(e: Ext) { try { await api.desconciliar(e.id); cargar(); } catch (x: any) { avisar({ tipo: "error", mensaje: x.message }); } }
  async function borrar(e: Ext) {
    if (!(await confirmar({ mensaje: `¿Borrar la línea del extracto del ${e.fecha} por ${money(e.importe)}?`, danger: true }))) return;
    try { await api.borrarExtracto(e.id); cargar(); } catch (x: any) { avisar({ tipo: "error", mensaje: x.message }); }
  }
  async function automatica() {
    try { const r = await api.conciliarAutomatica(cuenta); avisar({ tipo: "ok", mensaje: `${r.conciliadas} par(es) conciliado(s) automáticamente.` }); cargar(); }
    catch (e: any) { avisar({ tipo: "error", mensaje: e.message || String(e) }); }
  }

  const estadoPill = (c: boolean) => c ? <span className="pill ok">Conciliada</span> : <span className="pill warn">Pendiente</span>;
  const impCell = (v: number) => <span className="num" style={{ color: Number(v) < 0 ? "var(--crit)" : "var(--ok)" }}>{money(v)}</span>;

  const colsExt: Col[] = [
    { key: "fecha", label: "Fecha", sortable: true, render: (f) => <span className="num">{f.fecha}</span> },
    { key: "descripcion", label: "Descripción", render: (f) => f.descripcion || <span className="muted">—</span> },
    { key: "importe", label: "Importe", align: "right", render: (f) => impCell(f.importe) },
    { key: "conciliada", label: "Estado", render: (f) => f.id === selExt?.id ? <span className="pill brand">Seleccionada</span> : estadoPill(f.conciliada) },
  ];
  const accExt = (e: Ext) => e.conciliada
    ? [{ label: "Desconciliar", icon: "rotate-ccw", onClick: () => desconciliar(e) }]
    : [{ label: e.id === selExt?.id ? "Quitar selección" : "Seleccionar para conciliar", icon: "check", onClick: () => setSelExt(e.id === selExt?.id ? null : e) },
       { label: "Borrar", icon: "trash-2", danger: true, onClick: () => borrar(e) }];

  const colsMov: Col[] = [
    { key: "fecha", label: "Fecha", sortable: true, render: (f) => <span className="num">{f.fecha}</span> },
    { key: "numero", label: "Asiento", render: (f) => <span className="num">N° {f.numero || "—"}</span> },
    { key: "concepto", label: "Concepto" },
    { key: "importe", label: "Importe", align: "right", render: (f) => impCell(f.importe) },
    { key: "conciliada", label: "Estado", render: (f) => estadoPill(f.conciliada) },
  ];
  const accMov = (m: Mov) => m.conciliada ? [] : [{ label: "Vincular al extracto seleccionado", icon: "link", onClick: () => vincular(m) }];

  const dif = Number(data?.diferencia || 0);
  return (
    <div className="conc">
      <div className="conc-head">
        <div><h1 style={{ margin: 0 }}>Conciliación bancaria</h1>
          <p className="muted" style={{ margin: "2px 0 0" }}>Cotejá el extracto del banco contra los movimientos del mayor. Importe con signo (+ ingreso / − egreso).</p></div>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div className="conc-tb">
          <label className="conc-f">Cuenta banco<input value={cuenta} onChange={(e) => setCuenta(e.target.value)} style={{ width: 90 }} /></label>
          <label className="conc-f">Desde<input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} /></label>
          <label className="conc-f">Hasta<input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></label>
          <button className="btn" onClick={cargar}>Actualizar</button>
          <span style={{ flex: 1 }} />
          <button className="btn primary" onClick={automatica} title="Concilia pares del mismo importe sin conciliar">⚡ Conciliar automática</button>
        </div>
        {error && <p className="error" style={{ margin: "10px 14px" }}>{error}</p>}

        {data && (
          <div className="conc-sum">
            <div><span className="conc-k">Saldo extracto</span><b className="num">{money(data.saldo_extracto)}</b></div>
            <div><span className="conc-k">Saldo mayor</span><b className="num">{money(data.saldo_mayor)}</b></div>
            <div><span className="conc-k">Diferencia</span><b className="num">{money(dif)}</b> <span className={`pill ${dif === 0 ? "ok" : "crit"}`}>{dif === 0 ? "✓ Cuadra" : "Descuadre"}</span></div>
            <div><span className="conc-k">Pendientes</span><b>{data.pendientes_extracto} extracto · {data.pendientes_mayor} mayor</b></div>
          </div>
        )}
      </div>

      {selExt && <div className="conc-sel">Conciliando el extracto del <b>{selExt.fecha}</b> por <b className="num">{money(selExt.importe)}</b> — elegí "Vincular" en un movimiento del mayor del mismo importe. <button className="btn-ghost" onClick={() => setSelExt(null)}>Cancelar</button></div>}

      <div className="conc-grid">
        <div className="card" style={{ padding: "4px 14px 14px" }}>
          <h3 className="conc-h3">Extracto bancario</h3>
          <div className="conc-alta">
            <input type="date" value={nuevo.fecha} onChange={(e) => setNuevo({ ...nuevo, fecha: e.target.value })} />
            <input placeholder="Descripción" value={nuevo.descripcion} onChange={(e) => setNuevo({ ...nuevo, descripcion: e.target.value })} />
            <input className="num" placeholder="Importe ±" value={nuevo.importe} onChange={(e) => setNuevo({ ...nuevo, importe: e.target.value })} style={{ width: 110 }} />
            <button className="btn" onClick={agregar}>＋ Agregar</button>
          </div>
          <DataTable columns={colsExt} rows={(data?.extracto || [])} rowKey={(f: Ext) => f.id} actions={accExt} clientSort pageSize={25} defaultSort="fecha" emptyText="Sin líneas de extracto" />
        </div>
        <div className="card" style={{ padding: "4px 14px 14px" }}>
          <h3 className="conc-h3">Movimientos del mayor (cuenta banco)</h3>
          <DataTable columns={colsMov} rows={(data?.mayor || [])} rowKey={(f: Mov) => f.asiento_linea_id} actions={accMov} clientSort pageSize={25} defaultSort="fecha" emptyText="Sin movimientos en la cuenta" />
        </div>
      </div>

      <style>{`
        .conc-head { margin-bottom:14px; }
        .conc-tb { display:flex; align-items:flex-end; gap:10px; padding:11px 14px; border-bottom:1px solid var(--border); flex-wrap:wrap; }
        .conc-f { display:flex; flex-direction:column; gap:3px; font-size:11px; color:var(--ink-soft); font-weight:600; }
        .conc-f input { margin:0; }
        .conc-sum { display:flex; gap:26px; flex-wrap:wrap; padding:12px 16px; }
        .conc-sum > div { display:flex; flex-direction:column; gap:3px; }
        .conc-k { font-size:11px; text-transform:uppercase; letter-spacing:.04em; color:var(--ink-faint); font-weight:700; }
        .conc-sel { margin-top:12px; padding:10px 14px; background:var(--brand-soft, var(--surface-2)); border:1px solid var(--brand-2); border-radius:10px; font-size:13px; display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
        .conc-sel .btn-ghost { margin-left:auto; }
        .conc-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:16px; }
        .conc-h3 { font-size:13px; margin:10px 2px; text-transform:uppercase; letter-spacing:.04em; color:var(--ink-soft); }
        .conc-alta { display:flex; gap:8px; margin-bottom:10px; flex-wrap:wrap; }
        .conc-alta input { margin:0; }
        @media (max-width:900px){ .conc-grid { grid-template-columns:1fr; } }
      `}</style>
    </div>
  );
}
