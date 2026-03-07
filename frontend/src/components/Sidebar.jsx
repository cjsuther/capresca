import { NavLink } from "react-router-dom";
import { useHasPermission } from "../context/usePermissions";
import clsx from "clsx";

export function Sidebar({ menuItems, moduleCode, onClose }) {
  return (
    <aside className="w-56 min-h-screen bg-white border-r border-gray-200 pt-4 md:pt-6">
      <nav className="flex flex-col gap-1 px-2">
        {menuItems.map((item) => (
          <SidebarItem key={item.path} item={item} moduleCode={moduleCode} onClose={onClose} />
        ))}
      </nav>
    </aside>
  );
}

function SidebarItem({ item, moduleCode, onClose }) {
  const hasPermission = useHasPermission(moduleCode, item.permission);
  if (!hasPermission) return null;

  return (
    <NavLink
      to={item.path}
      onClick={onClose}
      className={({ isActive }) =>
        clsx(
          "flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors",
          isActive
            ? "bg-blue-50 text-blue-700"
            : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
        )
      }
    >
      {item.icon && <item.icon size={16} />}
      {item.label}
    </NavLink>
  );
}
