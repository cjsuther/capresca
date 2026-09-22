import { Sun, Moon, Monitor } from "lucide-react";
import clsx from "clsx";
import { useThemeStore } from "../context/themeStore";

const OPCIONES = [
  { id: "light", label: "Claro", icon: Sun },
  { id: "dark", label: "Oscuro", icon: Moon },
  { id: "system", label: "Sistema", icon: Monitor },
];

/**
 * Selector de tema. `variante="menu"` lo muestra como fila dentro del menú de usuario;
 * `variante="suelto"` como grupo de botones (login, pantallas sin topbar).
 */
export function ThemeToggle({ variante = "menu" }) {
  const tema = useThemeStore((s) => s.tema);
  const setTema = useThemeStore((s) => s.setTema);

  return (
    <div className={clsx("flex items-center gap-1", variante === "menu" && "px-3 py-2")}>
      {variante === "menu" && <span className="text-sm text-gray-600 mr-auto">Tema</span>}
      <div role="radiogroup" aria-label="Tema de la interfaz"
           className="flex items-center gap-0.5 p-0.5 rounded-lg bg-gray-100">
        {OPCIONES.map((o) => {
          const Icono = o.icon;
          const activo = tema === o.id;
          return (
            <button
              key={o.id}
              role="radio"
              aria-checked={activo}
              aria-label={o.label}
              title={o.label}
              onClick={() => setTema(o.id)}
              className={clsx(
                "p-1.5 rounded-md transition-colors",
                activo ? "bg-surface text-blue-700 shadow-sm" : "text-gray-500 hover:text-gray-800"
              )}
            >
              <Icono size={15} />
            </button>
          );
        })}
      </div>
    </div>
  );
}
