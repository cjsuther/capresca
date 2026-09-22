import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

// El Layout real trae topbar, campana de notificaciones y modal de contraseña: acá sólo
// interesa el ruteo del módulo y el sidebar, así que se reemplaza por un contenedor mínimo
// que igual ejercita el render prop del sidebar.
vi.mock("../../components/Layout", () => ({
  Layout: ({ children, sidebar }) => (
    <div>
      <div data-testid="sidebar">{typeof sidebar === "function" ? sidebar(undefined) : sidebar}</div>
      <main>{children}</main>
    </div>
  ),
}));

vi.mock("./pages/TransactionsPage", () => ({ default: () => <p>pantalla de transacciones</p> }));
vi.mock("./pages/NewTransactionPage", () => ({ default: () => <p>pantalla de alta</p> }));
vi.mock("./pages/RulesPage", () => ({ default: () => <p>pantalla de reglas</p> }));

import CajerosModule, { cajerosMenu } from "./index";
import { useAuthStore } from "../../context/authStore";

const sesion = (acciones = []) =>
  useAuthStore.setState({
    token: "tok",
    user: { id: 1, username: "ana" },
    permissions: { modules: ["cajeros"], actions: { cajeros: acciones } },
  });

function montar(ruta) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/modules/cajeros/*" element={<CajerosModule />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("cajerosMenu", () => {
  it("declara las tres entradas con su permiso y su ruta", () => {
    expect(cajerosMenu.map((i) => [i.label, i.path, i.permission])).toEqual([
      ["Transacciones", "/modules/cajeros/transactions", "transactions:read"],
      ["Nueva Transacción", "/modules/cajeros/transactions/new", "transactions:write"],
      ["Adm. Autorizaciones", "/modules/cajeros/rules", "rules:read"],
    ]);
    cajerosMenu.forEach((item) => expect(item.icon).toBeTypeOf("object"));
  });
});

describe("CajerosModule — ruteo", () => {
  beforeEach(() => sesion(["transactions:read", "transactions:write", "rules:read"]));

  it("la raíz del módulo redirige al listado de transacciones", () => {
    montar("/modules/cajeros");
    expect(screen.getByText("pantalla de transacciones")).toBeInTheDocument();
  });

  it("/transactions muestra el listado", () => {
    montar("/modules/cajeros/transactions");
    expect(screen.getByText("pantalla de transacciones")).toBeInTheDocument();
  });

  it("/transactions/new muestra el alta", () => {
    montar("/modules/cajeros/transactions/new");
    expect(screen.getByText("pantalla de alta")).toBeInTheDocument();
    expect(screen.queryByText("pantalla de transacciones")).not.toBeInTheDocument();
  });

  it("/transactions/:id reusa el listado (abre el detalle por URL)", () => {
    montar("/modules/cajeros/transactions/42");
    expect(screen.getByText("pantalla de transacciones")).toBeInTheDocument();
  });

  it("/rules muestra la administración de autorizaciones", () => {
    montar("/modules/cajeros/rules");
    expect(screen.getByText("pantalla de reglas")).toBeInTheDocument();
  });

  it("una ruta inexistente del módulo no renderiza ninguna pantalla", () => {
    montar("/modules/cajeros/no-existe");
    expect(screen.queryByText("pantalla de transacciones")).not.toBeInTheDocument();
    expect(screen.queryByText("pantalla de reglas")).not.toBeInTheDocument();
    // el chrome del módulo (sidebar) sigue presente
    expect(screen.getByTestId("sidebar")).toBeInTheDocument();
  });
});

describe("CajerosModule — sidebar por permisos", () => {
  it("con todos los permisos se ven las tres opciones", () => {
    sesion(["transactions:read", "transactions:write", "rules:read"]);
    montar("/modules/cajeros/transactions");
    expect(screen.getByText("Transacciones")).toBeInTheDocument();
    expect(screen.getByText("Nueva Transacción")).toBeInTheDocument();
    expect(screen.getByText("Adm. Autorizaciones")).toBeInTheDocument();
  });

  it("un cajero de sólo lectura no ve alta ni administración", () => {
    sesion(["transactions:read"]);
    montar("/modules/cajeros/transactions");
    expect(screen.getByText("Transacciones")).toBeInTheDocument();
    expect(screen.queryByText("Nueva Transacción")).not.toBeInTheDocument();
    expect(screen.queryByText("Adm. Autorizaciones")).not.toBeInTheDocument();
  });

  it("sin permisos del módulo el sidebar queda vacío pero la ruta se resuelve igual", () => {
    sesion([]);
    montar("/modules/cajeros/rules");
    expect(screen.queryAllByRole("link")).toHaveLength(0);
    // OJO: el menú se filtra, pero la ruta NO: entrando por URL la pantalla igual se monta.
    expect(screen.getByText("pantalla de reglas")).toBeInTheDocument();
  });
});
