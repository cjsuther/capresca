import { useEffect, useRef, useState } from "react";
import type { Video } from "./api";

/**
 * Paso 4 del trámite: videos que el ciudadano tiene que ver COMPLETOS antes de confirmar.
 *
 * - Se ven en orden: cada uno se habilita al terminar el anterior.
 * - No se puede adelantar (un salto hacia adelante vuelve al punto más lejano visto) ni cambiar la
 *   velocidad; sí volver atrás. Si la pestaña queda en segundo plano, el video se pausa.
 * - Un video cuenta como visto cuando termina habiendo recorrido todo su largo.
 * - Lo visto se recuerda en el navegador hasta enviar la solicitud (un corte o una recarga no obliga a
 *   verlos de nuevo). El backend exige igual la lista completa al enviar.
 */
const TOLERANCIA_SALTO = 0.75;   // s: más que esto hacia adelante del punto más lejano visto = adelantar
const TOLERANCIA_FINAL = 1.5;    // s: margen para considerar que llegó al final

export const claveVideos = (sub: string) => `portal_videos_${sub}`;

export function leerVistos(sub: string): string[] {
  try { return JSON.parse(localStorage.getItem(claveVideos(sub)) || "[]"); } catch { return []; }
}

export function guardarVistos(sub: string, ids: string[]) {
  try { localStorage.setItem(claveVideos(sub), JSON.stringify(ids)); } catch { /* modo privado */ }
}

export function olvidarVistos(sub: string) {
  try { localStorage.removeItem(claveVideos(sub)); } catch { /* modo privado */ }
}

const minutos = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

export function VideoObligatorio({ video, numero, completo, habilitado, onCompleto }: {
  video: Video; numero: number; completo: boolean; habilitado: boolean; onCompleto: (id: string) => void;
}) {
  const ref = useRef<HTMLVideoElement>(null);
  const maxVisto = useRef(0);
  const [progreso, setProgreso] = useState(completo ? 1 : 0);
  const [duracion, setDuracion] = useState(0);
  const [aviso, setAviso] = useState("");

  // Pestaña en segundo plano: se pausa (tiene que verlo, no dejarlo corriendo de fondo).
  useEffect(() => {
    const alOcultar = () => { if (document.hidden && ref.current && !ref.current.paused) ref.current.pause(); };
    document.addEventListener("visibilitychange", alOcultar);
    return () => document.removeEventListener("visibilitychange", alOcultar);
  }, []);

  const alAvanzar = () => {
    const v = ref.current;
    if (!v) return;
    if (!completo && v.currentTime > maxVisto.current + TOLERANCIA_SALTO) return;   // un salto: lo corrige alBuscar
    maxVisto.current = Math.max(maxVisto.current, v.currentTime);
    if (v.duration) setProgreso(completo ? 1 : Math.min(1, maxVisto.current / v.duration));
  };

  const alBuscar = () => {
    const v = ref.current;
    if (!v || completo) return;
    if (v.currentTime > maxVisto.current + TOLERANCIA_SALTO) {
      v.currentTime = maxVisto.current;
      setAviso("No se puede adelantar: el video se tiene que ver completo.");
    }
  };

  const alCambiarVelocidad = () => {
    const v = ref.current;
    if (v && v.playbackRate !== 1) {
      v.playbackRate = 1;
      setAviso("El video se reproduce a velocidad normal.");
    }
  };

  const alTerminar = () => {
    const v = ref.current;
    if (!v) return;
    if (completo || maxVisto.current >= (v.duration || 0) - TOLERANCIA_FINAL) {
      setProgreso(1); setAviso("");
      if (!completo) onCompleto(video.id);
    }
  };

  const estado = completo ? "ok" : habilitado ? "on" : "off";
  return (
    <article className={`p-video ${estado}`} aria-label={`Video ${numero}: ${video.titulo}`}>
      <header className="p-video-head">
        <span className="p-video-n">{completo ? "✓" : numero}</span>
        <b>{video.titulo}</b>
        <span className="p-fine">
          {completo ? "Visto" : habilitado ? (duracion ? `${minutos(duracion)} · ${Math.round(progreso * 100)}% visto` : "Listo para ver") : "Se habilita al terminar el anterior"}
        </span>
      </header>
      {habilitado || completo ? (
        <>
          <video
            ref={ref}
            src={video.url}
            controls
            playsInline
            preload="metadata"
            disablePictureInPicture
            controlsList="nodownload noplaybackrate"
            onContextMenu={(e) => e.preventDefault()}
            onLoadedMetadata={(e) => setDuracion(e.currentTarget.duration || 0)}
            onTimeUpdate={alAvanzar}
            onSeeking={alBuscar}
            onRateChange={alCambiarVelocidad}
            onEnded={alTerminar}
          />
          <div className="p-video-bar" role="progressbar" aria-label={`Progreso del video ${numero}`}
               aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progreso * 100)}>
            <span style={{ width: `${progreso * 100}%` }} />
          </div>
          {aviso && <p className="p-video-aviso" role="status">{aviso}</p>}
        </>
      ) : (
        <div className="p-video-lock" aria-hidden>🔒</div>
      )}
    </article>
  );
}

export function PasoVideos({ videos, vistos, onVisto, error }: {
  videos: Video[]; vistos: string[]; onVisto: (id: string) => void; error?: string;
}) {
  const faltan = videos.filter((v) => !vistos.includes(v.id)).length;
  return (
    <div className="p-card p-videos">
      <div className="p-subtitle" style={{ borderTop: "none", paddingTop: 0 }}>
        Mirá los videos <span>(obligatorio para continuar)</span>
      </div>
      <p className="p-fine" style={{ margin: "6px 0 14px" }}>
        Antes de confirmar tenés que ver los {videos.length} videos completos, en orden. No se pueden adelantar;
        si salís, lo que ya viste queda guardado.
      </p>
      {error && <div className="p-alert">{error}</div>}
      {videos.map((v, i) => (
        <VideoObligatorio key={v.id} video={v} numero={i + 1} completo={vistos.includes(v.id)}
                          habilitado={i === 0 || vistos.includes(videos[i - 1].id)} onCompleto={onVisto} />
      ))}
      <p className="p-fine" style={{ marginTop: 10 }}>
        {faltan === 0 ? "✓ Viste todos los videos." : `Te falta${faltan === 1 ? "" : "n"} ${faltan} video${faltan === 1 ? "" : "s"}.`}
      </p>
    </div>
  );
}
