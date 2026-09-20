import { useEffect, useState } from "react";
import { api } from "../../api";
import VolverFicha from "../../components/VolverFicha";
import DataTable, { Col } from "../../components/DataTable";

const COLS: Col[] = [
  { key: "codigo", label: "Código", sortable: true },
  { key: "nombre", label: "Nombre", sortable: true },
  { key: "activo", label: "Activo", sortable: true, render: (o) => (o.activo ? "Sí" : "No") },
];

export default function Organismos() {
  const [organismos, setOrganismos] = useState<any[]>([]);
  const [org, setOrg] = useState({ codigo: "", nombre: "" });
  const [error, setError] = useState("");

  async function cargar() { setOrganismos(await api.adminOrganismos()); }
  useEffect(() => { cargar(); }, []);

  async function guardar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try { await api.crearOrganismo(org); setOrg({ codigo: "", nombre: "" }); cargar(); }
    catch (err: any) { setError(err.message); }
  }

  return (
    <>
      <VolverFicha />
      <div className="card">
      <h2 style={{ marginTop: 0 }}>Organismos ({organismos.length})</h2>
      <form onSubmit={guardar} style={{ display: "flex", gap: "0.5rem", alignItems: "end", marginBottom: "1rem" }}>
        <div><label>Código</label><input value={org.codigo} onChange={(e) => setOrg({ ...org, codigo: e.target.value })} style={{ marginBottom: 0 }} required /></div>
        <div style={{ flex: 1 }}><label>Nombre</label><input value={org.nombre} onChange={(e) => setOrg({ ...org, nombre: e.target.value })} style={{ marginBottom: 0 }} required /></div>
        <button type="submit">Agregar</button>
      </form>
      {error && <p className="error">{error}</p>}
      <DataTable columns={COLS} rows={organismos} rowKey={(o) => o.id}
                 clientSort pageSize={25} defaultSort="codigo" emptyText="Sin organismos" />
    </div>
    </>
  );
}
