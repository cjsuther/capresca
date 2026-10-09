import { useState } from "react";
import { Field, Boton } from "../../../components/ui";
import { DOCUMENTOS_ESTANDAR, codigoDesde } from "./esquemas";

/**
 * Componente "Documentación y datos" de una línea: lo que el ciudadano adjunta y lo que completa en el
 * paso 3 del portal. Cada línea pide lo suyo (un crédito para la salud pide la orden médica).
 *
 * El código de cada ítem sale del título y lo sigue mientras nadie lo toque a mano; es lo que guarda
 * la solicitud, así que no se muestra para editar.
 */
export function EditorRequisitos({ config, editable, onChange }) {
  const documentos = config.documentos || [];
  const campos = config.campos || [];
  const codigos = (lista, salvo) => lista.filter((_, i) => i !== salvo).map((x) => x.codigo);

  const setDoc = (idx, patch) => onChange({ documentos: documentos.map((d, i) => (i === idx ? { ...d, ...patch } : d)) });
  const setCampo = (idx, patch) => onChange({ campos: campos.map((c, i) => (i === idx ? { ...c, ...patch } : c)) });
  /** Al cambiar el título, el código lo acompaña si todavía era el que salió del título anterior. */
  const conTitulo = (item, texto, lista, idx, clave) => {
    const auto = !item.codigo || item.codigo === codigoDesde(item[clave], codigos(lista, idx));
    return { [clave]: texto, ...(auto ? { codigo: codigoDesde(texto, codigos(lista, idx)) } : {}) };
  };

  const agregarDoc = (estandar) => {
    const base = estandar || { codigo: "", titulo: "", ayuda: "" };
    if (estandar && documentos.some((d) => d.codigo === estandar.codigo)) return;
    onChange({ documentos: [...documentos, { ...base, obligatorio: true }] });
  };
  const disponibles = DOCUMENTOS_ESTANDAR.filter((e) => !documentos.some((d) => d.codigo === e.codigo));

  return (
    <div className="flex flex-col gap-6">
      <section>
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <b className="text-sm text-gray-800">Documentación a adjuntar ({documentos.length})</b>
          <span className="flex-1" />
          {editable && disponibles.length > 0 && (
            <select className="input" aria-label="Agregar documento estándar" value=""
                    onChange={(e) => agregarDoc(disponibles.find((x) => x.codigo === e.target.value))}>
              <option value="">＋ Documento estándar…</option>
              {disponibles.map((x) => <option key={x.codigo} value={x.codigo}>{x.titulo}</option>)}
            </select>
          )}
          {editable && <Boton onClick={() => agregarDoc()}>＋ Otro documento</Boton>}
        </div>
        <p className="text-xs text-gray-500 mb-2">Un archivo por documento. Los opcionales se pueden saltear.</p>
        {documentos.map((d, idx) => (
          <div key={idx} className="flex flex-wrap items-end gap-3 bg-gray-50 rounded-lg p-3 mb-2">
            <div className="flex-1 min-w-[180px]">
              <Field label={`Documento ${idx + 1}`}>
                <input className="input w-full" disabled={!editable} value={d.titulo || ""}
                       placeholder="Ej.: Orden médica"
                       onChange={(e) => setDoc(idx, conTitulo(d, e.target.value, documentos, idx, "titulo"))} />
              </Field>
            </div>
            <div className="flex-[2] min-w-[200px]">
              <Field label="Ayuda para el ciudadano (opcional)">
                <input className="input w-full" disabled={!editable} value={d.ayuda || ""}
                       placeholder="Ej.: Firmada por el profesional, con fecha"
                       onChange={(e) => setDoc(idx, { ayuda: e.target.value })} />
              </Field>
            </div>
            <Obligatorio valor={d.obligatorio !== false} editable={editable}
                         etiqueta={`Documento ${idx + 1} obligatorio`}
                         onChange={(v) => setDoc(idx, { obligatorio: v })} />
            {editable && (
              <Quitar etiqueta={`Quitar documento ${idx + 1}`}
                      onClick={() => onChange({ documentos: documentos.filter((_, i) => i !== idx) })} />
            )}
          </div>
        ))}
        {!documentos.length && <p className="text-sm text-gray-400">No pide documentación.</p>}
      </section>

      <section>
        <div className="flex items-center mb-1">
          <b className="text-sm text-gray-800">Datos a completar ({campos.length})</b>
          <span className="flex-1" />
          {editable && (
            <Boton onClick={() => onChange({ campos: [...campos, { codigo: "", etiqueta: "", ayuda: "", tipo: "UNICA",
                                                                  opciones: [], obligatorio: true }] })}>
              ＋ Agregar dato
            </Boton>
          )}
        </div>
        <p className="text-xs text-gray-500 mb-2">
          Combos de selección única o múltiple. Quedan en la solicitud tal como se preguntaron.
        </p>
        {campos.map((c, idx) => (
          <div key={idx} className="bg-gray-50 rounded-lg p-3 mb-2 flex flex-col gap-3">
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex-[2] min-w-[200px]">
                <Field label={`Pregunta ${idx + 1}`}>
                  <input className="input w-full" disabled={!editable} value={c.etiqueta || ""}
                         placeholder="Ej.: Obra social"
                         onChange={(e) => setCampo(idx, conTitulo(c, e.target.value, campos, idx, "etiqueta"))} />
                </Field>
              </div>
              <div className="min-w-[170px]">
                <Field label="Selección">
                  <select className="input w-full" disabled={!editable} value={c.tipo}
                          aria-label={`Tipo de selección ${idx + 1}`}
                          onChange={(e) => setCampo(idx, { tipo: e.target.value })}>
                    <option value="UNICA">Única (elige una)</option>
                    <option value="MULTIPLE">Múltiple (elige varias)</option>
                  </select>
                </Field>
              </div>
              <Obligatorio valor={!!c.obligatorio} editable={editable} etiqueta={`Dato ${idx + 1} obligatorio`}
                           onChange={(v) => setCampo(idx, { obligatorio: v })} />
              {editable && (
                <Quitar etiqueta={`Quitar dato ${idx + 1}`}
                        onClick={() => onChange({ campos: campos.filter((_, i) => i !== idx) })} />
              )}
            </div>
            <div className="flex flex-wrap gap-3">
              <div className="flex-1 min-w-[200px]">
                <Opciones opciones={c.opciones || []} editable={editable} etiqueta={`Opciones ${idx + 1}`}
                          onChange={(opciones) => setCampo(idx, { opciones })} />
              </div>
              <div className="flex-1 min-w-[200px]">
                <Field label="Ayuda para el ciudadano (opcional)">
                  <input className="input w-full" disabled={!editable} value={c.ayuda || ""}
                         onChange={(e) => setCampo(idx, { ayuda: e.target.value })} />
                </Field>
              </div>
            </div>
          </div>
        ))}
        {!campos.length && <p className="text-sm text-gray-400">No pide datos adicionales.</p>}
      </section>
    </div>
  );
}

