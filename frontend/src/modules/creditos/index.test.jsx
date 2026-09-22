import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CreditosModule from "./index";
import { useAuthStore } from "../../context/authStore";

// El Layout real arrastra la campana de notificaciones (polling) y duplica el sidebar para mobile;
// acá sólo interesa que el módulo le pase el sidebar y resuelva sus rutas.
vi.mock("../../components/Layout", () => ({
  Layout: ({ children, sidebar }) => (
    <div>
      {typeof sidebar === "function" ? sidebar(undefined) : sidebar}
      <main>{children}</main>
    </div>
  ),
}));

// Las pantallas tienen sus propios tests: acá sólo se prueban menú, ruteo y permisos del módulo.
vi.mock("../../api/creditos", () => ({
  creditos: {
    cuotasMora: vi.fn().mockResolvedValue({ cantidad: 0, total: 0, items: [] }),
    pendientesCobro: vi.fn().mockResolvedValue({ cantidad: 0, total: 0, total_cuota: 0, total_mora: 0, items: [] }),
    envios: vi.fn().mockResolvedValue({ cantidad: 0, total: 0, items: [] }),
    jubiladosResumen: vi.fn().mockResolvedValue({ total: 0, liquidadas: 0, monto_total: 0 }),
    jubiladosPorDepto: vi.fn().mockResolvedValue([]),
    estadisticas: vi.fn().mockResolvedValue({ creditos_activos: 0, capital_otorgado_total: 0, saldo_total: 0, por_linea: [] }),
    ctoTablero: vi.fn().mockResolvedValue({ generadoEn: "2026-03-15", kpis: {
      saldoVigente: 0, activos: 0, capitalColocado: 0, contratos: 0, ticketPromedio: 0, cobrado: 0,
      cuotasPagadas: 0, moraMonto: 0, moraPct: 0, contratosEnMora: 0, recaudadoMes: 0,
      aLiquidarMonto: 0, aLiquidarN: 0, vencen30Monto: 0, vencen30Cuotas: 0,
      tnaPromedioPond: 0, plazoPromedio: 0 },
      porEstado: [], evolucion: [], aging: [], porProducto: [], contratos: [] }),
    verCarteraPdf: vi.fn(),
    verPendientesPdf: vi.fn(),
    descargarEnviosExcel: vi.fn(),
  },
}));

function sesion(acciones) {
  useAuthStore.setState({
    token: "tok", user: { username: "ana", full_name: "Ana Prueba" },
    permissions: { modules: ["creditos"], actions: { creditos: acciones } },
  });
}

const montar = (ruta = "/modules/creditos") =>
  render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/modules/creditos/*" element={<CreditosModule />} />
      </Routes>
    </MemoryRouter>
  );

beforeEach(() => sesion(["creditos:read", "creditos:write"]));

describe("módulo Créditos · menú", () => {
  it("muestra sólo pantallas de créditos, agrupadas", async () => {
    sesion(["creditos:read", "creditos:write", "heredadas:read"]);
    montar();
    expect(await screen.findByText("Consultas")).toBeInTheDocument();
    expect(screen.getByText("Reportes")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Cuotas en mora" })).toHaveAttribute(
      "href", "/modules/creditos/mora");
  });

  it("las pantallas heredadas del sistema viejo quedan ocultas sin su permiso", async () => {
    montar();
    expect(await screen.findByRole("link", { name: "Tablero de cartera" })).toBeInTheDocument();
    ["Cuotas en mora", "Simulador", "Líneas de crédito", "Cuenta corriente"].forEach((t) =>
      expect(screen.queryByRole("link", { name: t })).toBeNull());
    // Las creadas en la migración siguen visibles (las que el menú original marcaba como nuevas).
    ["Solicitudes de crédito", "Configurar Créditos", "Sistema de cálculos", "Liquidación por lote",
     "Caja de créditos", "Resumen de cobros", "Parámetros de créditos"].forEach((t) =>
      expect(screen.getByRole("link", { name: t })).toBeInTheDocument());
  });

  it("entrar por URL a una heredada sin permiso no abre la pantalla", async () => {
    montar("/modules/creditos/mora");
    expect(await screen.findByText("Pantalla heredada del sistema anterior")).toBeInTheDocument();
  });

  it("todas las opciones del menú llevan a una pantalla que existe", async () => {
    montar();
    const links = await screen.findAllByRole("link");
    expect(links.length).toBeGreaterThan(0);
    links.forEach((l) => expect(l).toHaveAttribute("href", expect.stringMatching(/^\/modules\/creditos\/.+/)));
    expect(screen.queryByTitle(/migración/)).toBeNull();     // no quedan opciones muertas
  });

  it("no incluye las otras áreas del CCyPP ni clientes", () => {
    montar();
    ["Caja", "Contabilidad", "Tesorería", "Seguros", "Despacho", "Mesa de Entradas",
     "Juegos / Quiniela", "General", "Seguridad", "Maestro de clientes (ABM)"].forEach((t) =>
      expect(screen.queryByText(t)).toBeNull());
  });
});

describe("módulo Créditos · ruteo y permisos", () => {
  it("la raíz del módulo lleva a su primera pantalla", async () => {
    montar();
    expect(await screen.findByRole("heading", { name: "Tablero de cartera" })).toBeInTheDocument();
  });

  it("entra a una pantalla por su ruta", async () => {
    sesion(["creditos:read", "creditos:write", "heredadas:read"]);
    montar("/modules/creditos/estadisticas");
    expect(await screen.findByRole("heading", { name: "Estadísticas de cartera" })).toBeInTheDocument();
  });

  it("una ruta que no existe avisa en pantalla", async () => {
    montar("/modules/creditos/pantalla-inventada");
    expect(await screen.findByText("Pantalla en migración")).toBeInTheDocument();
  });

  it("sin permiso de lectura no muestra ninguna pantalla", async () => {
    sesion([]);
    montar();
    expect(await screen.findByText("Sin acceso al módulo de Créditos")).toBeInTheDocument();
  });
});
