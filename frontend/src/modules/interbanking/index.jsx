import { Routes, Route, Navigate } from "react-router-dom";
import { CreditCard, ArrowLeftRight, ClipboardList, Settings } from "lucide-react";
import { Layout } from "../../components/Layout";
import { Sidebar } from "../../components/Sidebar";
import CuentasPage from "./pages/CuentasPage";
import TransferenciasPage from "./pages/TransferenciasPage";
import AuditoriaPage from "./pages/AuditoriaPage";
import ConfigPage from "./pages/ConfigPage";

export const interbankingMenu = [
  { label: "Cuentas",         path: "/modules/interbanking/cuentas",        permission: "cuentas:read",         icon: CreditCard },
  { label: "Transferencias",  path: "/modules/interbanking/transferencias",  permission: "transferencias:read",  icon: ArrowLeftRight },
  { label: "Auditoría",       path: "/modules/interbanking/auditoria",       permission: "auditoria:read",       icon: ClipboardList },
  { label: "Configuración",   path: "/modules/interbanking/config",          permission: "config:read",          icon: Settings },
];

export default function InterbankingModule() {
  const sidebar = (onClose) => <Sidebar menuItems={interbankingMenu} moduleCode="interbanking" onClose={onClose} />;

  return (
    <Layout sidebar={sidebar}>
      <Routes>
        <Route path="/" element={<Navigate to="cuentas" replace />} />
        <Route path="cuentas" element={<CuentasPage />} />
        <Route path="transferencias" element={<TransferenciasPage />} />
        <Route path="auditoria" element={<AuditoriaPage />} />
        <Route path="config" element={<ConfigPage />} />
      </Routes>
    </Layout>
  );
}
