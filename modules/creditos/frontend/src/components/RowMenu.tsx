import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Icon from "./Icon";

export type RowAction = {
  label: string;
  icon?: string;
  onClick: () => void;
  danger?: boolean;
  hidden?: boolean;
};

/** Botón ⋮ que abre un menú con las acciones de la fila. Reutilizable en toda la app. */
export default function RowMenu({ actions }: { actions: RowAction[] }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const btnRef = useRef<HTMLButtonElement>(null);
  const visibles = actions.filter((a) => !a.hidden);
  const MENU_W = 190;

  useLayoutEffect(() => {
    if (!open || !btnRef.current) return;
    const r = btnRef.current.getBoundingClientRect();
    // Alineado a la izquierda del botón (la columna es la primera), sin desbordar la pantalla.
    const left = Math.max(8, Math.min(r.left, window.innerWidth - MENU_W - 8));
    setPos({ top: r.bottom + 4, left });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("click", close);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    window.addEventListener("keydown", esc);
    return () => {
      window.removeEventListener("click", close);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
      window.removeEventListener("keydown", esc);
    };
  }, [open]);

  if (!visibles.length) return null;

  return (
    <>
      <button ref={btnRef} type="button" className={`rowmenu-btn${open ? " on" : ""}`}
              aria-label="Acciones" aria-haspopup="menu" aria-expanded={open}
              onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}>
        <Icon name="more-horizontal" size={18} />
      </button>
      {open && (
        <div className="rowmenu" role="menu"
             style={{ position: "fixed", top: pos.top, left: pos.left }}
             onClick={(e) => e.stopPropagation()}>
          {visibles.map((a, i) => (
            <button key={i} type="button" role="menuitem"
                    className={a.danger ? "danger" : undefined}
                    onClick={() => { setOpen(false); a.onClick(); }}>
              {a.icon && <Icon name={a.icon} size={16} />}
              <span>{a.label}</span>
            </button>
          ))}
        </div>
      )}
    </>
  );
}
