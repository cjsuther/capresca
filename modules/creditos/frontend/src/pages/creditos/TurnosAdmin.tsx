import { useState } from "react";
import { api } from "../../api";

// Administración de turnos de crédito: generación del mes (32065) con vista previa de la
// distribución por día hábil, y asignación de turno a un solicitante (32067/32068).
export default function TurnosAdmin() {
  const ahora = new Date();
  const perDefault = `${ahora.getFullYear()}${String(ahora.getMonth() + 2).padStart(2, "0")}`;
  const [periodo, setPeriodo] = useState(perDefault);
  const [cantidad, setCantidad] = useState("100");
  const [prev, setPrev] = useState<any>(null);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  // asignación
  const [cuil, setCuil] = useState("");
  const [nombre, setNombre] = useState("");
  const [numero, setNumero] = useState("");

  async function preview(e?: React.FormEvent) {
    e?.preventDefault(); setError(""); setMsg(""); setPrev(null);
    try { setPrev(await api.turnosPreview(periodo, Number(cantidad))); }
    catch (err: any) { setError(err.message); }
  }
  async function generar() {
    setError("");
    try {
      const r = await api.turnosGenerar({ periodo, cantidad: Number(cantidad) });
      setMsg(`Generados ${r.generados} turnos del período ${r.periodo}.`); setPrev(null);
    } catch (err: any) { setError(err.message); }
  }
  async function asignar(e?: React.FormEvent) {
    e?.preventDefault(); setError(""); setMsg("");
    try {
      const r = await api.turnoAsignar({
        periodo, cuil, apellido_nombre: nombre,
        numero: numero ? Number(numero) : undefined,
      });
      setMsg(`Turno N° ${r.numero} (${r.fecha}) asignado a ${r.apellido_nombre || r.cuil}.`);
      setCuil(""); setNombre(""); setNumero("");
    } catch (err: any) { setError(err.message); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Turnos de crédito — administración</h2>
        <p className="muted">Generación de los turnos del mes distribuidos por día hábil (32065) y asignación a solicitantes (32067/68). Nota: no hay tabla de feriados migrada, se excluyen sólo fines de semana.</p>
        {msg && <div className="aviso" style={{ borderColor: "var(--ok)", background: "var(--ok-soft)" }}>{msg}</div>}
        {error && <p className="error">{error}</p>}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Generar turnos del mes</h3>
        <form onSubmit={preview} style={{ display: "flex", gap: "0.5rem", alignItems: "end" }}>
          <div><label>Período (YYYYMM)</label><input value={periodo} onChange={(e) => setPeriodo(e.target.value)} style={{ marginBottom: 0, width: 110 }} /></div>
          <div><label>Cantidad de turnos</label><input value={cantidad} onChange={(e) => setCantidad(e.target.value)} style={{ marginBottom: 0, width: 110 }} /></div>
          <button type="submit">Previsualizar distribución</button>
        </form>
        {prev && (
          <div style={{ marginTop: "1rem" }}>
            <p>Días hábiles: <b>{prev.dias_habiles}</b> · Turnos/día: <b>{prev.turnos_por_dia}</b> · Resto: <b>{prev.resto}</b> · Total: <b>{prev.total}</b>{prev.ya_existen ? ` · ⚠ ya existen ${prev.ya_existen}` : ""}</p>
            <div style={{ overflowX: "auto", maxHeight: 240 }}>
              <table>
                <thead><tr><th>Fecha</th><th>Turnos</th></tr></thead>
                <tbody>{prev.distribucion.map((d: any, i: number) => (
                  <tr key={i}><td>{d.fecha}</td><td>{d.cantidad}</td></tr>
                ))}</tbody>
              </table>
            </div>
            <button onClick={generar} disabled={prev.ya_existen > 0} style={{ marginTop: "0.8rem" }}>Confirmar y generar</button>
          </div>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Asignar turno a un solicitante</h3>
        <form onSubmit={asignar} style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap" }}>
          <div><label>Período</label><input value={periodo} onChange={(e) => setPeriodo(e.target.value)} style={{ marginBottom: 0, width: 100 }} /></div>
          <div><label>CUIL</label><input value={cuil} onChange={(e) => setCuil(e.target.value)} style={{ marginBottom: 0, width: 140 }} /></div>
          <div><label>Apellido y nombre</label><input value={nombre} onChange={(e) => setNombre(e.target.value)} style={{ marginBottom: 0, width: 220 }} /></div>
          <div><label>N° (excepcional, opc.)</label><input value={numero} onChange={(e) => setNumero(e.target.value)} placeholder="próximo libre" style={{ marginBottom: 0, width: 120 }} /></div>
          <button type="submit" disabled={!cuil}>Asignar turno</button>
        </form>
      </div>
    </>
  );
}
