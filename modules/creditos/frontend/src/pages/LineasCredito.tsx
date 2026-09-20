import { useEffect, useState } from "react";
import { api } from "../api";
import DataTable, { Col } from "../components/DataTable";

// ABM de Líneas de crédito — pertenece al módulo Créditos (config del motor).
const SISTEMAS: Record<number, string> = {
  1: "Francés", 2: "Alemán", 3: "Directo", 4: "Francés c/gracia", 5: "Cuota fija s/interés",
};

const LINEA_VACIA = {
  nombre: "", cartera: 1, tipo_calculo: 1, tna: "0", tasa_mora_diaria: "0",
  iva: "21", por_afecta: "30", porcent_pp: "0", seguro_pct: "0",
  gastos_adm_pct: "0", plazo_max: 60, monto_max: "0",
  plazo_gracia: 0, paga_interes_gracia: false, suma_int_gracia_capital: false,
  admite_previo_pago: false, cta_contable: "", activa: true,
};

const COLS: Col[] = [
  { key: "nombre", label: "Nombre", sortable: true },
  { key: "cartera", label: "Cartera", sortable: true, align: "right" },
  { key: "tipo_calculo", label: "Sistema", sortable: true, render: (l) => SISTEMAS[l.tipo_calculo] },
  { key: "tna", label: "TNA", sortable: true, align: "right", sortValue: (l) => Number(l.tna), render: (l) => `${l.tna}%` },
  { key: "por_afecta", label: "% Afect.", sortable: true, align: "right", sortValue: (l) => Number(l.por_afecta), render: (l) => `${l.por_afecta}%` },
  { key: "plazo_max", label: "Plazo", sortable: true, align: "right" },
  { key: "activa", label: "Activa", sortable: true, render: (l) => (l.activa ? "Sí" : "No") },
];

export default function LineasCredito() {
  const [lineas, setLineas] = useState<any[]>([]);
  const [form, setForm] = useState<any>({ ...LINEA_VACIA });
  const [editId, setEditId] = useState<number | null>(null);
  const [error, setError] = useState("");

  async function cargar() { setLineas(await api.adminLineas()); }
  useEffect(() => { cargar(); }, []);

  const set = (k: string) => (e: any) =>
    setForm({ ...form, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  function editar(l: any) { setEditId(l.id); setForm({ ...l }); window.scrollTo(0, 0); }
  function nuevo() { setEditId(null); setForm({ ...LINEA_VACIA }); }

  async function guardar(e: React.FormEvent) {
    e.preventDefault(); setError("");
    try {
      const payload = { ...form };
      delete payload.id;
      if (editId) await api.editarLinea(editId, payload);
      else await api.crearLinea(payload);
      nuevo(); cargar();
    } catch (err: any) { setError(err.message); }
  }

  return (
    <>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>
          {editId ? `Editar línea #${editId}` : "Nueva línea de crédito"}
        </h2>
        <form onSubmit={guardar}>
          <div className="grid3">
            <div style={{ gridColumn: "span 2" }}><label>Nombre</label>
              <input value={form.nombre} onChange={set("nombre")} required /></div>
            <div><label>Cartera (código)</label>
              <input type="number" value={form.cartera} onChange={set("cartera")} /></div>
          </div>
          <div className="grid3">
            <div><label>Sistema de cálculo</label>
              <select value={form.tipo_calculo} onChange={set("tipo_calculo")}>
                {Object.entries(SISTEMAS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select></div>
            <div><label>TNA (%)</label><input value={form.tna} onChange={set("tna")} /></div>
            <div><label>Mora diaria (%)</label><input value={form.tasa_mora_diaria} onChange={set("tasa_mora_diaria")} /></div>
          </div>
          <div className="grid3">
            <div><label>% afectación haber</label><input value={form.por_afecta} onChange={set("por_afecta")} /></div>
            <div><label>Seguro (% saldo)</label><input value={form.seguro_pct} onChange={set("seguro_pct")} /></div>
            <div><label>Gastos adm (% saldo)</label><input value={form.gastos_adm_pct} onChange={set("gastos_adm_pct")} /></div>
          </div>
          <div className="grid3">
            <div><label>Plazo máx (cuotas)</label><input type="number" value={form.plazo_max} onChange={set("plazo_max")} /></div>
            <div><label>Monto máximo</label><input value={form.monto_max} onChange={set("monto_max")} /></div>
            <div><label>Plazo de gracia</label><input type="number" value={form.plazo_gracia} onChange={set("plazo_gracia")} /></div>
          </div>
          <div className="grid3">
            <div><label>% cancelado para previo pago</label><input value={form.porcent_pp} onChange={set("porcent_pp")} /></div>
            <div><label>Cta. contable</label><input value={form.cta_contable} onChange={set("cta_contable")} /></div>
            <div style={{ alignSelf: "end" }}>
              <label><input type="checkbox" checked={form.activa} onChange={set("activa")} style={{ width: "auto" }} /> Activa (habilitada)</label>
            </div>
          </div>
          <div className="grid3">
            <div style={{ alignSelf: "end" }}><label><input type="checkbox" checked={form.paga_interes_gracia} onChange={set("paga_interes_gracia")} style={{ width: "auto" }} /> Paga interés en gracia</label></div>
            <div style={{ alignSelf: "end" }}><label><input type="checkbox" checked={form.suma_int_gracia_capital} onChange={set("suma_int_gracia_capital")} style={{ width: "auto" }} /> Suma int. gracia a capital</label></div>
            <div style={{ alignSelf: "end" }}><label><input type="checkbox" checked={form.admite_previo_pago} onChange={set("admite_previo_pago")} style={{ width: "auto" }} /> Admite previo pago</label></div>
          </div>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button type="submit">{editId ? "Guardar cambios" : "Crear línea"}</button>
            {editId && <button type="button" onClick={nuevo} style={{ background: "var(--ink-faint)" }}>Cancelar</button>}
          </div>
          {error && <p className="error">{error}</p>}
        </form>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Líneas de crédito</h3>
        <DataTable columns={COLS} rows={lineas} rowKey={(l) => l.id}
                   actions={(l) => [{ label: "Editar", icon: "edit", onClick: () => editar(l) }]}
                   clientSort pageSize={25} defaultSort="nombre" emptyText="Sin líneas" />
      </div>
    </>
  );
}
