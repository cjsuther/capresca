import { useEffect, useRef } from "react";

// Editor tipo mini-Word (compartido): contentEditable + barra (título/subtítulo/párrafo, negrita/cursiva/
// subrayado, lista, alineación). Guarda HTML. Usado en Resoluciones y en Modelos de resolución.

export const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
export const esHtml = (t: string) => /<(p|div|h[1-4]|br|ul|ol|li|b|i|u|strong|em)\b/i.test(t || "");
// texto plano → HTML editable: párrafos por líneas en blanco, saltos simples con <br>.
export const plainAHtml = (t: string) =>
  !t ? "" : t.split(/\n{2,}/).map((b) => `<p>${esc(b).replace(/\n/g, "<br>")}</p>`).join("");
export const htmlTieneContenido = (h: string) =>
  (h || "").replace(/<[^>]*>/g, "").replace(/&nbsp;/g, " ").trim().length > 0;

export default function RichText({ value, onChange, placeholder, minHeight }:
  { value: string; onChange: (html: string) => void; placeholder?: string; minHeight?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  // Sentinel: nunca coincide con un value real, así el PRIMER render (incluso si el editor se monta ya
  // con contenido, p.ej. al abrir "Editar" tras cargar la plantilla) vuelca el HTML en el contentEditable.
  const last = useRef<string | null>(null);
  useEffect(() => {
    if (ref.current && value !== last.current && value !== ref.current.innerHTML) {
      ref.current.innerHTML = value || ""; last.current = value;
    }
  }, [value]);
  const emit = () => { const h = ref.current?.innerHTML || ""; last.current = h; onChange(h); };
  const cmd = (c: string, arg?: string) => { document.execCommand(c, false, arg); ref.current?.focus(); emit(); };
  const B = ({ c, a, t, children }: { c: string; a?: string; t: string; children: any }) =>
    <button type="button" className="rt-b" title={t} onMouseDown={(e) => { e.preventDefault(); cmd(c, a); }}>{children}</button>;
  return (
    <div className="rt">
      <div className="rt-tb">
        <B c="formatBlock" a="H2" t="Título">T</B>
        <B c="formatBlock" a="H3" t="Subtítulo"><span style={{ fontSize: 12 }}>t</span></B>
        <B c="formatBlock" a="P" t="Párrafo normal">¶</B>
        <span className="rt-sep" />
        <B c="bold" t="Negrita"><b>N</b></B>
        <B c="italic" t="Cursiva"><i>C</i></B>
        <B c="underline" t="Subrayado"><u>S</u></B>
        <span className="rt-sep" />
        <B c="insertUnorderedList" t="Lista">•—</B>
        <B c="justifyLeft" t="Alinear izquierda">⬱</B>
        <B c="justifyCenter" t="Centrar">≡</B>
        <B c="justifyFull" t="Justificar">☰</B>
      </div>
      <div ref={ref} className="rt-area" contentEditable suppressContentEditableWarning
           style={minHeight ? { minHeight } : undefined}
           data-ph={placeholder || ""} onInput={emit} onBlur={emit} />
      <style>{`
        .rt { border:1px solid var(--border); border-radius:10px; overflow:hidden; background:var(--surface); }
        .rt-tb { display:flex; align-items:center; gap:2px; padding:6px 8px; border-bottom:1px solid var(--border); background:var(--surface-2); flex-wrap:wrap; }
        .rt-b { min-width:28px; height:28px; padding:0 8px; border:1px solid var(--border); border-radius:7px; background:var(--surface); color:var(--ink); cursor:pointer; font-size:13px; line-height:1; display:inline-flex; align-items:center; justify-content:center; }
        .rt-b:hover { border-color:var(--brand-2); color:var(--brand-2); }
        .rt-sep { width:1px; align-self:stretch; background:var(--border); margin:2px 4px; }
        .rt-area { min-height:220px; max-height:420px; overflow:auto; padding:12px 14px; font-size:13.5px; line-height:1.55; outline:none; }
        .rt-area:empty:before { content:attr(data-ph); color:var(--ink-faint); }
        .rt-area h1,.rt-area h2 { font-size:15px; text-align:center; margin:.4em 0; font-weight:700; }
        .rt-area h3,.rt-area h4 { font-size:13.5px; margin:.4em 0; font-weight:700; }
        .rt-area p { margin:.4em 0; }
      `}</style>
    </div>
  );
}
