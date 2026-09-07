import { useNavigate } from "react-router-dom";
import { Layout } from "../components/Layout";
import { useAuthStore } from "../context/authStore";
import { Shield, Banknote, Users, Building, Scale, Receipt, Database } from "lucide-react";
import clsx from "clsx";

const ALL_MODULES = [
  {
    code: "security",
    name: "Seguridad",
    description: "Gestión de usuarios, roles y permisos del sistema",
    icon: Shield,
    color: "bg-purple-50 border-purple-200 text-purple-700",
    iconColor: "text-purple-500",
    path: "/modules/security",
  },
  {
    code: "cajeros",
    name: "Cajeros",
    description: "Solicitudes y autorizaciones de operaciones de caja",
    icon: Banknote,
    color: "bg-blue-50 border-blue-200 text-blue-700",
    iconColor: "text-blue-500",
    path: "/modules/cajeros",
  },
  {
    code: "clientes",
    name: "Clientes",
    description: "Gestión de personas físicas y jurídicas",
    icon: Users,
    color: "bg-green-50 border-green-200 text-green-700",
    iconColor: "text-green-500",
    path: "/modules/clientes",
  },
  {
    code: "interbanking",
    name: "Interbanking",
    description: "Cuentas, saldos y transferencias via Interbanking Argentina",
    icon: Building,
    color: "bg-indigo-50 border-indigo-200 text-indigo-700",
    iconColor: "text-indigo-500",
    path: "/modules/interbanking",
  },
  {
    code: "conciliacion",
    name: "Conciliación",
    description: "Conciliación de pagos y transferencias bancarias",
    icon: Scale,
    color: "bg-teal-50 border-teal-200 text-teal-700",
    iconColor: "text-teal-500",
    path: "/modules/conciliacion",
  },
  {
    code: "liquidaciones",
    name: "Liquidaciones",
    description: "Procesamiento de liquidaciones de juegos",
    icon: Receipt,
    color: "bg-amber-50 border-amber-200 text-amber-700",
    iconColor: "text-amber-500",
    path: "/modules/liquidaciones",
  },
  {
    code: "legacy",
    name: "Legacy",
    description: "Integración con el sistema legacy (VFP9) — interacciones IN/OUT",
    icon: Database,
    color: "bg-slate-50 border-slate-200 text-slate-700",
    iconColor: "text-slate-500",
    path: "/modules/legacy",
  },
];

export default function DashboardPage() {
  const navigate = useNavigate();
  const permissions = useAuthStore((s) => s.permissions);
  const enabledModules = permissions?.modules ?? [];

  const visibleModules = ALL_MODULES.filter((m) => enabledModules.includes(m.code));

  return (
    <Layout>
      <div className="max-w-4xl mx-auto">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 mb-2">Dashboard</h1>
        <p className="text-gray-500 mb-8">Selecciona un módulo para comenzar</p>

        {visibleModules.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <p>No tienes módulos habilitados.</p>
            <p className="text-sm mt-1">Contacta al administrador del sistema.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {visibleModules.map((mod) => (
              <button
                key={mod.code}
                onClick={() => navigate(mod.path)}
                className={clsx(
                  "border rounded-2xl p-6 text-left hover:shadow-md transition-shadow cursor-pointer",
                  mod.color
                )}
              >
                <div className={clsx("mb-4", mod.iconColor)}>
                  <mod.icon size={32} />
                </div>
                <h3 className="font-semibold text-lg mb-1">{mod.name}</h3>
                <p className="text-sm opacity-70">{mod.description}</p>
              </button>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
}
