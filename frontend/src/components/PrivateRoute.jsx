import { Navigate } from "react-router-dom";
import { useIsAuthenticated, useHasModule, useHasPermission } from "../context/usePermissions";

export function PrivateRoute({ children }) {
  const isAuth = useIsAuthenticated();
  if (!isAuth) return <Navigate to="/login" replace />;
  return children;
}

export function ModuleRoute({ moduleCode, children }) {
  const isAuth = useIsAuthenticated();
  const hasModule = useHasModule(moduleCode);
  if (!isAuth) return <Navigate to="/login" replace />;
  if (!hasModule) return <Navigate to="/dashboard" replace />;
  return children;
}

export function PermissionGate({ moduleCode, action, children, fallback = null }) {
  const hasPermission = useHasPermission(moduleCode, action);
  return hasPermission ? children : fallback;
}
