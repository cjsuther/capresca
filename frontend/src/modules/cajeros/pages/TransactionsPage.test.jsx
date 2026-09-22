import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/cajeros", () => ({
  getTransactions: vi.fn(),
  authorizeTransaction: vi.fn(),
  rejectTransaction: vi.fn(),
  deleteTransaction: vi.fn(),
}));

import {
  getTransactions, authorizeTransaction, rejectTransaction, deleteTransaction,
} from "../../../api/cajeros";
import TransactionsPage from "./TransactionsPage";
import { useAuthStore } from "../../../context/authStore";

const USUARIO = { id: 10, username: "ana" };

const sesion = (acciones = []) =>
  useAuthStore.setState({
    token: "tok",
    user: USUARIO,
    permissions: { modules: ["cajeros"], actions: { cajeros: acciones } },
  });

const TX_PENDIENTE = {
  id: 1,
  status: "PENDIENTE_AUTORIZACION",
  currency: "ARS",
  amount: "15000.00",
  reference: "REF-1",
  description: "pago proveedor",
  cajero_user_id: 10,
  cajero_username: "ana",
  authorizer_user_id: 10,
  authorizer_username: "ana",
  created_at: "2026-03-01T10:00:00Z",
  updated_at: "2026-03-01T10:00:00Z",
};

const TX_PROCESADA = {
  id: 2,
  status: "PROCESADA",
  currency: "USD",
  amount: "300.00",
  reference: null,
  cajero_user_id: 99,
  cajero_username: "beto",
  authorizer_user_id: null,
  created_at: "2026-03-02T10:00:00Z",
  updated_at: "2026-03-02T12:00:00Z",
};

