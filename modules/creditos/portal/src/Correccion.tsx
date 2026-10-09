import { useState } from "react";
import { api, type SolicitudDetalle, type DocDeLaSolicitud } from "./api";

const TIPOS = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
const MAX = 5 * 1024 * 1024;

/**
 * Documentación de una solicitud ya enviada, y la corrección cuando el asesor la observa.
 *
 * Mientras se evalúa, el ciudadano puede adjuntar lo que le faltó (un archivo que no subió al enviar).
 * Si el asesor la observa, ve su explicación, reemplaza los documentos que le pidió, corrige el CBU si
 * hace falta y la reenvía; hasta entonces no se aprueba ni se rechaza.
 */
export function Correccion({ detalle, onActualizar, onReenviada }: {
  detalle: SolicitudDetalle;
  onActualizar: () => Promise<void>;
  onReenviada: (mensaje: string) => void;
}) {
  const obs = detalle.observacion || null;
  const docs = detalle.documentacion || [];
  const [trabajando, setTrabajando] = useState("");
  const [error, setError] = useState("");
  const [cbu, setCbu] = useState(obs?.cbu_actual || "");

  if (!detalle.puede_adjuntar || (!obs && !docs.length)) return null;

  const hacer = async (que: string, fn: () => Promise<unknown>) => {
    setTrabajando(que); setError("");
    try { await fn(); await onActualizar(); } catch (e) { setError(String((e as Error).message || e)); }
    finally { setTrabajando(""); }
  };
  const subir = (d: DocDeLaSolicitud, file: File | undefined) => {
    if (!file) return;
    if (!TIPOS.includes(file.type)) { setError("Subí una imagen (JPG, PNG, WEBP) o un PDF."); return; }
    if (file.size > MAX) { setError("El archivo supera los 5 MB."); return; }
    hacer(d.tipo, () => api.docSubir(detalle.numero, file, d.tipo));
  };
  const reenviar = async () => {
    setTrabajando("reenviar"); setError("");
    try {
      const s = await api.reenviar(detalle.numero);
      onReenviada(`Listo: la solicitud ${s.numero} volvió a evaluación.`);
    } catch (e) { setError(String((e as Error).message || e)); }
    finally { setTrabajando(""); }
  };

  return (
    <section className="p-corr">
      {obs && (
        <div className="p-warnbox" role="status">
          <b>El asesor te pidió que corrijas tu solicitud</b>
          <p className="p-corr-detalle">{obs.detalle}</p>
          {obs.pendientes.length > 0 && <div className="p-fine">Falta: {obs.pendientes.join(", ")}.</div>}
        </div>
      )}

      <h3 className="p-corr-tit">Documentación</h3>
      <ul className="p-corr-docs" aria-label="Documentación de la solicitud">
        {docs.map((d) => {
          const pendiente = d.observado ? !d.corregido : !d.adjunto;
          const puedeSubir = !d.adjunto || (d.observado && !d.corregido);
          const etiqueta = d.adjunto ? (d.observado && !d.corregido ? "Reemplazar" : "") : "Adjuntar";
          return (
            <li key={d.tipo} className={`p-doc ${pendiente && (d.obligatorio || d.observado) ? "p-doc-falta" : ""}`}>
              <div className="p-doc-meta">
                <b>{d.titulo}{!d.obligatorio && <span className="p-fine"> (opcional)</span>}</b>
                <span className="p-fine">
                  {d.observado && (d.corregido ? "✓ Corregido · " : "Pedido por el asesor · ")}
                  {d.adjunto ? d.adjunto.nombre : "Sin adjuntar"}
                </span>
              </div>
              {puedeSubir && etiqueta && (
                <label className="p-btn-file">{trabajando === d.tipo ? "Subiendo…" : etiqueta}
                  <input type="file" accept={TIPOS.join(",")} hidden aria-label={`${etiqueta} ${d.titulo}`}
                         disabled={!!trabajando}
                         onChange={(e) => { subir(d, e.target.files?.[0]); e.target.value = ""; }} />
                </label>
              )}
            </li>
          );
        })}
      </ul>

      {obs?.cbu && (
        <div className="p-corr-cbu">
          <label className="p-fld"><span>CBU para acreditar el crédito (22 dígitos)</span>
            <input inputMode="numeric" value={cbu} maxLength={22} aria-label="CBU corregido"
                   onChange={(e) => setCbu(e.target.value.replace(/\D/g, "").slice(0, 22))} /></label>
          {obs.cbu_corregido && <span className="p-fine">✓ CBU corregido</span>}
          <button className="p-btn-ghost" disabled={cbu.length !== 22 || !!trabajando}
                  onClick={() => hacer("cbu", () => api.corregirCbu(detalle.numero, cbu))}>
            {trabajando === "cbu" ? "Guardando…" : "Guardar CBU"}
          </button>
        </div>
      )}

      {error && <div className="p-alert">{error}</div>}

      {obs && (
        <button className="p-btn" disabled={obs.pendientes.length > 0 || !!trabajando} onClick={reenviar}>
          {trabajando === "reenviar" ? "Reenviando…" : "Reenviar solicitud"}
        </button>
      )}
    </section>
  );
}
