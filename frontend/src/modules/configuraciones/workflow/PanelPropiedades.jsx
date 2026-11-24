import { useState } from "react";
import { Trash2, X } from "lucide-react";
import { Field } from "../../../components/ui";
import ConstructorCondicion from "./ConstructorCondicion";
import { describirCondicion } from "./condiciones";
import { ETIQUETA_TIPO, RESULTADOS, ROLES, TIPOS_DESTINATARIO, nombreDe } from "./grafo";

/**
 * Propiedades del nodo o de la conexión seleccionados.
 * `personas`: { grupos: [{id, name}], usuarios: [username], deSeguridad: bool } para los selectores
 * (si Seguridad no se pudo leer, se escribe el nombre a mano).
 */
export default function PanelPropiedades({ grafo, seleccion, variables, personas, soloLectura, problemas = {},
                                           onCambiarNodo, onCambiarConexion, onQuitar }) {
  if (!seleccion) {
    return <p className="text-sm text-gray-500">Elegí un nodo o una flecha para ver y cambiar sus propiedades.</p>;
  }
  if (seleccion.tipo === "conexion") {
    const c = grafo.conexiones.find((x) => x.id === seleccion.id);
    if (!c) return null;
    return <PropsConexion c={c} grafo={grafo} variables={variables} soloLectura={soloLectura}
                          onCambiar={(cambios) => onCambiarConexion(c.id, cambios)} onQuitar={() => onQuitar(seleccion)} />;
  }
  const n = grafo.nodos.find((x) => x.id === seleccion.id);
  if (!n) return null;
  const cambiar = (cambios) => onCambiarNodo(n.id, cambios);
  const probs = problemas[n.id] || [];
  return (
    <div className="grid gap-3" aria-label={`Propiedades de ${nombreDe(n)}`}>
      <div className="flex items-center gap-2">
        <span className="text-xs uppercase tracking-wide font-semibold text-gray-500">{ETIQUETA_TIPO[n.tipo]}</span>
        <span className="flex-1" />
        {!soloLectura && n.tipo !== "inicio" && (
          <button type="button" className="text-red-600 hover:underline text-sm flex items-center gap-1" onClick={() => onQuitar(seleccion)}>
            <Trash2 size={14} /> Quitar
          </button>
        )}
      </div>
      {probs.length > 0 && (
        <ul className="text-xs grid gap-1">
          {probs.map((x, i) => <li key={i} className={x.nivel === "error" ? "text-red-600" : "text-amber-700"}>{x.mensaje}</li>)}
        </ul>
      )}
      <Field label="Nombre">
        <input className="input" maxLength={80} value={n.nombre || ""} disabled={soloLectura}
               onChange={(e) => cambiar({ nombre: e.target.value })} />
      </Field>
      {n.tipo === "aprobacion" && <PropsAprobacion n={n} personas={personas} soloLectura={soloLectura} cambiar={cambiar} />}
      {n.tipo === "notificacion" && <PropsNotificacion n={n} personas={personas} soloLectura={soloLectura} cambiar={cambiar} />}
      {n.tipo === "fin" && (
        <Field label="Termina">
          <select className="input" value={n.resultado || ""} disabled={soloLectura} onChange={(e) => cambiar({ resultado: e.target.value })}>
            <option value="">— elegí —</option>
            {Object.entries(RESULTADOS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </Field>
      )}
      {n.tipo === "decision" && <SalidasDecision n={n} grafo={grafo} variables={variables} />}
    </div>
  );
}

function PropsAprobacion({ n, personas, soloLectura, cambiar }) {
  const a = n.asignar || { tipo: "rol", valor: "APROBAR" };
  return (
    <>
      <Field label="Aprueba">
        <select className="input" aria-label="Tipo de aprobador" value={a.tipo || ""} disabled={soloLectura}
                onChange={(e) => cambiar({ asignar: e.target.value === "rol" ? { tipo: "rol", valor: "APROBAR" } : { tipo: "grupo", valor: "" } })}>
          <option value="rol">Un rol de aprobación</option>
          <option value="grupo">Un grupo de Seguridad</option>
        </select>
      </Field>
      {a.tipo === "rol" ? (
        <Field label="Rol">
          <select className="input" value={a.valor || ""} disabled={soloLectura} onChange={(e) => cambiar({ asignar: { tipo: "rol", valor: e.target.value } })}>
            {Object.entries(ROLES).map(([k, v]) => <option key={k} value={k}>{v} (aprobaciones:{k.toLowerCase()})</option>)}
          </select>
        </Field>
      ) : (
        <Field label="Grupo">
          {personas?.grupos?.length ? (
            <select className="input" value={a.valor || ""} disabled={soloLectura}
                    onChange={(e) => {
                      const g = personas.grupos.find((x) => x.name === e.target.value);
                      cambiar({ asignar: { tipo: "grupo", valor: e.target.value, ...(g ? { id: g.id } : {}) } });
                    }}>
              <option value="">— elegí un grupo —</option>
              {personas.grupos.map((g) => <option key={g.id} value={g.name}>{g.name}</option>)}
            </select>
          ) : (
            <input className="input" placeholder="Nombre del grupo en Seguridad" value={a.valor || ""} disabled={soloLectura}
                   onChange={(e) => cambiar({ asignar: { tipo: "grupo", valor: e.target.value } })} />
          )}
        </Field>
      )}
      {a.tipo === "grupo" && (
        <p className="text-xs text-amber-700">Por grupo se puede diseñar y guardar, pero no publicar hasta el motor nuevo (fase 3).</p>
      )}
      <label className="flex items-start gap-2 text-sm text-gray-600">
        <input type="checkbox" className="mt-1" checked={n.cuatroOjos !== false} disabled={soloLectura}
               onChange={(e) => cambiar({ cuatroOjos: e.target.checked })} />
        Cuatro-ojos: no aprueba quien envió ni quien aprobó un paso anterior
      </label>
      <Personas titulo="Además aprueban (aunque no tengan el rol)" valores={n.incluir || []} personas={personas}
                soloLectura={soloLectura} onChange={(incluir) => cambiar({ incluir })} tono="ok" />
      <Personas titulo="No aprueban (aunque tengan el rol)" valores={n.excluir || []} personas={personas}
                soloLectura={soloLectura} onChange={(excluir) => cambiar({ excluir })} tono="crit" />
    </>
  );
}

/** Lista de usuarios con alta por selector (usuarios de Seguridad) o a mano. */
function Personas({ titulo, valores, personas, soloLectura, onChange, tono }) {
  const [nuevo, setNuevo] = useState("");
  const idLista = `usuarios-${titulo.length}`;
  const agregar = () => {
    const u = nuevo.trim();
    if (u && !valores.includes(u)) onChange([...valores, u].sort());
    setNuevo("");
  };
  return (
    <div className="grid gap-1">
      <span className="text-sm text-gray-600">{titulo}</span>
      <div className="flex flex-wrap gap-1.5">
        {valores.length === 0 && <span className="text-xs text-gray-400">nadie</span>}
        {valores.map((u) => (
          <span key={u} className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
            tono === "ok" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
            {u}
            {!soloLectura && (
              <button type="button" aria-label={`Quitar ${u}`} onClick={() => onChange(valores.filter((x) => x !== u))}><X size={12} /></button>
            )}
          </span>
        ))}
      </div>
      {!soloLectura && (
        <div className="flex gap-1">
          <input className="input !py-1" list={idLista} aria-label={titulo} placeholder="usuario" value={nuevo}
                 onChange={(e) => setNuevo(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); agregar(); } }} />
          <datalist id={idLista}>{(personas?.usuarios || []).map((u) => <option key={u} value={u} />)}</datalist>
          <button type="button" className="text-sm text-blue-600 hover:underline" onClick={agregar}>Agregar</button>
        </div>
      )}
    </div>
  );
}

