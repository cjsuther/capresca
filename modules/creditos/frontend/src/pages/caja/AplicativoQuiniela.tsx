import { useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });
const col = (v: number) => (v >= 0 ? "var(--ok)" : "var(--crit)"); // verde/rojo como el VFP

const COLS: Col[] = [
  { key: "cod_juego", label: "Cód.Jue.", sortable: true },
  { key: "juego", label: "Denominación", sortable: true },
  { key: "no_sorteo", label: "N° Sorteo", sortable: true, align: "right" },
  { key: "fecha_sorteo", label: "Fec.Sorteo", sortable: true, render: (it) => it.fecha_sorteo || "-" },
  { key: "moneda", label: "Moneda" },
  { key: "total", label: "Total", sortable: true, align: "right", sortValue: (it) => Number(it.total), render: (it) => money(it.total) },
  { key: "intereses", label: "Intereses", sortable: true, align: "right", sortValue: (it) => Number(it.intereses), render: (it) => money(it.intereses) },
  { key: "iva", label: "IVA", sortable: true, align: "right", sortValue: (it) => Number(it.iva), render: (it) => money(it.iva) },
  { key: "total_gral", label: "Total Gral.", sortable: true, align: "right", sortValue: (it) => Number(it.total_gral), render: (it) => <b>{money(it.total_gral)}</b> },
];

// Aplicativo de Caja de Quiniela (22505 / frm225050000aplicaj): se ingresa el código
// de agencia, se muestran sus liquidaciones pendientes separadas por moneda
// (bonos/pesos), se registran las formas de pago y se cobra. El vuelto por moneda es
// adeudado − cobrado (verde ≥ 0, rojo si el cobro no cubre lo adeudado).
export default function AplicativoQuiniela() {
  const [cod, setCod] = useState("");
  const [deuda, setDeuda] = useState<any>(null);
  const [pagBonos, setPagBonos] = useState("");
  const [pagPesos, setPagPesos] = useState("");
  const [preBonos, setPreBonos] = useState("");
  const [prePesos, setPrePesos] = useState("");
  const [recibo, setRecibo] = useState<any>(null);
  const [error, setError] = useState("");

  async function buscar(e?: React.FormEvent) {
    e?.preventDefault(); setError(""); setRecibo(null); setDeuda(null);
    const c = Number(cod);
    if (!c) { setError("Ingresá el código de agencia."); return; }
    try {
      const d = await api.deudaAgencia(c);
      setDeuda(d);
      setPagBonos(String(d.bonos)); setPagPesos(String(d.pesos));
      setPreBonos(""); setPrePesos("");
      if (!d.cantidad) setError(`La agencia ${c} no tiene liquidaciones pendientes.`);
    } catch (err: any) { setError(err.message); }
  }

  const cobBonos = Number(pagBonos || 0), cobPesos = Number(pagPesos || 0);
  // Vuelto = excedente entregado (entregado − adeudado). Rojo si NO cubre la deuda
  // (pago parcial: el sistema real no lo permite), verde si cubre y devuelve cambio.
  const vueBonos = deuda ? cobBonos - Number(deuda.bonos) : 0;
  const vuePesos = deuda ? cobPesos - Number(deuda.pesos) : 0;
  const cubre = vueBonos >= 0 && vuePesos >= 0;

  async function cobrar() {
    setError("");
    const formas: any[] = [];
    if (cobBonos) formas.push({ moneda: "B", importe: pagBonos });
    if (cobPesos) formas.push({ moneda: "$", importe: pagPesos });
    if (!formas.length) { setError("Ingresá al menos un importe (bonos o pesos)."); return; }
    if (!cubre) { setError("El cobro no cubre la deuda de la agencia. La cobranza salda el total (no admite pago parcial)."); return; }
    try {
      const r = await api.cobrarAgencia({
        cod_agencia: Number(cod), formas_pago: formas,
        premios_bonos: preBonos || "0", premios_pesos: prePesos || "0",
      });
      setRecibo(r); buscar();
    } catch (err: any) { setError(err.message); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Aplicativo de Caja — Quiniela</h2>
        <p className="muted">Cobro de liquidaciones de agencias de quiniela (bonos y pesos, con vuelto y premios). Fuente: <code>frm225050000aplicaj</code> (menú 22505).</p>
        <form onSubmit={buscar} style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
          <div><label>Código de agencia</label><input value={cod} onChange={(e) => setCod(e.target.value)} style={{ marginBottom: 0, width: 140 }} /></div>
          <button type="submit">Buscar deuda</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {deuda && deuda.cantidad > 0 && (
        <>
          <div className="card">
            <h3 style={{ marginTop: 0 }}>Liquidaciones pendientes — {money(deuda.total)}</h3>
            <DataTable columns={COLS} rows={deuda.items} rowKey={(it) => it.id}
                       clientSort defaultSort="no_sorteo" />
          </div>

          <div className="card">
            <h3 style={{ marginTop: 0 }}>Cobro</h3>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(140px, 1fr))", gap: "0.8rem", maxWidth: 520 }}>
              <div><label>Total Bonos</label><input value={money(deuda.bonos)} disabled style={{ marginBottom: 0 }} /></div>
              <div><label>Total Pesos</label><input value={money(deuda.pesos)} disabled style={{ marginBottom: 0 }} /></div>
              <div><label>Total Gral.</label><input value={money(deuda.total)} disabled style={{ marginBottom: 0 }} /></div>

              <div><label>Cobrado Bonos</label><input value={pagBonos} onChange={(e) => setPagBonos(e.target.value)} style={{ marginBottom: 0 }} /></div>
              <div><label>Cobrado Pesos</label><input value={pagPesos} onChange={(e) => setPagPesos(e.target.value)} style={{ marginBottom: 0 }} /></div>
              <div><label>Cobrado Total</label><input value={money(cobBonos + cobPesos)} disabled style={{ marginBottom: 0 }} /></div>

              <div><label>Vuelto B$</label><input value={money(vueBonos)} disabled style={{ marginBottom: 0, color: col(vueBonos) }} /></div>
              <div><label>Vuelto $</label><input value={money(vuePesos)} disabled style={{ marginBottom: 0, color: col(vuePesos) }} /></div>
              <div><label>Vuelto total</label><input value={money(vueBonos + vuePesos)} disabled style={{ marginBottom: 0, color: col(vueBonos + vuePesos) }} /></div>

              <div><label>Premios Bonos</label><input value={preBonos} onChange={(e) => setPreBonos(e.target.value)} placeholder="0" style={{ marginBottom: 0 }} /></div>
              <div><label>Premios Pesos</label><input value={prePesos} onChange={(e) => setPrePesos(e.target.value)} placeholder="0" style={{ marginBottom: 0 }} /></div>
            </div>
            <div style={{ marginTop: "1rem" }}>
              <button onClick={cobrar} disabled={!cubre}>Confirmar cobro y emitir recibo</button>
              {!cubre && <span style={{ marginLeft: "0.8rem", color: "var(--crit)" }}>El cobro debe cubrir la deuda total (no hay pago parcial).</span>}
            </div>
          </div>
        </>
      )}

      {recibo && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Recibo N° {recibo.no_recibo} — Agencia {recibo.cod_agencia}</h3>
          <p className="muted">{recibo.fecha_pago} · Cajero: {recibo.cajero}</p>
          <p className="kpi">Cobrado: {money(recibo.cobrado_total)} · Vuelto: {money(Number(recibo.vuelto_bonos) + Number(recibo.vuelto_pesos))}</p>
        </div>
      )}
    </>
  );
}
