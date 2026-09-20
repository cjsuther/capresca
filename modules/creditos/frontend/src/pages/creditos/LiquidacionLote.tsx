import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";
import { useNivelActual } from "../../permisos";
import { confirmar, avisar } from "../../ui/dialog";

// Liquidación de préstamos por lote (H-135): los contratos originados quedan A_LIQUIDAR y se liquidan
// agrupados por DÍA de originación; al liquidar el lote pasan a desembolso (respeta el workflow).
const money = (n: number) =>
  isFinite(n) ? new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 }).format(n) : "—";
const fecha = (s: string) => new Date(s + "T00:00:00").toLocaleDateString("es-AR");

type Contrato = { id: string; numero: string; cliente: string; producto: string; monto: number; plazo: number; pendienteAprobacion?: boolean };
type Lote = { fecha: string; cantidad: number; montoTotal: number; pendientes?: number; contratos: Contrato[] };

export default function LiquidacionLote() {
  const { soloLectura } = useNivelActual();
  const [lotes, setLotes] = useState<Lote[]>([]);
  const [sel, setSel] = useState<Lote | null>(null);
  const [err, setErr] = useState("");
  const [cargando, setCargando] = useState(true);
  const [liquidando, setLiquidando] = useState(false);

  const cargar = async () => {
    setErr(""); setCargando(true);
    try {
      const d = await api.ctoLotesLiquidacion();
      setLotes(d.items);
      setSel((prev) => (prev ? d.items.find((l: Lote) => l.fecha === prev.fecha) || null : null));
    } catch (e: any) { setErr(e.message || String(e)); }
    finally { setCargando(false); }
  };
  useEffect(() => { cargar(); }, []);

  async function liquidar(l: Lote) {
    if (!(await confirmar({ titulo: "Liquidar lote", confirmar: "Liquidar", mensaje: `Liquidar el lote del ${fecha(l.fecha)}: ${l.cantidad} crédito(s) por ${money(l.montoTotal)}.\n\nCada crédito pasa a desembolso (si el workflow lo exige, queda pendiente de aprobación). ¿Confirmás?` }))) return;
    setLiquidando(true);
    try {
      const r = await api.ctoLiquidarLote(l.fecha);
      const partes = [`Desembolsados: ${r.desembolsados.length}`];
      if (r.pendientesAprobacion.length) partes.push(`Pendientes de aprobación: ${r.pendientesAprobacion.length}`);
      if (r.errores.length) partes.push(`Con error: ${r.errores.length}`);
      avisar(`Lote del ${fecha(l.fecha)} procesado.\n${partes.join(" · ")}`);
      await cargar();
    } catch (e: any) { avisar({ tipo: "error", mensaje: e.message || String(e) }); }
    finally { setLiquidando(false); }
  }

  const colsLotes: Col[] = [
    { key: "fecha", label: "Día de originación", sortable: true, render: (l) => <b>{fecha(l.fecha)}</b> },
    { key: "cantidad", label: "Créditos", align: "right", sortable: true, render: (l) => <span className="num">{l.cantidad}</span> },
    { key: "montoTotal", label: "Monto a liquidar", align: "right", sortable: true, render: (l) => <span className="num">{money(l.montoTotal)}</span> },
    { key: "estado", label: "Estado", render: (l) => l.pendientes
      ? <span className="pill crit">{l.pendientes} esperando aprobación</span>
      : <span className="pill warn">A liquidar</span> },
  ];
  const colsCtos: Col[] = [
    { key: "numero", label: "N° contrato", render: (c) => <b>{c.numero}</b> },
    { key: "cliente", label: "Cliente" },
    { key: "producto", label: "Producto" },
    { key: "plazo", label: "Plazo", align: "right", render: (c) => <span className="num">{c.plazo}</span> },
    { key: "monto", label: "Monto", align: "right", render: (c) => <span className="num">{money(c.monto)}</span> },
    { key: "estado", label: "Estado", render: (c) => c.pendienteAprobacion
      ? <span className="pill crit">Esperando aprobación</span>
      : <span className="pill warn">A liquidar</span> },
  ];

  return (
    <>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 14, flexWrap: "wrap", marginBottom: 16 }}>
        <div>
          <h1 style={{ margin: 0 }}>Liquidación por lote</h1>
          <p className="muted" style={{ margin: 0 }}>Créditos originados pendientes de liquidar, agrupados por día. Al liquidar el lote pasan a desembolso.</p>
        </div>
      </div>

      {err && <p className="error">{err}</p>}

      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--border)", fontSize: 13, color: "var(--ink-soft)" }}>
          {cargando ? "Cargando…" : lotes.length ? `${lotes.length} lote(s) pendientes` : "No hay créditos pendientes de liquidar."}
        </div>
        <div style={{ padding: "4px 14px 14px" }}>
          <DataTable columns={colsLotes} rows={lotes} rowKey={(l) => l.fecha} clientSort defaultSort="fecha"
            rowStyle={(l) => (sel && l.fecha === sel.fecha ? { background: "var(--accent-soft)" } : undefined)}
            actions={(l) => [{ label: "Ver contratos", onClick: () => setSel(l) }]}
            emptyText="No hay créditos pendientes de liquidar." />
        </div>
      </div>

      {sel && (
        <div className="liq-ov" onMouseDown={(e) => { if (e.target === e.currentTarget) setSel(null); }}>
          <div className="liq-modal">
            <div className="liq-mh">
              <div>
                <div className="eyebrow">Lote del {fecha(sel.fecha)}</div>
                <b style={{ fontSize: 15 }}>{sel.cantidad} crédito(s) · {money(sel.montoTotal)}</b>
              </div>
              <button className="liq-x" onClick={() => setSel(null)} aria-label="Cerrar">✕</button>
            </div>
            <div className="liq-body">
              {!!sel.pendientes && (
                <p className="cfgc-err" style={{ marginTop: 0 }}>
                  {sel.pendientes} crédito(s) de este lote ya están esperando la aprobación del desembolso (workflow).
                  Se desembolsan cuando se aprueban en el Inbox de aprobaciones; volver a liquidar no los duplica.
                </p>
              )}
              <DataTable columns={colsCtos} rows={sel.contratos} rowKey={(c) => c.id} clientSort defaultSort="numero" />
            </div>
            <div className="liq-mf">
              <button className="btn-ghost" onClick={() => setSel(null)}>Cerrar</button>
              <div style={{ flex: 1 }} />
              <button className="primary" disabled={soloLectura || liquidando || !sel.cantidad}
                onClick={() => liquidar(sel)}>{liquidando ? "Liquidando…" : `💸 Liquidar lote (${sel.cantidad}) → desembolso`}</button>
            </div>
          </div>
          <style>{`
            .liq-ov { position:fixed; inset:0; background:rgba(16,24,40,.45); z-index:40; display:flex; align-items:center; justify-content:center; padding:16px; }
            .liq-modal { width:min(820px,96vw); max-height:92vh; overflow:hidden; background:var(--surface); border:1px solid var(--border); border-radius:14px; box-shadow:0 24px 70px -20px rgba(16,32,64,.55); display:flex; flex-direction:column; }
            .liq-mh { display:flex; align-items:center; gap:10px; padding:14px 18px; border-bottom:1px solid var(--border); }
            .liq-mh .liq-x { margin-left:auto; width:32px; height:32px; border-radius:8px; border:1px solid var(--border); background:var(--surface); cursor:pointer; color:var(--ink-soft); font-size:16px; }
            .liq-body { padding:14px 18px; overflow-y:auto; }
            .liq-mf { display:flex; gap:10px; align-items:center; padding:12px 18px; border-top:1px solid var(--border); background:var(--surface-2); }
          `}</style>
        </div>
      )}
    </>
  );
}
