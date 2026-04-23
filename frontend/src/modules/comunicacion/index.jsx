import { Routes, Route, Navigate } from "react-router-dom";
import { MessageCircle, Settings } from "lucide-react";
import { Layout } from "../../components/Layout";
import { Sidebar } from "../../components/Sidebar";
import ComunicacionPage from "./pages/ComunicacionPage";
import ConfigMenuPage from "./pages/ConfigMenuPage";

export const comunicacionMenu = [
  { label: "Conversaciones", path: "/modules/comunicacion/chat", permission: "chat:read", icon: MessageCircle },
  { label: "Configuración", path: "/modules/comunicacion/config", permission: "chat:config:read", icon: Settings },
];

export default function ComunicacionModule() {
  const sidebar = (onClose) => <Sidebar menuItems={comunicacionMenu} moduleCode="comunicacion" onClose={onClose} />;
  return (
    <Layout sidebar={sidebar}>
      <Routes>
        <Route path="/" element={<Navigate to="chat" replace />} />
        <Route path="chat" element={<ComunicacionPage />} />
        <Route path="config" element={<ConfigMenuPage />} />
      </Routes>
    </Layout>
  );
}
