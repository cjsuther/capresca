import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import RecalculoCreditoPage from "./RecalculoCreditoPage";
import { creditos } from "../../../../api/creditos";
import { useAuthStore } from "../../../../context/authStore";

vi.mock("../../../../api/creditos", () => ({
  creditos: { recalculoPreview: vi.fn(), recalculoAplicar: vi.fn() },
}));

const PREVIA = {
  modo: "vencimientos", cantidad_actual: 2, total_actual: 120000,
  cantidad_propuesta: 2, total_propuesto: 120000,
  actual: [
    { numero: 5, fecha_vto: "2026-03-10", total: 60000 },
    { numero: 6, fecha_vto: "2026-04-10", total: 60000 },
  ],
  propuesto: [
    { numero: 5, fecha_vto: "2026-05-10", total: 60000 },
    { numero: 6, fecha_vto: "2026-06-10", total: 60000 },
  ],
};

const sesion = (acciones) =>
  useAuthStore.setState({ token: "tok", user: { username: "ana" },
    permissions: { modules: ["creditos"], actions: { creditos: acciones } } });

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-03-15T12:00:00Z") });
  sesion(["creditos:read", "creditos:write"]);
  creditos.recalculoPreview.mockResolvedValue(PREVIA);
  creditos.recalculoAplicar.mockResolvedValue({ cuotas_resultantes: 2, total: 120000 });
});
afterEach(() => vi.useRealTimers());

async function previsualizar(u) {
  await u.type(screen.getByLabelText("N° de crédito"), "900");
  await u.click(screen.getByRole("button", { name: "Previsualizar" }));
}

describe("Recálculo de cuotas", () => {
  it("previsualiza reprogramando vencimientos y compara actual contra propuesto", async () => {
    const u = userEvent.setup();
    render(<RecalculoCreditoPage />);
    await previsualizar(u);

    await waitFor(() => expect(creditos.recalculoPreview).toHaveBeenCalledWith(
      900, { modo: "vencimientos", primer_vto: "2026-03-15", haber: undefined }));
    expect(await screen.findByText(/Vista previa/)).toBeInTheDocument();
    expect(screen.getByText("10/5/2026")).toBeInTheDocument();       // vencimiento propuesto
  });

  it("el modo jubilatorio pide el haber en vez de la fecha", async () => {
    const u = userEvent.setup();
    render(<RecalculoCreditoPage />);
    await u.selectOptions(screen.getByLabelText("Modo"), "jubilatorio");
    expect(screen.queryByLabelText("1er vto. (cuota 1)")).toBeNull();

    await u.type(screen.getByLabelText("N° de crédito"), "900");
    await u.type(screen.getByLabelText("Haber jubilatorio"), "250000");
    await u.click(screen.getByRole("button", { name: "Previsualizar" }));
    await waitFor(() => expect(creditos.recalculoPreview).toHaveBeenCalledWith(
      900, { modo: "jubilatorio", primer_vto: undefined, haber: "250000" }));
  });

  it("sin número de crédito no previsualiza", async () => {
    const u = userEvent.setup();
    render(<RecalculoCreditoPage />);
    await u.click(screen.getByRole("button", { name: "Previsualizar" }));
    expect(await screen.findByText("Ingresá un número de crédito.")).toBeInTheDocument();
    expect(creditos.recalculoPreview).not.toHaveBeenCalled();
  });

  it("aplicar exige confirmación y avisa el resultado", async () => {
    const u = userEvent.setup();
    render(<RecalculoCreditoPage />);
    await previsualizar(u);
    await u.click(await screen.findByRole("button", { name: "Confirmar y aplicar recálculo" }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(creditos.recalculoAplicar).not.toHaveBeenCalled();

    await u.click(screen.getByRole("button", { name: "Aplicar recálculo" }));
    await waitFor(() => expect(creditos.recalculoAplicar).toHaveBeenCalledWith(
      900, { modo: "vencimientos", primer_vto: "2026-03-15", haber: undefined }));
    expect(await screen.findByText(/Recálculo aplicado: 2 cuotas/)).toBeInTheDocument();
  });

  it("si el backend rechaza el recálculo lo muestra", async () => {
    creditos.recalculoAplicar.mockRejectedValue(new Error("El crédito está cancelado"));
    const u = userEvent.setup();
    render(<RecalculoCreditoPage />);
    await previsualizar(u);
    await u.click(await screen.findByRole("button", { name: "Confirmar y aplicar recálculo" }));
    await u.click(screen.getByRole("button", { name: "Aplicar recálculo" }));
    expect(await screen.findByText("El crédito está cancelado")).toBeInTheDocument();
  });

  it("en sólo lectura se previsualiza pero no se aplica", async () => {
    sesion(["creditos:read"]);
    const u = userEvent.setup();
    render(<RecalculoCreditoPage />);
    await previsualizar(u);
    expect(await screen.findByText(/Vista previa/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirmar y aplicar recálculo" })).toBeNull();
  });
});
