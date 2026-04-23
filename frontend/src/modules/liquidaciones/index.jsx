import { Routes, Route, Navigate } from "react-router-dom";
import { Receipt } from "lucide-react";
import { Layout } from "../../components/Layout";
import { Sidebar } from "../../components/Sidebar";
import LiquidacionesPage from "./pages/LiquidacionesPage";

export const liquidacionesMenu = [
  { label: "Liquidaciones", path: "/modules/liquidaciones/liquidaciones", permission: "liq:read", icon: Receipt },
];

export default function LiquidacionesModule() {
  const sidebar = (onClose) => <Sidebar menuItems={liquidacionesMenu} moduleCode="liquidaciones" onClose={onClose} />;
  return (
    <Layout sidebar={sidebar}>
      <Routes>
        <Route path="/" element={<Navigate to="liquidaciones" replace />} />
        <Route path="liquidaciones" element={<LiquidacionesPage />} />
      </Routes>
    </Layout>
  );
}
