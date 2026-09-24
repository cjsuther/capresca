import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw, Upload } from "lucide-react";

import { getImportacion, getImportaciones, subirDespacho } from "../../../api/despacho";

const ESTADOS = {
  PENDIENTE: ["Esperando", "bg-gray-100 text-gray-600"],
  PROCESANDO: ["Importando", "bg-blue-100 text-blue-700"],
  TERMINADA: ["Terminada", "bg-green-100 text-green-700"],
  ERROR: ["Con error", "bg-red-100 text-red-700"],
  INTERRUMPIDA: ["Interrumpida", "bg-amber-100 text-amber-700"],
};
const EN_CURSO = ["PENDIENTE", "PROCESANDO"];

const num = (n) => Number(n || 0).toLocaleString("es-AR");
const fechaHora = (s) => (s ? new Date(s).toLocaleString("es-AR") : "—");
const peso = (b) => (b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.round(b / 1024)} KB`);

/** Sin respuesta del servidor el error viene sin `detail`, y "no se pudo subir" no dice nada. */
function mensajeDeError(e) {
  if (e?.response?.status === 413) {
    return "El servidor rechazó el archivo por tamaño. Avisá a sistemas para ampliar el límite.";
  }
  if (!e?.response) {
    return "Se cortó la subida antes de terminar. Puede ser la conexión, o que la página esté "
      + "desactualizada: recargá con Ctrl+Shift+R (Cmd+Shift+R en Mac) y probá de nuevo.";
  }
  return e?.response?.data?.detail || `El servidor respondió ${e.response.status}.`;
}


function Estado({ estado }) {
  const [texto, clase] = ESTADOS[estado] || [estado, "bg-gray-100 text-gray-600"];
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${clase}`}>{texto}</span>;
}

export default function ImportarPage() {
  const [items, setItems] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [subiendo, setSubiendo] = useState(0);   // 0 = no está subiendo
  const inputRef = useRef(null);

  const cargar = useCallback(() => {
    getImportaciones()
      .then((d) => setItems(d.items ?? []))
      .catch((e) => setError(e?.response?.data?.detail || "No se pudieron cargar las importaciones"))
      .finally(() => setCargando(false));
  }, []);

  useEffect(cargar, [cargar]);

  // Mientras una corre, se consulta el avance cada 3 segundos.
  const enCurso = items.find((i) => EN_CURSO.includes(i.estado));
  useEffect(() => {
    if (!enCurso) return undefined;
    const t = setInterval(() => {
      getImportacion(enCurso.id)
        .then((d) => setItems((xs) => xs.map((x) => (x.id === d.id ? d : x))))
        .catch(() => {});
    }, 3000);
    return () => clearInterval(t);
  }, [enCurso?.id, enCurso?.estado]);   // eslint-disable-line react-hooks/exhaustive-deps

  const elegir = async (archivo) => {
    if (!archivo) return;
    setError(""); setSubiendo(1);
    try {
      const creada = await subirDespacho(archivo, (p) => setSubiendo(Math.max(p, 1)));
      setItems((xs) => [creada, ...xs]);
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setSubiendo(0);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Importar del sistema anterior</h1>
          <p className="text-sm text-gray-500 mt-1 max-w-3xl">
            Trae los modelos, las resoluciones y sus beneficiarios del despacho viejo
            (<code>rtf.dbf</code>, <code>resoluciones.dbf</code> y <code>beneficiarios.dbf</code>, en
            un .zip, con los <code>.FPT</code> que llevan el texto). Lo importado entra como ya
            emitido. Volver a subir el mismo archivo no duplica nada: las repetidas se omiten y, si
            alguna quedó sin cuerpo, se le completa.
          </p>
        </div>
        <button type="button" onClick={cargar}
                className="inline-flex items-center gap-2 px-3 py-2 text-sm rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50">
          <RefreshCw size={16} /> Actualizar
        </button>
      </div>

      {error && <div className="rounded-lg bg-red-50 text-red-700 text-sm px-4 py-3">{error}</div>}

      <div className="bg-surface rounded-xl border border-gray-200 p-5">
        <label className="flex flex-col items-center justify-center gap-2 border-2 border-dashed border-gray-300 rounded-xl py-8 cursor-pointer hover:border-blue-400 hover:bg-blue-50/40">
          <Upload size={22} className="text-gray-400" />
          <span className="text-sm font-medium text-gray-700">
            {subiendo ? `Subiendo… ${subiendo}%` : "Elegí el backup del despacho"}
          </span>
          <span className="text-xs text-gray-500">.zip con los DBF</span>
          <input ref={inputRef} type="file" accept=".zip" hidden disabled={!!subiendo || !!enCurso}
                 aria-label="Backup del despacho"
                 onChange={(e) => elegir(e.target.files?.[0])} />
        </label>
        {enCurso && (
          <p className="text-xs text-amber-700 mt-3">
            Hay una importación en curso. Cuando termine vas a poder subir otra.
          </p>
        )}
      </div>

      <div className="bg-surface rounded-xl border border-gray-200 overflow-x-auto">
        <table className="w-full text-sm min-w-[720px]">
          <thead>
            <tr className="bg-gray-50 text-left text-xs text-gray-500 border-b border-gray-200">
              <th className="px-4 py-2 font-medium">Archivo</th>
              <th className="px-4 py-2 font-medium">Estado</th>
              <th className="px-4 py-2 font-medium text-right">Modelos</th>
              <th className="px-4 py-2 font-medium text-right">Resoluciones</th>
              <th className="px-4 py-2 font-medium text-right">Beneficiarios</th>
              <th className="px-4 py-2 font-medium text-right">Textos reparados</th>
              <th className="px-4 py-2 font-medium text-right">Omitidas</th>
              <th className="px-4 py-2 font-medium">Cuándo</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {cargando && (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">Cargando…</td></tr>
            )}
            {!cargando && items.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">
                Todavía no se importó nada.
              </td></tr>
            )}
            {items.map((i) => (
              <tr key={i.id} className="align-top">
                <td className="px-4 py-3">
                  <div className="font-medium text-gray-800">{i.archivo}</div>
                  <div className="text-xs text-gray-500">{peso(i.tamano)}</div>
                  {i.mensaje && <p className="text-xs text-red-600 mt-1 max-w-md">{i.mensaje}</p>}
                </td>
                <td className="px-4 py-3"><Estado estado={i.estado} /></td>
                <td className="px-4 py-3 text-right tabular-nums">{num(i.modelos)}</td>
                <td className="px-4 py-3 text-right tabular-nums">{num(i.resoluciones)}</td>
                <td className="px-4 py-3 text-right tabular-nums">{num(i.beneficiarios)}</td>
                <td className="px-4 py-3 text-right tabular-nums">{num(i.reparadas)}</td>
                <td className="px-4 py-3 text-right tabular-nums text-gray-500">{num(i.omitidas)}</td>
                <td className="px-4 py-3 text-xs text-gray-500">{fechaHora(i.creadoEn)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
