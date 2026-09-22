import { Routes, Route, Navigate } from "react-router-dom";
import { Percent, TrendingUp, CalendarDays, GitBranch } from "lucide-react";
import { Layout } from "../../components/Layout";
import { Sidebar } from "../../components/Sidebar";
import { useHasPermission } from "../../context/usePermissions";
import { useAuthStore } from "../../context/authStore";
import ImpuestosPage from "./pages/ImpuestosPage";
import IndicesPage from "./pages/IndicesPage";
import FeriadosPage from "./pages/FeriadosPage";
import WorkflowPage from "./pages/WorkflowPage";

export const configuracionesMenu = [
  { label: "Impuestos", path: "/modules/configuraciones/impuestos", permission: "impuestos:read", icon: Percent },
  { label: "Índices de referencia", path: "/modules/configuraciones/indices", permission: "indices:read", icon: TrendingUp },
  { label: "Feriados", path: "/modules/configuraciones/feriados", permission: "feriados:read", icon: CalendarDays },
  { label: "Workflow de aprobaciones", path: "/modules/configuraciones/workflow", permission: "workflow:read", icon: GitBranch },
];

const PANTALLAS = [
  ["impuestos", ImpuestosPage], ["indices", IndicesPage], ["feriados", FeriadosPage], ["workflow", WorkflowPage],
];

/** Pantalla protegida por el permiso de lectura de su catálogo. */
function ConPermiso({ catalogo, children }) {
  const puede = useHasPermission("configuraciones", `${catalogo}:read`);
  return puede ? children : <Navigate to="/modules/configuraciones" replace />;
}

/** Primera pantalla que el usuario puede ver (el módulo se habilita con cualquiera de los permisos). */
const SIN_ACCIONES = [];   // referencia estable: un [] nuevo por render re-dispararía el store

function Inicio() {
  const acciones = useAuthStore((s) => s.permissions?.actions?.configuraciones ?? SIN_ACCIONES);
  const primera = PANTALLAS.map(([c]) => c).find((c) => acciones.includes(`${c}:read`));
  return primera ? <Navigate to={primera} replace /> : <Navigate to="/dashboard" replace />;
}

export default function ConfiguracionesModule() {
  const sidebar = (onClose) => (
    <Sidebar menuItems={configuracionesMenu} moduleCode="configuraciones" onClose={onClose} />
  );
  return (
    <Layout sidebar={sidebar}>
      <Routes>
        <Route path="/" element={<Inicio />} />
        {PANTALLAS.map(([catalogo, Pantalla]) => (
          <Route key={catalogo} path={catalogo}
                 element={<ConPermiso catalogo={catalogo}><Pantalla /></ConPermiso>} />
        ))}
        <Route path="*" element={<Navigate to="/modules/configuraciones" replace />} />
      </Routes>
    </Layout>
  );
}
