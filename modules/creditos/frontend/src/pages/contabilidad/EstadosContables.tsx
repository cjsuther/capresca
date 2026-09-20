import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

// Reportes contables armados desde los asientos + rubros del plan: sumas y saldos (balance de
// comprobación), situación patrimonial (Activo = Pasivo + PN) y estado de resultados (Ingresos − Egresos).

const money = (v: any) => Number(v || 0).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const RUBRO_PILL: Record<string, string> = { activo: "ok", pasivo: "warn", patrimonio: "brand", ingreso: "ok", egreso: "crit" };
type Vista = "sumas" | "situacion" | "resultados" | "centros" | "flujo";

export default function EstadosContables() {
  const [vista, setVista] = useState<Vista>("situacion");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [sys, setSys] = useState<any>(null);
  const [est, setEst] = useState<any>(null);
  const [cen, setCen] = useState<any>(null);
  const [flu, setFlu] = useState<any>(null);
  const [error, setError] = useState("");

  const cargar = () => {
    setError("");
    api.sumasYSaldos(desde, hasta).then(setSys).catch((e) => setError(e.message || String(e)));
    api.estadosContables(desde, hasta).then(setEst).catch((e) => setError(e.message || String(e)));
    api.porCentro(desde, hasta).then(setCen).catch(() => {});
    api.flujoEfectivo(desde, hasta).then(setFlu).catch(() => {});
  };
  useEffect(() => { cargar(); }, []);   // eslint-disable-line

  const cols: Col[] = [
    { key: "codigo", label: "Código", sortable: true, render: (f) => <span className="num">{f.codigo}</span> },
    { key: "nombre", label: "Cuenta", sortable: true },
    { key: "tipo", label: "Rubro", render: (f) => f.tipo ? <span className={`pill ${RUBRO_PILL[f.tipo] || "brand"}`}>{f.tipo[0].toUpperCase() + f.tipo.slice(1)}</span> : "—" },
    { key: "debe", label: "Debe", align: "right", render: (f) => <span className="num">{Number(f.debe) ? money(f.debe) : "—"}</span> },
    { key: "haber", label: "Haber", align: "right", render: (f) => <span className="num">{Number(f.haber) ? money(f.haber) : "—"}</span> },
    { key: "saldo_deudor", label: "Saldo deudor", align: "right", render: (f) => <span className="num">{Number(f.saldo_deudor) ? money(f.saldo_deudor) : "—"}</span> },
    { key: "saldo_acreedor", label: "Saldo acreedor", align: "right", render: (f) => <span className="num">{Number(f.saldo_acreedor) ? money(f.saldo_acreedor) : "—"}</span> },
  ];

  const sit = est?.situacion; const res = est?.resultados;
  const Grupo = ({ titulo, cuentas, total, fuerte }: { titulo: string; cuentas: any[]; total: any; fuerte?: boolean }) => (
    <div className="est-grupo">
      <div className={`est-gh ${fuerte ? "on" : ""}`}><span>{titulo}</span><b className="num">{money(total)}</b></div>
      {(cuentas || []).map((c: any) => (
        <div className="est-ln" key={c.codigo}><span className="num est-cod">{c.codigo}</span><span className="est-nm">{c.nombre}</span><span className="num">{money(c.valor)}</span></div>
      ))}
      {(!cuentas || cuentas.length === 0) && <div className="est-ln muted">sin movimientos</div>}
    </div>
  );

  return (
    <div className="est">
      <div className="est-head">
        <div><h1 style={{ margin: 0 }}>Estados contables</h1>
          <p className="muted" style={{ margin: "2px 0 0" }}>Situación patrimonial, resultados y sumas y saldos desde los asientos.</p></div>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div className="est-tb">
          <div className="est-tabs">
            {([["situacion", "Situación patrimonial"], ["resultados", "Estado de resultados"], ["sumas", "Sumas y saldos"], ["centros", "Por centro de costo"], ["flujo", "Flujo de efectivo"]] as [Vista, string][])
              .map(([v, l]) => <button key={v} className={vista === v ? "on" : ""} onClick={() => setVista(v)}>{l}</button>)}
          </div>
          <span style={{ flex: 1 }} />
          <label className="est-f">Desde<input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} /></label>
          <label className="est-f">Hasta<input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></label>
          <button className="btn" onClick={cargar}>Actualizar</button>
          <button className="btn-ghost" title="Exportar la vista actual a Excel"
            onClick={() => (vista === "sumas" ? api.sumasYSaldosExcel(desde, hasta) : api.estadosContablesExcel(desde, hasta))}>⬇ Excel</button>
        </div>

        {error && <p className="error" style={{ margin: "10px 14px" }}>{error}</p>}

        {vista === "sumas" && sys && (
          <div style={{ padding: "6px 14px 14px" }}>
            <DataTable columns={cols} rows={sys.filas} rowKey={(f) => f.codigo} clientSort pageSize={100} defaultSort="codigo" emptyText="Sin movimientos contables" />
            <div className="est-tot">
              <span>Totales</span>
              <span className="num">Debe {money(sys.totales.debe)}</span>
              <span className="num">Haber {money(sys.totales.haber)}</span>
              <span className="num">S. deudor {money(sys.totales.saldo_deudor)}</span>
              <span className="num">S. acreedor {money(sys.totales.saldo_acreedor)}</span>
              <span className={`pill ${sys.balanceado ? "ok" : "crit"}`}>{sys.balanceado ? "✓ Balanceado" : "Descuadre"}</span>
            </div>
          </div>
        )}

        {vista === "situacion" && sit && (
          <div className="est-body est-2col">
            <div>
              <Grupo titulo="ACTIVO" cuentas={sit.activo.cuentas} total={sit.activo.total} fuerte />
            </div>
            <div>
              <Grupo titulo="PASIVO" cuentas={sit.pasivo.cuentas} total={sit.pasivo.total} fuerte />
              <Grupo titulo="PATRIMONIO NETO" cuentas={[...(sit.patrimonio.cuentas || []), { codigo: "—", nombre: "Resultado del ejercicio", valor: sit.patrimonio.resultado_ejercicio }]} total={sit.patrimonio.total} fuerte />
            </div>
            {sit.otros && sit.otros.cuentas.length > 0 && (
              <div style={{ gridColumn: "span 2" }}>
                <Grupo titulo="Otras cuentas (a clasificar)" cuentas={sit.otros.cuentas} total={sit.otros.total} />
                <p className="muted" style={{ fontSize: 12, margin: "2px 0 0" }}>Cuentas de asientos con códigos fuera del plan (sin rubro). Se muestran del lado del activo. Clasificalas en el Plan de cuentas para que caigan en su rubro.</p>
              </div>
            )}
            <div className="est-eq">
              <span>Activo <b className="num">{money(sit.total_activo)}</b></span>
              <span className="est-igual">=</span>
              <span>Pasivo + PN <b className="num">{money(sit.total_pasivo_pn)}</b></span>
              <span className={`pill ${sit.balanceado ? "ok" : "crit"}`}>{sit.balanceado ? "✓ Balancea" : "No balancea"}</span>
            </div>
          </div>
        )}

        {vista === "resultados" && res && (
          <div className="est-body">
            <Grupo titulo="INGRESOS" cuentas={res.ingresos.cuentas} total={res.ingresos.total} fuerte />
            <Grupo titulo="EGRESOS" cuentas={res.egresos.cuentas} total={res.egresos.total} fuerte />
            <div className={`est-resu ${Number(res.resultado) >= 0 ? "ok" : "no"}`}>
              <span>Resultado del ejercicio {Number(res.resultado) >= 0 ? "(ganancia)" : "(pérdida)"}</span>
              <b className="num">{money(res.resultado)}</b>
            </div>
          </div>
        )}

        {vista === "centros" && cen && (
          <div style={{ padding: "6px 14px 14px" }}>
            <DataTable columns={[
              { key: "codigo", label: "Centro", sortable: true, render: (f: any) => f.codigo ? <span className="num">{f.codigo}</span> : <span className="muted">—</span> },
              { key: "nombre", label: "Nombre", sortable: true },
              { key: "debe", label: "Debe", align: "right", render: (f: any) => <span className="num">{money(f.debe)}</span> },
              { key: "haber", label: "Haber", align: "right", render: (f: any) => <span className="num">{money(f.haber)}</span> },
              { key: "saldo", label: "Saldo", align: "right", render: (f: any) => <span className="num">{money(f.saldo)}</span> },
            ]} rows={cen.filas} rowKey={(f: any) => f.codigo || "sin"} clientSort pageSize={50} defaultSort="codigo" emptyText="Sin movimientos por centro" />
          </div>
        )}

        {vista === "flujo" && flu && (
          <div className="est-body">
            <div className="est-flu-cta muted">
              Efectivo: {(flu.cuentas_efectivo || []).map((c: any) => `${c.codigo} ${c.nombre}`).join(" · ") || "—"}
            </div>
            <div className="est-flu-ini"><span>Saldo inicial</span><b className="num">{money(flu.saldo_inicial)}</b></div>
            <Grupo titulo="ENTRADAS (orígenes)" cuentas={(flu.entradas || []).map((f: any) => ({ codigo: f.codigo, nombre: f.nombre, valor: f.monto }))} total={flu.total_entradas} fuerte />
            <Grupo titulo="SALIDAS (aplicaciones)" cuentas={(flu.salidas || []).map((f: any) => ({ codigo: f.codigo, nombre: f.nombre, valor: f.monto }))} total={flu.total_salidas} fuerte />
            <div className={`est-resu ${Number(flu.neto) >= 0 ? "ok" : "no"}`}>
              <span>Flujo neto del período {Number(flu.neto) >= 0 ? "(aumentó el efectivo)" : "(disminuyó el efectivo)"}</span>
              <b className="num">{money(flu.neto)}</b>
            </div>
            <div className="est-flu-fin"><span>Saldo final</span><b className="num">{money(flu.saldo_final)}</b></div>
          </div>
        )}
      </div>

      <style>{`
        .est-head { margin-bottom:14px; }
        .est-tb { display:flex; align-items:center; gap:10px; padding:11px 14px; border-bottom:1px solid var(--border); flex-wrap:wrap; }
        .est-tabs { display:inline-flex; gap:3px; background:var(--surface-2); border:1px solid var(--border); border-radius:10px; padding:3px; }
        .est-tabs button { border:0; background:transparent; font:inherit; font-size:12.5px; font-weight:600; color:var(--ink-soft); padding:7px 12px; border-radius:7px; cursor:pointer; }
        .est-tabs button.on { background:var(--surface); color:var(--ink); box-shadow:0 1px 2px rgba(16,24,40,.14); }
        .est-f { display:flex; flex-direction:column; gap:3px; font-size:11px; color:var(--ink-soft); font-weight:600; }
        .est-f input { margin:0; }
        .est-tot { display:flex; gap:16px; align-items:center; justify-content:flex-end; flex-wrap:wrap; padding:10px 4px 0; font-size:13px; border-top:1px solid var(--border); margin-top:6px; }
        .est-tot > span:first-child { font-weight:700; color:var(--ink-soft); margin-right:auto; text-transform:uppercase; font-size:11px; letter-spacing:.04em; }
        .est-body { padding:16px; }
        .est-2col { display:grid; grid-template-columns:1fr 1fr; gap:16px 24px; }
        .est-2col .est-eq { grid-column:span 2; }
        .est-grupo { margin-bottom:16px; }
        .est-gh { display:flex; justify-content:space-between; align-items:center; padding:8px 10px; border-radius:8px; background:var(--surface-2); font-size:12px; font-weight:800; text-transform:uppercase; letter-spacing:.04em; color:var(--ink); }
        .est-ln { display:flex; align-items:center; gap:10px; padding:5px 10px; border-bottom:1px solid var(--border); font-size:13px; }
        .est-cod { color:var(--ink-faint); font-size:11.5px; min-width:52px; }
        .est-nm { flex:1; } .est-ln > .num:last-child { font-variant-numeric:tabular-nums; }
        .est-eq { display:flex; align-items:center; gap:14px; justify-content:center; padding:12px; background:var(--surface-2); border-radius:10px; font-size:14px; flex-wrap:wrap; }
        .est-igual { font-size:20px; color:var(--ink-faint); }
        .est-resu { display:flex; justify-content:space-between; align-items:center; padding:12px 14px; border-radius:10px; font-size:15px; font-weight:700; }
        .est-resu.ok { background:var(--ok-soft); color:var(--ok); } .est-resu.no { background:var(--crit-soft); color:var(--crit); }
        .est-flu-cta { font-size:12px; margin-bottom:12px; }
        .est-flu-ini, .est-flu-fin { display:flex; justify-content:space-between; align-items:center; padding:10px 12px; border-radius:10px; background:var(--surface-2); font-size:14px; font-weight:600; margin-bottom:12px; }
        .est-flu-fin { margin-top:12px; margin-bottom:0; border:1px solid var(--border); }
        @media (max-width:760px){ .est-2col { grid-template-columns:1fr; } .est-2col .est-eq { grid-column:span 1; } }
      `}</style>
    </div>
  );
}
