import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const COLS: Col[] = [
  { key: "banco", label: "Banco", sortable: true },
  { key: "cuenta", label: "Cuenta", sortable: true, render: (c) => c.cuenta || "-" },
  { key: "numero_desde", label: "Rango", sortable: true, align: "right", render: (c) => `${c.numero_desde}–${c.numero_hasta}` },
  { key: "proximo", label: "Próximo", sortable: true, align: "right" },
  { key: "activa", label: "Activa", sortable: true, render: (c) => (c.activa ? "Sí" : "Agotada") },
];

export default function Chequeras() {
  const [chequeras, setChequeras] = useState<any[]>([]);
  const [nueva, setNueva] = useState({ banco: "", cuenta: "", desde: "", hasta: "" });
  const [error, setError] = useState("");

  async function cargar() { setChequeras(await api.chequeras()); }
  useEffect(() => { cargar(); }, []);

  async function crear(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try {
      await api.crearChequera({ ...nueva, desde: Number(nueva.desde), hasta: Number(nueva.hasta) });
      setNueva({ banco: "", cuenta: "", desde: "", hasta: "" }); cargar();
    } catch (err: any) { setError(err.message); }
  }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Chequeras</h2>
      <form onSubmit={crear} style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap", marginBottom: "0.8rem" }}>
        <div><label>Banco</label><input value={nueva.banco} onChange={(e) => setNueva({ ...nueva, banco: e.target.value })} style={{ marginBottom: 0 }} required /></div>
        <div><label>Cuenta</label><input value={nueva.cuenta} onChange={(e) => setNueva({ ...nueva, cuenta: e.target.value })} style={{ marginBottom: 0 }} /></div>
        <div><label>Desde N°</label><input type="number" value={nueva.desde} onChange={(e) => setNueva({ ...nueva, desde: e.target.value })} style={{ marginBottom: 0 }} required /></div>
        <div><label>Hasta N°</label><input type="number" value={nueva.hasta} onChange={(e) => setNueva({ ...nueva, hasta: e.target.value })} style={{ marginBottom: 0 }} required /></div>
        <button type="submit">Alta chequera</button>
      </form>
      {error && <p className="error">{error}</p>}
      <DataTable columns={COLS} rows={chequeras} rowKey={(c) => c.id}
                 clientSort pageSize={25} defaultSort="banco" emptyText="Sin chequeras" />
    </div>
  );
}
