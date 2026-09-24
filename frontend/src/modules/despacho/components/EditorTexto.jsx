import { useEffect, useRef } from "react";
import { Bold, Italic, Underline, List, AlignLeft, AlignCenter, AlignJustify, Heading } from "lucide-react";

/**
 * Editor del cuerpo del instrumento legal: un mini-Word.
 *
 * El texto se guarda como HTML, que es lo que después rinde el export a Word (títulos centrados,
 * negrita, listas). Se usa igual para el cuerpo de una resolución y para la plantilla de un modelo.
 */
const BOTONES = [
  { cmd: "bold", icon: Bold, titulo: "Negrita" },
  { cmd: "italic", icon: Italic, titulo: "Cursiva" },
  { cmd: "underline", icon: Underline, titulo: "Subrayado" },
  { cmd: "insertUnorderedList", icon: List, titulo: "Lista" },
  { cmd: "justifyLeft", icon: AlignLeft, titulo: "Izquierda" },
  { cmd: "justifyCenter", icon: AlignCenter, titulo: "Centrado" },
  { cmd: "justifyFull", icon: AlignJustify, titulo: "Justificado" },
];

export function EditorTexto({ value, onChange, disabled = false, alto = "min-h-[16rem]", label }) {
  const ref = useRef(null);

  // Sólo se escribe el HTML de afuera cuando es distinto: si no, el cursor salta en cada tecla.
  useEffect(() => {
    if (ref.current && ref.current.innerHTML !== (value || "")) {
      ref.current.innerHTML = value || "";
    }
  }, [value]);

  const aplicar = (cmd) => {
    if (disabled) return;
    ref.current?.focus();
    document.execCommand(cmd, false, null);
    onChange(ref.current.innerHTML);
  };

  const titulo = () => {
    if (disabled) return;
    ref.current?.focus();
    document.execCommand("formatBlock", false, "h2");
    onChange(ref.current.innerHTML);
  };

  return (
    <div className={`border border-gray-300 rounded-lg overflow-hidden ${disabled ? "opacity-60" : ""}`}>
      <div className="flex flex-wrap items-center gap-0.5 bg-gray-50 border-b border-gray-200 px-2 py-1">
        <button type="button" onClick={titulo} disabled={disabled} title="Título"
                className="p-1.5 rounded hover:bg-gray-200 text-gray-600">
          <Heading size={15} />
        </button>
        <span className="w-px h-5 bg-gray-300 mx-1" />
        {BOTONES.map(({ cmd, icon: Icono, titulo: t }) => (
          <button key={cmd} type="button" title={t} disabled={disabled}
                  onClick={() => aplicar(cmd)}
                  className="p-1.5 rounded hover:bg-gray-200 text-gray-600">
            <Icono size={15} />
          </button>
        ))}
      </div>
      <div
        ref={ref}
        role="textbox"
        aria-label={label || "Texto del instrumento"}
        contentEditable={!disabled}
        suppressContentEditableWarning
        onInput={(e) => onChange(e.currentTarget.innerHTML)}
        className={`${alto} p-4 text-sm bg-surface text-gray-800 focus:outline-none prose-despacho`}
      />
    </div>
  );
}
