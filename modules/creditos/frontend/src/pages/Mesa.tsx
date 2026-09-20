import { useEffect, useState } from "react";
import { api } from "../api";
import DataTable, { Col } from "../components/DataTable";

const COLS_TURNO: Col[] = [
  { key: "numero", label: "Turno", sortable: true, align: "right" },
  { key: "tipo", label: "Tipo", sortable: true },
  { key: "cliente", label: "Cliente", sortable: true, render: (t) => t.cliente || "-" },
];

export default function Mesa() {
  const hoy = new Date().toISOString().slice(0, 10);
  const [tipos, setTipos] = useState<any[]>([]);
  const [tablero, setTablero] = useState<any>(null);
  const [nuevo, setNuevo] = useState({ tipo_tramite_id: 0, cliente_nombre: "", cliente_cuil: "" });
  const [box, setBox] = useState("Box 1");
  const [ultimoLlamado, setUltimoLlamado] = useState<any>(null);
  const [error, setError] = useState("");

  async function cargar() {
    setTablero(await api.tablero(hoy));
  }
  useEffect(() => {
    api.tiposTramite().then((t) => {
      setTipos(t);
      if (t.length) setNuevo((n) => ({ ...n, tipo_tramite_id: t[0].id }));
    });
    cargar();
  }, []);

  async function generar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try {
      await api.generarTurno({ ...nuevo, tipo_tramite_id: Number(nuevo.tipo_tramite_id), fecha: hoy });
      setNuevo({ ...nuevo, cliente_nombre: "", cliente_cuil: "" });
      cargar();
    } catch (err: any) { setError(err.message); }
  }

  async function llamar() {
    setError("");
    try {
      setUltimoLlamado(await api.llamarSiguiente({ box, fecha: hoy }));
      cargar();
    } catch (err: any) { setError(err.message); setUltimoLlamado(null); }
  }
  async function atender(id: number) { await api.atenderTurno(id); cargar(); }
  async function cancelar(id: number) { await api.cancelarTurno(id); cargar(); }

  const tipoNombre = (id: number) => tipos.find((t) => t.id === id)?.nombre || id;

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Mesa de entradas — Turnos ({hoy})</h2>
        <form onSubmit={generar} style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap" }}>
          <div><label>Tipo de trámite</label>
            <select value={nuevo.tipo_tramite_id} onChange={(e) => setNuevo({ ...nuevo, tipo_tramite_id: Number(e.target.value) })} style={{ marginBottom: 0 }}>
              {tipos.map((t) => <option key={t.id} value={t.id}>{t.nombre}</option>)}
            </select></div>
          <div style={{ flex: 1, minWidth: 180 }}><label>Cliente (opcional)</label>
            <input value={nuevo.cliente_nombre} onChange={(e) => setNuevo({ ...nuevo, cliente_nombre: e.target.value })} style={{ marginBottom: 0 }} /></div>
          <button type="submit">Generar turno</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      {tablero && (
        <div className="card">
          <div className="grid3">
            <div><div className="kpi">{tablero.en_espera.length}</div><div className="kpi-label">En espera</div></div>
            <div><div className="kpi">{tablero.atendidos}</div><div className="kpi-label">Atendidos</div></div>
            <div><div className="kpi">{tablero.cancelados}</div><div className="kpi-label">Cancelados</div></div>
          </div>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "end", marginTop: "1rem" }}>
            <div><label>Box</label><input value={box} onChange={(e) => setBox(e.target.value)} style={{ marginBottom: 0 }} /></div>
            <button onClick={llamar}>Llamar siguiente</button>
            {ultimoLlamado && (
              <span className="badge-ok" style={{ fontSize: "1.1rem" }}>
                → Turno {ultimoLlamado.numero} ({box})
              </span>
            )}
          </div>
        </div>
      )}

      {tablero && tablero.llamados.length > 0 && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Llamados (en atención)</h3>
          <DataTable rows={tablero.llamados} rowKey={(t) => t.id}
                     columns={[...COLS_TURNO, { key: "box", label: "Box", sortable: true }]}
                     actions={(t) => [{ label: "Atender", icon: "check", onClick: () => atender(t.id) }]}
                     clientSort defaultSort="numero" emptyText="Sin llamados" />
        </div>
      )}

      {tablero && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Cola en espera</h3>
          <DataTable rows={tablero.en_espera} rowKey={(t) => t.id} columns={COLS_TURNO}
                     actions={(t) => [{ label: "Cancelar turno", icon: "ban", danger: true, onClick: () => cancelar(t.id) }]}
                     clientSort defaultSort="numero" emptyText="Sin turnos en espera" />
        </div>
      )}
    </>
  );
}
