import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import NuevoClientePage from "./NuevoClientePage";
import { createHumanClient, createLegalClient } from "../../../api/clientes";

vi.mock("../../../api/clientes", () => ({
  createHumanClient: vi.fn(),
  createLegalClient: vi.fn(),
}));

// Los <label> de esta pantalla no están asociados por htmlFor: el control es su hermano.
const campo = (etiqueta) =>
  screen.getByText(etiqueta).parentElement.querySelector("input, select");

const crear = () => screen.getByRole("button", { name: "Crear cliente" });

function montar(tipo = "humano") {
  return render(
    <MemoryRouter initialEntries={[`/modules/clientes/nuevo/${tipo}`]}>
      <Routes>
        <Route path="/modules/clientes/nuevo/:type" element={<NuevoClientePage />} />
        <Route path="/modules/clientes/lista" element={<p>listado de clientes</p>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("NuevoClientePage — persona física", () => {
  beforeEach(() => {
    createHumanClient.mockResolvedValue({ id: 1 });
    createLegalClient.mockResolvedValue({ id: 2 });
  });

  it("muestra el formulario de persona física y no el de empresa", () => {
    montar("humano");
    expect(screen.getByRole("heading", { name: "Nueva Persona Física" })).toBeInTheDocument();
    expect(screen.getByText("Datos personales")).toBeInTheDocument();
    expect(screen.queryByText("Razón social *")).not.toBeInTheDocument();
  });

  it("crea el cliente con datos base + perfil y vuelve al listado", async () => {
    const user = userEvent.setup();
    montar("humano");

    await user.type(campo("Email"), "ana@correo.com");
    await user.type(campo("Teléfono"), "299-555");
    await user.type(campo("Dirección"), "San Martín 100");
    await user.type(campo("Ciudad"), "Neuquén");
    await user.type(campo("Nombre *"), "Ana");
    await user.type(campo("Apellido *"), "Pérez");
    await user.type(campo("Número de documento"), "30111222");
    await user.type(campo("Nacionalidad"), "Argentina");
    await user.click(crear());

    await waitFor(() => expect(createHumanClient).toHaveBeenCalledTimes(1));
    expect(createHumanClient).toHaveBeenCalledWith({
      email: "ana@correo.com",
      phone: "299-555",
      address: "San Martín 100",
      city: "Neuquén",
      country: "AR",
      profile: {
        first_name: "Ana",
        last_name: "Pérez",
        document_type: "DNI",
        document_number: "30111222",
        nationality: "Argentina",
      },
    });
    expect(await screen.findByText("listado de clientes")).toBeInTheDocument();
    expect(createLegalClient).not.toHaveBeenCalled();
  });

  it("no envía nada si faltan nombre y apellido (campos obligatorios)", async () => {
    const user = userEvent.setup();
    montar("humano");
    await user.click(crear());
    expect(createHumanClient).not.toHaveBeenCalled();
    expect(screen.queryByText("listado de clientes")).not.toBeInTheDocument();
  });

  it("permite elegir otro tipo de documento", async () => {
    const user = userEvent.setup();
    montar("humano");
    await user.type(campo("Nombre *"), "Ana");
    await user.type(campo("Apellido *"), "Pérez");
    await user.selectOptions(campo("Tipo de documento"), "PASAPORTE");
    await user.click(crear());

    await waitFor(() => expect(createHumanClient).toHaveBeenCalled());
    expect(createHumanClient.mock.calls[0][0].profile.document_type).toBe("PASAPORTE");
  });

  it("el país arranca en AR", () => {
    montar("humano");
    expect(campo("País")).toHaveValue("AR");
  });
});

describe("NuevoClientePage — persona jurídica", () => {
  beforeEach(() => {
    createHumanClient.mockResolvedValue({ id: 1 });
    createLegalClient.mockResolvedValue({ id: 2 });
  });

  it("muestra el formulario de empresa (cualquier :type distinto de 'humano')", () => {
    montar("juridico");
    expect(screen.getByRole("heading", { name: "Nueva Persona Jurídica" })).toBeInTheDocument();
    expect(screen.getByText("Datos de la empresa")).toBeInTheDocument();
    expect(screen.queryByText("Nombre *")).not.toBeInTheDocument();
  });

  it("crea la empresa con CUIT y número de agencia", async () => {
    const user = userEvent.setup();
    montar("juridico");

    await user.type(campo("Razón social *"), "Agencia Sur SRL");
    await user.type(campo("Nombre comercial"), "Agencia Sur");
    await user.type(campo("Número fiscal"), "30711222333");
    await user.type(campo("Representante legal"), "Ana Pérez");
    await user.type(campo("Sector / industria"), "Juegos");
    await user.type(campo("Nro. Agencia"), "000042");
    await user.click(crear());

    await waitFor(() => expect(createLegalClient).toHaveBeenCalledTimes(1));
    expect(createLegalClient.mock.calls[0][0].profile).toEqual({
      legal_name: "Agencia Sur SRL",
      trade_name: "Agencia Sur",
      tax_id: "30711222333",
      tax_id_type: "CUIT",
      legal_representative: "Ana Pérez",
      industry_sector: "Juegos",
      agency_number: "000042",
    });
    expect(createHumanClient).not.toHaveBeenCalled();
  });

  it("no envía nada si falta la razón social", async () => {
    const user = userEvent.setup();
    montar("juridico");
    await user.type(campo("Número fiscal"), "30711222333");
    await user.click(crear());
    expect(createLegalClient).not.toHaveBeenCalled();
  });

  it("permite cambiar el tipo de identificación fiscal", async () => {
    const user = userEvent.setup();
    montar("juridico");
    await user.type(campo("Razón social *"), "ACME");
    await user.selectOptions(campo("Tipo de identificación fiscal"), "RUT");
    await user.click(crear());

    await waitFor(() => expect(createLegalClient).toHaveBeenCalled());
    expect(createLegalClient.mock.calls[0][0].profile.tax_id_type).toBe("RUT");
  });
});

describe("NuevoClientePage — errores y navegación", () => {
  it("muestra el detalle que devuelve el backend", async () => {
    createHumanClient.mockRejectedValue({ response: { data: { detail: "CUIL duplicado" } } });
    const user = userEvent.setup();
    montar("humano");

    await user.type(campo("Nombre *"), "Ana");
    await user.type(campo("Apellido *"), "Pérez");
    await user.click(crear());

    expect(await screen.findByText("CUIL duplicado")).toBeInTheDocument();
    expect(screen.queryByText("listado de clientes")).not.toBeInTheDocument();
  });

  it("si el error no trae detalle muestra un mensaje genérico", async () => {
    createLegalClient.mockRejectedValue(new Error("sin red"));
    const user = userEvent.setup();
    montar("juridico");

    await user.type(campo("Razón social *"), "ACME");
    await user.click(crear());

    expect(await screen.findByText("Error al crear cliente")).toBeInTheDocument();
  });

  it("Cancelar vuelve a la pantalla anterior sin llamar a la API", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/previa", "/modules/clientes/nuevo/humano"]} initialIndex={1}>
        <Routes>
          <Route path="/modules/clientes/nuevo/:type" element={<NuevoClientePage />} />
          <Route path="/previa" element={<p>pantalla previa</p>} />
        </Routes>
      </MemoryRouter>
    );

    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.getByText("pantalla previa")).toBeInTheDocument();
    expect(createHumanClient).not.toHaveBeenCalled();
  });
});
