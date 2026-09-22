import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ClientesListPage from "./ClientesListPage";
import { getClients } from "../../../api/clientes";

vi.mock("../../../api/clientes", () => ({ getClients: vi.fn() }));

const HUMANO = {
  id: 1,
  code: "CLI-0001",
  client_type: "HUMAN",
  email: "ana@correo.com",
  city: "Neuquén",
  is_active: true,
  human_profile: { first_name: "Ana", last_name: "Pérez" },
};

const JURIDICO = {
  id: 2,
  code: "CLI-0002",
  client_type: "LEGAL",
  email: null,
  city: null,
  is_active: false,
  legal_profile: { legal_name: "Agencia Sur SRL", agency_number: "000042" },
};

function montar() {
  return render(
    <MemoryRouter initialEntries={["/modules/clientes/lista"]}>
      <Routes>
        <Route path="/modules/clientes/lista" element={<ClientesListPage />} />
        <Route path="/modules/clientes/:id" element={<p>detalle del cliente</p>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("ClientesListPage", () => {
  beforeEach(() => {
    getClients.mockResolvedValue({ data: [HUMANO, JURIDICO], total: 2 });
  });

  it("muestra el cartel de carga antes de la primera respuesta", async () => {
    let resolver;
    getClients.mockReturnValueOnce(new Promise((r) => { resolver = r; }));
    montar();

    expect(screen.getByText("Cargando...")).toBeInTheDocument();
    resolver({ data: [], total: 0 });
    await waitFor(() => expect(screen.getByText("Sin resultados")).toBeInTheDocument());
  });

  it("pide el listado al montar, sin filtros", async () => {
    montar();
    await waitFor(() => expect(getClients).toHaveBeenCalledTimes(1));
    expect(getClients).toHaveBeenCalledWith({ search: "", client_type: "" });
  });

  it("muestra el total de registros y una fila por cliente", async () => {
    montar();
    expect(await screen.findByText("Ana Pérez")).toBeInTheDocument();
    expect(screen.getByText("2 registros")).toBeInTheDocument();
    expect(screen.getByText("CLI-0001")).toBeInTheDocument();
    expect(screen.getByText("Agencia Sur SRL")).toBeInTheDocument();
    expect(screen.getByText("000042")).toBeInTheDocument();
  });

  it("marca el estado activo/inactivo de cada cliente", async () => {
    montar();
    expect(await screen.findByText("Activo")).toBeInTheDocument();
    expect(screen.getByText("Inactivo")).toBeInTheDocument();
  });

  it("reemplaza por guión los datos faltantes de la persona jurídica", async () => {
    montar();
    const fila = (await screen.findByText("Agencia Sur SRL")).closest("tr");
    // email y ciudad vienen en null
    expect(within(fila).getAllByText("—")).toHaveLength(2);
  });

  it("muestra guión cuando el cliente no trae ningún perfil", async () => {
    getClients.mockResolvedValue({
      data: [{ id: 9, code: "CLI-0009", client_type: "LEGAL", is_active: true }],
      total: 1,
    });
    montar();
    const fila = (await screen.findByText("CLI-0009")).closest("tr");
    expect(within(fila).getAllByText("—").length).toBeGreaterThan(0);
  });

  it("avisa cuando no hay resultados", async () => {
    getClients.mockResolvedValue({ data: [], total: 0 });
    montar();
    expect(await screen.findByText("Sin resultados")).toBeInTheDocument();
    expect(screen.getByText("0 registros")).toBeInTheDocument();
  });

  it("busca por texto y por tipo al enviar el formulario", async () => {
    const user = userEvent.setup();
    montar();
    await screen.findByText("Ana Pérez");

    await user.type(screen.getByPlaceholderText("Buscar por nombre, documento, email..."), "perez");
    await user.selectOptions(screen.getByRole("combobox"), "HUMAN");
    await user.click(screen.getByRole("button", { name: "Buscar" }));

    await waitFor(() =>
      expect(getClients).toHaveBeenLastCalledWith({ search: "perez", client_type: "HUMAN" })
    );
  });

  it("al hacer click en una fila navega al detalle del cliente", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByText("Ana Pérez"));
    expect(screen.getByText("detalle del cliente")).toBeInTheDocument();
  });
});
