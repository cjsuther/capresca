import { useEffect, useState } from "react";
import { api, EvidenciaSso, LlamadaSso } from "./api";

// Evidencia del canje del code con Mi Catamarca: qué le mandó nuestro servidor a Mi Catamarca y qué le
// respondió, paso por paso. Se muestra en la pantalla de ingreso cuando el ingreso falla, para poder
// presentarla ante el proveedor. Los secretos y los tokens llegan tapados desde el backend.

const PASOS: Record<string, string> = {
  token: "Canje del código por los tokens",
  userinfo: "Datos del ciudadano",
  jwks: "Claves públicas para verificar la firma",
};

const json = (v: unknown) => (typeof v === "string" ? v : JSON.stringify(v ?? {}, null, 2));
const hora = (v: string | null) => (v ? new Date(v).toLocaleString("es-AR") : "");

/** Texto plano con toda la evidencia, para copiar o descargar. */
export function textoEvidencia(e: EvidenciaSso): string {
  const lineas = [
    "Evidencia del ingreso con Mi Catamarca (portal mi.ccypp.gob.ar)",
    `Intento: ${e.intento}`,
    `Fecha: ${hora(e.fecha)} (${e.fecha})`,
    `Resultado: ${e.resultado}${e.error ? ` - ${e.error}` : ""}`,
  ];
  e.llamadas.forEach((l, i) => {
    lineas.push("", `=== ${i + 1}. ${PASOS[l.paso] || l.paso} ===`,
      `${l.metodo} ${l.url}`,
      `Respuesta HTTP: ${l.estado_http ?? "sin respuesta"}${l.duracion_ms != null ? ` (${l.duracion_ms} ms)` : ""}`);
    if (l.error) lineas.push(`Error: ${l.error}`);
    lineas.push("--- Headers enviados ---", json(l.solicitud?.headers));
    if (l.solicitud?.datos) lineas.push("--- Datos enviados ---", json(l.solicitud.datos));
    if (l.respuesta) lineas.push("--- Headers de la respuesta ---", json(l.respuesta.headers),
                                 "--- Cuerpo de la respuesta ---", json(l.respuesta.cuerpo));
  });
  return lineas.join("\n");
}

function descargar(e: EvidenciaSso) {
  const blob = new Blob([textoEvidencia(e)], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `evidencia-mi-catamarca-${e.intento.slice(0, 8)}.txt`;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

function Llamada({ l, n }: { l: LlamadaSso; n: number }) {
  const ok = l.estado_http != null && l.estado_http < 400;
  return (
    <section className="p-ev-llamada">
      <h3>{n}. {PASOS[l.paso] || l.paso}</h3>
      <p className="p-ev-linea"><code>{l.metodo} {l.url}</code></p>
      <p className="p-ev-linea">
        Respuesta: <b className={ok ? "p-ev-ok" : "p-ev-mal"}>{l.estado_http ?? "sin respuesta"}</b>
        {l.duracion_ms != null && <span className="p-ev-dim"> · {l.duracion_ms} ms</span>}
        {l.error && <span className="p-ev-mal"> · {l.error}</span>}
      </p>
      <div className="p-ev-grid">
        <div>
          <h4>Enviado</h4>
          <pre aria-label={`Enviado en el paso ${n}`}>{json({ headers: l.solicitud?.headers, datos: l.solicitud?.datos ?? undefined })}</pre>
        </div>
        <div>
          <h4>Recibido</h4>
          <pre aria-label={`Recibido en el paso ${n}`}>{l.respuesta
            ? `${json(l.respuesta.headers)}\n\n${json(l.respuesta.cuerpo)}` : "Sin respuesta del servidor."}</pre>
        </div>
      </div>
    </section>
  );
}

export function EvidenciaIngreso({ intento }: { intento: string }) {
  const [ev, setEv] = useState<EvidenciaSso | null>(null);
  const [err, setErr] = useState("");
  const [copiado, setCopiado] = useState(false);

  useEffect(() => {
    api.evidenciaIngreso(intento).then(setEv).catch((e) => setErr(String(e?.message || e)));
  }, [intento]);

  async function copiar() {
    if (!ev) return;
    try { await navigator.clipboard.writeText(textoEvidencia(ev)); setCopiado(true); }
    catch { setCopiado(false); }
  }

  return (
    <div className="p-card p-ev" role="region" aria-label="Detalle técnico del ingreso">
      <h2>Detalle técnico del intento de ingreso</h2>
      {err && <p className="p-ev-dim">No se pudo obtener el detalle: {err}</p>}
      {!ev && !err && <p className="p-ev-dim">Cargando el detalle…</p>}
      {ev && <>
        <p className="p-ev-dim">
          {hora(ev.fecha)} · intento <code>{ev.intento}</code><br />
          Lo que nuestro servidor le envió a Mi Catamarca al verificar el ingreso y lo que Mi Catamarca respondió.
          Las claves y los tokens se muestran ocultos.
        </p>
        {ev.error && <p className="p-ev-linea">Resultado: <b className="p-ev-mal">{ev.error}</b></p>}
        <div className="p-ev-acciones">
          <button className="p-btn-ghost" onClick={copiar}>{copiado ? "Copiado" : "Copiar"}</button>
          <button className="p-btn-ghost" onClick={() => descargar(ev)}>Descargar</button>
        </div>
        {ev.llamadas.length === 0 && <p className="p-ev-dim">No se llegó a llamar a Mi Catamarca.</p>}
        {ev.llamadas.map((l, i) => <Llamada key={i} l={l} n={i + 1} />)}
      </>}
      <style>{`
        .p-ev { width:100%; max-width:960px; padding:22px; text-align:left; }
        .p-ev h2 { font-size:1.1rem; margin:0 0 8px; }
        .p-ev h3 { font-size:.95rem; margin:0 0 6px; }
        .p-ev h4 { font-size:.8rem; margin:0 0 4px; color:var(--p-muted); text-transform:uppercase; letter-spacing:.04em; }
        .p-ev-dim { color:var(--p-muted); font-size:.85rem; line-height:1.5; margin:0 0 10px; }
        .p-ev-linea { font-size:.85rem; margin:0 0 6px; overflow-wrap:anywhere; }
        .p-ev-ok { color:var(--p-ok); } .p-ev-mal { color:var(--p-crit); }
        .p-ev-acciones { display:flex; gap:8px; margin:6px 0 14px; }
        .p-ev-llamada { border-top:1px solid var(--p-border); padding-top:12px; margin-top:12px; }
        .p-ev-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
        .p-ev pre { margin:0; background:var(--p-bg); border:1px solid var(--p-border); border-radius:8px;
          padding:10px; font-size:.75rem; line-height:1.4; max-height:320px; overflow:auto;
          white-space:pre-wrap; word-break:break-all; color:var(--p-ink); }
        @media (max-width:720px) { .p-ev-grid { grid-template-columns:1fr; } }
      `}</style>
    </div>
  );
}
