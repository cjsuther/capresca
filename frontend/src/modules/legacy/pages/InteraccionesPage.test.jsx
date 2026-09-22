import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import InteraccionesPage from "./InteraccionesPage";
import * as legacyApi from "../../../api/legacy";

vi.mock("../../../api/legacy", () => ({
  getInteractions: vi.fn(),
  getDatabases: vi.fn(),
}));

const HOY = new Date().toISOString().slice(0, 10);

const IN_OK = {
  id: 1,
  occurred_at: "2026-09-20T09:00:00Z",
  direction: "IN",
  database: "QUINIELA",
  table_name: "cajaliq",
  operation: "SELECT",
  rows_affected: 320,
  status: "OK",
  latency_ms: 48,
  origin_module: "conciliacion",
  payload_summary: { filtro: "fecha=2026-09-20" },
  error_message: null,
  outbox_id: null,
};

const OUT_ERROR = {
  id: 2,
  occurred_at: "2026-09-20T09:05:00Z",
  direction: "OUT",
  database: "QUINIELA",
  table_name: "agencias",
  operation: "UPDATE",
  rows_affected: null,
  status: "ERROR",
  latency_ms: null,
  origin_module: null,
  payload_summary: null,
  error_message: "El DBF está bloqueado por otro proceso",
  outbox_id: 991,
};

const PAGINA = { items: [IN_OK, OUT_ERROR], total: 2, page: 1, page_size: 50 };

function montar() {
  return render(
    <MemoryRouter>
      <InteraccionesPage />
    </MemoryRouter>
  );
}

/** Última llamada a getInteractions (la lista se recarga en cada cambio de filtro). */
const ultimosParams = () =>
  legacyApi.getInteractions.mock.calls[legacyApi.getInteractions.mock.calls.length - 1][0];

describe("InteraccionesPage · listado", () => {
  beforeEach(() => {
    legacyApi.getDatabases.mockResolvedValue({ databases: ["QUINIELA", "TOMBOLA"] });
    legacyApi.getInteractions.mockResolvedValue(PAGINA);
  });

  it("pide la primera página del día con las bases disponibles", async () => {
    montar();

    await waitFor(() => expect(legacyApi.getInteractions).toHaveBeenCalled());
    expect(ultimosParams()).toEqual({
      page: 1,
      page_size: 50,
      date_from: HOY,
      date_to: HOY,
    });
    expect(await screen.findByRole("option", { name: "QUINIELA" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "TOMBOLA" })).toBeInTheDocument();
  });

  it("muestra las interacciones IN y OUT con sus datos", async () => {
    montar();

    const filaIn = (await screen.findByText("cajaliq")).closest("tr");
    expect(within(filaIn).getByText("IN")).toBeInTheDocument();
    expect(within(filaIn).getByText("SELECT")).toBeInTheDocument();
    expect(within(filaIn).getByText("320")).toBeInTheDocument();
    expect(within(filaIn).getByText("OK")).toBeInTheDocument();
    expect(within(filaIn).getByText("48 ms")).toBeInTheDocument();
    expect(within(filaIn).getByText("conciliacion")).toBeInTheDocument();

    const filaOut = screen.getByText("agencias").closest("tr");
    expect(within(filaOut).getByText("OUT")).toBeInTheDocument();
    expect(within(filaOut).getByText("ERROR")).toBeInTheDocument();
    expect(within(filaOut).getAllByText("—")).toHaveLength(3);

    expect(screen.getByText("2 interacciones")).toBeInTheDocument();
  });

  it("avisa cuando no hay interacciones para los filtros", async () => {
    legacyApi.getInteractions.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 50 });
    montar();

    expect(
      await screen.findByText("No hay interacciones para los filtros seleccionados.")
    ).toBeInTheDocument();
    expect(screen.getByText("0 interacciones")).toBeInTheDocument();
  });

  it("muestra el detalle del error de la API", async () => {
    legacyApi.getInteractions.mockRejectedValue({
      response: { data: { detail: "Módulo legacy apagado" } },
    });
    montar();
    expect(await screen.findByText("Módulo legacy apagado")).toBeInTheDocument();
  });

  it("si el error no trae detalle usa el mensaje genérico", async () => {
    legacyApi.getInteractions.mockRejectedValue(new Error("sin red"));
    montar();
    expect(await screen.findByText("Error al cargar interacciones")).toBeInTheDocument();
  });

  it("si falla el listado de bases el filtro queda sólo con Todas", async () => {
    legacyApi.getDatabases.mockRejectedValue(new Error("500"));
    montar();

    await screen.findByText("cajaliq");
    const selectBase = screen.getByLabelText("Base de datos", { selector: "select" });
    expect(within(selectBase).getAllByRole("option")).toHaveLength(1);
  });

  it("tolera una respuesta de bases sin la clave databases", async () => {
    legacyApi.getDatabases.mockResolvedValue({});
    montar();

    await screen.findByText("cajaliq");
    const selectBase = screen.getByLabelText("Base de datos", { selector: "select" });
    expect(within(selectBase).getAllByRole("option")).toHaveLength(1);
  });

  it("el botón Actualizar vuelve a pedir la página", async () => {
    const user = userEvent.setup();
    montar();
    await screen.findByText("cajaliq");

    await user.click(screen.getByRole("button", { name: /Actualizar/ }));
    await waitFor(() => expect(legacyApi.getInteractions).toHaveBeenCalledTimes(2));
  });
});

