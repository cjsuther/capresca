import { useEffect, useState } from "react";
import { Modal, Boton, Alerta } from "./index";
import { Pill } from "./Pill";

/**
 * Abre un documento en una pestaña nueva, para tenerlo a la vista junto a la pantalla. La pestaña se abre
 * en el mismo click (si se abre después de la descarga, el navegador la bloquea como ventana emergente) y
 * se llena cuando llega el archivo. La URL del archivo no se revoca: la pestaña la usa mientras esté
 * abierta, y el navegador la libera al cerrar el sistema.
 *
 * cargar() → Promise<Blob>. Devuelve una promesa que falla si no se pudo abrir.
 */
export async function abrirEnPestana(cargar, nombre = "documento") {
  const w = window.open("", "_blank");
  if (!w) throw new Error("El navegador bloqueó la pestaña nueva: permití las ventanas emergentes para este sitio.");
  const mensaje = (texto) => { try { w.document.title = nombre; w.document.body.textContent = texto; } catch { /* sin acceso */ } };
  mensaje(`Cargando ${nombre}…`);
  try {
    const blob = await cargar();
    w.location.replace(URL.createObjectURL(blob));
  } catch (e) {
    mensaje(`No se pudo abrir ${nombre}.`);
    throw e;
  }
}

/**
 * Vista previa de la documentación adjunta, dentro de la página: imágenes y PDF se ven en el modal.
 * Permite pasar de un documento al otro, descargar el que se está viendo o abrirlo en una pestaña
 * nueva (para verlo al lado de los datos).
 *
 * docs: [{ id, tipo, nombre, tamano }] · cargar(doc) → Promise<Blob> · etiquetas: { tipo: "texto" }
 */
export function VisorDocumento({ docs, inicial = 0, cargar, etiquetas = {}, eyebrow = "Documentación", onClose }) {
  const [i, setI] = useState(inicial);
  const [archivo, setArchivo] = useState(null);   // { url, tipo, blob }
  const [error, setError] = useState("");
  const doc = docs[i];

  useEffect(() => {
    let url = null;
    let vigente = true;
    setArchivo(null); setError("");
    cargar(doc)
      .then((blob) => {
        if (!vigente) return;
        url = URL.createObjectURL(blob);
        setArchivo({ url, tipo: blob.type || "", blob });
      })
      .catch((e) => vigente && setError(e.message || "No se pudo abrir el archivo"));
    return () => { vigente = false; if (url) URL.revokeObjectURL(url); };
  }, [doc?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const esImagen = archivo?.tipo.startsWith("image/");
  const esPdf = archivo?.tipo === "application/pdf";

  return (
    <Modal titulo={etiquetas[doc.tipo] || doc.tipo} eyebrow={eyebrow} onClose={onClose} ancho="max-w-5xl"
           footer={<>
             <span className="text-xs text-gray-500 truncate">{doc.nombre}</span>
             <span className="flex-1" />
             {archivo && (
               // URL propia (no la del modal, que se revoca al cerrarlo): la pestaña sigue sirviendo.
               <button type="button" onClick={() => window.open(URL.createObjectURL(archivo.blob), "_blank")}
                       className="px-4 py-2 text-sm rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50">
                 Abrir en pestaña nueva
               </button>
             )}
             {archivo && (
               <a href={archivo.url} download={doc.nombre}
                  className="px-4 py-2 text-sm rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50">Descargar</a>
             )}
             <Boton variante="secundario" onClick={onClose}>Cerrar</Boton>
           </>}>
      {docs.length > 1 && (
        <div className="flex flex-wrap gap-2 mb-3" role="tablist" aria-label="Documentos">
          {docs.map((d, n) => (
            <button key={d.id} role="tab" aria-selected={n === i} onClick={() => setI(n)}
                    className={`text-sm px-3 py-1 rounded-full border ${n === i
                      ? "border-blue-600 bg-blue-50 text-blue-700" : "border-gray-200 text-gray-600 hover:bg-gray-50"}`}>
              {etiquetas[d.tipo] || d.tipo}
            </button>
          ))}
        </div>
      )}
      {error && <Alerta>{error}</Alerta>}
      {!archivo && !error && <p className="text-sm text-gray-500 py-10 text-center">Cargando…</p>}
      {esImagen && (
        <div className="flex justify-center bg-gray-50 rounded-lg p-2">
          <img src={archivo.url} alt={`${etiquetas[doc.tipo] || doc.tipo}: ${doc.nombre}`}
               className="max-h-[70vh] w-auto object-contain" />
        </div>
      )}
      {esPdf && <iframe src={archivo.url} title={doc.nombre} className="w-full h-[70vh] rounded-lg border border-gray-200" />}
      {archivo && !esImagen && !esPdf && (
        <p className="text-sm text-gray-600 py-6 text-center">
          Este formato no tiene vista previa <Pill>{archivo.tipo || "desconocido"}</Pill>. Usá “Descargar”.
        </p>
      )}
    </Modal>
  );
}
