import { useEffect, useState } from "react";
import { api } from "../api";

type Linea = {
  id: number; nombre: string; tipo_calculo: number; tna: string;
  por_afecta: string; plazo_max: number; monto_max: string;
};

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

export default function Simulador() {
  const [lineas, setLineas] = useState<Linea[]>([]);
  const [form, setForm] = useState({
    linea_id: 0, capital: "500000", plazo: 12,
    fecha_primer_vencimiento: new Date().toISOString().slice(0, 10),
    cuota_fija: "", sueldo: "650000", total_afectado: "0",
  });
  const [res, setRes] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.lineas().then((l) => {
      setLineas(l);
      if (l.length) setForm((f) => ({ ...f, linea_id: l[0].id }));
    });
  }, []);

  const lineaSel = lineas.find((l) => l.id === Number(form.linea_id));
  const esTipo5 = lineaSel?.tipo_calculo === 5;

  async function simular(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setRes(null);
    try {
      const payload: any = {
        linea_id: Number(form.linea_id),
        capital: form.capital,
        plazo: Number(form.plazo),
        fecha_primer_vencimiento: form.fecha_primer_vencimiento,
        sueldo: form.sueldo || null,
        total_afectado: form.total_afectado || "0",
      };
      if (esTipo5) payload.cuota_fija = form.cuota_fija;
      setRes(await api.simular(payload));
    } catch (err: any) {
      setError(err.message);
    }
  }

  const set = (k: string) => (e: any) => setForm({ ...form, [k]: e.target.value });

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Simulador de crédito</h2>
        <p className="muted">Motor de cálculo portado de <code>set_class.prg</code> (VFP).</p>
        <form onSubmit={simular}>
          <div className="grid3">
            <div>
              <label>Línea de crédito</label>
              <select value={form.linea_id} onChange={set("linea_id")}>
                {lineas.map((l) => (
                  <option key={l.id} value={l.id}>{l.nombre} (TNA {l.tna}%)</option>
                ))}
              </select>
            </div>
            <div>
              <label>Capital</label>
              <input value={form.capital} onChange={set("capital")} />
            </div>
            <div>
              <label>{esTipo5 ? "Plazo (se recalcula)" : "Plazo (cuotas)"}</label>
              <input type="number" value={form.plazo} onChange={set("plazo")} disabled={esTipo5} />
            </div>
          </div>
          <div className="grid3">
            <div>
              <label>1er vencimiento</label>
              <input type="date" value={form.fecha_primer_vencimiento} onChange={set("fecha_primer_vencimiento")} />
            </div>
            {esTipo5 && (
              <div>
                <label>Cuota fija</label>
                <input value={form.cuota_fija} onChange={set("cuota_fija")} />
              </div>
            )}
            <div>
              <label>Sueldo (para margen)</label>
              <input value={form.sueldo} onChange={set("sueldo")} />
            </div>
            <div>
              <label>Ya afectado</label>
              <input value={form.total_afectado} onChange={set("total_afectado")} />
            </div>
          </div>
          <button type="submit">Calcular plan de cuotas</button>
          {error && <p className="error">{error}</p>}
        </form>
      </div>

      {res && (
        <>
          <div className="card">
            <div className="grid3">
              <div><div className="kpi">{res.cantidad_cuotas}</div><div className="kpi-label">Cuotas</div></div>
              <div><div className="kpi">{money(res.total_a_pagar)}</div><div className="kpi-label">Total a pagar</div></div>
              <div><div className="kpi">{money(res.cuota_promedio)}</div><div className="kpi-label">Cuota promedio</div></div>
            </div>
            {res.margen_disponible != null && (
              <p style={{ marginTop: "1rem" }}>
                Margen disponible: <b>{money(res.margen_disponible)}</b> —{" "}
                {res.puede_tomar_credito
                  ? <span className="badge-ok">PUEDE tomar el crédito</span>
                  : <span className="badge-no">NO puede tomar el crédito</span>}
              </p>
            )}
            {res.advertencias?.map((a: string, i: number) => (
              <div className="aviso" key={i}>⚠ {a}</div>
            ))}
          </div>

          <div className="card">
            <h3 style={{ marginTop: 0 }}>Plan de cuotas</h3>
            <div style={{ overflowX: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>#</th><th>Vencimiento</th><th>Saldo</th><th>Capital</th>
                    <th>Interés</th><th>IVA int.</th><th>Seguro</th><th>Gastos</th><th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {res.cuotas.map((c: any) => (
                    <tr key={c.numero}>
                      <td>{c.numero}</td><td>{c.vencimiento}</td>
                      <td>{money(c.saldo_capital)}</td><td>{money(c.amortizacion)}</td>
                      <td>{money(c.interes)}</td><td>{money(c.iva_interes)}</td>
                      <td>{money(c.seguro)}</td><td>{money(c.gastos_adm)}</td>
                      <td><b>{money(c.total)}</b></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </>
  );
}
