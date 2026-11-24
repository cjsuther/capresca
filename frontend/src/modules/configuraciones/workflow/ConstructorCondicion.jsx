import { Plus, X } from "lucide-react";
import { TEXTO_OPERADOR, cambiarRegla, leerValor, operadoresPara, reglaNueva } from "./condiciones";

/**
 * Constructor simple de condiciones: «variable · operador · valor», combinadas con «todas» (y) o
 * «alguna» (o). Las variables las declara el proceso.
 */
export default function ConstructorCondicion({ condicion, variables, onChange, soloLectura = false }) {
  const cond = condicion || { modo: "todas", reglas: [] };
  const reglas = cond.reglas || [];
  const hayVariables = Object.keys(variables || {}).length > 0;
  const cambiar = (i, r) => onChange({ ...cond, reglas: reglas.map((x, j) => (j === i ? r : x)) });

  if (!hayVariables) {
    return <p className="text-sm text-gray-500">Este proceso no declara variables para decidir.</p>;
  }
  return (
    <div className="grid gap-2" role="group" aria-label="Condición">
      {reglas.length > 1 && (
        <label className="text-sm text-gray-600 flex items-center gap-2">
          Se cumple si
          <select className="input !py-1 !w-auto" aria-label="Modo de la condición" value={cond.modo || "todas"}
                  disabled={soloLectura} onChange={(e) => onChange({ ...cond, modo: e.target.value })}>
            <option value="todas">se cumplen todas</option>
            <option value="alguna">se cumple alguna</option>
          </select>
        </label>
      )}
      {reglas.map((r, i) => {
        const v = variables[r.variable];
        return (
          <div key={i} className="grid grid-cols-[1fr_auto] gap-1 border border-gray-200 rounded-lg p-2">
            <div className="grid gap-1">
              <select className="input !py-1" aria-label={`Variable ${i + 1}`} value={r.variable} disabled={soloLectura}
                      onChange={(e) => cambiar(i, cambiarRegla(r, "variable", e.target.value, variables))}>
                {!v && <option value={r.variable}>{r.variable} (no existe)</option>}
                {Object.entries(variables).map(([k, x]) => <option key={k} value={k}>{x.nombre}</option>)}
              </select>
              <select className="input !py-1" aria-label={`Operador ${i + 1}`} value={r.op} disabled={soloLectura}
                      onChange={(e) => cambiar(i, cambiarRegla(r, "op", e.target.value, variables))}>
                {operadoresPara(v).map((op) => <option key={op} value={op}>{TEXTO_OPERADOR[op] || op}</option>)}
              </select>
              <CampoValor variable={v} regla={r} soloLectura={soloLectura} indice={i}
                          onChange={(valor) => cambiar(i, { ...r, valor })} />
            </div>
            {!soloLectura && (
              <button type="button" aria-label={`Quitar regla ${i + 1}`} className="self-start text-gray-400 hover:text-red-600"
                      onClick={() => onChange({ ...cond, reglas: reglas.filter((_, j) => j !== i) })}>
                <X size={16} />
              </button>
            )}
          </div>
        );
      })}
      {!soloLectura && (
        <button type="button" className="text-sm text-blue-600 hover:underline flex items-center gap-1 justify-self-start"
                onClick={() => onChange({ ...cond, modo: cond.modo || "todas", reglas: [...reglas, reglaNueva(variables)] })}>
          <Plus size={14} /> Agregar regla
        </button>
      )}
    </div>
  );
}

function CampoValor({ variable, regla, onChange, soloLectura, indice }) {
  const etiqueta = `Valor ${indice + 1}`;
  if (!variable) return null;
  if (variable.tipo === "booleano") {
    return (
      <select className="input !py-1" aria-label={etiqueta} value={String(regla.valor)} disabled={soloLectura}
              onChange={(e) => onChange(e.target.value === "true")}>
        <option value="true">sí</option><option value="false">no</option>
      </select>
    );
  }
  if (variable.tipo === "opcion" && regla.op === "en") {
    const sel = Array.isArray(regla.valor) ? regla.valor : [];
    return (
      <div className="flex flex-wrap gap-2" role="group" aria-label={etiqueta}>
        {(variable.opciones || []).map((o) => (
          <label key={o} className="text-sm flex items-center gap-1">
            <input type="checkbox" checked={sel.includes(o)} disabled={soloLectura}
                   onChange={(e) => onChange(e.target.checked ? [...sel, o] : sel.filter((x) => x !== o))} />
            {o}
          </label>
        ))}
      </div>
    );
  }
  if (variable.tipo === "opcion") {
    return (
      <select className="input !py-1" aria-label={etiqueta} value={regla.valor ?? ""} disabled={soloLectura}
              onChange={(e) => onChange(e.target.value)}>
        {(variable.opciones || []).map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  }
  return (
    <input className="input !py-1" aria-label={etiqueta} disabled={soloLectura}
           inputMode={variable.tipo === "numero" ? "decimal" : undefined}
           defaultValue={regla.valor ?? ""}
           key={`${regla.variable}-${regla.op}`}
           onBlur={(e) => onChange(leerValor(variable, e.target.value))} />
  );
}
