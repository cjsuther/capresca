import { useEffect, useMemo, useState } from "react";
import { PageHeader, Card, Toolbar, Field, LimpiarFiltros, Alerta, Boton, Modal } from "../../../components/ui";
import { DataTable } from "../../../components/ui/DataTable";
import { Pill } from "../../../components/ui/Pill";
import { Confirmacion } from "../../../components/ui/Confirmacion";
import {
  listarImpuestos, crearImpuesto, editarImpuesto, bajaImpuesto, reactivarImpuesto, mensajeDeError,
} from "../../../api/configuraciones";
import { usePuedeEditar } from "../permisos";

const TIPOS = ["IVA", "IIBB", "SELLADO", "PERCEPCION", "RETENCION", "OTRO"];
const BASES = [
  ["INTERES", "Interés"], ["CARGOS", "Cargos"], ["CUOTA", "Cuota"], ["CAPITAL", "Capital"], ["TOTAL", "Total"],
];
const NOMBRE_BASE = Object.fromEntries(BASES);
const VACIO = {
  codigo: "", nombre: "", tipo: "IVA", alicuota: "", base: "INTERES", cuenta_contable: "",
  jurisdiccion: "", vigente_desde: "", vigente_hasta: "", activo: true,
};

const fecha = (iso) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString("es-AR") : "");
const pct = (n) => `${Number(n).toLocaleString("es-AR", { maximumFractionDigits: 4 })} %`;

