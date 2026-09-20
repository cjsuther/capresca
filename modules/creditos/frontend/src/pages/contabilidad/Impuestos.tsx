import { useEffect, useState } from "react";
import { api } from "../../api";
import DataTable, { Col } from "../../components/DataTable";

// Maestro de impuestos del sistema (Contabilidad → Impuestos). Alta/edición/baja para que
// otros módulos (p. ej. Configurar Créditos, componente TAX) los referencien.

const TIPOS = ["IVA", "IIBB", "SELLADO", "PERCEPCION", "RETENCION", "OTRO"];
const BASES = ["INTERES", "CARGOS", "CUOTA", "CAPITAL", "TOTAL"];
const VACIO = { codigo: "", nombre: "", tipo: "IVA", alicuota: 0, base: "INTERES", cuenta_contable: "", jurisdiccion: "", activo: true };

export default function Impuestos() {
  const [rows, setRows] = useState<any[]>([]);
  const [estado, setEstado] = useState("todos");
  const [form, setForm] = useState<any>({ ...VACIO });
  const [editId, setEditId] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function cargar() { setRows((await api.impuestos(estado === "activos" ? "activos" : undefined)).items); }
  useEffect(() => { cargar(); }, [estado]); // eslint-disable-line

  const set = (k: string) => (e: any) => setForm({ ...form, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  function nuevo() { setEditId(null); setForm({ ...VACIO }); setError(""); }
  function editar(i: any) { setEditId(i.id); setForm({ ...i }); setError(""); window.scrollTo(0, 0); }

  async function guardar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    const payload = { ...form, alicuota: Number(form.alicuota) || 0 };
    try {
      if (editId) await api.impuestoEditar(editId, payload);
      else await api.impuestoCrear(payload);
      nuevo(); cargar();
    } catch (err: any) { setError(err.message); }
  }
  async function baja(i: any) { await api.impuestoBaja(i.id); cargar(); }
  async function reactivar(i: any) { await api.impuestoReactivar(i.id); cargar(); }

  const cols: Col[] = [
    { key: "codigo", label: "Código", sortable: true },
    { key: "nombre", label: "Nombre", sortable: true },
    { key: "tipo", label: "Tipo", sortable: true },
    { key: "alicuota", label: "Alícuota", sortable: true, align: "right", render: (i) => `${i.alicuota} %` },
    { key: "base", label: "Base", sortable: true },
    { key: "cuenta_contable", label: "Cuenta", render: (i) => i.cuenta_contable || "—" },
    { key: "jurisdiccion", label: "Jurisdicción", render: (i) => i.jurisdiccion || "—" },
    { key: "activo", label: "Estado", sortable: true, render: (i) => <span className={`pill ${i.activo ? "ok" : "crit"}`}>{i.activo ? "Activo" : "Baja"}</span> },
  ];
  const acciones = (i: any) => [
    { label: "Editar", icon: "edit", onClick: () => editar(i) },
    { label: "Dar de baja", icon: "ban", danger: true, onClick: () => baja(i), hidden: !i.activo },
    { label: "Reactivar", icon: "rotate-ccw", onClick: () => reactivar(i), hidden: i.activo },
  ];

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>{editId ? `Editar impuesto #${editId}` : "Nuevo impuesto"}</h2>
        <p className="muted" style={{ marginTop: 0 }}>Maestro general del sistema. Cualquier módulo puede referenciar estos impuestos (créditos, seguros, tesorería).</p>
        <form onSubmit={guardar}>
          <div className="grid3">
            <div><label>Código</label><input value={form.codigo} onChange={set("codigo")} placeholder="IVA21" required disabled={!!editId} /></div>
            <div style={{ gridColumn: "span 2" }}><label>Nombre</label><input value={form.nombre} onChange={set("nombre")} required /></div>
          </div>
          <div className="grid3">
            <div><label>Tipo</label><select value={form.tipo} onChange={set("tipo")}>{TIPOS.map((t) => <option key={t}>{t}</option>)}</select></div>
            <div><label>Alícuota (%)</label><input className="num" type="number" step="0.01" value={form.alicuota} onChange={set("alicuota")} /></div>
            <div><label>Base de cálculo</label><select value={form.base} onChange={set("base")}>{BASES.map((b) => <option key={b}>{b}</option>)}</select></div>
          </div>
          <div className="grid3">
            <div><label>Cuenta contable</label><input value={form.cuenta_contable} onChange={set("cuenta_contable")} placeholder="2.1.07.01" /></div>
            <div><label>Jurisdicción (IIBB)</label><input value={form.jurisdiccion} onChange={set("jurisdiccion")} /></div>
            <div style={{ alignSelf: "end" }}><label><input type="checkbox" checked={form.activo} onChange={set("activo")} style={{ width: "auto" }} /> Activo</label></div>
          </div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button type="submit">{editId ? "Guardar cambios" : "Crear impuesto"}</button>
            {editId && <button type="button" className="btn-ghost" onClick={nuevo}>Cancelar</button>}
          </div>
          {error && <p className="error">{error}</p>}
        </form>
      </div>

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem" }}>
          <h3 style={{ margin: 0 }}>Impuestos ({rows.length})</h3>
          <select value={estado} onChange={(e) => setEstado(e.target.value)} style={{ marginBottom: 0, width: "auto" }}>
            <option value="todos">Todos</option><option value="activos">Sólo activos</option>
          </select>
        </div>
        <div style={{ marginTop: "0.6rem" }}>
          <DataTable columns={cols} rows={rows} rowKey={(i) => i.id} actions={acciones}
                     clientSort pageSize={25} defaultSort="codigo" emptyText="Sin impuestos" />
        </div>
      </div>
    </>
  );
}
