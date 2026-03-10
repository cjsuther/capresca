import { Routes, Route, Navigate } from "react-router-dom";
import { Receipt, PlusCircle, ShieldCheck } from "lucide-react";
import { Layout } from "../../components/Layout";
import { Sidebar } from "../../components/Sidebar";
import TransactionsPage from "./pages/TransactionsPage";
import NewTransactionPage from "./pages/NewTransactionPage";
import RulesPage from "./pages/RulesPage";

export const cajerosMenu = [
  { label: "Transacciones", path: "/modules/cajeros/transactions", permission: "transactions:read", icon: Receipt },
  { label: "Nueva Transacción", path: "/modules/cajeros/transactions/new", permission: "transactions:write", icon: PlusCircle },
  { label: "Adm. Autorizaciones", path: "/modules/cajeros/rules", permission: "rules:read", icon: ShieldCheck },
];

export default function CajerosModule() {
  const sidebar = (onClose) => <Sidebar menuItems={cajerosMenu} moduleCode="cajeros" onClose={onClose} />;

  return (
    <Layout sidebar={sidebar}>
      <Routes>
        <Route path="/" element={<Navigate to="transactions" replace />} />
        <Route path="transactions" element={<TransactionsPage />} />
        <Route path="transactions/new" element={<NewTransactionPage />} />
        <Route path="transactions/:id" element={<TransactionsPage />} />
        <Route path="rules" element={<RulesPage />} />
      </Routes>
    </Layout>
  );
}
