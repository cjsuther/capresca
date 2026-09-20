import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Icon from "./Icon";
import { api, usuarioSesion } from "../api";

const THEME_KEY = "ccypp_theme";

function prefersDark() {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}
export function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === "dark" || saved === "light") {
    document.documentElement.setAttribute("data-theme", saved);
  }
}
function currentTheme(): "dark" | "light" {
  const attr = document.documentElement.getAttribute("data-theme");
  if (attr === "dark" || attr === "light") return attr;
  return prefersDark() ? "dark" : "light";
}

export default function Topbar() {
  const nav = useNavigate();
  const [theme, setTheme] = useState<"dark" | "light">(currentTheme());
  const [pendientes, setPendientes] = useState(0);
  const { nombre, username } = usuarioSesion();   // usuario de Portezuelo (misma sesión)

  useEffect(() => { setTheme(currentTheme()); }, []);
  // Alertas del sistema: cuántas tareas hay en el inbox de aprobaciones (poll cada 60s).
  useEffect(() => {
    let vivo = true;
    const tick = () => api.inboxCount().then((d) => vivo && setPendientes(d.total || 0)).catch(() => {});
    tick();
    const id = setInterval(tick, 60_000);
    return () => { vivo = false; clearInterval(id); };
  }, []);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem(THEME_KEY, next);
    setTheme(next);
  }

  const iniciales = (nombre || "U").slice(0, 2).toUpperCase();

  return (
    <header className="topbar">
      <div className="search">
        <Icon name="search" size={16} />
        <input placeholder="Buscar cliente, crédito, CUIL, N° de OP…" aria-label="Buscar" />
      </div>
      <div className="top-actions">
        {/* Volver al tablero de Portezuelo (fuera de esta app: navegación completa, no del router). */}
        <a className="icon-btn" href="/dashboard" title="Volver a Portezuelo" aria-label="Volver a Portezuelo">
          <Icon name="home" size={17} />
        </a>
        <button className="icon-btn" onClick={toggleTheme}
                title={theme === "dark" ? "Tema claro" : "Tema oscuro"}
                aria-label="Cambiar tema">
          <Icon name={theme === "dark" ? "sun" : "moon"} size={17} />
        </button>
        <button className="icon-btn bell-btn" title={pendientes ? `Inbox — ${pendientes} pendiente(s)` : "Inbox"}
                aria-label="Inbox" onClick={() => nav("/creditos/inbox-aprobaciones")}>
          <Icon name="inbox" size={17} />
          {pendientes > 0 && <span className="bell-badge">{pendientes > 9 ? "9+" : pendientes}</span>}
        </button>
        <div className="userchip">
          <span className="av">{iniciales}</span>
          <div>
            <div className="who">{nombre || "Usuario"}</div>
            {username && username !== nombre && <div className="role">{username}</div>}
          </div>
        </div>
      </div>
    </header>
  );
}
