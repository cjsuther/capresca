import { useEffect, useState } from "react";
import { PageHeader, Card, Toolbar, Field, Alerta, Boton, Modal } from "../../../components/ui";
import { DataTable } from "../../../components/ui/DataTable";
import { Pill } from "../../../components/ui/Pill";
import { Confirmacion } from "../../../components/ui/Confirmacion";
import {
  listarPaises, listarFeriados, crearFeriado, editarFeriado, borrarFeriado, importarFeriados, mensajeDeError,
} from "../../../api/configuraciones";
import { usePuedeEditar } from "../permisos";

const TIPOS = [["INAMOVIBLE", "Inamovible", "crit"], ["TRASLADABLE", "Trasladable", "warn"], ["PUENTE", "Puente", "brand"]];
const TIPO = Object.fromEntries(TIPOS.map(([v, l, t]) => [v, { l, t }]));
const HOY = new Date().getFullYear();

const fechaLarga = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("es-AR", { weekday: "short", day: "2-digit", month: "2-digit", year: "numeric" });

export default function FeriadosPage() {
  const puedeEditar = usePuedeEditar("feriados");
  const [paises, setPaises] = useState([{ codigo: "AR", nombre: "Argentina" }]);
  const [pais, setPais] = useState("AR");
  const [anio, setAnio] = useState(HOY);
  const [anios, setAnios] = useState([HOY]);
  const [items, setItems] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [form, setForm] = useState(null);
  const [errForm, setErrForm] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [borrando, setBorrando] = useState(null);
  const [importando, setImportando] = useState(false);

  useEffect(() => { listarPaises().then((d) => setPaises(d.items)).catch(() => {}); }, []);

  const cargar = () => {
    setCargando(true);
    return listarFeriados(pais, anio)
      .then((d) => {
        setItems(d.items);
        setAnios([...new Set([...d.anios, HOY - 1, HOY, HOY + 1, HOY + 2])].sort());
        setError("");
      })
      .catch((e) => setError(mensajeDeError(e, "No se pudo cargar el calendario")))
      .finally(() => setCargando(false));
  };
  useEffect(() => { cargar(); }, [pais, anio]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const abrir = (f) => {
    setErrForm("");
    setForm(f ? { ...f } : { pais, fecha: `${anio}-01-01`, nombre: "", tipo: "INAMOVIBLE", activo: true });
  };

  async function guardar(e) {
    e.preventDefault();
    setGuardando(true); setErrForm("");
    try {
      if (form.id) await editarFeriado(form.id, form);
      else await crearFeriado(form);
      setForm(null);
      cargar();
    } catch (err) {
      setErrForm(mensajeDeError(err));
    } finally {
      setGuardando(false);
    }
  }

  async function borrar() {
    try {
      await borrarFeriado(borrando.id);
      cargar();
    } catch (err) {
      setError(mensajeDeError(err));
    } finally {
      setBorrando(null);
    }
  }

  async function importar() {
    setImportando(true); setError(""); setAviso("");
    try {
      const r = await importarFeriados(pais, anio);
      setAviso(`${r.importados} feriado(s) nuevo(s) de ${r.totalFuente} · fuente: ${r.fuente}.`);
      cargar();
    } catch (err) {
      setError(mensajeDeError(err));
    } finally {
      setImportando(false);
    }
  }

  const columnas = [
    { key: "fecha", label: "Fecha", sortable: true, render: (f) => <span className="tabular-nums">{fechaLarga(f.fecha)}</span> },
    { key: "nombre", label: "Feriado", sortable: true, render: (f) => <span className={f.activo ? "" : "line-through text-gray-400"}>{f.nombre}</span> },
    { key: "tipo", label: "Tipo", render: (f) => <Pill tono={TIPO[f.tipo]?.t}>{TIPO[f.tipo]?.l || f.tipo}</Pill> },
    { key: "origen", label: "Origen", render: (f) => (f.origen === "OFICIAL" ? "Calendario oficial" : "Carga manual") },
    { key: "activo", label: "Estado", render: (f) => <Pill tono={f.activo ? "ok" : "neutral"}>{f.activo ? "Vigente" : "Inactivo"}</Pill> },
    ...(puedeEditar ? [{
      key: "acciones", label: "", align: "right",
      render: (f) => (
        <div className="flex justify-end gap-2">
          <button onClick={() => abrir(f)} className="text-blue-600 hover:underline text-sm">Editar</button>
          <button onClick={() => setBorrando(f)} className="text-red-600 hover:underline text-sm">Borrar</button>
        </div>
      ),
    }] : []),
  ];

  return (
    <>
      <PageHeader titulo="Feriados"
                  descripcion="Días no laborables por país. El motor de cuotas corre a día hábil los vencimientos que caen en un feriado vigente.">
        {puedeEditar && (
          <>
            <Boton variante="secundario" onClick={importar} disabled={importando}>
              {importando ? "Importando…" : `Importar ${anio}`}
            </Boton>
            <Boton onClick={() => abrir(null)}>＋ Nuevo feriado</Boton>
          </>
        )}
      </PageHeader>

      {error && <div className="mb-4"><Alerta>{error}</Alerta></div>}
      {aviso && <div className="mb-4"><Alerta tipo="ok">{aviso}</Alerta></div>}

      <Card padding={false}>
        <Toolbar>
          <Field label="País">
            <select className="input" value={pais} onChange={(e) => setPais(e.target.value)}>
              {paises.map((p) => <option key={p.codigo} value={p.codigo}>{p.nombre}</option>)}
            </select>
          </Field>
          <Field label="Año">
            <select className="input" value={anio} onChange={(e) => setAnio(Number(e.target.value))}>
              {anios.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </Field>
          <span className="text-sm text-gray-500 pb-2">{items.filter((f) => f.activo).length} vigente(s)</span>
        </Toolbar>
        <DataTable columns={columnas} rows={items} rowKey={(f) => f.id}
                   emptyText={cargando ? "Cargando…" : `Sin feriados cargados para ${anio}.${puedeEditar ? " Podés importarlos." : ""}`} />
      </Card>

      {form && (
        <Modal titulo={form.id ? "Editar feriado" : "Nuevo feriado"} eyebrow="Feriados" onClose={() => setForm(null)} ancho="max-w-lg"
               footer={<>
                 <span className="flex-1" />
                 <Boton variante="secundario" type="button" onClick={() => setForm(null)}>Cancelar</Boton>
                 <Boton type="submit" form="form-feriado" disabled={guardando}>{guardando ? "Guardando…" : "Guardar"}</Boton>
               </>}>
          <form id="form-feriado" onSubmit={guardar} className="grid sm:grid-cols-2 gap-3">
            {errForm && <div className="sm:col-span-2"><Alerta>{errForm}</Alerta></div>}
            <Field label="Fecha"><input className="input" type="date" required value={form.fecha} onChange={set("fecha")} /></Field>
            <Field label="Tipo">
              <select className="input" value={form.tipo} onChange={set("tipo")}>
                {TIPOS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </Field>
            <Field label="Nombre" className="sm:col-span-2">
              <input className="input" required maxLength={120} value={form.nombre} onChange={set("nombre")} />
            </Field>
            <label className="sm:col-span-2 flex items-center gap-2 text-sm text-gray-600">
              <input type="checkbox" checked={form.activo} onChange={set("activo")} />
              Vigente (si no, el motor no lo tiene en cuenta)
            </label>
          </form>
        </Modal>
      )}

      {borrando && (
        <Confirmacion titulo="Borrar feriado"
                      mensaje={`${fechaLarga(borrando.fecha)} · ${borrando.nombre}\nLos cronogramas nuevos dejan de correr ese día. Los contratos ya firmados no cambian.`}
                      confirmar="Borrar" onConfirmar={borrar} onCancelar={() => setBorrando(null)} />
      )}
    </>
  );
}
