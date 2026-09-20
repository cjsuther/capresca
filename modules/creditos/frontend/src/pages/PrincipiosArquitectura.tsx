import { useEffect, useState } from "react";
import { api } from "../api";

type Principio = {
  id: string; categoria: string; titulo: string; enunciado: string;
  motivo: string; aplica: string[]; ref: string;
};

export default function PrincipiosArquitectura() {
  const [items, setItems] = useState<Principio[]>([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.principiosArquitectura().then((d) => setItems(d.items)).catch((e) => setErr(String(e)));
  }, []);

  return (
    <div className="parq">
      <div className="parq-head">
        <h1>Principios de arquitectura</h1>
        <p>Criterios que guían las decisiones de diseño de la aplicación. Se van sumando durante la construcción;
          cada decisión estructural nueva se toma a la luz de esta lista y, si aporta uno nuevo, se agrega.</p>
        <span className="parq-count">{items.length} principios</span>
      </div>
      {err && <div className="alert crit">{err}</div>}

      <div className="parq-list">
        {items.map((p, i) => (
          <article className="parq-card" key={p.id}>
            <div className="parq-num">{String(i + 1).padStart(2, "0")}</div>
            <div className="parq-body">
              <div className="parq-top">
                <span className="parq-cat">{p.categoria}</span>
                <h2>{p.titulo}</h2>
              </div>
              <p className="parq-enun">{p.enunciado}</p>
              <div className="parq-porque">
                <span className="parq-lbl">Por qué</span>
                <p>{p.motivo}</p>
              </div>
              <div className="parq-foot">
                <div className="parq-aplica">
                  {p.aplica.map((a) => <span className="parq-chip" key={a}>{a}</span>)}
                </div>
                <code className="parq-ref" title="Referencia (hallazgo / caso / archivo)">{p.ref}</code>
              </div>
            </div>
          </article>
        ))}
      </div>

      <style>{`
        .parq { max-width: 940px; }
        .parq-head { margin-bottom: 20px; }
        .parq-head h1 { margin: 0 0 6px; }
        .parq-head p { margin: 0; color: var(--ink-soft); max-width: 70ch; line-height: 1.5; }
        .parq-count { display:inline-block; margin-top:10px; font-size:.72rem; text-transform:uppercase; letter-spacing:.5px;
          color: var(--ink-soft); border:1px solid var(--border); border-radius:999px; padding:3px 10px; }
        .parq-list { display:flex; flex-direction:column; gap:14px; }
        .parq-card { display:flex; gap:16px; background:var(--surface); border:1px solid var(--border); border-radius:14px;
          padding:16px 18px; box-shadow: var(--shadow, 0 1px 2px rgba(0,0,0,.04)); }
        .parq-num { font-size:1.4rem; font-weight:700; color:var(--brand-2); font-variant-numeric:tabular-nums;
          line-height:1; min-width:34px; opacity:.85; }
        .parq-body { flex:1; min-width:0; }
        .parq-top { display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; margin-bottom:8px; }
        .parq-cat { font-size:.66rem; text-transform:uppercase; letter-spacing:.5px; font-weight:700;
          color:var(--brand-2); background:color-mix(in srgb, var(--brand-2) 12%, transparent);
          border-radius:6px; padding:3px 8px; white-space:nowrap; }
        .parq-top h2 { margin:0; font-size:1.05rem; line-height:1.3; }
        .parq-enun { margin:0 0 10px; line-height:1.55; color:var(--ink); }
        .parq-porque { border-left:3px solid var(--border); padding:2px 0 2px 12px; margin:0 0 12px; }
        .parq-lbl { display:block; font-size:.64rem; text-transform:uppercase; letter-spacing:.5px; color:var(--ink-faint); margin-bottom:2px; }
        .parq-porque p { margin:0; color:var(--ink-soft); line-height:1.5; font-size:.9rem; }
        .parq-foot { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; }
        .parq-aplica { display:flex; gap:6px; flex-wrap:wrap; }
        .parq-chip { font-size:.72rem; color:var(--ink-soft); background:var(--surface-2); border:1px solid var(--border);
          border-radius:999px; padding:2px 9px; }
        .parq-ref { font-size:.72rem; color:var(--ink-faint); background:var(--surface-2); border:1px solid var(--border);
          border-radius:6px; padding:2px 7px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:100%; }
      `}</style>
    </div>
  );
}
