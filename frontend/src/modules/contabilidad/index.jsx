import { Routes, Route, Navigate } from "react-router-dom";
import { BookOpen, ListTree, Library } from "lucide-react";
import { Layout } from "../../components/Layout";
import { Sidebar } from "../../components/Sidebar";
import TransaccionesPage from "./pages/TransaccionesPage";
import LibrosPage from "./pages/LibrosPage";
import PlanCuentasPage from "./pages/PlanCuentasPage";

export const contabilidadMenu = [
  { label: "Transacciones", path: "/modules/contabilidad/transacciones", permission: "asientos:read", icon: ListTree },
  { label: "Libros y estados", path: "/modules/contabilidad/libros", permission: "asientos:read", icon: BookOpen },
  { label: "Plan de cuentas", path: "/modules/contabilidad/plan", permission: "asientos:read", icon: Library },
];

export default function ContabilidadModule() {
  const sidebar = (onClose) => <Sidebar menuItems={contabilidadMenu} moduleCode="contabilidad" onClose={onClose} />;
  return (
    <Layout sidebar={sidebar}>
      <Routes>
        <Route path="/" element={<Navigate to="transacciones" replace />} />
        <Route path="transacciones" element={<TransaccionesPage />} />
        <Route path="libros" element={<LibrosPage />} />
        <Route path="plan" element={<PlanCuentasPage />} />
        <Route path="*" element={<Navigate to="/modules/contabilidad" replace />} />
      </Routes>
    </Layout>
  );
}
