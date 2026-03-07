import { Routes, Route, Navigate } from "react-router-dom";
import { FileText, CheckCircle, Clock, Banknote } from "lucide-react";
import { Layout } from "../../components/Layout";
import { Sidebar } from "../../components/Sidebar";
import SolicitudesPage from "./pages/SolicitudesPage";
import AutorizacionesPage from "./pages/AutorizacionesPage";
import LimitesPage from "./pages/LimitesPage";
import OperacionesPage from "./pages/OperacionesPage";

export const cajerosMenu = [
  { label: "Mis Solicitudes", path: "/modules/cajeros/solicitudes", permission: "requests:read", icon: FileText },
  { label: "Autorizaciones", path: "/modules/cajeros/autorizaciones", permission: "requests:authorize", icon: CheckCircle },
  { label: "Límites", path: "/modules/cajeros/limites", permission: "limits:read", icon: Banknote },
  { label: "Operaciones", path: "/modules/cajeros/operaciones", permission: "operations:read", icon: Clock },
];

export default function CajerosModule() {
  const sidebar = <Sidebar menuItems={cajerosMenu} moduleCode="cajeros" />;

  return (
    <Layout sidebar={sidebar}>
      <Routes>
        <Route path="/" element={<Navigate to="solicitudes" replace />} />
        <Route path="solicitudes" element={<SolicitudesPage />} />
        <Route path="autorizaciones" element={<AutorizacionesPage />} />
        <Route path="limites" element={<LimitesPage />} />
        <Route path="operaciones" element={<OperacionesPage />} />
      </Routes>
    </Layout>
  );
}
