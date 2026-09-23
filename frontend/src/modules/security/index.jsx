import { Routes, Route, Navigate } from "react-router-dom";
import { Shield, Users, Key, UsersRound } from "lucide-react";
import { Layout } from "../../components/Layout";
import { Sidebar } from "../../components/Sidebar";
import UsersPage from "./pages/UsersPage";
import RolesPage from "./pages/RolesPage";
import GroupsPage from "./pages/GroupsPage";

export const securityMenu = [
  { label: "Usuarios", path: "/modules/security/users", permission: "users:read", icon: Users },
  { label: "Grupos", path: "/modules/security/groups", permission: "groups:read", icon: UsersRound },
  { label: "Roles", path: "/modules/security/roles", permission: "roles:read", icon: Key },
];

export default function SecurityModule() {
  const sidebar = (onClose) => <Sidebar menuItems={securityMenu} moduleCode="security" onClose={onClose} />;

  return (
    <Layout sidebar={sidebar}>
      <Routes>
        <Route path="/" element={<Navigate to="users" replace />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="groups" element={<GroupsPage />} />
        <Route path="roles" element={<RolesPage />} />
      </Routes>
    </Layout>
  );
}
