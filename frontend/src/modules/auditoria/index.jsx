import { Routes, Route, Navigate } from "react-router-dom";
import { ClipboardList } from "lucide-react";
import { Layout } from "../../components/Layout";
import { Sidebar } from "../../components/Sidebar";
import EventosPage from "./pages/EventosPage";

export const auditoriaMenu = [
  { label: "Registro de actividad", path: "/modules/auditoria/eventos", permission: "eventos:read", icon: ClipboardList },
];

export default function AuditoriaModule() {
  const sidebar = (onClose) => <Sidebar menuItems={auditoriaMenu} moduleCode="auditoria" onClose={onClose} />;
  return (
    <Layout sidebar={sidebar}>
      <Routes>
        <Route path="/" element={<Navigate to="eventos" replace />} />
        <Route path="eventos" element={<EventosPage />} />
        <Route path="*" element={<Navigate to="/modules/auditoria" replace />} />
      </Routes>
    </Layout>
  );
}
