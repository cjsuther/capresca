import { NavLink } from "react-router-dom";
import clsx from "clsx";
import { MENU } from "./menu";
import { usePuedeVerHeredadas } from "./permisos";

const BASE = "/modules/creditos";

/** Menú del módulo Créditos, agrupado (Consultas, Reportes…). */
export function CreditosSidebar({ onClose }) {
  const verHeredadas = usePuedeVerHeredadas();
  const grupos = MENU
    .map((g) => ({ ...g, items: g.items.filter((i) => verHeredadas || !i.heredada) }))
    .filter((g) => g.items.length);
  return (
    <aside className="w-56 min-h-screen bg-surface border-r border-gray-200 pt-4 md:pt-6 overflow-y-auto">
      <nav className="flex flex-col px-2 pb-8">
        {grupos.map((g) => (
          <div key={g.label} className="mb-3">
            <p className="px-3 py-1 text-[10px] uppercase tracking-wide text-gray-400 font-semibold">{g.label}</p>
            {g.items.map((i) => (
              <NavLink
                key={i.to}
                to={`${BASE}/${i.to}`}
                onClick={onClose}
                className={({ isActive }) => clsx(
                  "block px-3 py-1.5 rounded-md text-[13px] transition-colors",
                  isActive ? "bg-blue-50 text-blue-700 font-medium" : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                )}
              >{i.label}</NavLink>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}
