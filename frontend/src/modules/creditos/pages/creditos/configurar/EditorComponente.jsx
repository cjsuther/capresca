import { Field, Boton, Alerta } from "../../../components/ui";
import { Pill } from "../../../components/Pill";
import {
  SCHEMA, ITEM_SCHEMA, ITEM_NUEVO, ITEM_TITULO, ITEM_SINGULAR, ICONOS, FORMULA, esDefault,
} from "./esquemas";

/** Campo del editor genérico (bool / select / texto o número). */
function CampoEsquema({ f, valor, disabled, onChange }) {
  if (f.t === "bool") {
    return (
      <Field label={f.l}>
        <select className="input w-full" disabled={disabled} value={String(!!valor)}
                onChange={(e) => onChange(e.target.value === "true")}>
          <option value="true">Sí</option><option value="false">No</option>
        </select>
      </Field>
    );
  }
  if (f.t === "select") {
    return (
      <Field label={f.l}>
        <select className="input w-full" disabled={disabled} value={valor ?? ""} onChange={(e) => onChange(e.target.value)}>
          {f.o.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      </Field>
    );
  }
  return (
    <Field label={f.l}>
      <input className="input w-full" disabled={disabled}
             type={f.t === "num" ? "number" : f.t === "date" ? "date" : "text"}
             value={valor ?? ""}
             onChange={(e) => onChange(f.t === "num" ? Number(e.target.value) || 0 : e.target.value)} />
    </Field>
  );
}

/**
 * Editor del componente seleccionado de una línea: condiciones núcleo (interés, montos y plazos,
 * cargos, mora), disponibilidad, el editor genérico por esquema y las listas de ítems.
 */
export function EditorComponente({
  comp, cfg, errores, editable, editableDisp, tienePadre, indices, impuestos,
  catSegmentos, catCanales, setCfg, setCompCfg, toggleComp, reheredarComp, guardarDisponibilidad,
}) {
  if (!comp) return null;

  const indiceVal = indices.find((x) => x.codigo === cfg.indice)?.valor || 0;
  const tnaEfectiva = cfg.modalidad === "VARIABLE" ? indiceVal + (cfg.margen || 0) : cfg.tna;
  const items = comp.config.items || [];
  const updItem = (idx, patch) =>
    setCompCfg(comp.codigo, { items: items.map((x, i) => (i === idx ? { ...x, ...patch } : x)) });

  if (!comp.activo) {
    return (
      <div className="text-center py-10">
        <div className="text-4xl mb-2">{ICONOS[comp.codigo]}</div>
        <p className="text-gray-500 mb-4">Este componente no está agregado a la línea.</p>
        <Boton disabled={comp.codigo === "AVAILABILITY" ? !editableDisp : !editable}
               onClick={() => toggleComp(comp.codigo, true)}>
          ＋ Agregar “{comp.nombre}”
        </Boton>
      </div>
    );
  }

  const arr = (k) => (Array.isArray(comp.config[k])
    ? comp.config[k]
    : String(comp.config[k] || "").split(",").map((s) => s.trim()).filter(Boolean));
  const toggleChip = (k, val) => {
    const cur = arr(k);
    setCompCfg(comp.codigo, { [k]: cur.includes(val) ? cur.filter((x) => x !== val) : [...cur, val] });
  };

  return (
    <>
      <div className="flex items-start gap-3 mb-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-blue-600 font-semibold">
            Componente · {comp.categoria}
          </p>
          <h2 className="font-semibold text-gray-800">{comp.nombre}</h2>
          <p className="text-sm text-gray-500">Condiciones tipadas del componente.</p>
        </div>
        <div className="ml-auto flex flex-col items-end gap-1.5">
          <Pill tono="brand">{comp.codigo}</Pill>
          {tienePadre
            ? <Pill tono={comp.heredado ? "neutral" : "brand"}>{comp.heredado ? "HEREDADO" : "PROPIO"}</Pill>
            : <Pill tono={esDefault(comp.codigo, comp.config, cfg) ? "neutral" : "brand"}>
                {esDefault(comp.codigo, comp.config, cfg) ? "POR DEFECTO" : "PERSONALIZADO"}
              </Pill>}
          {tienePadre && !comp.heredado && editable && (
            <Boton variante="secundario" onClick={() => reheredarComp(comp.codigo)}>↩ Volver a heredar</Boton>
          )}
        </div>
      </div>

      {errores.length > 0 && (
        <div className="mb-4">
          <Alerta>
            <b>{errores.length} problema(s) en este componente:</b>
            <ul className="list-disc list-inside mt-1">{errores.map((m, i) => <li key={i}>{m}</li>)}</ul>
          </Alerta>
        </div>
      )}

      {comp.codigo === "INTEREST" && (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Sistema de cálculo">
              <select className="input w-full" disabled={!editable} value={cfg.sistema}
                      onChange={(e) => setCfg({ sistema: e.target.value })}>
                <option value="FRANCES">Francés · cuota constante</option>
                <option value="ALEMAN">Alemán · capital constante</option>
                <option value="AMERICANO">Americano · sólo interés, capital al final</option>
                <option value="BULLET">A vencimiento · pago único</option>
              </select>
            </Field>
            <Field label="Modalidad de tasa">
              <select className="input w-full" disabled={!editable} value={cfg.modalidad}
                      onChange={(e) => setCfg({ modalidad: e.target.value })}>
                <option value="FIJA">Tasa fija</option>
                <option value="VARIABLE">Variable (índice + margen)</option>
              </select>
            </Field>
            {cfg.modalidad === "FIJA" ? (
              <Field label="Tasa nominal anual (%)">
                <input type="number" className="input w-full" disabled={!editable} value={cfg.tna}
                       onChange={(e) => setCfg({ tna: Number(e.target.value) || 0 })} />
              </Field>
            ) : (
              <>
                <Field label="Índice de referencia (maestro)">
                  <select className="input w-full" disabled={!editable} value={cfg.indice || ""}
                          onChange={(e) => setCfg({ indice: e.target.value })}>
                    <option value="">— elegí un índice —</option>
                    {indices.map((x) => <option key={x.codigo} value={x.codigo}>{x.codigo} · {x.nombre} ({x.valor}%)</option>)}
                  </select>
                </Field>
                <Field label="Margen (%)">
                  <input type="number" className="input w-full" disabled={!editable} value={cfg.margen || 0}
                         onChange={(e) => setCfg({ margen: Number(e.target.value) || 0 })} />
                </Field>
              </>
            )}
            <Field label="Base de días">
              <select className="input w-full" disabled={!editable} value={cfg.baseDias}
                      onChange={(e) => setCfg({ baseDias: e.target.value })}>
                <option>ACT/365</option><option>30/360</option><option>ACT/360</option>
              </select>
            </Field>
          </div>

          {cfg.modalidad === "FIJA" && (
            <div className="grid gap-3 sm:grid-cols-3 mt-3">
              <Field label="¿Tasa negociable?">
                <select className="input w-full" disabled={!editable} value={String(!!cfg.tnaNegociable)}
                        onChange={(e) => setCfg({ tnaNegociable: e.target.value === "true" })}>
                  <option value="false">No — tasa fija</option>
                  <option value="true">Sí — banda negociable</option>
                </select>
              </Field>
              {cfg.tnaNegociable && (
                <>
                  <Field label="TNA mínima (%)">
                    <input type="number" className="input w-full" disabled={!editable} value={cfg.tnaMin || 0}
                           onChange={(e) => setCfg({ tnaMin: Number(e.target.value) || 0 })} />
                  </Field>
                  <Field label="TNA máxima (%)">
                    <input type="number" className="input w-full" disabled={!editable} value={cfg.tnaMax || 0}
                           onChange={(e) => setCfg({ tnaMax: Number(e.target.value) || 0 })} />
                  </Field>
                </>
              )}
            </div>
          )}

          <div className="mt-4 border border-gray-200 rounded-xl p-3 bg-gray-50">
            <p className="text-[11px] uppercase tracking-wide text-blue-600 font-semibold">Motor certificado</p>
            <code className="text-sm">{FORMULA[cfg.sistema]}</code>
            <p className="text-xs text-gray-500 mt-1">
              Calculador <b>{cfg.sistema}</b> · redondeo HALF_UP ·{" "}
              {cfg.modalidad === "VARIABLE"
                ? `tasa efectiva ${indiceVal.toFixed(2)}% + ${(cfg.margen || 0).toFixed(2)}% = ${tnaEfectiva.toFixed(2)}%`
                : `TNA vigente ${cfg.tna.toFixed(2)}% · ${cfg.tnaNegociable
                    ? `negociable entre ${(cfg.tnaMin || 0).toFixed(2)}% y ${(cfg.tnaMax || 0).toFixed(2)}%`
                    : "no negociable"}`}
            </p>
          </div>
        </>
      )}

      {comp.codigo === "TERM_AMOUNT" && (
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Monto mínimo">
            <input type="number" className="input w-full" disabled={!editable} value={cfg.montoMin}
                   onChange={(e) => setCfg({ montoMin: Number(e.target.value) || 0 })} />
          </Field>
          <Field label="Monto máximo">
            <input type="number" className="input w-full" disabled={!editable} value={cfg.montoMax}
                   onChange={(e) => setCfg({ montoMax: Number(e.target.value) || 0 })} />
          </Field>
          <Field label="Plazo mínimo">
            <input type="number" className="input w-full" disabled={!editable} value={cfg.plazoMin}
                   onChange={(e) => setCfg({ plazoMin: Number(e.target.value) || 0 })} />
          </Field>
          <Field label="Plazo máximo">
            <input type="number" className="input w-full" disabled={!editable} value={cfg.plazoMax}
                   onChange={(e) => setCfg({ plazoMax: Number(e.target.value) || 0 })} />
          </Field>
          <Field label="Frecuencia de pago">
            <select className="input w-full" disabled={!editable} value={cfg.frecuencia}
                    onChange={(e) => setCfg({ frecuencia: e.target.value })}>
              <option>MENSUAL</option><option>TRIMESTRAL</option>
            </select>
          </Field>
          <Field label="Gracia de capital (cuotas)">
            <input type="number" className="input w-full" disabled={!editable} value={cfg.graciaCapital}
                   onChange={(e) => setCfg({ graciaCapital: Number(e.target.value) || 0 })} />
          </Field>
        </div>
      )}

      {comp.codigo === "CHARGE" && (
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Cargo de otorgamiento (%)">
            <input type="number" className="input w-full" disabled={!editable} value={cfg.cargoOtorg}
                   onChange={(e) => setCfg({ cargoOtorg: Number(e.target.value) || 0 })} />
          </Field>
        </div>
      )}

      {comp.codigo === "OVERDUE" && (
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="TNA punitoria (%)">
            <input type="number" className="input w-full" disabled={!editable} value={cfg.moraTNA}
                   onChange={(e) => setCfg({ moraTNA: Number(e.target.value) || 0 })} />
          </Field>
        </div>
      )}

      {comp.codigo === "AVAILABILITY" && (
        <div className="flex flex-col gap-4">
          <div>
            <p className="text-xs font-medium text-gray-500 mb-1.5">
              Segmentos habilitados <span className="text-gray-400">(vacío = todos)</span>
            </p>
            <div className="flex flex-wrap gap-2">
              {catSegmentos.map((s) => (
                <button key={s} type="button" disabled={!editableDisp} onClick={() => toggleChip("segmentos", s)}
                        className={`px-3 py-1 text-xs rounded-full border ${
                          arr("segmentos").includes(s) ? "bg-blue-50 border-blue-300 text-blue-700" : "border-gray-200 text-gray-500"}`}>
                  {s.replace(/_/g, " ")}
                </button>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs font-medium text-gray-500 mb-1.5">
              Canales habilitados <span className="text-gray-400">(vacío = todos; en el portal sólo se ofrece si la disponibilidad está activa)</span>
            </p>
            <div className="flex flex-wrap gap-2">
              {catCanales.map((s) => (
                <button key={s} type="button" disabled={!editableDisp} onClick={() => toggleChip("canales", s)}
                        className={`px-3 py-1 text-xs rounded-full border ${
                          arr("canales").includes(s) ? "bg-blue-50 border-blue-300 text-blue-700" : "border-gray-200 text-gray-500"}`}>
                  {s}
                </button>
              ))}
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Edad mínima">
              <input type="number" className="input w-full" disabled={!editableDisp} value={comp.config.edadMin ?? ""}
                     onChange={(e) => setCompCfg(comp.codigo, { edadMin: Number(e.target.value) || 0 })} />
            </Field>
            <Field label="Edad máxima">
              <input type="number" className="input w-full" disabled={!editableDisp} value={comp.config.edadMax ?? ""}
                     onChange={(e) => setCompCfg(comp.codigo, { edadMax: Number(e.target.value) || 0 })} />
            </Field>
            <Field label="Antigüedad mín. (meses)">
              <input type="number" className="input w-full" disabled={!editableDisp} value={comp.config.antiguedadMinMeses ?? ""}
                     onChange={(e) => setCompCfg(comp.codigo, { antiguedadMinMeses: Number(e.target.value) || 0 })} />
            </Field>
            <Field label="Requiere garante">
              <select className="input w-full" disabled={!editableDisp} value={String(!!comp.config.requiereGarante)}
                      onChange={(e) => setCompCfg(comp.codigo, { requiereGarante: e.target.value === "true" })}>
                <option value="true">Sí</option><option value="false">No</option>
              </select>
            </Field>
            <Field label="Vigente desde">
              <input type="date" className="input w-full" disabled={!editableDisp} value={comp.config.vigenteDesde || ""}
                     onChange={(e) => setCompCfg(comp.codigo, { vigenteDesde: e.target.value })} />
            </Field>
            <Field label="Vigente hasta">
              <input type="date" className="input w-full" disabled={!editableDisp} value={comp.config.vigenteHasta || ""}
                     onChange={(e) => setCompCfg(comp.codigo, { vigenteHasta: e.target.value })} />
            </Field>
          </div>
          {!editable && editableDisp && (
            <div className="flex items-center gap-3 border-t border-gray-200 pt-3">
              <span className="text-sm text-gray-500">
                La disponibilidad se puede modificar aunque la línea esté publicada: no crea versión nueva.
              </span>
              <Boton onClick={guardarDisponibilidad}>Guardar disponibilidad</Boton>
            </div>
          )}
        </div>
      )}

      {SCHEMA[comp.codigo] && (
        <div className={`grid gap-3 sm:grid-cols-3 ${["CHARGE", "OVERDUE"].includes(comp.codigo) ? "mt-3" : ""}`}>
          {SCHEMA[comp.codigo].map((f) => (
            <CampoEsquema key={f.k} f={f} valor={comp.config[f.k]} disabled={!editable}
                          onChange={(v) => setCompCfg(comp.codigo, { [f.k]: v })} />
          ))}
        </div>
      )}

      {ITEM_SCHEMA[comp.codigo] && (
        <div className="mt-4">
          <div className="flex items-center mb-2">
            <b className="text-sm text-gray-800">{ITEM_TITULO[comp.codigo]} ({items.length})</b>
            <span className="flex-1" />
            {editable && (
              <Boton onClick={() => setCompCfg(comp.codigo, { items: [...items, { ...ITEM_NUEVO[comp.codigo] }] })}>
                ＋ Agregar {ITEM_SINGULAR[comp.codigo]}
              </Boton>
            )}
          </div>
          {items.map((it, idx) => (
            <div key={idx} className="flex flex-wrap items-end gap-3 bg-gray-50 rounded-lg p-3 mb-2">
              {ITEM_SCHEMA[comp.codigo].map((f) => (
                <div key={f.k} className="flex-1 min-w-[140px]">
                  {f.t === "impuesto" ? (
                    <Field label={f.l}>
                      <select className="input w-full" disabled={!editable} value={it.codigo ?? ""}
                              onChange={(e) => {
                                const imp = impuestos.find((x) => x.codigo === e.target.value);
                                updItem(idx, imp
                                  ? { codigo: imp.codigo, etiqueta: imp.nombre, base: imp.base, porcentaje: imp.alicuota }
                                  : { codigo: "" });
                              }}>
                        <option value="">— manual —</option>
                        {impuestos.map((x) => <option key={x.codigo} value={x.codigo}>{x.codigo} · {x.nombre}</option>)}
                      </select>
                    </Field>
                  ) : (
                    <CampoEsquema f={f} valor={it[f.k]} disabled={!editable}
                                  onChange={(v) => updItem(idx, { [f.k]: v })} />
                  )}
                </div>
              ))}
              {editable && (
                <button onClick={() => setCompCfg(comp.codigo, { items: items.filter((_, i) => i !== idx) })}
                        aria-label={`Quitar ${ITEM_SINGULAR[comp.codigo]} ${idx + 1}`}
                        className="px-2 py-2 text-sm text-red-600 border border-red-300 rounded-lg hover:bg-red-50">✕</button>
              )}
            </div>
          ))}
          {!items.length && (
            <p className="text-sm text-gray-400">Sin ítems. Agregá una {ITEM_SINGULAR[comp.codigo]}.</p>
          )}
        </div>
      )}

      {!SCHEMA[comp.codigo] && !ITEM_SCHEMA[comp.codigo]
        && !["INTEREST", "TERM_AMOUNT", "AVAILABILITY"].includes(comp.codigo) && (
        <dl className="text-sm text-gray-600">
          <div className="flex justify-between border-b border-gray-100 py-1"><dt>Estado</dt><dd>ACTIVO</dd></div>
          <div className="flex justify-between border-b border-gray-100 py-1"><dt>Categoría</dt><dd>{comp.categoria}</dd></div>
        </dl>
      )}
    </>
  );
}
