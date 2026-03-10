import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import { PrivateRoute, ModuleRoute } from "./components/PrivateRoute";
import SecurityModule from "./modules/security";
import CajerosModule from "./modules/cajeros";
import ClientesModule from "./modules/clientes";
import InterbankingModule from "./modules/interbanking";
import ConciliacionModule from "./modules/conciliacion";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route
          path="/dashboard"
          element={
            <PrivateRoute>
              <DashboardPage />
            </PrivateRoute>
          }
        />

        <Route
          path="/modules/security/*"
          element={
            <ModuleRoute moduleCode="security">
              <SecurityModule />
            </ModuleRoute>
          }
        />

        <Route
          path="/modules/cajeros/*"
          element={
            <ModuleRoute moduleCode="cajeros">
              <CajerosModule />
            </ModuleRoute>
          }
        />

        <Route
          path="/modules/clientes/*"
          element={
            <ModuleRoute moduleCode="clientes">
              <ClientesModule />
            </ModuleRoute>
          }
        />

        <Route
          path="/modules/interbanking/*"
          element={
            <ModuleRoute moduleCode="interbanking">
              <InterbankingModule />
            </ModuleRoute>
          }
        />

        <Route
          path="/modules/conciliacion/*"
          element={
            <ModuleRoute moduleCode="conciliacion">
              <ConciliacionModule />
            </ModuleRoute>
          }
        />

        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
