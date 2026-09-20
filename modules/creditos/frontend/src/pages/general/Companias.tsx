import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

const COLS: Col[] = [
  { key: "nombre", label: "Nombre", sortable: true },
  { key: "cuit", label: "CUIT", sortable: true, render: (c) => c.cuit || "-" },
  { key: "activa", label: "Activa", sortable: true, render: (c) => (c.activa ? "Sí" : "No") },
];

export default function Companias() {
  const [companias, setCompanias] = useState<any[]>([]);
  const [cia, setCia] = useState({ nombre: "", cuit: "" });
  const [error, setError] = useState("");

  async function cargar() { setCompanias(await api.adminCompanias()); }
  useEffect(() => { cargar(); }, []);

  async function guardar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try { await api.crearCompania(cia); setCia({ nombre: "", cuit: "" }); cargar(); }
    catch (err: any) { setError(err.message); }
  }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Compañías de seguros ({companias.length})</h2>
      <form onSubmit={guardar} style={{ display: "flex", gap: "0.5rem", alignItems: "end", marginBottom: "1rem" }}>
        <div style={{ flex: 1 }}><label>Nombre</label><input value={cia.nombre} onChange={(e) => setCia({ ...cia, nombre: e.target.value })} style={{ marginBottom: 0 }} required /></div>
        <div><label>CUIT</label><input value={cia.cuit} onChange={(e) => setCia({ ...cia, cuit: e.target.value })} style={{ marginBottom: 0 }} /></div>
        <button type="submit">Agregar</button>
      </form>
      {error && <p className="error">{error}</p>}
      <DataTable columns={COLS} rows={companias} rowKey={(c) => c.id}
                 clientSort pageSize={25} defaultSort="nombre" emptyText="Sin compañías" />
    </div>
  );
}