function montar(ruta = "/modules/cajeros/transactions") {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/modules/cajeros/transactions" element={<TransactionsPage />} />
        <Route path="/modules/cajeros/transactions/:id" element={<TransactionsPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("TransactionsPage — listado", () => {
  beforeEach(() => {
    vi.mocked(getTransactions).mockReset();
    vi.mocked(authorizeTransaction).mockReset();
    vi.mocked(rejectTransaction).mockReset();
    vi.mocked(deleteTransaction).mockReset();
    sesion([]);
  });

  it("muestra el estado de carga inicial", () => {
    getTransactions.mockReturnValue(new Promise(() => {}));
    montar();
    expect(screen.getByText("Cargando...")).toBeInTheDocument();
  });

  it("avisa cuando no hay transacciones", async () => {
    getTransactions.mockResolvedValue([]);
    montar();
    expect(await screen.findByText("Sin transacciones")).toBeInTheDocument();
  });

  it("renderiza monto formateado, moneda, referencia y estado", async () => {
    getTransactions.mockResolvedValue([TX_PENDIENTE, TX_PROCESADA]);
    montar();

    expect(await screen.findByRole("cell", { name: "Pend. Autorización" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Procesada" })).toBeInTheDocument();
    expect(screen.getByText("15.000,00")).toBeInTheDocument();
    expect(screen.getByText("300,00")).toBeInTheDocument();
    expect(screen.getByText("REF-1")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "ARS" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "USD" })).toBeInTheDocument();
  });

  it("muestra un mensaje si falla la carga", async () => {
    getTransactions.mockRejectedValue(new Error("500"));
    montar();
    expect(await screen.findByText("Error al cargar transacciones")).toBeInTheDocument();
  });

  it("oculta la columna Cajero sin permiso de lectura global", async () => {
    getTransactions.mockResolvedValue([TX_PROCESADA]);
    montar();
    await screen.findByRole("cell", { name: "Procesada" });
    expect(screen.queryByRole("columnheader", { name: "Cajero" })).not.toBeInTheDocument();
  });

  it("muestra la columna Cajero con transactions:read_all", async () => {
    sesion(["transactions:read_all"]);
    getTransactions.mockResolvedValue([TX_PROCESADA]);
    montar();
    await screen.findByRole("cell", { name: "Procesada" });
    expect(screen.getByRole("columnheader", { name: "Cajero" })).toBeInTheDocument();
    expect(screen.getByText("beto")).toBeInTheDocument();
  });

  it("muestra la columna Cajero con transactions:admin", async () => {
    sesion(["transactions:admin"]);
    getTransactions.mockResolvedValue([TX_PROCESADA]);
    montar();
    await screen.findByRole("cell", { name: "Procesada" });
    expect(screen.getByRole("columnheader", { name: "Cajero" })).toBeInTheDocument();
  });
});

describe("TransactionsPage — filtros", () => {
  beforeEach(() => {
    vi.mocked(getTransactions).mockReset().mockResolvedValue([]);
    sesion([]);
  });

  it("pide al backend los 4 estados por defecto", async () => {
    montar();
    await screen.findByText("Sin transacciones");
    expect(getTransactions).toHaveBeenCalledWith({
      status: "PENDIENTE_AUTORIZACION,PROCESADA,AUTORIZADA,RECHAZADA",
    });
  });

  it("al desmarcar un estado se recarga sin ese estado", async () => {
    const user = userEvent.setup();
    montar();
    await screen.findByText("Sin transacciones");

    await user.click(screen.getByRole("button", { name: "Procesada" }));

    await waitFor(() =>
      expect(getTransactions).toHaveBeenLastCalledWith({
        status: "PENDIENTE_AUTORIZACION,AUTORIZADA,RECHAZADA",
      })
    );
  });

  it("si se seleccionan TODOS los estados no manda el filtro status", async () => {
    const user = userEvent.setup();
    montar();
    await screen.findByText("Sin transacciones");

    await user.click(screen.getByRole("button", { name: "Eliminada" }));

    await waitFor(() => expect(getTransactions).toHaveBeenLastCalledWith({}));
  });

  it("el filtro de moneda se agrega a los params", async () => {
    const user = userEvent.setup();
    montar();
    await screen.findByText("Sin transacciones");

    await user.selectOptions(screen.getByRole("combobox"), "EUR");

    await waitFor(() =>
      expect(getTransactions).toHaveBeenLastCalledWith({
        status: "PENDIENTE_AUTORIZACION,PROCESADA,AUTORIZADA,RECHAZADA",
        currency: "EUR",
      })
    );
  });
});

describe("TransactionsPage — autorizar y rechazar", () => {
  beforeEach(() => {
    vi.mocked(getTransactions).mockReset().mockResolvedValue([TX_PENDIENTE]);
    vi.mocked(authorizeTransaction).mockReset().mockResolvedValue({});
    vi.mocked(rejectTransaction).mockReset().mockResolvedValue({});
    vi.mocked(deleteTransaction).mockReset().mockResolvedValue({});
    sesion(["transactions:authorize"]);
  });

  it("sin permiso de autorización no aparecen los botones", async () => {
    sesion([]);
    montar();
    await screen.findByRole("cell", { name: "Pend. Autorización" });
    expect(screen.queryByRole("button", { name: /Autorizar/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Rechazar/ })).not.toBeInTheDocument();
  });

  it("no ofrece autorizar si el autorizador asignado es otro usuario", async () => {
    getTransactions.mockResolvedValue([{ ...TX_PENDIENTE, authorizer_user_id: 77 }]);
    montar();
    await screen.findByRole("cell", { name: "Pend. Autorización" });
    expect(screen.queryByRole("button", { name: /Autorizar/ })).not.toBeInTheDocument();
  });

  it("no ofrece acciones sobre transacciones que no están pendientes", async () => {
    getTransactions.mockResolvedValue([{ ...TX_PENDIENTE, status: "AUTORIZADA" }]);
    montar();
    await screen.findByRole("cell", { name: "Autorizada" });
    expect(screen.queryByRole("button", { name: /Autorizar/ })).not.toBeInTheDocument();
  });

  it("autoriza y recarga el listado", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Autorizar/ }));

    expect(authorizeTransaction).toHaveBeenCalledWith(1);
    await waitFor(() => expect(getTransactions).toHaveBeenCalledTimes(2));
  });

  it("muestra el error de la API al autorizar", async () => {
    authorizeTransaction.mockRejectedValue({ response: { data: { detail: "Fuera de horario" } } });
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Autorizar/ }));

    expect(await screen.findByText("Fuera de horario")).toBeInTheDocument();
  });

  it("el modal de rechazo exige un motivo antes de confirmar", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Rechazar/ }));

    expect(screen.getByText("Rechazar transacción")).toBeInTheDocument();
    const confirmar = screen.getByRole("button", { name: "Confirmar rechazo" });
    expect(confirmar).toBeDisabled();

    await user.type(screen.getByPlaceholderText("Describe el motivo del rechazo..."), "   ");
    expect(confirmar).toBeDisabled();

    await user.type(screen.getByPlaceholderText("Describe el motivo del rechazo..."), "monto erróneo");
    expect(confirmar).toBeEnabled();
  });

  it("rechaza con el motivo escrito y cierra el modal", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Rechazar/ }));
    await user.type(screen.getByPlaceholderText("Describe el motivo del rechazo..."), "duplicada");
    await user.click(screen.getByRole("button", { name: "Confirmar rechazo" }));

    expect(rejectTransaction).toHaveBeenCalledWith(1, { rejection_reason: "duplicada" });
    await waitFor(() => expect(screen.queryByText("Rechazar transacción")).not.toBeInTheDocument());
  });

  it("si falla el rechazo muestra el error y cierra el modal igual", async () => {
    rejectTransaction.mockRejectedValue({ response: { data: { detail: "Ya fue autorizada" } } });
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Rechazar/ }));
    await user.type(screen.getByPlaceholderText("Describe el motivo del rechazo..."), "duplicada");
    await user.click(screen.getByRole("button", { name: "Confirmar rechazo" }));

    expect(await screen.findByText("Ya fue autorizada")).toBeInTheDocument();
    expect(screen.queryByText("Rechazar transacción")).not.toBeInTheDocument();
  });

  it("se puede cerrar el modal de rechazo con Cancelar", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByRole("button", { name: /Rechazar/ }));
    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(screen.queryByText("Rechazar transacción")).not.toBeInTheDocument();
    expect(rejectTransaction).not.toHaveBeenCalled();
  });
});

