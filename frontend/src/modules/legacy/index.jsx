import { Routes, Route, Navigate } from "react-router-dom";
import { Database, Activity } from "lucide-react";
import { Layout } from "../../components/Layout";
import { Sidebar } from "../../components/Sidebar";
import InteraccionesPage from "./pages/InteraccionesPage";
import EstadoPage from "./pages/EstadoPage";

export const legacyMenu = [
  { label: "Interacciones", path: "/modules/legacy/interacciones", permission: "interactions:read", icon: Database },
  { label: "Estado", path: "/modules/legacy/estado", permission: "interactions:read", icon: Activity },
];

export default function LegacyModule() {
  const sidebar = (onClose) => <Sidebar menuItems={legacyMenu} moduleCode="legacy" onClose={onClose} />;
  return (
    <Layout sidebar={sidebar}>
      <Routes>
        <Route path="/" element={<Navigate to="interacciones" replace />} />
        <Route path="interacciones" element={<InteraccionesPage />} />
        <Route path="estado" element={<EstadoPage />} />
      </Routes>
    </Layout>
  );
}
