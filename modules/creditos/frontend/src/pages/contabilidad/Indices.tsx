import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

// Maestro de índices de referencia (Contabilidad → Índices). Usados por tasas variables
// en Configurar Créditos: tasa efectiva = valor del índice + margen.

const VACIO = { codigo: "", nombre: "", valor: 0, fuente: "", fecha_valor: "", activo: true };

export default function Indices() {
  const [rows, setRows] = useState<any[]>([]);
  const [estado, setEstado] = useState("todos");
  const [form, setForm] = useState<any>({ ...VACIO });
  const [editId, setEditId] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function cargar() { setRows((await api.indices(estado === "activos" ? "activos" : undefined)).items); }
  useEffect(() => { cargar(); }, [estado]); // eslint-disable-line

  const set = (k: string) => (e: any) => setForm({ ...form, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  function nuevo() { setEditId(null); setForm({ ...VACIO }); setError(""); }
  function editar(i: any) { setEditId(i.id); setForm({ ...i, fecha_valor: i.fecha_valor || "" }); setError(""); window.scrollTo(0, 0); }

  async function guardar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    const payload = { ...form, valor: Number(form.valor) || 0, fecha_valor: form.fecha_valor || null };
    try {
      if (editId) await api.indiceEditar(editId, payload); else await api.indiceCrear(payload);
      nuevo(); cargar();
    } catch (err: any) { setError(err.message); }
  }

  const cols: Col[] = [
    { key: "codigo", label: "Código", sortable: true },
    { key: "nombre", label: "Nombre", sortable: true },
    { key: "valor", label: "Valor (TNA)", sortable: true, align: "right", render: (i) => `${i.valor} %` },
    { key: "fuente", label: "Fuente", render: (i) => i.fuente || "—" },
    { key: "fecha_valor", label: "Fecha", render: (i) => i.fecha_valor || "—" },
    { key: "activo", label: "Estado", sortable: true, render: (i) => <span className={`pill ${i.activo ? "ok" : "crit"}`}>{i.activo ? "Activo" : "Baja"}</span> },
  ];
  const acciones = (i: any) => [
    { label: "Editar", icon: "edit", onClick: () => editar(i) },
    { label: "Dar de baja", icon: "ban", danger: true, onClick: async () => { await api.indiceBaja(i.id); cargar(); }, hidden: !i.activo },
    { label: "Reactivar", icon: "rotate-ccw", onClick: async () => { await api.indiceReactivar(i.id); cargar(); }, hidden: i.activo },
  ];

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>{editId ? `Editar índice #${editId}` : "Nuevo índice de referencia"}</h2>
        <p className="muted" style={{ marginTop: 0 }}>Índices para tasas variables (BADLAR, política monetaria, UVA…). La tasa efectiva de un producto variable = valor del índice + margen.</p>
        <form onSubmit={guardar}>
          <div className="grid3">
            <div><label>Código</label><input value={form.codigo} onChange={set("codigo")} placeholder="BADLAR" required disabled={!!editId} /></div>
            <div style={{ gridColumn: "span 2" }}><label>Nombre</label><input value={form.nombre} onChange={set("nombre")} required /></div>
          </div>
          <div className="grid3">
            <div><label>Valor / TNA (%)</label><input className="num" type="number" step="0.01" value={form.valor} onChange={set("valor")} /></div>
            <div><label>Fuente</label><input value={form.fuente} onChange={set("fuente")} placeholder="BCRA" /></div>
            <div><label>Fecha del valor</label><input type="date" value={form.fecha_valor} onChange={set("fecha_valor")} /></div>
          </div>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <button type="submit">{editId ? "Guardar cambios" : "Crear índice"}</button>
            {editId && <button type="button" className="btn-ghost" onClick={nuevo}>Cancelar</button>}
            <label style={{ marginLeft: "0.5rem" }}><input type="checkbox" checked={form.activo} onChange={set("activo")} style={{ width: "auto" }} /> Activo</label>
          </div>
          {error && <p className="error">{error}</p>}
        </form>
      </div>

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem" }}>
          <h3 style={{ margin: 0 }}>Índices ({rows.length})</h3>
          <select value={estado} onChange={(e) => setEstado(e.target.value)} style={{ marginBottom: 0, width: "auto" }}>
            <option value="todos">Todos</option><option value="activos">Sólo activos</option>
          </select>
        </div>
        <div style={{ marginTop: "0.6rem" }}>
          <DataTable columns={cols} rows={rows} rowKey={(i) => i.id} actions={acciones}
                     clientSort pageSize={25} defaultSort="codigo" emptyText="Sin índices" />
        </div>
      </div>
    </>
  );
}
