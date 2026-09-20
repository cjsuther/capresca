import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";
import LimpiarFiltros from "../../components/LimpiarFiltros";

const COLS: Col[] = [
  { key: "id", label: "N°", sortable: true },
  { key: "razon_social", label: "Razón social", sortable: true },
  { key: "cuit", label: "CUIT", sortable: true, render: (p) => p.cuit || "-" },
  { key: "tipo_iva", label: "IVA", sortable: true, render: (p) => p.tipo_iva || "-" },
  { key: "localidad", label: "Localidad", sortable: true, render: (p) => p.localidad || "-" },
  { key: "contacto", label: "Contacto", render: (p) => p.contacto || "-" },
];

const VACIO = {
  razon_social: "", cuit: "", contacto: "", domicilio: "",
  localidad: "", departamento: "", tipo_iva: "RI", ingresos_brutos: "",
};

export default function Proveedores() {
  const [rows, setRows] = useState<any[]>([]);
  const [busq, setBusq] = useState("");
  const [q, setQ] = useState("");
  const [nuevo, setNuevo] = useState({ ...VACIO });
  const [error, setError] = useState("");

  async function cargar() { setRows(await api.adminProveedores(q)); }
  useEffect(() => { cargar(); }, [q]);

  async function crear(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try { await api.crearProveedor(nuevo); setNuevo({ ...VACIO }); cargar(); }
    catch (err: any) { setError(err.message); }
  }
  const set = (k: string) => (e: any) => setNuevo({ ...nuevo, [k]: e.target.value });

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Nuevo proveedor</h2>
        <form onSubmit={crear}>
          <div className="grid3">
            <div><label>Razón social</label><input value={nuevo.razon_social} onChange={set("razon_social")} required /></div>
            <div><label>CUIT</label><input value={nuevo.cuit} onChange={set("cuit")} /></div>
            <div><label>Tipo IVA</label>
              <select value={nuevo.tipo_iva} onChange={set("tipo_iva")}>
                <option value="RI">Resp. Inscripto</option><option value="MT">Monotributo</option>
                <option value="EX">Exento</option><option value="CF">Cons. Final</option>
              </select></div>
          </div>
          <div className="grid3">
            <div><label>Contacto</label><input value={nuevo.contacto} onChange={set("contacto")} /></div>
            <div><label>Domicilio</label><input value={nuevo.domicilio} onChange={set("domicilio")} /></div>
            <div><label>Localidad</label><input value={nuevo.localidad} onChange={set("localidad")} /></div>
          </div>
          <button type="submit">Agregar proveedor</button>
          {error && <p className="error">{error}</p>}
        </form>
      </div>

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem" }}>
          <h3 style={{ margin: 0 }}>Proveedores ({rows.length})</h3>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <form onSubmit={(e) => { e.preventDefault(); setQ(busq); }}>
              <input value={busq} onChange={(e) => setBusq(e.target.value)} placeholder="Buscar razón social / CUIT" style={{ marginBottom: 0 }} />
            </form>
            <LimpiarFiltros activo={!!q || !!busq} onClear={() => { setBusq(""); setQ(""); }} />
          </div>
        </div>
        <div style={{ marginTop: "0.6rem" }}>
          <DataTable columns={COLS} rows={rows} rowKey={(p) => p.id}
                     rowStyle={(p) => (p.anulado ? { opacity: 0.5 } : undefined)}
                     clientSort pageSize={25} defaultSort="id" emptyText="Sin proveedores" />
        </div>
      </div>
    </>
  );
}
