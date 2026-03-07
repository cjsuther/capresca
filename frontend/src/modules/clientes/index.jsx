import { Routes, Route, Navigate } from "react-router-dom";
import { Users, UserPlus, Building2 } from "lucide-react";
import { Layout } from "../../components/Layout";
import { Sidebar } from "../../components/Sidebar";
import ClientesListPage from "./pages/ClientesListPage";
import ClienteDetailPage from "./pages/ClienteDetailPage";
import NuevoClientePage from "./pages/NuevoClientePage";

export const clientesMenu = [
  { label: "Todos los clientes", path: "/modules/clientes/lista", permission: "clients:read", icon: Users },
  { label: "Nueva Persona Física", path: "/modules/clientes/nuevo/humano", permission: "clients:write", icon: UserPlus },
  { label: "Nueva Persona Jurídica", path: "/modules/clientes/nuevo/juridico", permission: "clients:write", icon: Building2 },
];

export default function ClientesModule() {
  const sidebar = (onClose) => <Sidebar menuItems={clientesMenu} moduleCode="clientes" onClose={onClose} />;

  return (
    <Layout sidebar={sidebar}>
      <Routes>
        <Route path="/" element={<Navigate to="lista" replace />} />
        <Route path="lista" element={<ClientesListPage />} />
        <Route path="nuevo/:type" element={<NuevoClientePage />} />
        <Route path=":id" element={<ClienteDetailPage />} />
      </Routes>
    </Layout>
  );
}
