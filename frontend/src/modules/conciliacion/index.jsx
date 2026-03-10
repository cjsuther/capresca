import { Routes, Route, Navigate } from "react-router-dom";
import { Scale } from "lucide-react";
import { Layout } from "../../components/Layout";
import { Sidebar } from "../../components/Sidebar";
import ConciliacionPage from "./pages/ConciliacionPage";

export const conciliacionMenu = [
  { label: "Conciliación", path: "/modules/conciliacion/conciliacion", permission: "conciliacion:read", icon: Scale },
];

export default function ConciliacionModule() {
  const sidebar = (onClose) => <Sidebar menuItems={conciliacionMenu} moduleCode="conciliacion" onClose={onClose} />;
  return (
    <Layout sidebar={sidebar}>
      <Routes>
        <Route path="/" element={<Navigate to="conciliacion" replace />} />
        <Route path="conciliacion" element={<ConciliacionPage />} />
      </Routes>
    </Layout>
  );
}