export default function ImpuestosPage() {
  const puedeEditar = usePuedeEditar("impuestos");
  const [items, setItems] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [soloActivos, setSoloActivos] = useState(false);
  const [form, setForm] = useState(null);          // null = cerrado; {id?, ...campos}
  const [guardando, setGuardando] = useState(false);
  const [errForm, setErrForm] = useState("");
  const [baja, setBaja] = useState(null);

  const cargar = () =>
    listarImpuestos("todos")
      .then((d) => { setItems(d.items); setError(""); })
      .catch((e) => setError(mensajeDeError(e, "No se pudieron cargar los impuestos")))
      .finally(() => setCargando(false));
  useEffect(() => { cargar(); }, []);

  const visibles = useMemo(() => {
    const t = q.trim().toLowerCase();
    return items.filter((i) => (!soloActivos || i.activo)
      && (!t || i.codigo.toLowerCase().includes(t) || i.nombre.toLowerCase().includes(t)));
  }, [items, q, soloActivos]);

  const abrir = (i) => {
    setErrForm("");
    setForm(i ? { ...VACIO, ...i, vigente_desde: i.vigente_desde || "", vigente_hasta: i.vigente_hasta || "" } : { ...VACIO });
  };
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  async function guardar(e) {
    e.preventDefault();
    setGuardando(true); setErrForm("");
    const d = {
      ...form, alicuota: Number(form.alicuota || 0),
      vigente_desde: form.vigente_desde || null, vigente_hasta: form.vigente_hasta || null,
    };
    try {
      if (form.id) await editarImpuesto(form.id, d);
      else await crearImpuesto(d);
      setForm(null);
      cargar();
    } catch (err) {
      setErrForm(mensajeDeError(err));
    } finally {
      setGuardando(false);
    }
  }

  async function cambiarEstado(i, activar) {
    setError("");
    try {
      if (activar) await reactivarImpuesto(i.id);
      else await bajaImpuesto(i.id);
      setBaja(null);
      cargar();
    } catch (err) {
      setError(mensajeDeError(err));
      setBaja(null);
    }
  }

  const columnas = [
    { key: "codigo", label: "Código", sortable: true, render: (i) => <span className="font-medium text-gray-800">{i.codigo}</span> },
    { key: "nombre", label: "Nombre", sortable: true },
    { key: "tipo", label: "Tipo", sortable: true },
    { key: "alicuota", label: "Alícuota", align: "right", sortable: true, render: (i) => <span className="tabular-nums">{pct(i.alicuota)}</span> },
    { key: "base", label: "Base", render: (i) => NOMBRE_BASE[i.base] || i.base },
    { key: "cuenta_contable", label: "Cuenta contable" },
    {
      key: "vigencia", label: "Vigencia",
      render: (i) => (i.vigente_desde || i.vigente_hasta
        ? `${fecha(i.vigente_desde) || "…"} – ${fecha(i.vigente_hasta) || "…"}` : <span className="text-gray-400">Sin límite</span>),
    },
    { key: "activo", label: "Estado", render: (i) => <Pill tono={i.activo ? "ok" : "neutral"}>{i.activo ? "Activo" : "De baja"}</Pill> },
    ...(puedeEditar ? [{
      key: "acciones", label: "", align: "right",
      render: (i) => (
        <div className="flex justify-end gap-2">
          <button onClick={() => abrir(i)} className="text-blue-600 hover:underline text-sm">Editar</button>
          {i.activo
            ? <button onClick={() => setBaja(i)} className="text-red-600 hover:underline text-sm">Dar de baja</button>
            : <button onClick={() => cambiarEstado(i, true)} className="text-green-700 hover:underline text-sm">Reactivar</button>}
        </div>
      ),
    }] : []),
  ];

  return (
    <>
      <PageHeader titulo="Impuestos"
                  descripcion="IVA, ingresos brutos, sellados y percepciones. Créditos los usa al armar sus productos (componente de impuestos).">
        {puedeEditar && <Boton onClick={() => abrir(null)}>＋ Nuevo impuesto</Boton>}
      </PageHeader>

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      <Card padding={false}>
        <Toolbar>
          <Field label="Buscar">
            <input className="input" placeholder="Código o nombre" value={q} onChange={(e) => setQ(e.target.value)} />
          </Field>
          <label className="flex items-center gap-2 text-sm text-gray-600 pb-2">
            <input type="checkbox" checked={soloActivos} onChange={(e) => setSoloActivos(e.target.checked)} />
            Sólo activos
          </label>
          <LimpiarFiltros activo={!!q || soloActivos} onClear={() => { setQ(""); setSoloActivos(false); }} />
        </Toolbar>
        <DataTable columns={columnas} rows={visibles} rowKey={(i) => i.id} clientSort defaultSort="codigo"
                   emptyText={cargando ? "Cargando…" : "No hay impuestos que coincidan"} />
      </Card>

      {form && (
        <Modal titulo={form.id ? `Editar ${form.codigo}` : "Nuevo impuesto"} eyebrow="Impuestos"
               onClose={() => setForm(null)} ancho="max-w-2xl"
               footer={<>
                 <span className="flex-1" />
                 <Boton variante="secundario" type="button" onClick={() => setForm(null)}>Cancelar</Boton>
                 <Boton type="submit" form="form-impuesto" disabled={guardando}>{guardando ? "Guardando…" : "Guardar"}</Boton>
               </>}>
          <form id="form-impuesto" onSubmit={guardar} className="grid sm:grid-cols-2 gap-3">
            {errForm && <div className="sm:col-span-2"><Alerta>{errForm}</Alerta></div>}
            <Field label="Código"><input className="input" required maxLength={20} value={form.codigo} onChange={set("codigo")} /></Field>
            <Field label="Nombre"><input className="input" required maxLength={120} value={form.nombre} onChange={set("nombre")} /></Field>
            <Field label="Tipo">
              <select className="input" value={form.tipo} onChange={set("tipo")}>
                {TIPOS.map((t) => <option key={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Alícuota (%)">
              <input className="input" type="number" required min="0" max="100" step="0.0001" value={form.alicuota} onChange={set("alicuota")} />
            </Field>
            <Field label="Se calcula sobre">
              <select className="input" value={form.base} onChange={set("base")}>
                {BASES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </Field>
            <Field label="Cuenta contable"><input className="input" maxLength={12} value={form.cuenta_contable} onChange={set("cuenta_contable")} /></Field>
            <Field label="Jurisdicción (IIBB)"><input className="input" maxLength={40} value={form.jurisdiccion} onChange={set("jurisdiccion")} /></Field>
            <div />
            <Field label="Vigente desde"><input className="input" type="date" value={form.vigente_desde} onChange={set("vigente_desde")} /></Field>
            <Field label="Vigente hasta"><input className="input" type="date" value={form.vigente_hasta} onChange={set("vigente_hasta")} /></Field>
            <p className="sm:col-span-2 text-xs text-gray-500">
              Los productos de crédito guardan la alícuota al publicarse: cambiarla acá no modifica contratos ya firmados.
            </p>
          </form>
        </Modal>
      )}

      {baja && (
        <Confirmacion titulo="Dar de baja el impuesto"
                      mensaje={`${baja.codigo} · ${baja.nombre}\nDeja de ofrecerse al armar productos nuevos. Los productos que ya lo usan no cambian.`}
                      confirmar="Dar de baja" onConfirmar={() => cambiarEstado(baja, false)} onCancelar={() => setBaja(null)} />
      )}
    </>
  );
}
