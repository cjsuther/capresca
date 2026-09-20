import { createContext, useContext, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { api, getToken } from "./api";
import { MENU, items as itemsDe } from "./menu";

// RBAC en el front: gatea menú, rutas y acciones según los permisos del usuario en Portezuelo.
// Los permisos son POR ÁREA (Seguridad de Portezuelo → módulo Créditos): `<area>:read` = CONSULTA,
// `<area>:write` = ESCRITURA. El área de una pantalla es el primer segmento de su ruta.
const ORDEN: Record<string, number> = { NINGUNO: 0, CONSULTA: 1, ESCRITURA: 2, TOTAL: 3 };
const ALIAS_AREA: Record<string, string> = { "controles-version": "seguridad" };

type Estado = { areas: Record<string, string>; roles: string[]; cargado: boolean };
type Ctx = {
  estado: Estado; nivel: (r: string) => string; puedeVer: (r: string) => boolean; puedeEscribir: (r: string) => boolean;
  esAdmin: boolean; recargar: () => void;
};

const PermisosCtx = createContext<Ctx>({
  estado: { areas: {}, roles: [], cargado: false },
  nivel: () => "NINGUNO", puedeVer: () => false, puedeEscribir: () => false, esAdmin: false, recargar: () => {},
});

export function areaDeRuta(ruta: string): string {
  const seg = ruta.replace(/^\/+/, "").split("/")[0];
  return ALIAS_AREA[seg] || seg;
}

// Caché por token: evita re-fetch en cada navegación (Layout se remonta por ruta).
let _cache: Estado | null = null;
let _cacheToken = "";

export function PermisosProvider({ children }: { children: React.ReactNode }) {
  const [estado, setEstado] = useState<Estado>(_cache ?? { areas: {}, roles: [], cargado: false });

  function recargar() {
    const tok = getToken() || "";
    if (!tok) { setEstado({ areas: {}, roles: [], cargado: true }); return; }
    if (_cacheToken === tok && _cache) { setEstado(_cache); return; }
    api.misPermisos()
      .then((d: any) => { _cache = { areas: d.areas || {}, roles: d.roles || [], cargado: true }; _cacheToken = tok; setEstado(_cache); })
      .catch(() => setEstado((e) => ({ ...e, cargado: true })));
  }
  useEffect(() => { recargar(); }, []);

  const nivel = (ruta: string) => estado.areas[areaDeRuta(ruta)] || "NINGUNO";
  const puedeVer = (ruta: string) => ORDEN[nivel(ruta)] >= 1;
  const puedeEscribir = (ruta: string) => ORDEN[nivel(ruta)] >= 2;
  // Administrador del módulo = escritura sobre Seguridad (configura workflow, ve la vista completa del menú).
  const esAdmin = estado.areas["seguridad"] === "ESCRITURA";
  return <PermisosCtx.Provider value={{ estado, nivel, puedeVer, puedeEscribir, esAdmin, recargar }}>{children}</PermisosCtx.Provider>;
}

export const usePermisos = () => useContext(PermisosCtx);

// Nivel del usuario sobre la PANTALLA actual. `soloLectura` = tiene acceso pero no ESCRITURA
// (para ocultar/deshabilitar botones de alta/edición/baja). No aplica durante la carga.
export function useNivelActual() {
  const { pathname } = useLocation();
  const { nivel, puedeEscribir, estado } = usePermisos();
  const ruta = rutaMenuDe(pathname);
  return {
    ruta,
    nivel: ruta ? nivel(ruta) : "TOTAL",
    soloLectura: !!ruta && estado.cargado && !puedeEscribir(ruta),
  };
}

// Ruta del menú que corresponde a un pathname (la más específica que sea prefijo).
export function rutaMenuDe(pathname: string): string | null {
  let mejor: string | null = null;
  for (const m of MENU) for (const i of itemsDe(m)) {
    if (pathname === i.to || pathname.startsWith(i.to + "/")) {
      if (!mejor || i.to.length > mejor.length) mejor = i.to;
    }
  }
  return mejor;
}
