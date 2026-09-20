import { useEffect, useState } from "react";
import { api } from "../api";
import DataTable, { Col } from "../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const ESTADOS: Record<string, string> = {
  I: "Ingresada", A: "Aprobada", O: "Otorgada", B: "Baja",
};

export default function Solicitudes() {
  const [clientes, setClientes] = useState<any[]>([]);
  const [lineas, setLineas] = useState<any[]>([]);
  const [solicitudes, setSolicitudes] = useState<any[]>([]);
  const [detalle, setDetalle] = useState<any>(null);
  const [credito, setCredito] = useState<any>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    cliente_id: 0, linea_id: 0, monto_solicitado: "300000",
    cantidad_cuotas: 12, fecha_primer_vencimiento: new Date().toISOString().slice(0, 10),
    cuota_fija: "", garante1_cuil: "",
  });

  async function refrescar() {
    setSolicitudes(await api.solicitudes());
  }
  useEffect(() => {
    api.clientes({ limit: 100 }).then((d) => {
      setClientes(d.items);
      if (d.items.length) setForm((f) => ({ ...f, cliente_id: d.items[0].id }));
    });
    api.lineas().then((l) => {
      setLineas(l);
      if (l.length) setForm((f) => ({ ...f, linea_id: l[0].id }));
    });
    refrescar();
  }, []);

  const set = (k: string) => (e: any) => setForm({ ...form, [k]: e.target.value });
  const lineaSel = lineas.find((l) => l.id === Number(form.linea_id));
  const esTipo5 = lineaSel?.tipo_calculo === 5;

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setCredito(null);
    try {
      const payload: any = {
        cliente_id: Number(form.cliente_id), linea_id: Number(form.linea_id),
        monto_solicitado: form.monto_solicitado,
        cantidad_cuotas: Number(form.cantidad_cuotas),
        fecha_primer_vencimiento: form.fecha_primer_vencimiento,
        garante1_cuil: form.garante1_cuil,
      };
      if (esTipo5) payload.cuota_fija = form.cuota_fija;
      const s = await api.crearSolicitud(payload);
      setDetalle(s);
      refrescar();
    } catch (err: any) { setError(err.message); }
  }

  async function verDetalle(id: number) {
    setCredito(null); setError("");
    setDetalle(await api.solicitud(id));
  }

  const colsSol: Col[] = [
    { key: "id", label: "#", sortable: true, align: "right" },
    { key: "cliente", label: "Cliente", sortable: true,
      sortValue: (s) => clientes.find((c) => c.id === s.cliente_id)?.apellido_nombre || String(s.cliente_id),
      render: (s) => clientes.find((c) => c.id === s.cliente_id)?.apellido_nombre || s.cliente_id },
    { key: "monto_solicitado", label: "Monto", sortable: true, align: "right",
      sortValue: (s) => Number(s.monto_solicitado), render: (s) => money(s.monto_solicitado) },
    { key: "cantidad_cuotas", label: "Cuotas", sortable: true, align: "right" },
    { key: "estado", label: "Estado", sortable: true, render: (s) => ESTADOS[s.estado] || s.estado },
  ];

  async function otorgar(id: number, forzar = false) {
    setError("");
    try {
      const cred = await api.otorgar(id, forzar);
      setCredito(cred);
      setDetalle(await api.solicitud(id));
      refrescar();
    } catch (err: any) { setError(err.message); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Nueva solicitud de crédito</h2>
        <form onSubmit={crear}>
          <div className="grid3">
            <div>
              <label>Cliente</label>
              <select value={form.cliente_id} onChange={set("cliente_id")}>
                {clientes.map((c) => (
                  <option key={c.id} value={c.id}>{c.apellido_nombre}</option>
                ))}
              </select>
            </div>
            <div>
              <label>Línea</label>
              <select value={form.linea_id} onChange={set("linea_id")}>
                {lineas.map((l) => (
                  <option key={l.id} value={l.id}>{l.nombre}</option>
                ))}
              </select>
            </div>
            <div>
              <label>Monto</label>
              <input value={form.monto_solicitado} onChange={set("monto_solicitado")} />
            </div>
          </div>
          <div className="grid3">
            <div>
              <label>{esTipo5 ? "Plazo (recalcula)" : "Cuotas"}</label>
              <input type="number" value={form.cantidad_cuotas} onChange={set("cantidad_cuotas")} disabled={esTipo5} />
            </div>
            {esTipo5 && (
              <div><label>Cuota fija</label>
                <input value={form.cuota_fija} onChange={set("cuota_fija")} /></div>
            )}
            <div>
              <label>1er vencimiento</label>
              <input type="date" value={form.fecha_primer_vencimiento} onChange={set("fecha_primer_vencimiento")} />
            </div>
            <div>
              <label>Garante (CUIL)</label>
              <input value={form.garante1_cuil} onChange={set("garante1_cuil")} />
            </div>
          </div>
          <button type="submit">Registrar solicitud</button>
          {error && <p className="error">{error}</p>}
        </form>
      </div>

      {detalle && (
        <div className="sold-ov" onMouseDown={(e) => { if (e.target === e.currentTarget) { setDetalle(null); setCredito(null); } }}>
          <div className="sold-modal">
            <div className="sold-mh">
              <div>
                <div className="eyebrow">Solicitud #{detalle.id} · {ESTADOS[detalle.estado]}</div>
                <h3 style={{ margin: 0 }}>{detalle.cliente_nombre}</h3>
              </div>
              <button className="sold-x" onClick={() => { setDetalle(null); setCredito(null); }} aria-label="Cerrar">✕</button>
            </div>
            <div className="sold-body">
              <p style={{ marginTop: 0 }}>
                {detalle.linea_nombre} · {money(detalle.monto_solicitado)} · {detalle.cantidad_cuotas} cuotas
                {detalle.margen_disponible != null && <> · Margen: <b>{money(detalle.margen_disponible)}</b></>}
              </p>
              {detalle.advertencias?.map((a: string, i: number) => (
                <div className="aviso" key={i}>⚠ {a}</div>
              ))}
              {detalle.credito_id && (
                <p className="badge-ok" style={{ marginTop: "0.6rem" }}>Crédito otorgado N° {detalle.credito_id}</p>
              )}
              {credito && (
                <div style={{ marginTop: 14 }}>
                  <h4 style={{ margin: "0 0 8px" }}>Crédito N° {credito.id} — plan de {credito.cantidad_cuotas} cuotas · total {money(credito.total_a_pagar)}</h4>
                  <div style={{ overflowX: "auto" }}>
                    <table>
                      <thead>
                        <tr><th>#</th><th>Vto</th><th>Saldo</th><th>Capital</th><th>Interés</th><th>IVA</th><th>Total</th></tr>
                      </thead>
                      <tbody>
                        {credito.cuotas.map((c: any) => (
                          <tr key={c.numero}>
                            <td>{c.numero}</td><td>{c.fecha_vencimiento}</td>
                            <td>{money(c.saldo_capital)}</td><td>{money(c.amortizacion)}</td>
                            <td>{money(c.interes)}</td><td>{money(c.iva_interes)}</td>
                            <td><b>{money(c.total)}</b></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
            <div className="sold-mf">
              <button className="btn-ghost" onClick={() => { setDetalle(null); setCredito(null); }}>Cerrar</button>
              <div style={{ flex: 1 }} />
              {detalle.estado === "I" && <>
                {!detalle.puede_otorgarse && (
                  <button onClick={() => otorgar(detalle.id, true)} style={{ background: "var(--alerta)" }}>Otorgar igual (forzar)</button>
                )}
                <button className="primary" onClick={() => otorgar(detalle.id)} disabled={!detalle.puede_otorgarse}>Otorgar crédito</button>
              </>}
            </div>
          </div>
          <style>{`
            .sold-ov { position:fixed; inset:0; background:rgba(16,24,40,.45); z-index:40; display:flex; align-items:center; justify-content:center; padding:16px; }
            .sold-modal { width:min(820px,96vw); max-height:92vh; overflow:hidden; background:var(--surface); border:1px solid var(--border); border-radius:14px; box-shadow:0 24px 70px -20px rgba(16,32,64,.55); display:flex; flex-direction:column; }
            .sold-mh { display:flex; align-items:center; gap:10px; padding:14px 18px; border-bottom:1px solid var(--border); }
            .sold-mh .sold-x { margin-left:auto; width:32px; height:32px; border-radius:8px; border:1px solid var(--border); background:var(--surface); cursor:pointer; color:var(--ink-soft); font-size:16px; }
            .sold-body { padding:14px 18px; overflow-y:auto; }
            .sold-mf { display:flex; gap:10px; align-items:center; padding:12px 18px; border-top:1px solid var(--border); background:var(--surface-2); }
          `}</style>
        </div>
      )}

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Solicitudes</h3>
        <DataTable columns={colsSol} rows={solicitudes} rowKey={(s) => s.id}
                   actions={(s) => [{ label: "Ver detalle", icon: "eye", onClick: () => verDetalle(s.id) }]}
                   clientSort pageSize={25} defaultSort="id" emptyText="Sin solicitudes" />
      </div>
    </>
  );
}
