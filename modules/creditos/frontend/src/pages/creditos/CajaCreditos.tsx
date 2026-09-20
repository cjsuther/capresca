import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import { useNivelActual } from "../../permisos";
import { confirmar, pedirTexto } from "../../ui/dialog";

const money = (n: number) => "$" + (n || 0).toLocaleString("es-AR", { maximumFractionDigits: 2 });
const MEDIOS = ["EFECTIVO", "TRANSFERENCIA", "DEBITO", "CHEQUE"];

export default function CajaCreditos() {
  const { soloLectura } = useNivelActual();
  const [contratos, setContratos] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [cto, setCto] = useState<any>(null);
  const [medio, setMedio] = useState("EFECTIVO");
  const [recibo, setRecibo] = useState<any>(null);
  const [err, setErr] = useState("");

  const cargar = () => api.ctoListar().then((d) => setContratos(d.items || d)).catch((e) => setErr(String(e)));
  useEffect(() => { cargar(); }, []);

  const activos = useMemo(() => {
    const ql = q.toLowerCase();
    return contratos.filter((c) => c.estado === "ACTIVO" &&
      (!ql || (c.cliente_nombre || "").toLowerCase().includes(ql) || (c.numero_contrato || "").toLowerCase().includes(ql)));
  }, [contratos, q]);

  const abrir = async (c: any) => { setRecibo(null); setErr(""); try { setCto(await api.ctoObtener(c.id)); } catch (e: any) { setErr(e.message); } };
  const proxima = () => cto?.cuotas?.find((x: any) => x.estado === "PENDIENTE");

  const cobrar = async (tipo: string, importe = 0, modo?: string, cuotas?: number) => {
    if (!cto) return;
    setErr("");
    try {
      const r = await api.ctoActividadCaja(cto.id, tipo, importe, medio, modo, cuotas);
      const nuevo = await api.ctoObtener(cto.id);
      setCto(nuevo);
      const act = [...nuevo.actividades].reverse().find((a: any) => a.tipo === tipo && a.estado !== "REVERSADA");
      const asi = nuevo.asientos?.[nuevo.asientos.length - 1];
      setRecibo({ act, asi, cliente: nuevo.cliente_nombre, contrato: nuevo.numero_contrato });
      cargar();
    } catch (e: any) { setErr(e.message || String(e)); }
  };

  const cobrarCuota = () => cobrar("PAYMENT");
  const cobrarParcial = async () => { const v = Number(await pedirTexto({ titulo: "Cobro parcial", mensaje: "Importe del cobro parcial:", tipo: "number", requerido: true })); if (v > 0) cobrar("PAYMENT", v); };
  const adelantar = async () => { const n = Number(await pedirTexto({ titulo: "Adelantar cuotas", mensaje: "¿Cuántas cuotas adelantar (pagar de una)?", tipo: "number", requerido: true })); if (n > 1) cobrar("PAYMENT", 0, undefined, n); };
  const prepago = async () => {
    const v = Number(await pedirTexto({ titulo: "Prepago de capital", mensaje: "Prepago de capital — importe:", tipo: "number", requerido: true })); if (!v || v <= 0) return;
    const modo = (await confirmar({ titulo: "Prepago de capital", mensaje: "¿Cómo aplicar el prepago?", confirmar: "Baja de CUOTA", cancelar: "Baja de PLAZO" })) ? "BAJA_CUOTA" : "BAJA_PLAZO";
    cobrar("PARTIAL_PREPAYMENT", v, modo);
  };

  return (
    <div className="caja cfgc">
      <h1>Caja de créditos</h1>
      <p className="muted">Cobranza de contratos de la línea nueva. Elegí el contrato, el medio de pago y cobrá la cuota (total o parcial) o registrá un prepago. Cada cobro se asienta en el Libro Diario.</p>
      {err && <div className="cfgc-err" style={{ margin: "8px 0" }}>{err}</div>}

      <div className="caja-cols">
        <div className="caja-lista">
          <input placeholder="Buscar contrato o cliente…" value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="caja-scroll">
            {activos.map((c) => (
              <div key={c.id} className={"caja-item" + (cto?.id === c.id ? " on" : "")} onClick={() => abrir(c)}>
                <b>{c.numero_contrato}</b>
                <span>{c.cliente_nombre}</span>
                <small>saldo {money(c.saldo_capital)}</small>
              </div>
            ))}
            {activos.length === 0 && <p className="muted" style={{ padding: 10 }}>Sin contratos activos.</p>}
          </div>
        </div>

        <div className="caja-panel">
          {!cto ? <p className="muted">Elegí un contrato para cobrar.</p> : (
            <>
              <h3>{cto.numero_contrato} · {cto.cliente_nombre}</h3>
              <div className="caja-metrics">
                <div><small>Saldo capital</small><b>{money(cto.saldo_capital)}</b></div>
                <div><small>Próxima cuota</small><b>{proxima() ? `#${proxima().numero_cuota} · ${money(proxima().total)}` : "—"}</b></div>
                <div><small>Vence</small><b>{proxima()?.fecha_vencimiento || "—"}</b></div>
                <div><small>Ya pagado (cuota)</small><b>{money(proxima()?.pagado || 0)}</b></div>
              </div>

              <div className="caja-cobro">
                <label>Medio de pago
                  <select value={medio} onChange={(e) => setMedio(e.target.value)}>
                    {MEDIOS.map((m) => <option key={m} value={m}>{m}</option>)}
                  </select>
                </label>
                {soloLectura ? <span className="pill">🔒 Sólo lectura</span> : <>
                  <button className="btn primary" disabled={!proxima()} onClick={cobrarCuota}>Cobrar cuota</button>
                  <button className="btn" disabled={!proxima()} onClick={cobrarParcial}>Cobro parcial</button>
                  <button className="btn" disabled={!proxima()} onClick={adelantar}>Adelantar cuotas</button>
                  <button className="btn" onClick={prepago}>Prepago capital</button>
                </>}
              </div>

              {recibo && (
                <div className="caja-recibo">
                  <div className="caja-recibo-h">🧾 Recibo — {recibo.contrato}</div>
                  <div className="caja-recibo-b">
                    <div><span>Cliente</span><b>{recibo.cliente}</b></div>
                    <div><span>Operación</span><b>{recibo.act?.tipo}</b></div>
                    <div><span>Importe</span><b>{money(recibo.act?.importe || 0)}</b></div>
                    <div><span>Medio</span><b>{recibo.act?.dato?.medio_pago || medio}</b></div>
                    {recibo.act?.dato?.interes_punitorio > 0 && <div><span>Mora</span><b>{money(recibo.act.dato.interes_punitorio + (recibo.act.dato.iva_punitorio || 0))}</b></div>}
                    <div><span>Fecha</span><b>{recibo.act?.fecha}</b></div>
                  </div>
                  {recibo.asi && (
                    <table className="caja-asiento">
                      <thead><tr><th>Cuenta</th><th>Debe</th><th>Haber</th></tr></thead>
                      <tbody>{recibo.asi.lineas.map((l: any, i: number) => (
                        <tr key={i}><td>{l.cuenta}{l.nombre ? ` · ${l.nombre}` : ""}</td><td className="num">{l.debe ? money(l.debe) : ""}</td><td className="num">{l.haber ? money(l.haber) : ""}</td></tr>
                      ))}</tbody>
                    </table>
                  )}
                </div>
              )}

              <details style={{ marginTop: 12 }}>
                <summary>Plan de cuotas ({cto.cuotas.length})</summary>
                <table className="caja-cuotas">
                  <thead><tr><th>#</th><th>Vto</th><th>Cuota</th><th>Pagado</th><th>Estado</th></tr></thead>
                  <tbody>{cto.cuotas.map((x: any) => (
                    <tr key={x.numero_cuota} className={x.estado === "PAGADA" ? "pg" : ""}>
                      <td>{x.numero_cuota}</td><td>{x.fecha_vencimiento}</td><td className="num">{money(x.total)}</td>
                      <td className="num">{money(x.pagado)}</td><td>{x.estado}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </details>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
