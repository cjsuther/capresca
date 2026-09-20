/**
 * Diálogos in-app (reemplazo de window.confirm / alert / prompt).
 *
 * API imperativa, drop-in y sin props/context: se importa la función y se usa.
 *   const ok = await confirmar({ mensaje: "…", danger: true });
 *   await avisar("Guardado");                 // o avisar({ titulo, mensaje, tipo:"error" })
 *   const motivo = await pedirTexto({ mensaje: "Motivo:", requerido: true });
 *
 * El host <Dialogos/> se monta UNA sola vez en el root de la app. Todos cierran con Esc (cancela),
 * confirman/aceptan con Enter, y el clic en el fondo cancela. Estilo scopeado en `.ui-dlg*`.
 */
import { useEffect, useRef, useState } from "react";

type Base = { titulo?: string; mensaje: string };
type ConfirmOpts = Base & { confirmar?: string; cancelar?: string; danger?: boolean };
type AvisoOpts = Base & { tipo?: "ok" | "error"; aceptar?: string };
type TextoOpts = Base & {
  valor?: string; placeholder?: string; tipo?: "text" | "number";
  requerido?: boolean; confirmar?: string; cancelar?: string;
};

type Pedido =
  | { kind: "confirm"; opts: ConfirmOpts; resolve: (v: boolean) => void }
  | { kind: "aviso"; opts: AvisoOpts; resolve: () => void }
  | { kind: "texto"; opts: TextoOpts; resolve: (v: string | null) => void };

// --- store singleton (pub/sub) para no depender de context en los call sites ---
let _push: ((p: Pedido) => void) | null = null;
const _cola: Pedido[] = [];
function encolar(p: Pedido) {
  if (_push) _push(p);
  else _cola.push(p);   // si el host todavía no montó, se guarda y se vuelca al montar
}

export function confirmar(opts: ConfirmOpts): Promise<boolean> {
  return new Promise((resolve) => encolar({ kind: "confirm", opts, resolve }));
}
export function avisar(opts: AvisoOpts | string): Promise<void> {
  const o = typeof opts === "string" ? { mensaje: opts } : opts;
  return new Promise((resolve) => encolar({ kind: "aviso", opts: o, resolve }));
}
export function pedirTexto(opts: TextoOpts): Promise<string | null> {
  return new Promise((resolve) => encolar({ kind: "texto", opts, resolve }));
}

export function Dialogos() {
  const [actual, setActual] = useState<Pedido | null>(null);
  const pendientes = useRef<Pedido[]>([]);
  const [texto, setTexto] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const okRef = useRef<HTMLButtonElement>(null);

  // Registrar el push del store y volcar lo que se haya encolado antes de montar.
  useEffect(() => {
    const recibir = (p: Pedido) => {
      setActual((cur) => { if (cur) { pendientes.current.push(p); return cur; } return p; });
    };
    _push = recibir;
    if (_cola.length) { const c = _cola.splice(0); c.forEach(recibir); }
    return () => { _push = null; };
  }, []);

  // Al abrir uno nuevo: precargar texto y enfocar el control principal.
  useEffect(() => {
    if (!actual) return;
    if (actual.kind === "texto") setTexto(actual.opts.valor ?? "");
    const t = setTimeout(() => {
      if (actual.kind === "texto") inputRef.current?.focus();
      else okRef.current?.focus();
    }, 30);
    return () => clearTimeout(t);
  }, [actual]);

  if (!actual) return null;

  const siguiente = () => {
    const next = pendientes.current.shift() ?? null;
    setActual(next);
  };
  const cerrarCancel = () => {
    if (actual.kind === "confirm") actual.resolve(false);
    else if (actual.kind === "texto") actual.resolve(null);
    else actual.resolve();
    siguiente();
  };
  const aceptar = () => {
    if (actual.kind === "confirm") actual.resolve(true);
    else if (actual.kind === "aviso") actual.resolve();
    else {
      const v = texto.trim();
      if (actual.opts.requerido && !v) { inputRef.current?.focus(); return; }
      actual.resolve(actual.opts.tipo === "number" ? texto : v);
    }
    siguiente();
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") { e.stopPropagation(); cerrarCancel(); }
    else if (e.key === "Enter" && actual.kind !== "texto") { e.preventDefault(); aceptar(); }
  };

  const o = actual.opts as ConfirmOpts & AvisoOpts & TextoOpts;
  const esError = actual.kind === "aviso" && (o.tipo === "error");
  const danger = actual.kind === "confirm" && !!o.danger;
  const tituloDefault = actual.kind === "aviso" ? (esError ? "Atención" : "Aviso")
    : actual.kind === "confirm" ? "Confirmar" : "";
  const mostrarCancelar = actual.kind !== "aviso";
  const labelOk = actual.kind === "aviso" ? (o.aceptar || "Aceptar")
    : (o.confirmar || (actual.kind === "texto" ? "Aceptar" : "Confirmar"));

  return (
    <div className="ui-dlg-scrim" onMouseDown={(e) => { if (e.target === e.currentTarget) cerrarCancel(); }}>
      <div className="ui-dlg" role="dialog" aria-modal="true" onKeyDown={onKey}>
        <div className={"ui-dlg-head" + (esError ? " err" : "") + (danger ? " danger" : "")}>
          <span className="ui-dlg-ico" aria-hidden>{esError ? "!" : danger ? "!" : actual.kind === "texto" ? "✎" : "?"}</span>
          <b>{o.titulo || tituloDefault}</b>
        </div>
        <div className="ui-dlg-body">
          <p>{o.mensaje}</p>
          {actual.kind === "texto" && (
            <input
              ref={inputRef}
              className={o.tipo === "number" ? "num" : ""}
              type={o.tipo === "number" ? "number" : "text"}
              inputMode={o.tipo === "number" ? "decimal" : undefined}
              placeholder={o.placeholder}
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); aceptar(); } }}
            />
          )}
        </div>
        <div className="ui-dlg-foot">
          {mostrarCancelar && <button className="btn-ghost" onClick={cerrarCancel}>{o.cancelar || "Cancelar"}</button>}
          <button ref={okRef} className={danger ? "btn-danger" : ""} onClick={aceptar}>{labelOk}</button>
        </div>
      </div>
      <style>{`
        .ui-dlg-scrim{position:fixed;inset:0;background:rgba(16,24,40,.45);z-index:80;display:flex;align-items:center;justify-content:center;padding:16px;}
        .ui-dlg{width:min(440px,94vw);max-height:88vh;overflow:hidden;background:var(--surface);border:1px solid var(--border);border-radius:14px;box-shadow:0 24px 70px -20px rgba(16,32,64,.55);display:flex;flex-direction:column;}
        .ui-dlg-head{display:flex;align-items:center;gap:10px;padding:15px 18px 10px;font-size:15px;color:var(--ink);}
        .ui-dlg-ico{width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:15px;background:var(--accent-soft);color:var(--brand-2);flex:none;}
        .ui-dlg-head.err .ui-dlg-ico,.ui-dlg-head.danger .ui-dlg-ico{background:var(--crit-soft);color:var(--crit);}
        .ui-dlg-body{padding:2px 18px 8px;overflow-y:auto;}
        .ui-dlg-body p{margin:0 0 10px;font-size:13.5px;line-height:1.55;color:var(--ink-soft);white-space:pre-line;}
        .ui-dlg-body input{width:100%;margin:2px 0 6px;}
        .ui-dlg-foot{display:flex;gap:10px;justify-content:flex-end;padding:12px 18px 16px;}
        .ui-dlg-foot button{min-width:92px;}
      `}</style>
    </div>
  );
}