describe("TransactionsPage — eliminar", () => {
  beforeEach(() => {
    vi.mocked(getTransactions).mockReset().mockResolvedValue([TX_PENDIENTE]);
    vi.mocked(deleteTransaction).mockReset().mockResolvedValue({});
    sesion(["transactions:delete"]);
  });

  it("elimina la propia transacción tras confirmar", async () => {
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByTitle("Eliminar"));

    expect(confirmar).toHaveBeenCalledWith("¿Eliminar transacción #1?");
    expect(deleteTransaction).toHaveBeenCalledWith(1);
    await waitFor(() => expect(getTransactions).toHaveBeenCalledTimes(2));
    confirmar.mockRestore();
  });

  it("si se cancela la confirmación no llama a la API", async () => {
    const confirmar = vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByTitle("Eliminar"));

    expect(deleteTransaction).not.toHaveBeenCalled();
    confirmar.mockRestore();
  });

  it("muestra el error si la baja falla", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    deleteTransaction.mockRejectedValue({ response: { data: { detail: "No se puede eliminar" } } });
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByTitle("Eliminar"));

    expect(await screen.findByText("No se puede eliminar")).toBeInTheDocument();
    vi.mocked(window.confirm).mockRestore();
  });

  it("un cajero sin admin no puede borrar transacciones ajenas", async () => {
    getTransactions.mockResolvedValue([{ ...TX_PENDIENTE, cajero_user_id: 99 }]);
    montar();
    await screen.findByRole("cell", { name: "Pend. Autorización" });
    expect(screen.queryByTitle("Eliminar")).not.toBeInTheDocument();
  });

  it("transactions:admin permite borrar transacciones ajenas", async () => {
    sesion(["transactions:admin"]);
    getTransactions.mockResolvedValue([{ ...TX_PENDIENTE, cajero_user_id: 99 }]);
    montar();
    expect(await screen.findByTitle("Eliminar")).toBeInTheDocument();
  });
});

describe("TransactionsPage — panel de detalle", () => {
  beforeEach(() => {
    vi.mocked(getTransactions).mockReset().mockResolvedValue([TX_PENDIENTE, TX_PROCESADA]);
    sesion([]);
  });

  it("abre el detalle al hacer click en la fila", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByText("REF-1"));

    const detalle = await screen.findByText("Transacción #1");
    expect(detalle).toBeInTheDocument();
    expect(screen.getByText("ARS 15.000,00")).toBeInTheDocument();
    expect(screen.getByText("pago proveedor")).toBeInTheDocument();
  });

  it("abre el detalle automáticamente cuando la URL trae el id", async () => {
    montar("/modules/cajeros/transactions/2");
    expect(await screen.findByText("Transacción #2")).toBeInTheDocument();
    expect(screen.getByText("USD 300,00")).toBeInTheDocument();
  });

  it("ignora un id de la URL que no está en el listado", async () => {
    montar("/modules/cajeros/transactions/999");
    await screen.findByRole("cell", { name: "Pend. Autorización" });
    expect(screen.queryByText(/^Transacción #/)).not.toBeInTheDocument();
  });

  it("el detalle muestra el motivo de rechazo cuando existe", async () => {
    getTransactions.mockResolvedValue([
      { ...TX_PENDIENTE, id: 3, status: "RECHAZADA", rejection_reason: "importe mal cargado", authorized_at: "2026-03-03T10:00:00Z" },
    ]);
    montar("/modules/cajeros/transactions/3");
    expect(await screen.findByText("Transacción #3")).toBeInTheDocument();
    expect(screen.getByText("importe mal cargado")).toBeInTheDocument();
    expect(screen.getByText("Fecha autorización")).toBeInTheDocument();
  });

  it("se cierra el detalle con la X", async () => {
    const user = userEvent.setup();
    montar("/modules/cajeros/transactions/2");
    const titulo = await screen.findByText("Transacción #2");
    const cerrar = within(titulo.parentElement).getByRole("button");

    await user.click(cerrar);

    await waitFor(() => expect(screen.queryByText("Transacción #2")).not.toBeInTheDocument());
  });
});
