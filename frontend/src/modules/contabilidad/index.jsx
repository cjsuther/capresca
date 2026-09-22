import { Routes, Route, Navigate } from "react-router-dom";
import { BookOpen, ListTree, Library, Scale, Settings2 } from "lucide-react";
import { Layout } from "../../components/Layout";
import { Sidebar } from "../../components/Sidebar";
import TransaccionesPage from "./pages/TransaccionesPage";
import LibrosPage from "./pages/LibrosPage";
import PlanCuentasPage from "./pages/PlanCuentasPage";
import ConciliacionPage from "./pages/ConciliacionPage";
import DefinicionesPage from "./pages/DefinicionesPage";

export const contabilidadMenu = [
  { label: "Transacciones", path: "/modules/contabilidad/transacciones", permission: "asientos:read", icon: ListTree },
  { label: "Definiciones de asiento", path: "/modules/contabilidad/definiciones", permission: "asientos:read", icon: Settings2 },
  { label: "Libros y estados", path: "/modules/contabilidad/libros", permission: "asientos:read", icon: BookOpen },
  { label: "Conciliación bancaria", path: "/modules/contabilidad/conciliacion", permission: "asientos:read", icon: Scale },
  { label: "Plan de cuentas", path: "/modules/contabilidad/plan", permission: "asientos:read", icon: Library },
];

export default function ContabilidadModule() {
  const sidebar = (onClose) => <Sidebar menuItems={contabilidadMenu} moduleCode="contabilidad" onClose={onClose} />;
  return (
    <Layout sidebar={sidebar}>
      <Routes>
        <Route path="/" element={<Navigate to="transacciones" replace />} />
        <Route path="transacciones" element={<TransaccionesPage />} />
        <Route path="definiciones" element={<DefinicionesPage />} />
        <Route path="libros" element={<LibrosPage />} />
        <Route path="conciliacion" element={<ConciliacionPage />} />
        <Route path="plan" element={<PlanCuentasPage />} />
        <Route path="*" element={<Navigate to="/modules/contabilidad" replace />} />
      </Routes>
    </Layout>
  );
}
