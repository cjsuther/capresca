import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LogOut, KeyRound, ChevronDown, Menu, X } from "lucide-react";
import { useAuthStore } from "../context/authStore";
import { useUser } from "../context/usePermissions";
import { logout as apiLogout } from "../api/auth";
import { changeMyPassword } from "../api/security";
import { ChangePasswordModal } from "./ChangePasswordModal";
import { NotificationBell } from "./NotificationBell";

export function Layout({ children, sidebar }) {
  const navigate = useNavigate();
  const logoutStore = useAuthStore((s) => s.logout);
  const user = useUser();
  const [menuOpen, setMenuOpen] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const closeSidebar = () => setSidebarOpen(false);

  const handleLogout = async () => {
    await apiLogout();
    logoutStore();
    navigate("/login");
  };

  // sidebar es un render prop: (onClose) => JSX
  const renderSidebar = (onClose) =>
    typeof sidebar === "function" ? sidebar(onClose) : sidebar;

  return (
    <div className="flex flex-col min-h-screen">
      {/* Topbar */}
      <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-4 md:px-6 shrink-0 z-20 relative">
        <div className="flex items-center gap-2 md:gap-4">
          {/* Hamburger — solo en mobile cuando hay sidebar */}
          {sidebar && (
            <button
              onClick={() => setSidebarOpen(true)}
              className="md:hidden p-2 rounded-lg hover:bg-gray-100 text-gray-600"
              aria-label="Abrir menú"
            >
              <Menu size={20} />
            </button>
          )}
          <Link to="/dashboard" className="flex items-center gap-2 hover:opacity-80">
            <img src="/logo-condor.svg" alt="Portezuelo" className="h-8 w-auto" />
            <span className="hidden sm:inline font-semibold text-sm text-gray-800">Portezuelo</span>
          </Link>
        </div>

        {/* Notificaciones + Menú de usuario */}
        <div className="flex items-center gap-1">
        <NotificationBell />
        <div className="relative">
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-900 px-3 py-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <span className="hidden sm:inline">{user?.full_name || user?.username}</span>
            <span className="sm:hidden">{(user?.full_name || user?.username || "").split(" ")[0]}</span>
            <ChevronDown size={14} />
          </button>

          {menuOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
              <div className="absolute right-0 top-full mt-1 w-52 bg-white border rounded-xl shadow-lg z-20 overflow-hidden">
                <div className="px-4 py-3 border-b bg-gray-50">
                  <p className="text-sm font-medium text-gray-800">{user?.full_name || user?.username}</p>
                  <p className="text-xs text-gray-400">{user?.username}</p>
                </div>
                <button
                  onClick={() => { setMenuOpen(false); setShowPasswordModal(true); }}
                  className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-gray-600 hover:bg-gray-50 text-left"
                >
                  <KeyRound size={15} />
                  Cambiar contraseña
                </button>
                <div className="border-t" />
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 text-left"
                >
                  <LogOut size={15} />
                  Cerrar sesión
                </button>
              </div>
            </>
          )}
        </div>
        </div>
      </header>

      {/* Mobile sidebar overlay */}
      {sidebar && (
        <div className={`fixed inset-0 z-50 md:hidden transition-opacity duration-200 ${sidebarOpen ? "opacity-100" : "opacity-0 pointer-events-none"}`}>
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/50" onClick={closeSidebar} />
          {/* Panel */}
          <div className={`relative h-full w-56 bg-white shadow-xl transform transition-transform duration-200 ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}`}>
            <div className="flex items-center justify-between px-4 py-3 border-b">
              <span className="text-sm font-semibold text-gray-700">Menú</span>
              <button onClick={closeSidebar} className="p-1 rounded text-gray-400 hover:text-gray-700">
                <X size={18} />
              </button>
            </div>
            {renderSidebar(closeSidebar)}
          </div>
        </div>
      )}

      {/* Body */}
      <div className="flex flex-1 min-h-0">
        {/* Desktop sidebar */}
        {sidebar && (
          <div className="hidden md:block shrink-0">
            {renderSidebar(undefined)}
          </div>
        )}
        <main className="flex-1 p-4 sm:p-6 overflow-auto">{children}</main>
      </div>

      {showPasswordModal && (
        <ChangePasswordModal
          title="Cambiar mi contraseña"
          requireCurrent
          onSave={(current, newPass) => changeMyPassword(current, newPass)}
          onClose={() => setShowPasswordModal(false)}
        />
      )}
    </div>
  );
}
