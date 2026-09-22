import { useEffect, useState } from "react";
import { creditos } from "../../../../api/creditos";
import { DataTable } from "../../components/DataTable";
import { PageHeader, Card, Field, Boton, Alerta } from "../../components/ui";
import { usePuedeEscribir } from "../../permisos";

// ABM de líneas de crédito (configuración del motor de cálculo).
const SISTEMAS = {
  1: "Francés", 2: "Alemán", 3: "Directo", 4: "Francés c/gracia", 5: "Cuota fija s/interés",
};

const VACIA = {
  nombre: "", cartera: 1, tipo_calculo: 1, tna: "0", tasa_mora_diaria: "0",
  iva: "21", por_afecta: "30", porcent_pp: "0", seguro_pct: "0",
  gastos_adm_pct: "0", plazo_max: 60, monto_max: "0",
  plazo_gracia: 0, paga_interes_gracia: false, suma_int_gracia_capital: false,
  admite_previo_pago: false, cta_contable: "", activa: true,
};

const COLS = [
  { key: "nombre", label: "Nombre", sortable: true },
  { key: "cartera", label: "Cartera", sortable: true, align: "right" },
  { key: "tipo_calculo", label: "Sistema", sortable: true, render: (l) => SISTEMAS[l.tipo_calculo] },
  { key: "tna", label: "TNA", sortable: true, align: "right", sortValue: (l) => Number(l.tna), render: (l) => `${l.tna}%` },
  { key: "por_afecta", label: "% Afect.", sortable: true, align: "right", sortValue: (l) => Number(l.por_afecta), render: (l) => `${l.por_afecta}%` },
  { key: "plazo_max", label: "Plazo", sortable: true, align: "right" },
  { key: "activa", label: "Activa", sortable: true, render: (l) => (l.activa ? "Sí" : "No") },
];

export default function LineasCreditoPage() {
  const puedeEscribir = usePuedeEscribir();
  const [lineas, setLineas] = useState([]);
  const [form, setForm] = useState(VACIA);
  const [editId, setEditId] = useState(null);
  const [error, setError] = useState("");

  const cargar = () => creditos.adminLineas().then(setLineas).catch((e) => setError(e.message));
  useEffect(() => { cargar(); }, []);

  const set = (k) => (e) =>
    setForm({ ...form, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  const editar = (l) => { setEditId(l.id); setForm({ ...l }); window.scrollTo(0, 0); };
  const nuevo = () => { setEditId(null); setForm(VACIA); };

  async function guardar(e) {
    e.preventDefault();
    setError("");
    const payload = { ...form };
    delete payload.id;
    try {
      if (editId) await creditos.editarLinea(editId, payload);
      else await creditos.crearLinea(payload);
      nuevo(); cargar();
    } catch (err) { setError(err.message); }
  }

  const Check = ({ campo, children }) => (
    <label className="flex items-center gap-2 text-sm text-gray-700 self-end">
      <input type="checkbox" checked={!!form[campo]} onChange={set(campo)} className="w-auto" />
      {children}
    </label>
  );

  return (
    <>
      <PageHeader
        titulo="Líneas de crédito"
        descripcion="Configuración del motor: sistema de cálculo, tasas, afectación del haber y topes de cada línea."
      />

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      {puedeEscribir && (
        <Card className="mb-4">
          <h2 className="font-semibold text-gray-800 mb-3">
            {editId ? `Editar línea #${editId}` : "Nueva línea de crédito"}
          </h2>
          <form onSubmit={guardar} className="grid gap-3 sm:grid-cols-3">
            <Field label="Nombre" className="sm:col-span-2">
              <input className="input w-full" value={form.nombre} onChange={set("nombre")} required />
            </Field>
            <Field label="Cartera (código)">
              <input type="number" className="input w-full" value={form.cartera} onChange={set("cartera")} />
            </Field>
            <Field label="Sistema de cálculo">
              <select className="input w-full" value={form.tipo_calculo} onChange={set("tipo_calculo")}>
                {Object.entries(SISTEMAS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </Field>
            <Field label="TNA (%)"><input className="input w-full" value={form.tna} onChange={set("tna")} /></Field>
            <Field label="Mora diaria (%)">
              <input className="input w-full" value={form.tasa_mora_diaria} onChange={set("tasa_mora_diaria")} />
            </Field>
            <Field label="% afectación haber">
              <input className="input w-full" value={form.por_afecta} onChange={set("por_afecta")} />
            </Field>
            <Field label="Seguro (% saldo)">
              <input className="input w-full" value={form.seguro_pct} onChange={set("seguro_pct")} />
            </Field>
            <Field label="Gastos adm (% saldo)">
              <input className="input w-full" value={form.gastos_adm_pct} onChange={set("gastos_adm_pct")} />
            </Field>
            <Field label="Plazo máx (cuotas)">
              <input type="number" className="input w-full" value={form.plazo_max} onChange={set("plazo_max")} />
            </Field>
            <Field label="Monto máximo">
              <input className="input w-full" value={form.monto_max} onChange={set("monto_max")} />
            </Field>
            <Field label="Plazo de gracia">
              <input type="number" className="input w-full" value={form.plazo_gracia} onChange={set("plazo_gracia")} />
            </Field>
            <Field label="% cancelado para previo pago">
              <input className="input w-full" value={form.porcent_pp} onChange={set("porcent_pp")} />
            </Field>
            <Field label="Cta. contable">
              <input className="input w-full" value={form.cta_contable} onChange={set("cta_contable")} />
            </Field>
            <Check campo="activa">Activa (habilitada)</Check>
            <Check campo="paga_interes_gracia">Paga interés en gracia</Check>
            <Check campo="suma_int_gracia_capital">Suma int. gracia a capital</Check>
            <Check campo="admite_previo_pago">Admite previo pago</Check>
            <div className="sm:col-span-3 flex gap-2">
              <Boton type="submit">{editId ? "Guardar cambios" : "Crear línea"}</Boton>
              {editId && <Boton type="button" variante="secundario" onClick={nuevo}>Cancelar</Boton>}
            </div>
          </form>
        </Card>
      )}

      <Card padding={false}>
        <p className="px-4 py-3 text-sm text-gray-500 border-b border-gray-200">
          {lineas.length} líneas{puedeEscribir ? " · clickeá una para editarla" : ""}
        </p>
        <div className="p-4">
          <DataTable columns={COLS} rows={lineas} rowKey={(l) => l.id}
                     onRowClick={puedeEscribir ? editar : undefined}
                     clientSort pageSize={25} defaultSort="nombre" emptyText="Sin líneas" />
        </div>
      </Card>
    </>
  );
}
