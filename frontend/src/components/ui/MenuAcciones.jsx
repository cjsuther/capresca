import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { MoreHorizontal } from "lucide-react";

/**
 * Botón "⋯" con las acciones de una fila o tarjeta (viene del sistema anterior, que tenía este menú
 * en todas las grillas). El menú se posiciona `fixed` para que no lo recorte el contenedor de la
 * tabla, y se cierra al hacer clic afuera, al scrollear o con Escape.
 *
 * acciones: [{ label, onClick, danger?, oculta?, title? }]
 */
export function MenuAcciones({ acciones = [], etiqueta = "Acciones" }) {
  const [abierto, setAbierto] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const btn = useRef(null);
  const visibles = acciones.filter((a) => a && !a.oculta);
  const ANCHO = 220;

  useLayoutEffect(() => {
    if (!abierto || !btn.current) return;
    const r = btn.current.getBoundingClientRect();
    setPos({ top: r.bottom + 4, left: Math.max(8, Math.min(r.right - ANCHO, window.innerWidth - ANCHO - 8)) });
  }, [abierto]);

  useEffect(() => {
    if (!abierto) return;
    const cerrar = () => setAbierto(false);
    const esc = (e) => e.key === "Escape" && setAbierto(false);
    window.addEventListener("click", cerrar);
    window.addEventListener("scroll", cerrar, true);
    window.addEventListener("resize", cerrar);
    window.addEventListener("keydown", esc);
    return () => {
      window.removeEventListener("click", cerrar);
      window.removeEventListener("scroll", cerrar, true);
      window.removeEventListener("resize", cerrar);
      window.removeEventListener("keydown", esc);
    };
  }, [abierto]);

  if (!visibles.length) return null;

  return (
    <>
      <button
        ref={btn}
        type="button"
        aria-label={etiqueta}
        aria-haspopup="menu"
        aria-expanded={abierto}
        onClick={(e) => { e.stopPropagation(); setAbierto((o) => !o); }}
        className={`p-1.5 rounded-lg border border-transparent text-gray-400 hover:text-gray-700 hover:bg-gray-100 ${
          abierto ? "bg-gray-100 text-gray-700 border-gray-200" : ""}`}
      >
        <MoreHorizontal size={18} />
      </button>
      {abierto && (
        <div
          role="menu"
          onClick={(e) => e.stopPropagation()}
          style={{ position: "fixed", top: pos.top, left: pos.left, width: ANCHO }}
          className="z-50 bg-surface border border-gray-200 rounded-xl shadow-lg py-1 overflow-hidden"
        >
          {visibles.map((a, i) => (
            <button
              key={i}
              type="button"
              role="menuitem"
              title={a.title}
              onClick={() => { setAbierto(false); a.onClick(); }}
              className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 ${
                a.danger ? "text-red-600 hover:bg-red-50" : "text-gray-700"}`}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
    </>
  );
}
