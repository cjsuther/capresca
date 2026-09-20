import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const money = (v: string | number) =>
  Number(v).toLocaleString("es-AR", { style: "currency", currency: "ARS" });

const COLS: Col[] = [
  { key: "apellido_nombre", label: "Beneficiario", sortable: true },
  { key: "cuil", label: "CUIL", sortable: true, render: (b) => b.cuil || "-" },
  { key: "monto_mensual", label: "Monto mensual", sortable: true, align: "right",
    sortValue: (b) => Number(b.monto_mensual), render: (b) => money(b.monto_mensual) },
  { key: "estado", label: "Estado", sortable: true, render: (b) => (b.estado === "V" ? "Vigente" : "Baja") },
];

export default function Regimenes() {
  const [regimenes, setRegimenes] = useState<any[]>([]);
  const [regId, setRegId] = useState(0);
  const [benef, setBenef] = useState<any[]>([]);
  const [nuevoB, setNuevoB] = useState({ apellido_nombre: "", cuil: "", monto_mensual: "" });
  const [periodo, setPeriodo] = useState("2026-05");
  const [genRes, setGenRes] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.regimenes().then((r) => { setRegimenes(r); if (r.length) setRegId(r[0].id); });
  }, []);
  useEffect(() => { if (regId) api.beneficiarios(regId).then(setBenef); }, [regId]);

  async function altaBenef(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try {
      await api.crearBeneficiario(regId, { ...nuevoB, monto_mensual: nuevoB.monto_mensual || null });
      setNuevoB({ apellido_nombre: "", cuil: "", monto_mensual: "" });
      setBenef(await api.beneficiarios(regId));
    } catch (err: any) { setError(err.message); }
  }
  async function generar() {
    setError("");
    try {
      setGenRes(await api.generarCuotasRegimen(regId, periodo));
      setBenef(await api.beneficiarios(regId));
    } catch (err: any) { setError(err.message); }
  }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Regímenes especiales</h2>
      <p className="muted">Renta Vitalicia Malvinas, Excombatientes, Subsidio a la Familia. Genera las cuotas del período y sus órdenes de pago en Tesorería.</p>
      <div style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 220 }}><label>Régimen</label>
          <select value={regId} onChange={(e) => setRegId(Number(e.target.value))} style={{ marginBottom: 0 }}>
            {regimenes.map((r) => <option key={r.id} value={r.id}>{r.nombre}</option>)}
          </select></div>
        <div><label>Período</label>
          <input value={periodo} onChange={(e) => setPeriodo(e.target.value)} placeholder="YYYY-MM" style={{ marginBottom: 0 }} /></div>
        <button onClick={generar}>Generar cuotas del período</button>
      </div>
      {genRes && (
        <div className="aviso" style={{ marginTop: "0.8rem", borderColor: "var(--ok)", background: "var(--ok-soft)" }}>
          {genRes.regimen} — {genRes.periodo}: <b>{genRes.cuotas_generadas}</b> cuotas generadas,{" "}
          <b>{genRes.ordenes_pago}</b> órdenes de pago, total <b>{money(genRes.total)}</b>.
        </div>
      )}
      <form onSubmit={altaBenef} style={{ display: "flex", gap: "0.5rem", alignItems: "end", marginTop: "1rem", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 180 }}><label>Nuevo beneficiario</label>
          <input value={nuevoB.apellido_nombre} onChange={(e) => setNuevoB({ ...nuevoB, apellido_nombre: e.target.value })} placeholder="Apellido y nombre" style={{ marginBottom: 0 }} required /></div>
        <div><label>CUIL</label><input value={nuevoB.cuil} onChange={(e) => setNuevoB({ ...nuevoB, cuil: e.target.value })} style={{ marginBottom: 0 }} /></div>
        <div><label>Monto (opc.)</label><input value={nuevoB.monto_mensual} onChange={(e) => setNuevoB({ ...nuevoB, monto_mensual: e.target.value })} style={{ marginBottom: 0 }} /></div>
        <button type="submit">Agregar</button>
      </form>
      {error && <p className="error">{error}</p>}
      <div style={{ marginTop: "1rem" }}>
        <DataTable columns={COLS} rows={benef} rowKey={(b) => b.id}
                   clientSort pageSize={25} defaultSort="apellido_nombre" emptyText="Sin beneficiarios" />
      </div>
    </div>
  );
}