describe("InteraccionesPage · filtros", () => {
  beforeEach(() => {
    legacyApi.getDatabases.mockResolvedValue({ databases: ["QUINIELA", "TOMBOLA"] });
    legacyApi.getInteractions.mockResolvedValue(PAGINA);
  });

  it("filtra por dirección, base y estado", async () => {
    const user = userEvent.setup();
    montar();
    await screen.findByText("cajaliq");

    await user.selectOptions(screen.getByLabelText("Dirección", { selector: "select" }), "OUT");
    await waitFor(() => expect(ultimosParams()).toMatchObject({ direction: "OUT" }));

    await user.selectOptions(screen.getByLabelText("Base de datos", { selector: "select" }), "TOMBOLA");
    await waitFor(() => expect(ultimosParams()).toMatchObject({ database: "TOMBOLA" }));

    await user.selectOptions(screen.getByLabelText("Estado", { selector: "select" }), "ERROR");
    await waitFor(() =>
      expect(ultimosParams()).toMatchObject({ direction: "OUT", database: "TOMBOLA", status: "ERROR" })
    );
  });

  it("filtra por tabla y por rango de fechas", async () => {
    const user = userEvent.setup();
    montar();
    await screen.findByText("cajaliq");

    await user.type(screen.getByPlaceholderText("ej. cajaliq"), "cajaliq");
    await waitFor(() => expect(ultimosParams()).toMatchObject({ table: "cajaliq" }));

    fireEvent.change(screen.getByLabelText("Desde", { selector: "input" }), {
      target: { value: "2026-09-01" },
    });
    fireEvent.change(screen.getByLabelText("Hasta", { selector: "input" }), {
      target: { value: "2026-09-15" },
    });
    await waitFor(() =>
      expect(ultimosParams()).toMatchObject({ date_from: "2026-09-01", date_to: "2026-09-15" })
    );
  });

  it("los filtros vacíos no viajan como query params", async () => {
    const user = userEvent.setup();
    montar();
    await screen.findByText("cajaliq");

    await user.selectOptions(screen.getByLabelText("Dirección", { selector: "select" }), "IN");
    await waitFor(() => expect(ultimosParams()).toMatchObject({ direction: "IN" }));

    await user.selectOptions(screen.getByLabelText("Dirección", { selector: "select" }), "");
    await waitFor(() => expect(ultimosParams()).not.toHaveProperty("direction"));
    expect(ultimosParams()).not.toHaveProperty("status");
  });
});

describe("InteraccionesPage · fila expandida", () => {
  beforeEach(() => {
    legacyApi.getDatabases.mockResolvedValue({ databases: [] });
    legacyApi.getInteractions.mockResolvedValue(PAGINA);
  });

  it("despliega el payload de una interacción exitosa y la vuelve a cerrar", async () => {
    const user = userEvent.setup();
    montar();

    await user.click((await screen.findByText("cajaliq")).closest("tr"));
    expect(screen.getByText("payload_summary:")).toBeInTheDocument();
    expect(screen.getByText(/fecha=2026-09-20/)).toBeInTheDocument();

    await user.click(screen.getByText("cajaliq").closest("tr"));
    expect(screen.queryByText("payload_summary:")).not.toBeInTheDocument();
  });

  it("despliega el error y el outbox_id de una escritura fallida", async () => {
    const user = userEvent.setup();
    montar();

    await user.click((await screen.findByText("agencias")).closest("tr"));
    expect(screen.getByText("El DBF está bloqueado por otro proceso")).toBeInTheDocument();
    expect(screen.getByText("outbox_id: 991")).toBeInTheDocument();
    // sin payload muestra un objeto vacío
    expect(screen.getByText("{}")).toBeInTheDocument();
  });

  it("sólo queda una fila expandida a la vez", async () => {
    const user = userEvent.setup();
    montar();

    await user.click((await screen.findByText("cajaliq")).closest("tr"));
    await user.click(screen.getByText("agencias").closest("tr"));

    expect(screen.getAllByText("payload_summary:")).toHaveLength(1);
    expect(screen.getByText("outbox_id: 991")).toBeInTheDocument();
  });
});

describe("InteraccionesPage · paginación", () => {
  beforeEach(() => {
    legacyApi.getDatabases.mockResolvedValue({ databases: [] });
    legacyApi.getInteractions.mockResolvedValue({ ...PAGINA, total: 120 });
  });

  it("calcula las páginas y navega hacia adelante y atrás", async () => {
    const user = userEvent.setup();
    montar();

    expect(await screen.findByText("Página 1 de 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await waitFor(() => expect(ultimosParams()).toMatchObject({ page: 2 }));
    expect(screen.getByText("Página 2 de 3")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anterior" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Anterior" }));
    await waitFor(() => expect(ultimosParams()).toMatchObject({ page: 1 }));
  });

  it("cambiar un filtro vuelve a la primera página", async () => {
    const user = userEvent.setup();
    montar();
    await screen.findByText("Página 1 de 3");

    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await waitFor(() => expect(ultimosParams()).toMatchObject({ page: 2 }));

    await user.selectOptions(screen.getByLabelText("Estado", { selector: "select" }), "OK");
    await waitFor(() => expect(ultimosParams()).toMatchObject({ page: 1, status: "OK" }));
    expect(screen.getByText("Página 1 de 3")).toBeInTheDocument();
  });

  it("con una sola página ambos botones quedan deshabilitados", async () => {
    legacyApi.getInteractions.mockResolvedValue({ ...PAGINA, total: 0 });
    montar();

    expect(await screen.findByText("Página 1 de 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
  });
});