function PropsNotificacion({ n, personas, soloLectura, cambiar }) {
  const dest = n.destinatarios || [];
  const set = (i, d) => cambiar({ destinatarios: dest.map((x, j) => (j === i ? d : x)) });
  return (
    <>
      <div className="grid gap-2">
        <span className="text-sm text-gray-600">Avisar a</span>
        {dest.map((d, i) => (
          <div key={i} className="flex gap-1">
            <select className="input !py-1" aria-label={`Destinatario ${i + 1}`} value={d.tipo} disabled={soloLectura}
                    onChange={(e) => set(i, { tipo: e.target.value, valor: "" })}>
              {Object.entries(TIPOS_DESTINATARIO).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            {d.tipo === "rol" && (
              <select className="input !py-1" aria-label={`Rol ${i + 1}`} value={d.valor} disabled={soloLectura}
                      onChange={(e) => set(i, { ...d, valor: e.target.value })}>
                <option value="">—</option>
                {Object.entries(ROLES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            )}
            {(d.tipo === "grupo" || d.tipo === "usuario") && (
              <input className="input !py-1" aria-label={`${TIPOS_DESTINATARIO[d.tipo]} ${i + 1}`} value={d.valor} disabled={soloLectura}
                     list={d.tipo === "grupo" ? "wf-grupos" : "wf-usuarios"} onChange={(e) => set(i, { ...d, valor: e.target.value })} />
            )}
            {!soloLectura && (
              <button type="button" aria-label={`Quitar destinatario ${i + 1}`} className="text-gray-400 hover:text-red-600"
                      onClick={() => cambiar({ destinatarios: dest.filter((_, j) => j !== i) })}><X size={16} /></button>
            )}
          </div>
        ))}
        <datalist id="wf-grupos">{(personas?.grupos || []).map((g) => <option key={g.id} value={g.name} />)}</datalist>
        <datalist id="wf-usuarios">{(personas?.usuarios || []).map((u) => <option key={u} value={u} />)}</datalist>
        {!soloLectura && (
          <button type="button" className="text-sm text-blue-600 hover:underline justify-self-start"
                  onClick={() => cambiar({ destinatarios: [...dest, { tipo: "rol", valor: "" }] })}>＋ Destinatario</button>
        )}
      </div>
      <Field label="Mensaje">
        <textarea className="input" rows={3} maxLength={500} value={n.mensaje || ""} disabled={soloLectura}
                  onChange={(e) => cambiar({ mensaje: e.target.value })} />
      </Field>
      <p className="text-xs text-amber-700">Las notificaciones se diseñan ahora y se envían cuando llegue el motor nuevo (fase 3).</p>
    </>
  );
}

function SalidasDecision({ n, grafo, variables }) {
  const salidas = grafo.conexiones.filter((c) => c.de === n.id);
  const destino = (id) => nombreDe(grafo.nodos.find((x) => x.id === id));
  return (
    <div className="grid gap-1">
      <span className="text-sm text-gray-600">Caminos (elegí una flecha para cambiar su condición)</span>
      {salidas.length === 0 && <span className="text-xs text-gray-400">Todavía no tiene salidas: arrastrá desde el punto de abajo.</span>}
      <ul className="text-sm grid gap-1">
        {salidas.map((c) => (
          <li key={c.id}>→ <b>{destino(c.a)}</b>: {c.defecto ? "si no se cumple ninguna" : describirCondicion(c.condicion, variables)}</li>
        ))}
      </ul>
    </div>
  );
}

function PropsConexion({ c, grafo, variables, soloLectura, onCambiar, onQuitar }) {
  const origen = grafo.nodos.find((x) => x.id === c.de);
  const destino = grafo.nodos.find((x) => x.id === c.a);
  return (
    <div className="grid gap-3" aria-label="Propiedades de la flecha">
      <div className="flex items-center gap-2">
        <span className="text-xs uppercase tracking-wide font-semibold text-gray-500">Flecha</span>
        <span className="flex-1" />
        {!soloLectura && (
          <button type="button" className="text-red-600 hover:underline text-sm flex items-center gap-1" onClick={onQuitar}>
            <Trash2 size={14} /> Quitar
          </button>
        )}
      </div>
      <p className="text-sm text-gray-700">De <b>{nombreDe(origen)}</b> a <b>{nombreDe(destino)}</b></p>
      {origen?.tipo === "aprobacion" && (
        <Field label="Cuándo">
          <select className="input" value={c.salida || ""} disabled={soloLectura} onChange={(e) => onCambiar({ salida: e.target.value })}>
            <option value="aprobado">Si aprueba</option>
            <option value="rechazado">Si rechaza</option>
          </select>
        </Field>
      )}
      {origen?.tipo === "decision" && (
        <>
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input type="checkbox" checked={!!c.defecto} disabled={soloLectura}
                   onChange={(e) => onCambiar(e.target.checked ? { defecto: true, condicion: undefined }
                                                               : { defecto: false, condicion: { modo: "todas", reglas: [] } })} />
            Camino «si no» (cuando no se cumple ninguna otra condición)
          </label>
          {!c.defecto && (
            <ConstructorCondicion condicion={c.condicion} variables={variables} soloLectura={soloLectura}
                                  onChange={(condicion) => onCambiar({ condicion })} />
          )}
        </>
      )}
    </div>
  );
}
