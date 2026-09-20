import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import { avisar } from "../../ui/dialog";

// Parametrización contable: qué cuenta del plan imputa cada EVENTO de una operación (otorgamiento,
// cobranza de capital/interés/IVA…). Editable — así se "asigna un asiento a una operación" sin tocar código.

type Cuenta = { codigo: string; nombre: string; imputable: boolean };
type Imp = { id: number; clave: string; grupo: string; descripcion: string; cuenta_codigo: string; cuenta_nombre: string };

export default function Imputaciones() {
  const [rows, setRows] = useState<Imp[]>([]);
  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState<number | null>(null);

  const cargar = () => api.imputaciones().then(setRows).catch((e) => setError(e.message || String(e)));
  useEffect(() => { cargar(); api.planCuentas().then((cs: Cuenta[]) => setCuentas(cs.filter((c) => c.imputable))).catch(() => {}); }, []);

  const grupos = useMemo(() => {
    const g: Record<string, Imp[]> = {};
    for (const r of rows) (g[r.grupo] = g[r.grupo] || []).push(r);
    return g;
  }, [rows]);

  async function cambiar(imp: Imp, codigo: string) {
    if (!codigo || codigo === imp.cuenta_codigo) return;
    setGuardando(imp.id); setError("");
    try {
      const r = await api.editarImputacion(imp.id, codigo);
      setRows((rs) => rs.map((x) => x.id === imp.id ? { ...x, cuenta_codigo: r.cuenta_codigo, cuenta_nombre: r.cuenta_nombre } : x));
      avisar("Imputación actualizada.");
    } catch (e: any) { avisar({ tipo: "error", mensaje: e.message || String(e) }); }
    finally { setGuardando(null); }
  }

  return (
    <div className="imp">
      <div className="imp-head">
        <h1 style={{ margin: 0 }}>Parametrización contable</h1>
        <p className="muted" style={{ margin: "2px 0 0" }}>Asigná qué cuenta del plan imputa cada evento de las operaciones. Los asientos automáticos usan esta configuración.</p>
      </div>

      {error && <p className="error">{error}</p>}

      {Object.entries(grupos).map(([grupo, items]) => (
        <div className="card imp-card" key={grupo}>
          <div className="imp-gh">{grupo}</div>
          {items.map((imp) => (
            <div className="imp-row" key={imp.id}>
              <div className="imp-desc">
                <span className="imp-lbl">{imp.descripcion}</span>
                <span className="imp-clave num">{imp.clave}</span>
              </div>
              <div className="imp-cta">
                <select value={imp.cuenta_codigo} disabled={guardando === imp.id} onChange={(e) => cambiar(imp, e.target.value)}>
                  {!cuentas.some((c) => c.codigo === imp.cuenta_codigo) && <option value={imp.cuenta_codigo}>{imp.cuenta_codigo} · {imp.cuenta_nombre}</option>}
                  {cuentas.map((c) => <option key={c.codigo} value={c.codigo}>{c.codigo} · {c.nombre}</option>)}
                </select>
              </div>
            </div>
          ))}
        </div>
      ))}
      {rows.length === 0 && !error && <p className="muted">Cargando…</p>}

      <style>{`
        .imp-head { margin-bottom:14px; }
        .imp-card { padding:0; margin-bottom:14px; overflow:hidden; }
        .imp-gh { padding:11px 16px; border-bottom:1px solid var(--border); background:var(--surface-2); font-size:11px; text-transform:uppercase; letter-spacing:.05em; font-weight:800; color:var(--brand-2); }
        .imp-row { display:flex; align-items:center; gap:14px; padding:11px 16px; border-bottom:1px solid var(--border); flex-wrap:wrap; }
        .imp-row:last-child { border-bottom:0; }
        .imp-desc { flex:1; min-width:200px; display:flex; flex-direction:column; gap:2px; }
        .imp-lbl { font-size:13.5px; color:var(--ink); font-weight:600; }
        .imp-clave { font-size:11px; color:var(--ink-faint); }
        .imp-cta { min-width:280px; }
        .imp-cta select { margin:0; width:100%; }
      `}</style>
    </div>
  );
}
