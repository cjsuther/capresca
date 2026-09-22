import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { BuscadorCliente, nombreCliente } from "./BuscadorCliente";
import { searchClients } from "../../../api/clientes";

vi.mock("../../../api/clientes", () => ({ searchClients: vi.fn() }));

const PERSONA = { id: 7, code: "PH-7", human_profile: { first_name: "Ana", last_name: "Perez", document_number: "30123456" } };
const EMPRESA = { id: 8, code: "PJ-8", legal_profile: { legal_name: "Agencia 113 SRL", tax_id: "30-1-1" } };

beforeEach(() => {
  vi.clearAllMocks();
  searchClients.mockResolvedValue({ data: [PERSONA, EMPRESA] });
});

describe("BuscadorCliente (padrón del sistema)", () => {
  it("busca en el padrón y devuelve el cliente elegido", async () => {
    const onSelect = vi.fn();
    const u = userEvent.setup();
    render(<BuscadorCliente onSelect={onSelect} />);

    await u.type(screen.getByPlaceholderText(/Buscar cliente/), "pere");
    await waitFor(() => expect(searchClients).toHaveBeenCalledWith("pere"));
    await u.click(await screen.findByText(/Perez, Ana/));
    expect(onSelect).toHaveBeenCalledWith(PERSONA);
  });

  it("no consulta con menos de dos caracteres", async () => {
    const u = userEvent.setup();
    render(<BuscadorCliente onSelect={vi.fn()} />);
    await u.type(screen.getByPlaceholderText(/Buscar cliente/), "p");
    await new Promise((r) => setTimeout(r, 350));
    expect(searchClients).not.toHaveBeenCalled();
  });

  it("muestra el cliente elegido y deja cambiarlo", async () => {
    const onSelect = vi.fn();
    const u = userEvent.setup();
    render(<BuscadorCliente onSelect={onSelect} seleccionado={PERSONA} />);

    expect(screen.getByText("Perez, Ana")).toBeInTheDocument();
    expect(screen.getByText("· 30123456")).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: "Cambiar cliente" }));
    expect(onSelect).toHaveBeenCalledWith(null);
  });

  it("si el padrón no responde lo dice", async () => {
    searchClients.mockRejectedValue({ response: { data: { detail: "Sin permisos sobre clientes" } } });
    const u = userEvent.setup();
    render(<BuscadorCliente onSelect={vi.fn()} />);
    await u.type(screen.getByPlaceholderText(/Buscar cliente/), "pere");
    expect(await screen.findByText("Sin permisos sobre clientes")).toBeInTheDocument();
  });

  it("nombreCliente resuelve personas físicas y jurídicas", () => {
    expect(nombreCliente(PERSONA)).toBe("Perez, Ana");
    expect(nombreCliente(EMPRESA)).toBe("Agencia 113 SRL");
    expect(nombreCliente(null)).toBe("");
  });
});
