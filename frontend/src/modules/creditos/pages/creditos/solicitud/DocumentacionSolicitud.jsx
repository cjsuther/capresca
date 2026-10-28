import { useRef } from "react";
import { Field } from "../../../components/ui";
import { Pill } from "../../../components/Pill";
import { fmtBytes } from "../../../components/format";

// Lo mismo que acepta el portal (services/documentos.py): imágenes o PDF de hasta 5 MB.
export const TIPOS_ARCHIVO = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
const MAX_BYTES = 5 * 1024 * 1024;

/** "" si el archivo se puede adjuntar; si no, el motivo. El backend vuelve a validarlo. */
export function errorArchivo(archivo) {
  if (!TIPOS_ARCHIVO.includes(archivo?.type)) return "Formato no permitido. Subí una imagen (JPG, PNG, WEBP) o un PDF.";
  if (!archivo.size) return "El archivo está vacío.";
  if (archivo.size > MAX_BYTES) return "El archivo supera el máximo de 5 MB.";
  return "";
}

/** Títulos de los documentos obligatorios que todavía no tienen archivo. */
export const docsFaltantes = (pedidos, actuales) =>
  pedidos.filter((d) => d.obligatorio && !actuales[d.tipo]).map((d) => d.titulo);

/** Las preguntas obligatorias de la línea que no se contestaron. */
export const datosFaltantes = (campos, valores) =>
  campos.filter((c) => c.obligatorio && !(valores[c.codigo] || []).length).map((c) => c.etiqueta);

/**
 * La documentación que pide la línea, una fila por documento, como en el portal.
 * `actuales`: { tipo: { nombre, tamano } } con lo ya adjuntado (archivo elegido o documento guardado).
 */
export function ListaDocumentos({ pedidos, actuales, onElegir, onQuitar, onVer, ocupado = false, soloLectura = false }) {
  const inputs = useRef({});
  if (!pedidos.length) return <p className="text-sm text-gray-500">Esta línea no pide documentación.</p>;
  return (
    <ul className="flex flex-col divide-y divide-gray-100 border border-gray-200 rounded-lg">
      {pedidos.map((d) => {
        const actual = actuales[d.tipo];
        return (
          <li key={d.tipo} className="flex flex-wrap items-center gap-2 px-3 py-2 text-sm">
            <div className="min-w-0 flex-1">
              <p className="font-medium text-gray-800">
                {d.titulo}{" "}
                {d.obligatorio ? <Pill tono={actual ? "ok" : "warn"}>{actual ? "adjunto" : "obligatorio"}</Pill>
                  : <Pill>opcional</Pill>}
              </p>
              {d.ayuda && <p className="text-xs text-gray-500">{d.ayuda}</p>}
              {actual && (
                <p className="text-xs text-gray-600 truncate">
                  {onVer && actual.id
                    ? <button type="button" className="text-blue-600 hover:underline" onClick={() => onVer(actual)}>{actual.nombre}</button>
                    : actual.nombre}
                  <span className="text-gray-400"> · {fmtBytes(actual.tamano)}</span>
                </p>
              )}
            </div>
            {!soloLectura && (
              <div className="flex gap-3">
                <input type="file" className="hidden" accept={TIPOS_ARCHIVO.join(",")} aria-label={`Archivo de ${d.titulo}`}
                       ref={(el) => { inputs.current[d.tipo] = el; }}
                       onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) onElegir(d, f); }} />
                <button type="button" disabled={ocupado} className="text-blue-600 hover:underline disabled:opacity-50"
                        onClick={() => inputs.current[d.tipo]?.click()}>
                  {actual ? "Reemplazar" : "Adjuntar"}
                </button>
                {actual && onQuitar && (
                  <button type="button" disabled={ocupado} className="text-red-600 hover:underline disabled:opacity-50"
                          onClick={() => onQuitar(d, actual)}>Quitar</button>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** Los datos que pregunta la línea (selección única o múltiple), igual que el portal. */
export function DatosDeLaLinea({ campos, valores, onChange }) {
  if (!campos.length) return null;
  const set = (codigo, v) => onChange({ ...valores, [codigo]: v });
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {campos.map((c) => {
        const elegidas = valores[c.codigo] || [];
        const etiqueta = `${c.etiqueta}${c.obligatorio ? " *" : ""}`;
        return (
          <Field key={c.codigo} label={etiqueta}>
            {c.tipo === "UNICA" ? (
              <select className="input w-full" aria-label={c.etiqueta} value={elegidas[0] || ""}
                      onChange={(e) => set(c.codigo, e.target.value ? [e.target.value] : [])}>
                <option value="">(elegí una opción)</option>
                {c.opciones.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            ) : (
              <div className="flex flex-col gap-1">
                {c.opciones.map((o) => (
                  <label key={o} className="flex items-center gap-2 text-sm text-gray-700">
                    <input type="checkbox" checked={elegidas.includes(o)}
                           onChange={(e) => set(c.codigo, e.target.checked ? [...elegidas, o] : elegidas.filter((x) => x !== o))} />
                    {o}
                  </label>
                ))}
              </div>
            )}
            {c.ayuda && <span className="text-xs text-gray-500">{c.ayuda}</span>}
          </Field>
        );
      })}
    </div>
  );
}
