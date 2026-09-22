import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { Layout } from "../../components/Layout";
import { CreditosSidebar } from "./Sidebar";
import { RUTAS, primeraRuta } from "./rutas";
import { usePuedeVer } from "./permisos";

/**
 * Módulo Créditos (CCyPP). El backend corre en su propio contenedor (creditos:8010) detrás del
 * gateway; acá vive sólo el frontend, con el Layout y la sesión del sistema. El acceso se gatea con
 * los permisos creditos:read / creditos:write que administra Seguridad.
 */
function SinAcceso() {
  return (
    <div className="bg-surface border border-gray-200 rounded-xl p-8 text-center">
      <p className="text-gray-800 font-medium">Sin acceso al módulo de Créditos</p>
      <p className="text-sm text-gray-500 mt-1">Pedí en Seguridad el permiso <code className="text-xs">creditos:read</code>.</p>
    </div>
  );
}

function NoEncontrada() {
  const { pathname } = useLocation();
  return (
    <div className="bg-surface border border-gray-200 rounded-xl p-8 text-center">
      <p className="text-gray-800 font-medium">Pantalla en migración</p>
      <p className="text-sm text-gray-500 mt-1">
        <code className="text-xs">{pathname}</code> todavía no está disponible en el frontend del sistema.
      </p>
    </div>
  );
}

export default function CreditosModule() {
  const puedeVer = usePuedeVer();
  const sidebar = (onClose) => <CreditosSidebar onClose={onClose} />;
  const inicio = primeraRuta();

  return (
    <Layout sidebar={sidebar}>
      {puedeVer ? (
        <Routes>
          <Route path="/" element={inicio ? <Navigate to={inicio} replace /> : <NoEncontrada />} />
          {Object.entries(RUTAS).map(([ruta, Pantalla]) => (
            <Route key={ruta} path={ruta} element={<Pantalla />} />
          ))}
          <Route path="*" element={<NoEncontrada />} />
        </Routes>
      ) : <SinAcceso />}
    </Layout>
  );
}
