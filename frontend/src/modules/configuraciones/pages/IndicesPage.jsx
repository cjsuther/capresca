import { useEffect, useMemo, useState } from "react";
import { PageHeader, Card, Toolbar, Field, LimpiarFiltros, Alerta, Boton, Modal } from "../../../components/ui";
import { DataTable } from "../../../components/ui/DataTable";
import { Pill } from "../../../components/ui/Pill";
import { Confirmacion } from "../../../components/ui/Confirmacion";
import {
  listarIndices, crearIndice, editarIndice, bajaIndice, reactivarIndice, mensajeDeError,
} from "../../../api/configuraciones";
import { usePuedeEditar } from "../permisos";

const VACIO = { codigo: "", nombre: "", valor: "", fuente: "", fecha_valor: "", activo: true };
const fecha = (iso) => (iso ? new Date(`${iso}T00:00:00`).toLocaleDateString("es-AR") : "—");
const pct = (n) => `${Number(n).toLocaleString("es-AR", { maximumFractionDigits: 4 })} %`;

export default function IndicesPage() {
  const puedeEditar = usePuedeEditar("indices");
  const [items, setItems] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [form, setForm] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const [errForm, setErrForm] = useState("");
  const [baja, setBaja] = useState(null);

  const cargar = () =>
    listarIndices("todos")
      .then((d) => { setItems(d.items); setError(""); })
      .catch((e) => setError(mensajeDeError(e, "No se pudieron cargar los índices")))
      .finally(() => setCargando(false));
  useEffect(() => { cargar(); }, []);

  const visibles = useMemo(() => {
    const t = q.trim().toLowerCase();
    return items.filter((i) => !t || i.codigo.toLowerCase().includes(t) || i.nombre.toLowerCase().includes(t));
  }, [items, q]);

  const abrir = (i) => { setErrForm(""); setForm(i ? { ...VACIO, ...i, fecha_valor: i.fecha_valor || "" } : { ...VACIO }); };
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function guardar(e) {
    e.preventDefault();
    setGuardando(true); setErrForm("");
    const d = { ...form, valor: Number(form.valor || 0), fecha_valor: form.fecha_valor || null };
    try {
      if (form.id) await editarIndice(form.id, d);
      else await crearIndice(d);
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
      if (activar) await reactivarIndice(i.id);
      else await bajaIndice(i.id);
      cargar();
    } catch (err) {
      setError(mensajeDeError(err));
    } finally {
      setBaja(null);
    }
  }

  const columnas = [
    { key: "codigo", label: "Código", sortable: true, render: (i) => <span className="font-medium text-gray-800">{i.codigo}</span> },
    { key: "nombre", label: "Nombre", sortable: true },
    { key: "valor", label: "Valor (TNA)", align: "right", sortable: true, render: (i) => pct(i.valor) },
    { key: "fuente", label: "Fuente" },
    { key: "fecha_valor", label: "Al", sortable: true, render: (i) => fecha(i.fecha_valor) },
    { key: "activo", label: "Estado", render: (i) => <Pill tono={i.activo ? "ok" : "neutral"}>{i.activo ? "Activo" : "De baja"}</Pill> },
    ...(puedeEditar ? [{
      key: "acciones", label: "", align: "right",
      render: (i) => (
        <div className="flex justify-end gap-2">
          <button onClick={() => abrir(i)} className="text-blue-600 hover:underline text-sm">Actualizar</button>
          {i.activo
            ? <button onClick={() => setBaja(i)} className="text-red-600 hover:underline text-sm">Dar de baja</button>
            : <button onClick={() => cambiarEstado(i, true)} className="text-green-700 hover:underline text-sm">Reactivar</button>}
        </div>
      ),
    }] : []),
  ];

  return (
    <>
      <PageHeader titulo="Índices de referencia"
                  descripcion="Tasas de referencia para las líneas de tasa variable (TNA = índice + margen). Un cambio impacta en las simulaciones nuevas y en el próximo repricing de los contratos.">
        {puedeEditar && <Boton onClick={() => abrir(null)}>＋ Nuevo índice</Boton>}
      </PageHeader>

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      <Card padding={false}>
        <Toolbar>
          <Field label="Buscar">
            <input className="input" placeholder="Código o nombre" value={q} onChange={(e) => setQ(e.target.value)} />
          </Field>
          <LimpiarFiltros activo={!!q} onClear={() => setQ("")} />
        </Toolbar>
        <DataTable columns={columnas} rows={visibles} rowKey={(i) => i.id} clientSort defaultSort="codigo"
                   emptyText={cargando ? "Cargando…" : "No hay índices que coincidan"} />
      </Card>

      {form && (
        <Modal titulo={form.id ? `Actualizar ${form.codigo}` : "Nuevo índice"} eyebrow="Índices de referencia"
               onClose={() => setForm(null)} ancho="max-w-xl"
               footer={<>
                 <span className="flex-1" />
                 <Boton variante="secundario" type="button" onClick={() => setForm(null)}>Cancelar</Boton>
                 <Boton type="submit" form="form-indice" disabled={guardando}>{guardando ? "Guardando…" : "Guardar"}</Boton>
               </>}>
          <form id="form-indice" onSubmit={guardar} className="grid sm:grid-cols-2 gap-3">
            {errForm && <div className="sm:col-span-2"><Alerta>{errForm}</Alerta></div>}
            <Field label="Código"><input className="input" required maxLength={30} value={form.codigo} onChange={set("codigo")} /></Field>
            <Field label="Nombre"><input className="input" required maxLength={120} value={form.nombre} onChange={set("nombre")} /></Field>
            <Field label="Valor (% nominal anual)">
              <input className="input" type="number" required min="0" max="1000" step="0.0001" value={form.valor} onChange={set("valor")} />
            </Field>
            <Field label="Valor al"><input className="input" type="date" value={form.fecha_valor} onChange={set("fecha_valor")} /></Field>
            <Field label="Fuente" className="sm:col-span-2">
              <input className="input" maxLength={60} placeholder="BCRA, INDEC…" value={form.fuente} onChange={set("fuente")} />
            </Field>
          </form>
        </Modal>
      )}

      {baja && (
        <Confirmacion titulo="Dar de baja el índice"
                      mensaje={`${baja.codigo} · ${baja.nombre}\nNo se ofrece para líneas nuevas. Las líneas publicadas que lo usan siguen cotizando con su último valor.`}
                      confirmar="Dar de baja" onConfirmar={() => cambiarEstado(baja, false)} onCancelar={() => setBaja(null)} />
      )}
    </>
  );
}
