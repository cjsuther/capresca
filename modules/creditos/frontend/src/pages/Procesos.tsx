import { useEffect, useState } from "react";
import { api } from "../api";

type Proceso = {
  id: string; categoria: string; titulo: string; descripcion: string;
  pasos: string[]; donde: string; verificacion: string; ref: string;
};

export default function Procesos() {
  const [items, setItems] = useState<Proceso[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.procesos().then((d) => setItems(d.items)).catch((e) => setErr(String(e)));
  }, []);

  return (
    <div className="proc">
      <div className="proc-head">
        <h1>Procesos de calidad</h1>
        <p>Los mecanismos repetibles que garantizan la calidad de la migración — no <i>qué</i> construimos, sino
          <b> cómo lo garantizamos</b>. Cada proceso es una guarda o un método que se aplica de forma sistemática;
          la mayoría falla ruidoso si se viola (candado de diseño, guardas de integridad) o verifica contra la
          fuente de verdad (equivalencia vs VFP, QA profundo).</p>
        <span className="proc-count">{items.length} procesos</span>
      </div>
      {err && <div className="alert crit">{err}</div>}

      <div className="proc-list">
        {items.map((p, i) => (
          <article className="proc-card" key={p.id}>
            <div className="proc-num">{String(i + 1).padStart(2, "0")}</div>
            <div className="proc-body">
              <div className="proc-top">
                <span className="proc-cat">{p.categoria}</span>
                <h2>{p.titulo}</h2>
              </div>
              <p className="proc-desc">{p.descripcion}</p>
              <ol className="proc-pasos">
                {p.pasos.map((s, k) => <li key={k}>{s}</li>)}
              </ol>
              <div className="proc-meta">
                <div><span className="proc-lbl">Dónde</span> <code>{p.donde}</code></div>
                <div><span className="proc-lbl proc-ok">Verificación</span> {p.verificacion}</div>
              </div>
              <div className="proc-foot">
                <code className="proc-ref" title="Hallazgo / caso de Controles de Versión">{p.ref}</code>
              </div>
            </div>
          </article>
        ))}
      </div>

      <style>{`
        .proc { max-width: 980px; }
        .proc-head h1 { margin:0 0 6px; }
        .proc-head p { color:var(--ink-soft); margin:0; max-width:72ch; line-height:1.5; }
        .proc-count { display:inline-block; margin-top:10px; font-size:12px; font-weight:700; color:var(--brand-2); background:var(--brand-soft); border-radius:999px; padding:3px 11px; }
        .proc-list { display:flex; flex-direction:column; gap:14px; margin-top:18px; }
        .proc-card { display:flex; gap:14px; background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:16px 18px; }
        .proc-num { font-size:1.5rem; font-weight:800; color:var(--border-strong); min-width:34px; line-height:1; }
        .proc-body { flex:1; }
        .proc-top { display:flex; flex-direction:column; gap:2px; margin-bottom:6px; }
        .proc-cat { font-size:10.5px; font-weight:800; letter-spacing:.04em; text-transform:uppercase; color:var(--brand-2); }
        .proc-top h2 { margin:0; font-size:1.05rem; }
        .proc-desc { color:var(--ink); margin:0 0 10px; line-height:1.5; }
        .proc-pasos { margin:0 0 10px; padding-left:1.1rem; color:var(--ink-soft); font-size:.9rem; line-height:1.55; }
        .proc-pasos li { margin-bottom:2px; }
        .proc-meta { display:flex; flex-direction:column; gap:4px; font-size:.85rem; color:var(--ink-soft); border-top:1px solid var(--border); padding-top:8px; }
        .proc-meta code { color:var(--ink); font-family:var(--font-mono,monospace); font-size:.8rem; }
        .proc-lbl { font-size:.68rem; font-weight:800; letter-spacing:.03em; text-transform:uppercase; color:var(--ink-faint); }
        .proc-ok { color:var(--ok); }
        .proc-foot { margin-top:8px; }
        .proc-ref { font-size:11px; color:var(--ink-faint); background:var(--surface-2); border-radius:6px; padding:2px 8px; }
      `}</style>
    </div>
  );
}
