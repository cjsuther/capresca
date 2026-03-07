import { Routes, Route, Navigate } from "react-router-dom";
import { Shield, Users, Key } from "lucide-react";
import { Layout } from "../../components/Layout";
import { Sidebar } from "../../components/Sidebar";
import UsersPage from "./pages/UsersPage";
import RolesPage from "./pages/RolesPage";

export const securityMenu = [
  { label: "Usuarios", path: "/modules/security/users", permission: "users:read", icon: Users },
  { label: "Roles", path: "/modules/security/roles", permission: "roles:read", icon: Key },
];

export default function SecurityModule() {
  const sidebar = (onClose) => <Sidebar menuItems={securityMenu} moduleCode="security" onClose={onClose} />;

  return (
    <Layout sidebar={sidebar}>
      <Routes>
        <Route path="/" element={<Navigate to="users" replace />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="roles" element={<RolesPage />} />
      </Routes>
    </Layout>
  );
}