function Obligatorio({ valor, editable, etiqueta, onChange }) {
  return (
    <label className="flex items-center gap-2 text-sm text-gray-700 pb-2">
      <input type="checkbox" disabled={!editable} checked={valor} aria-label={etiqueta}
             onChange={(e) => onChange(e.target.checked)} />
      Obligatorio
    </label>
  );
}

function Quitar({ etiqueta, onClick }) {
  return (
    <button onClick={onClick} aria-label={etiqueta}
            className="px-2 py-2 text-sm text-red-600 border border-red-300 rounded-lg hover:bg-red-50">✕</button>
  );
}

/** Una opción por renglón. El texto se guarda aparte para poder escribir el renglón siguiente. */
function Opciones({ opciones, editable, etiqueta, onChange }) {
  const [texto, setTexto] = useState(opciones.join("\n"));
  return (
    <Field label="Opciones (una por renglón)">
      <textarea className="input w-full" rows={Math.max(3, opciones.length + 1)} disabled={!editable}
                aria-label={etiqueta} value={texto} placeholder={"OSEP\nPAMI\nSin cobertura"}
                onChange={(e) => {
                  setTexto(e.target.value);
                  onChange(e.target.value.split("\n").map((s) => s.trim()).filter(Boolean));
                }} />
    </Field>
  );
}
