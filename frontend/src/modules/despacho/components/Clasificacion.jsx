/** Sector y actividad de un modelo o un acto: texto libre, con lo ya cargado como sugerencia. */
export function CamposClasificacion({ valor, onChange, opciones }) {
  return (
    <>
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-gray-500">Sector al que pertenece</span>
        <input className="input" list="despacho-sectores" maxLength={80} aria-label="Sector"
               value={valor.sector || ""} onChange={(e) => onChange({ sector: e.target.value })} />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-gray-500">Actividad a la que refiere</span>
        <input className="input" list="despacho-actividades" maxLength={80} aria-label="Actividad"
               value={valor.actividad || ""} onChange={(e) => onChange({ actividad: e.target.value })} />
      </label>
      <datalist id="despacho-sectores">
        {(opciones?.sectores || []).map((s) => <option key={s} value={s} />)}
      </datalist>
      <datalist id="despacho-actividades">
        {(opciones?.actividades || []).map((a) => <option key={a} value={a} />)}
      </datalist>
    </>
  );
}

/** Los dos combos de filtro por sector y actividad. */
export function FiltrosClasificacion({ filtros, onChange, opciones }) {
  return (
    <>
      <select className="input w-full sm:w-44" value={filtros.sector} aria-label="Filtrar por sector"
              onChange={(e) => onChange({ sector: e.target.value })}>
        <option value="">Todos los sectores</option>
        {(opciones?.sectores || []).map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
      <select className="input w-full sm:w-44" value={filtros.actividad} aria-label="Filtrar por actividad"
              onChange={(e) => onChange({ actividad: e.target.value })}>
        <option value="">Todas las actividades</option>
        {(opciones?.actividades || []).map((a) => <option key={a} value={a}>{a}</option>)}
      </select>
    </>
  );
}
