import { useCallback, useEffect, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";

import { activarSerie, crearSerie, editarSerie, eliminarSerie, getSeries } from "../../../api/despacho";
import { Alerta, Boton, Card, Field, Modal, PageHeader } from "../../../components/ui";
import { useHasPermission } from "../../../context/usePermissions";

const SERIE_POR_DEFECTO = 1;
const detalle = (e, texto) => e?.response?.data?.detail || texto;

/** Alta (número + nombre) o edición (sólo nombre y orden: el número es la clave de la numeración). */
function FormSerie({ serie, onClose, onGuardada }) {
  const nueva = !serie;
  const [numero, setNumero] = useState(serie?.serie ?? "");
  const [nombre, setNombre] = useState(serie?.nombre ?? "");
  const [orden, setOrden] = useState(serie?.orden ?? "");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  async function guardar(e) {
    e.preventDefault();
    setError("");
    if (nueva && (!/^\d+$/.test(String(numero).trim()) || Number(numero) < 1)) {
      setError("El número de la serie es obligatorio y tiene que ser mayor que cero.");
      return;
    }
    if (!nombre.trim()) {
      setError("El nombre de la serie es obligatorio.");
      return;
    }
    const datos = { nombre, orden: String(orden).trim() === "" ? null : Number(orden) };
    setGuardando(true);
    try {
      onGuardada(nueva ? await crearSerie({ ...datos, serie: Number(numero) }) : await editarSerie(serie.serie, datos));
    } catch (err) {
      setError(detalle(err, "No se pudo guardar la serie"));
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Modal titulo={nueva ? "Nueva serie" : `Serie ${serie.serie}`} eyebrow="Catálogos" ancho="max-w-md" onClose={onClose}
           footer={(
             <>
               <Boton variante="secundario" type="button" onClick={onClose}>Cancelar</Boton>
               <Boton type="submit" form="form-serie" className="ml-auto" disabled={guardando}>
                 {guardando ? "Guardando…" : "Guardar"}
               </Boton>
             </>
           )}>
      <form id="form-serie" onSubmit={guardar} className="space-y-3">
        <Alerta>{error}</Alerta>
        <Field label="Número">
          <input type="number" min="1" className="input w-32" aria-label="Número de serie" value={numero}
                 disabled={!nueva} onChange={(e) => setNumero(e.target.value)} />
        </Field>
        <p className="text-xs text-gray-500 -mt-1">
          {nueva
            ? "Si la serie viene del sistema anterior, usá el mismo número (TIPO_RES). Después no se puede cambiar."
            : "El número no se cambia: es la clave de la numeración de los actos."}
        </p>
        <Field label="Nombre">
          <input className="input w-full" aria-label="Nombre de la serie" maxLength={60} value={nombre}
                 onChange={(e) => setNombre(e.target.value)} />
        </Field>
        <Field label="Orden en las listas">
          <input type="number" min="0" className="input w-32" aria-label="Orden" value={orden}
                 placeholder={nueva ? "al final" : ""} onChange={(e) => setOrden(e.target.value)} />
        </Field>
      </form>
    </Modal>
  );
}

/** Las series de numeración: cada una lleva su propio correlativo y N° oficial por año. */
function SeriesCatalogo() {
  const puedeEditar = useHasPermission("despacho", "series:write");
  const [series, setSeries] = useState([]);
  const [editando, setEditando] = useState(null);     // null | "nueva" | serie
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const cargar = useCallback(() => {
    getSeries({ incluir_inactivas: true }).then(setSeries)
      .catch((e) => setError(detalle(e, "No se pudieron cargar las series")));
  }, []);
  useEffect(cargar, [cargar]);

  const accion = async (fn, mensaje) => {
    setError(""); setOk("");
    try { await fn(); setOk(mensaje); cargar(); }
    catch (e) { setError(detalle(e, "No se pudo completar la acción")); }
  };

  const borrar = (s) => {
    if (!window.confirm(`¿Borrar la serie ${s.serie} · ${s.nombre}? No se puede deshacer.`)) return;
    accion(() => eliminarSerie(s.serie), `Se borró la serie ${s.serie}.`);
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="text-sm text-gray-500 max-w-3xl">
          El área que emite el acto. Cada serie numera por su cuenta (correlativo y N° oficial por año). Una serie
          inactiva no se ofrece para modelos ni actos nuevos, pero lo ya emitido en ella no cambia.
        </p>
        {puedeEditar && (
          <Boton onClick={() => setEditando("nueva")} className="inline-flex items-center gap-2">
            <Plus size={16} /> Nueva serie
          </Boton>
        )}
      </div>

      <Alerta>{error}</Alerta>
      {ok && <Alerta tipo="ok">{ok}</Alerta>}

      <Card padding={false}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-xs uppercase tracking-wide text-gray-500">
                <th className="px-3 py-2 text-right">N°</th>
                <th className="px-3 py-2 text-left">Nombre</th>
                <th className="px-3 py-2 text-right">Orden</th>
                <th className="px-3 py-2 text-left">Estado</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {series.map((s) => (
                <tr key={s.serie} className={s.activa ? "" : "text-gray-400"}>
                  <td className="px-3 py-2 text-right tabular-nums">{s.serie}</td>
                  <td className="px-3 py-2 font-medium">{s.nombre}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{s.orden}</td>
                  <td className="px-3 py-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${s.activa ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                      {s.activa ? "Activa" : "Inactiva"}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    {puedeEditar && (
                      <div className="flex items-center justify-end gap-2">
                        <button type="button" aria-label={`Editar serie ${s.serie}`} title="Editar"
                                onClick={() => setEditando(s)} className="p-1 text-gray-500 hover:text-blue-600">
                          <Pencil size={16} />
                        </button>
                        {s.serie !== SERIE_POR_DEFECTO && (
                          <button type="button" className="text-xs text-gray-600 hover:text-blue-600"
                                  onClick={() => accion(() => activarSerie(s.serie, !s.activa),
                                                        `Serie ${s.serie} ${s.activa ? "desactivada" : "activada"}.`)}>
                            {s.activa ? "Desactivar" : "Activar"}
                          </button>
                        )}
                        {s.serie !== SERIE_POR_DEFECTO && !s.en_uso && (
                          <button type="button" aria-label={`Borrar serie ${s.serie}`} title="Borrar (no tiene uso)"
                                  onClick={() => borrar(s)} className="p-1 text-gray-500 hover:text-red-600">
                            <Trash2 size={16} />
                          </button>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!puedeEditar && (
          <p className="px-3 py-2 text-xs text-gray-500 border-t border-gray-100">
            Para crear o editar series hace falta el permiso «Administrar las series de numeración».
          </p>
        )}
      </Card>

      {editando && (
        <FormSerie serie={editando === "nueva" ? null : editando} onClose={() => setEditando(null)}
                   onGuardada={(s) => { setEditando(null); setOk(`Serie ${s.serie} · ${s.nombre} guardada.`); cargar(); }} />
      )}
    </div>
  );
}

// Los catálogos del módulo. Por ahora, las series; los próximos se suman como otra pestaña.
const CATALOGOS = [{ clave: "series", titulo: "Series de numeración", Componente: SeriesCatalogo }];

export default function CatalogosPage() {
  const [activo, setActivo] = useState(CATALOGOS[0].clave);
  const { Componente } = CATALOGOS.find((c) => c.clave === activo);

  return (
    <div className="space-y-4">
      <PageHeader titulo="Catálogos" descripcion="Las tablas que configuran el despacho." />
      <div role="tablist" className="flex gap-1 border-b border-gray-200">
        {CATALOGOS.map((c) => (
          <button key={c.clave} type="button" role="tab" aria-selected={c.clave === activo}
                  onClick={() => setActivo(c.clave)}
                  className={`px-3 py-2 text-sm -mb-px border-b-2 ${c.clave === activo
                    ? "border-blue-600 text-blue-700 font-medium" : "border-transparent text-gray-500 hover:text-gray-800"}`}>
            {c.titulo}
          </button>
        ))}
      </div>
      <Componente />
    </div>
  );
}
