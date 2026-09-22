import { useEffect, useRef, useState } from "react";
import { FileText, Upload, Trash2 } from "lucide-react";
import { getDocumentos, subirDocumento, getDocumentoArchivo, borrarDocumento } from "../../../api/clientes";
import { PermissionGate } from "../../../components/PrivateRoute";
import { VisorDocumento } from "../../../components/ui/VisorDocumento";
import { Confirmacion } from "../../../components/ui/Confirmacion";
import { Pill } from "../../../components/ui/Pill";

const TIPOS = { DNI_FRENTE: "DNI (frente)", DNI_DORSO: "DNI (dorso)", RECIBO: "Recibo de sueldo", OTRO: "Otro" };
const FORMATOS = "image/jpeg,image/png,image/webp,application/pdf";
const MAX = 10 * 1024 * 1024;

const tamano = (n) => (n < 1024 * 1024 ? `${Math.round(n / 1024)} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`);
const detalle = (e, porDefecto) => {
  const d = e?.response?.data?.detail;
  return typeof d === "string" ? d : porDefecto;
};

/**
 * Documentación del cliente: la carga el operador o llega de otro módulo (p.ej. la solicitud de crédito
 * del portal, con su origen). Se ve dentro de la página, se descarga y se da de baja.
 */
export function DocumentosCliente({ clientId }) {
  const [docs, setDocs] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [tipo, setTipo] = useState("DNI_FRENTE");
  const [subiendo, setSubiendo] = useState(false);
  const [viendo, setViendo] = useState(null);
  const [borrando, setBorrando] = useState(null);
  const input = useRef(null);

  const cargar = () =>
    getDocumentos(clientId)
      .then((d) => { setDocs(d.items); setError(""); })
      .catch((e) => setError(detalle(e, "No se pudieron cargar los documentos")))
      .finally(() => setCargando(false));
  useEffect(() => { cargar(); }, [clientId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function subir(archivo) {
    if (!archivo) return;
    setError("");
    if (!FORMATOS.split(",").includes(archivo.type)) { setError("Formato no permitido (JPG, PNG, WEBP o PDF)."); return; }
    if (archivo.size > MAX) { setError("El archivo supera los 10 MB."); return; }
    setSubiendo(true);
    try {
      await subirDocumento(clientId, archivo, tipo);
      await cargar();
    } catch (e) {
      setError(detalle(e, "No se pudo subir el documento"));
    } finally {
      setSubiendo(false);
      if (input.current) input.current.value = "";
    }
  }

  async function borrar() {
    try {
      await borrarDocumento(clientId, borrando.id);
      await cargar();
    } catch (e) {
      setError(detalle(e, "No se pudo borrar el documento"));
    } finally {
      setBorrando(null);
    }
  }

  return (
    <div className="bg-surface border rounded-xl p-5 mb-6">
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <FileText size={16} className="text-gray-500" />
        <h3 className="font-medium text-gray-700">Documentos</h3>
        <span className="flex-1" />
        <PermissionGate moduleCode="clientes" action="clients:write">
          <select className="input text-sm" value={tipo} onChange={(e) => setTipo(e.target.value)} aria-label="Tipo de documento">
            {Object.entries(TIPOS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <label className={`flex items-center gap-1 px-3 py-2 text-sm rounded-lg cursor-pointer ${subiendo
            ? "bg-gray-100 text-gray-400" : "bg-blue-600 text-white hover:bg-blue-700"}`}>
            <Upload size={14} /> {subiendo ? "Subiendo…" : "Adjuntar"}
            <input ref={input} type="file" accept={FORMATOS} hidden disabled={subiendo}
                   onChange={(e) => subir(e.target.files?.[0])} />
          </label>
        </PermissionGate>
      </div>

      {error && <p className="text-sm text-red-600 mb-3" role="alert">{error}</p>}

      {cargando ? (
        <p className="text-sm text-gray-400">Cargando…</p>
      ) : docs.length === 0 ? (
        <p className="text-sm text-gray-400">Sin documentos cargados</p>
      ) : (
        <ul className="space-y-2" aria-label="Documentos del cliente">
          {docs.map((d, i) => (
            <li key={d.id} className="flex flex-wrap items-center gap-3 bg-gray-50 rounded-lg px-4 py-2.5">
              <Pill tono={d.tipo === "OTRO" ? "neutral" : "brand"}>{TIPOS[d.tipo] || d.tipo}</Pill>
              <button onClick={() => setViendo(i)} className="text-sm text-blue-600 hover:underline truncate max-w-xs text-left">
                {d.nombre}
              </button>
              <span className="text-xs text-gray-400">{tamano(d.tamano)}</span>
              <span className="flex-1" />
              <span className="text-xs text-gray-500">
                {d.origen}{d.created_at ? ` · ${new Date(d.created_at).toLocaleDateString("es-AR")}` : ""}
              </span>
              <PermissionGate moduleCode="clientes" action="clients:write">
                <button onClick={() => setBorrando(d)} aria-label={`Borrar ${d.nombre}`}
                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg">
                  <Trash2 size={14} />
                </button>
              </PermissionGate>
            </li>
          ))}
        </ul>
      )}

      {viendo != null && docs[viendo] && (
        <VisorDocumento docs={docs} inicial={viendo} etiquetas={TIPOS} eyebrow="Documentos del cliente"
                        cargar={(d) => getDocumentoArchivo(clientId, d.id)} onClose={() => setViendo(null)} />
      )}
      {borrando && (
        <Confirmacion titulo="Borrar documento" confirmar="Borrar"
                      mensaje={`${TIPOS[borrando.tipo] || borrando.tipo} · ${borrando.nombre}\nSe elimina de la ficha del cliente. No se puede deshacer.`}
                      onConfirmar={borrar} onCancelar={() => setBorrando(null)} />
      )}
    </div>
  );
}
