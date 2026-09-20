import { useState } from "react";
import { api } from "../../api";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

// Cobranza de caja. Dos modos, reconstruidos del menú real:
//  - Por crédito (busca 1 crédito y paga sus cuotas).
//  - Cola por persona (22515 / frm225150000cresegu1): busca por CUIL/DNI/nombre y
//    cobra en un solo recibo las cuotas pendientes de TODOS los créditos.
export default function Cobranza() {
  const [modo, setModo] = useState<"credito" | "cola">("credito");
  const [fecha, setFecha] = useState(new Date().toISOString().slice(0, 10));
  const [recibo, setRecibo] = useState<any>(null);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");

  // --- modo por crédito ---
  const [creditoId, setCreditoId] = useState("");
  const [pendientes, setPendientes] = useState<any[]>([]);
  const [sel, setSel] = useState<Record<number, boolean>>({});

  // --- modo cola por persona ---
  const [busq, setBusq] = useState("");
  const [cola, setCola] = useState<any>({ items: [], total: 0, clientes: [] });
  const [selCola, setSelCola] = useState<Record<string, boolean>>({});

  function reset() { setError(""); setAviso(""); setRecibo(null); }

  async function buscar(e?: React.FormEvent) {
    e?.preventDefault(); reset(); setSel({});
    const id = Number(creditoId);
    if (!id) { setError("Ingresá un número de crédito."); setPendientes([]); return; }
    try {
      const p = await api.pendientes(id, fecha);
      setPendientes(p);
      if (!p.length) {
        try {
          const cr = await api.credito(id);
          setAviso(cr.estado === "C"
            ? `El crédito ${id} está cancelado: no tiene cuotas pendientes.`
            : `El crédito ${id} no tiene cuotas pendientes al ${fecha}.`);
        } catch { setAviso(`No existe el crédito ${id}.`); }
      }
    } catch (err: any) { setError(err.message); setPendientes([]); }
  }

  async function buscarCola(e?: React.FormEvent) {
    e?.preventDefault(); reset(); setSelCola({});
    const q = busq.trim();
    if (!q) { setError("Ingresá CUIL, DNI o nombre."); return; }
    // heurística: sólo dígitos y 11 => CUIL; sólo dígitos => DNI; si no, nombre
    const soloNum = /^\d+$/.test(q);
    const query = soloNum ? (q.length >= 11 ? { cuil: q } : { dni: q }) : { nombre: q };
    try {
      const c = await api.cola({ ...query, fecha });
      setCola(c);
      if (!c.items.length) setAviso("Sin cuotas pendientes para esa búsqueda.");
    } catch (err: any) { setError(err.message); setCola({ items: [], total: 0, clientes: [] }); }
  }

  const seleccionadas = pendientes.filter((p) => sel[p.numero]);
  const totalSel = seleccionadas.reduce((a, p) => a + Number(p.total_a_pagar), 0);

  const colaSel = cola.items.filter((_: any, i: number) => selCola[i]);
  const totalCola = colaSel.reduce((a: number, it: any) => a + Number(it.total), 0);

  async function cobrar() {
    reset();
    try {
      const r = await api.cobrar({
        credito_id: Number(creditoId), cuotas: seleccionadas.map((p) => p.numero),
        fecha_pago: fecha, via_pago: "EFECTIVO",
      });
      setRecibo(r); buscar();
    } catch (err: any) { setError(err.message); }
  }

  async function cobrarCola() {
    reset();
    // agrupar seleccionadas por crédito
    const porCred: Record<number, number[]> = {};
    colaSel.forEach((it: any) => {
      (porCred[it.credito_id] ??= []).push(it.cuota);
    });
    try {
      const r = await api.cobrarCola({
        items: Object.entries(porCred).map(([cid, cuotas]) => ({
          credito_id: Number(cid), cuotas,
        })),
        fecha_pago: fecha, via_pago: "EFECTIVO",
      });
      setRecibo(r); buscarCola();
    } catch (err: any) { setError(err.message); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Cobranza de caja</h2>
        <div style={{ display: "flex", gap: "0.4rem", marginBottom: "0.8rem" }}>
          <button onClick={() => { setModo("credito"); reset(); }}
                  style={{ background: modo === "credito" ? undefined : "var(--ink-soft)" }}>Por crédito</button>
          <button onClick={() => { setModo("cola"); reset(); }}
                  style={{ background: modo === "cola" ? undefined : "var(--ink-soft)" }}>Cola por persona</button>
        </div>

        {modo === "credito" ? (
          <form onSubmit={buscar} style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
            <div><label>N° de crédito</label><input value={creditoId} onChange={(e) => setCreditoId(e.target.value)} style={{ marginBottom: 0 }} /></div>
            <div><label>Fecha de pago</label><input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} style={{ marginBottom: 0 }} /></div>
            <button type="submit">Buscar cuotas pendientes</button>
          </form>
        ) : (
          <form onSubmit={buscarCola} style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
            <div><label>CUIL, DNI o nombre</label><input value={busq} onChange={(e) => setBusq(e.target.value)} placeholder="Ej: 27… / 12345678 / PEREZ" style={{ marginBottom: 0, width: 260 }} /></div>
            <div><label>Fecha de pago</label><input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)} style={{ marginBottom: 0 }} /></div>
            <button type="submit">Buscar cola</button>
          </form>
        )}
        {error && <p className="error">{error}</p>}
        {aviso && <div className="aviso" style={{ marginTop: "0.6rem" }}>ℹ {aviso}</div>}
      </div>

      {modo === "credito" && pendientes.length > 0 && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Cuotas pendientes</h3>
          <table>
            <thead><tr><th></th><th>#</th><th>Vto</th><th>Cuota</th><th>Días mora</th><th>Punitorio</th><th>Total a pagar</th></tr></thead>
            <tbody>
              {pendientes.map((p) => (
                <tr key={p.numero}>
                  <td style={{ textAlign: "center" }}><input type="checkbox" style={{ width: "auto", margin: 0 }} checked={!!sel[p.numero]} onChange={(e) => setSel({ ...sel, [p.numero]: e.target.checked })} /></td>
                  <td>{p.numero}</td><td>{p.fecha_vencimiento}</td><td>{money(p.importe_cuota)}</td>
                  <td>{p.dias_mora}</td><td>{money(p.interes_punitorio)}</td><td><b>{money(p.total_a_pagar)}</b></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: "1rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>Seleccionadas: <b>{seleccionadas.length}</b> · Total: <b>{money(totalSel)}</b></span>
            <button onClick={cobrar} disabled={!seleccionadas.length}>Cobrar y emitir recibo</button>
          </div>
        </div>
      )}

      {modo === "cola" && cola.items.length > 0 && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Cola de caja — {money(cola.total)}</h3>
          <table>
            <thead><tr><th></th><th>Origen</th><th>DNI</th><th>Apellido y nombre</th><th>N° Créd.</th><th>N° Cta</th><th>Importe</th><th>Interés</th><th>IVA</th><th>Total</th></tr></thead>
            <tbody>
              {cola.items.map((it: any, i: number) => (
                <tr key={i}>
                  <td style={{ textAlign: "center" }}><input type="checkbox" style={{ width: "auto", margin: 0 }} checked={!!selCola[i]} onChange={(e) => setSelCola({ ...selCola, [i]: e.target.checked })} /></td>
                  <td>{it.origen}</td><td>{it.dni}</td><td>{it.apellido_nombre}</td>
                  <td>{it.credito_id}</td><td>{it.cuota}</td>
                  <td>{money(it.importe)}</td><td>{money(it.interes)}</td><td>{money(it.iva)}</td>
                  <td><b>{money(it.total)}</b></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: "1rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>Seleccionadas: <b>{colaSel.length}</b> · Total: <b>{money(totalCola)}</b></span>
            <button onClick={cobrarCola} disabled={!colaSel.length}>Cobrar y emitir recibo</button>
          </div>
        </div>
      )}

      {recibo && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
            <h3 style={{ marginTop: 0 }}>Recibo N° {recibo.numero} — {recibo.cliente_nombre}</h3>
            <button onClick={() => api.verReciboPdf(recibo.id)}>Ver recibo PDF</button>
          </div>
          <p className="muted">{recibo.fecha_pago} · {recibo.via_pago} · Cajero: {recibo.cajero}</p>
          <p className="kpi">Total recibo: {money(recibo.total)}</p>
        </div>
      )}
    </>
  );
}
