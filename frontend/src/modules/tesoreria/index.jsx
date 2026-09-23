import { Routes, Route, Navigate } from "react-router-dom";
import { Layers, FilePlus2 } from "lucide-react";
import { Layout } from "../../components/Layout";
import { Sidebar } from "../../components/Sidebar";
import { useHasPermission } from "../../context/usePermissions";
import LotesPage from "./pages/LotesPage";
import LotePage from "./pages/LotePage";
import NuevoLotePage from "./pages/NuevoLotePage";

export const tesoreriaMenu = [
  { label: "Lotes de pagos", path: "/modules/tesoreria/lotes", permission: "lotes:read", icon: Layers },
  { label: "Nuevo lote manual", path: "/modules/tesoreria/nuevo", permission: "lotes:write", icon: FilePlus2 },
];

function ConPermiso({ accion, children }) {
  return useHasPermission("tesoreria", accion) ? children : <Navigate to="/dashboard" replace />;
}

export default function TesoreriaModule() {
  const sidebar = (onClose) => <Sidebar menuItems={tesoreriaMenu} moduleCode="tesoreria" onClose={onClose} />;
  return (
    <Layout sidebar={sidebar}>
      <Routes>
        <Route path="/" element={<Navigate to="lotes" replace />} />
        <Route path="lotes" element={<ConPermiso accion="lotes:read"><LotesPage /></ConPermiso>} />
        <Route path="lotes/:id" element={<ConPermiso accion="lotes:read"><LotePage /></ConPermiso>} />
        <Route path="nuevo" element={<ConPermiso accion="lotes:write"><NuevoLotePage /></ConPermiso>} />
        <Route path="*" element={<Navigate to="/modules/tesoreria" replace />} />
      </Routes>
    </Layout>
  );
}
