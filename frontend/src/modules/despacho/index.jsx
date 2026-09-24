import { Routes, Route, Navigate } from "react-router-dom";
import { FileText, Files, ListChecks, FolderOpen, Upload } from "lucide-react";

import { Layout } from "../../components/Layout";
import { Sidebar } from "../../components/Sidebar";
import ModelosPage from "./pages/ModelosPage";
import ResolucionesPage from "./pages/ResolucionesPage";
import AnexoPage from "./pages/AnexoPage";
import ExpedientesPage from "./pages/ExpedientesPage";
import ImportarPage from "./pages/ImportarPage";

export const despachoMenu = [
  { label: "Modelo de resoluciones", path: "/modules/despacho/modelos", permission: "resoluciones:read", icon: FileText },
  { label: "Resoluciones y disposiciones", path: "/modules/despacho/resoluciones", permission: "resoluciones:read", icon: Files },
  { label: "Anexo de resolución", path: "/modules/despacho/anexo", permission: "resoluciones:read", icon: ListChecks },
  { label: "Expedientes y pases", path: "/modules/despacho/expedientes", permission: "resoluciones:read", icon: FolderOpen },
  { label: "Importar del sistema anterior", path: "/modules/despacho/importar", permission: "importar", icon: Upload },
];

export default function DespachoModule() {
  const sidebar = (onClose) => <Sidebar menuItems={despachoMenu} moduleCode="despacho" onClose={onClose} />;

  return (
    <Layout sidebar={sidebar}>
      <Routes>
        <Route path="/" element={<Navigate to="resoluciones" replace />} />
        <Route path="modelos" element={<ModelosPage />} />
        <Route path="resoluciones" element={<ResolucionesPage />} />
        <Route path="anexo" element={<AnexoPage />} />
        <Route path="expedientes" element={<ExpedientesPage />} />
        <Route path="importar" element={<ImportarPage />} />
      </Routes>
    </Layout>
  );
}
