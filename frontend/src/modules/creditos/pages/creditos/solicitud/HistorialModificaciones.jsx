import { useState } from "react";
import { Pill } from "../../../components/Pill";
import { fecha } from "../../../components/format";

export const CAMPO_EDITADO = {
  producto_id: "Línea", monto: "Monto", plazo: "Cuotas", segmento: "Segmento", fecha_nacimiento: "Fecha de nacimiento",
  antiguedad_meses: "Antigüedad", relacion: "Relación", sueldo: "Sueldo neto", cbu: "CBU", observaciones: "Observaciones",
};

export const fechaHora = (iso) => (iso ? new Date(iso).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "short" }) : "");

/** Un valor del historial tal como se lee en pantalla. */
function valor(campo, v, { money, nombreLinea }) {
  if (v === null || v === undefined || v === "") return "—";
  switch (campo) {
    case "monto": case "sueldo": return money(v);
    case "plazo": return `${v} cuotas`;
    case "producto_id": return nombreLinea(v);
    case "fecha_nacimiento": return fecha(v);
    case "antiguedad_meses": return `${String(Math.round((Number(v) / 12) * 10) / 10).replace(".", ",")} años`;
    default: return String(v);
  }
}

/**
 * Quién modificó qué en la solicitud: cada modificación con su fecha, el estado en que estaba y, por campo,
 * el valor que había antes y el que hay ahora. Arranca colapsado; las más nuevas arriba. Las registradas
 * antes de guardar los valores sólo dicen qué campos cambiaron.
 */
export function HistorialModificaciones({ modificaciones = [], money, nombreLinea = (id) => id }) {
  const [abierto, setAbierto] = useState(false);
  if (!modificaciones.length) return null;
  const ultima = modificaciones[modificaciones.length - 1];
  return (
    <div className="mt-4 border border-gray-200 rounded-xl">
      <button type="button" onClick={() => setAbierto((v) => !v)} aria-expanded={abierto}
              className="w-full flex flex-wrap items-center gap-2 px-3 py-2 text-left text-sm hover:bg-gray-50 rounded-xl">
        <span className="text-gray-500">{abierto ? "▾" : "▸"}</span>
        <span className="font-semibold text-gray-700">Historial de modificaciones ({modificaciones.length})</span>
        <span className="text-xs text-gray-500">· última: {ultima.por}, {fechaHora(ultima.en)}</span>
      </button>
      {abierto && (
        <ul className="flex flex-col gap-2 px-3 pb-3">
          {[...modificaciones].reverse().map((m, i) => (
            <li key={`${m.en}-${i}`} className="border border-gray-200 rounded-lg p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <b className="text-gray-800">{m.por}</b>
                <span className="text-xs text-gray-500">{fechaHora(m.en)}</span>
                {m.estado && <Pill>{m.estado}</Pill>}
              </div>
              {m.cambios ? (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs uppercase tracking-wide text-gray-500">
                      <th className="text-left font-medium pb-1 pr-3">Campo</th>
                      <th className="text-left font-medium pb-1 pr-3">Antes</th>
                      <th className="text-left font-medium pb-1">Ahora</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {Object.entries(m.cambios).map(([campo, c]) => (
                      <tr key={campo}>
                        <td className="py-1 pr-3 text-gray-500 whitespace-nowrap">{CAMPO_EDITADO[campo] || campo}</td>
                        <td className="py-1 pr-3 text-gray-600 tabular-nums break-all">{valor(campo, c.antes, { money, nombreLinea })}</td>
                        <td className="py-1 text-gray-900 font-medium tabular-nums break-all">{valor(campo, c.despues, { money, nombreLinea })}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-gray-600">Cambió: {(m.campos || []).map((c) => CAMPO_EDITADO[c] || c).join(", ")} (sin los valores: se registró antes de guardarlos).</p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
