import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { salir } from "../api";
import Icon from "./Icon";
import Logo from "./Logo";

import { MENU, items } from "../menu";
import { usePermisos } from "../permisos";

const VER_TODO_KEY = "sidebar_ver_todo";
// Módulos que se ven COMPLETOS aun en la vista restringida (además de todas las opciones `new`). H-193.
const SIEMPRE_VISIBLE = new Set(["Clientes", "General"]);

export default function Sidebar() {
  const location = useLocation();
  const { puedeVer, esAdmin } = usePermisos();   // sólo el administrador del módulo alterna la vista completa
  // El admin por defecto VE TODO y puede "Ocultar" (dejar la vista restringida); los no-admin SIEMPRE ven
  // la vista restringida: sólo Clientes, General y las opciones marcadas `new`.
  const [verTodo, setVerTodo] = useState<boolean>(() => {
    try { return localStorage.getItem(VER_TODO_KEY) !== "0"; } catch { return true; }
  });
  const toggleVerTodo = () => setVerTodo((v) => {
    const n = !v; try { localStorage.setItem(VER_TODO_KEY, n ? "1" : "0"); } catch { /* ignore */ }
    return n;
  });
  const restringido = !esAdmin || !verTodo;   // no-admin: siempre; admin: cuando "ocultó"
  const itemVisible = (m: typeof MENU[number], i: { to: string; nuevo?: boolean }) =>
    puedeVer(i.to) && (!restringido || SIEMPRE_VISIBLE.has(m.label) || !!i.nuevo);
  const moduloActivo = MENU.find((m) => items(m).some((i) => location.pathname.startsWith(i.to)));
  const [abierto, setAbierto] = useState<string | null>(moduloActivo?.label ?? "Clientes");

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <Logo size={48} onDark />
        <div>
          <span className="sidebar-logo">C.C. y P.P.</span>
          <span className="sidebar-sub">Ca.Pre.S.Ca.</span>
        </div>
      </div>
      <nav className="sidebar-nav">
        {MENU.map((m) => {
          // Grupos con al menos una pantalla visible: por permiso del perfil y por la regla de visibilidad
          // (vista restringida = sólo Clientes/General completos + opciones `new`). H-193.
          const grupos = m.grupos
            .map((g) => ({ ...g, items: g.items.filter((i) => itemVisible(m, i)) }))
            .filter((g) => g.items.length > 0);
          if (grupos.length === 0) return null;                 // módulo sin pantallas visibles → oculto
          const expandido = abierto === m.label;
          const activoAqui = grupos.some((g) => g.items.some((i) => location.pathname.startsWith(i.to)));
          return (
            <div key={m.label} className="sb-group">
              <button className={`sb-modulo ${activoAqui ? "activo" : ""}`}
                      onClick={() => setAbierto(expandido ? null : m.label)}>
                <span className="sb-icon"><Icon name={m.icon} /></span>
                <span className="sb-label">{m.label}</span>
                <span className={`sb-chevron ${expandido ? "abierto" : ""}`}><Icon name="chevron" size={14} /></span>
              </button>
              {expandido && (
                <div className="sb-items">
                  {grupos.map((g) => (
                    <div key={g.label} className="sb-sub">
                      {g.items.map((i) => (
                        <NavLink key={i.to} to={i.to}
                          className={({ isActive }) => `sb-item ${isActive ? "activo" : ""}`}>
                          {i.nuevo && <span className="sb-new">new</span>}{i.label}
                        </NavLink>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </nav>
      {esAdmin && (
        <button className={`sb-ocultos ${!verTodo ? "on" : ""}`} onClick={toggleVerTodo}
                title="Vista restringida: sólo Clientes, General y opciones nuevas (así lo ven los no-administradores)">
          <Icon name={verTodo ? "eye-off" : "eye"} size={15} />
          {verTodo ? "Ocultar módulos" : "Mostrar todos los módulos"}
        </button>
      )}
      <button className="sb-salir" onClick={() => { salir(); }}><Icon name="logout" size={16} /> Salir</button>
    </aside>
  );
}
