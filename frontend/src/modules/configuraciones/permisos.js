import { useHasPermission } from "../../context/usePermissions";

// Cada catálogo tiene su par de permisos en Seguridad: `configuraciones:<catalogo>:read|write`.
export const usePuedeEditar = (catalogo) => useHasPermission("configuraciones", `${catalogo}:write`);
