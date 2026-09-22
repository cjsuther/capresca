import { useAuthStore } from "../../context/authStore";

// RBAC del módulo Créditos. Los permisos los administra Seguridad de Portezuelo sobre el módulo
// "creditos": `creditos:read` = CONSULTA, `creditos:write` = ESCRITURA.
const AREA = "creditos";

const acciones = (s) => s.permissions?.actions?.creditos ?? [];

/** Nivel del usuario sobre el módulo: NINGUNO | CONSULTA | ESCRITURA. */
export function useNivel() {
  return useAuthStore((s) => {
    const a = acciones(s);
    if (a.includes(`${AREA}:write`)) return "ESCRITURA";
    if (a.includes(`${AREA}:read`)) return "CONSULTA";
    return "NINGUNO";
  });
}

export const usePuedeVer = () => useNivel() !== "NINGUNO";
export const usePuedeEscribir = () => useNivel() === "ESCRITURA";
/** Sólo lectura: entra pero no opera (para ocultar altas, bajas y ediciones). */
export const useSoloLectura = () => useNivel() === "CONSULTA";

/** Roles del workflow de aprobaciones (permisos sueltos, no del área). */
export const usePuedeAprobar = () => useAuthStore((s) => acciones(s).includes("aprobaciones:aprobar"));
export const usePuedeSupervisar = () => useAuthStore((s) => acciones(s).includes("aprobaciones:supervisar"));
