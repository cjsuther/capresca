import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/tesoreria", async (orig) => ({
  ...(await orig()),
  verLote: vi.fn(), aprobarLote: vi.fn(), rechazarLote: vi.fn(), excluirPago: vi.fn(), incluirPago: vi.fn(),
  cuentasOrigen: vi.fn(),
  enviarLote: vi.fn(), actualizarLote: vi.fn(), reintentarPago: vi.fn(), resolverPago: vi.fn(),
}));

import * as api from "../../../api/tesoreria";
import LotePage from "./LotePage";

const P1 = { id: 11, beneficiario: "PEREZ JUAN", documento: "20301234569", cbu: "2850590940090418135201", monto: 500000,
             concepto: "Desembolso", estado: "PENDIENTE", motivo: "", id_operacion_ib: "" };
const P2 = { ...P1, id: 12, beneficiario: "GOMEZ ANA", monto: 300000 };
const BASE = {
  id: 3, codigo: "LOT-2026-00003", origen: "CREDITOS", descripcion: "Desembolsos", referencia_origen: "r",
  estado: "PENDIENTE_APROBACION", simulado: false, cantidad: 2, total: 800000, por_estado: { PENDIENTE: 2 },
  creado_en: "2026-09-22T10:00:00", creado_por: "ana", pagos: [P1, P2], aprobaciones: [], niveles: 1, nivel_actual: 1,
  puede_aprobar: true, motivo_no_aprueba: "", puede_enviar: true, puede_editar: true, envio_simulado: true,
  eventos: [{ fecha: "2026-09-22T10:00:00", usuario: "ana", accion: "ALTA", detalle: "2 pago(s)" }],
};

const CUENTAS = {
  items: [
    { account_number: "99900011122", account_type: "CC", bank_number: "011", nombre: "Cuenta de pagos", predeterminada: true },
    { account_number: "46600513539", account_type: "CA", bank_number: "017", nombre: "Recaudación", predeterminada: false },
  ],
  error: "",
};

function montar(lote, cuentas = CUENTAS) {
  api.verLote.mockResolvedValue(lote);
  api.cuentasOrigen.mockResolvedValue(cuentas);
  render(
    <MemoryRouter initialEntries={["/lotes/3"]}>
      <Routes><Route path="/lotes/:id" element={<LotePage />} /></Routes>
    </MemoryRouter>,
  );
}

describe("LotePage", () => {
  beforeEach(() => vi.clearAllMocks());

  it("muestra pagos, historial y aviso de simulación", async () => {
    montar(BASE);
    expect(await screen.findByText("Lote LOT-2026-00003")).toBeInTheDocument();
    expect(screen.getByText("PEREZ JUAN")).toBeInTheDocument();
    expect(screen.getByText(/Modo simulación activo/)).toBeInTheDocument();
    expect(screen.getByText("alta")).toBeInTheDocument();
  });

  it("excluir pide motivo", async () => {
    api.excluirPago.mockResolvedValue({ ...BASE, pagos: [{ ...P1, estado: "EXCLUIDO", motivo: "CBU dudoso" }, P2] });
    montar(BASE);
    const fila = (await screen.findByText("PEREZ JUAN")).closest("tr");
    await userEvent.click(within(fila).getByRole("button", { name: "Excluir" }));
    const dialogo = screen.getByRole("dialog", { name: /Excluir el pago/ });
    const boton = within(dialogo).getByRole("button", { name: "Excluir" });
    expect(boton).toBeDisabled();
    await userEvent.type(within(dialogo).getByRole("textbox"), "CBU dudoso");
    await userEvent.click(boton);
    expect(api.excluirPago).toHaveBeenCalledWith(3, 11, "CBU dudoso");
    expect(await screen.findByText("Pago excluido.")).toBeInTheDocument();
  });

  it("aprobar con confirmación", async () => {
    api.aprobarLote.mockResolvedValue({ ...BASE, estado: "APROBADO" });
    montar(BASE);
    await userEvent.click(await screen.findByRole("button", { name: /Aprobar/ }));
    await userEvent.click(within(screen.getByRole("dialog", { name: /Aprobar el lote/ })).getByRole("button", { name: "Aprobar" }));
    expect(api.aprobarLote).toHaveBeenCalledWith(3);
    expect(await screen.findByText("Lote aprobado: listo para enviar.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Enviar por Interbanking/ })).toBeInTheDocument();
  });

  it("quien no puede aprobar ve el motivo", async () => {
    montar({ ...BASE, puede_aprobar: false, motivo_no_aprueba: "Cuatro ojos: no podés aprobar un lote que cargaste vos." });
    expect(await screen.findByText(/Cuatro ojos/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Aprobar/ })).not.toBeInTheDocument();
  });

  it("enviar un lote aprobado desde la cuenta predeterminada", async () => {
    api.enviarLote.mockResolvedValue({ ...BASE, estado: "CONFIRMADO", simulado: true, por_estado: { CONFIRMADO: 2 },
                                       pagos: [{ ...P1, estado: "CONFIRMADO" }, { ...P2, estado: "CONFIRMADO" }] });
    montar({ ...BASE, estado: "APROBADO" });
    const select = await screen.findByLabelText("Cuenta desde la que se paga");
    await waitFor(() => expect(select).toHaveValue("99900011122"));
    await userEvent.click(screen.getByRole("button", { name: /Enviar por Interbanking/ }));
    const conf = screen.getByRole("dialog", { name: "Enviar por Interbanking" });
    expect(conf).toHaveTextContent("011/99900011122/CC · Cuenta de pagos");
    expect(conf).toHaveTextContent("no se mueve dinero");
    await userEvent.click(within(conf).getByRole("button", { name: "Enviar" }));
    expect(api.enviarLote).toHaveBeenCalledWith(3, "99900011122");
    expect(await screen.findByText(/se envió en modo simulación/)).toBeInTheDocument();
  });

  it("se puede elegir otra cuenta de origen", async () => {
    api.enviarLote.mockResolvedValue({ ...BASE, estado: "ENVIADO" });
    montar({ ...BASE, estado: "APROBADO" });
    const select = await screen.findByLabelText("Cuenta desde la que se paga");
    await waitFor(() => expect(select).toHaveValue("99900011122"));
    await userEvent.selectOptions(select, "46600513539");
    await userEvent.click(screen.getByRole("button", { name: /Enviar por Interbanking/ }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Enviar" }));
    expect(api.enviarLote).toHaveBeenCalledWith(3, "46600513539");
  });

  it("sin cuentas no deja enviar y dice qué configurar", async () => {
    montar({ ...BASE, estado: "APROBADO" }, { items: [], error: "No se pudieron listar las cuentas del banco" });
    expect(await screen.findByText(/cargá la cuenta de pagos en Interbanking/)).toBeInTheDocument();
    expect(screen.getByText("No se pudieron listar las cuentas del banco")).toBeInTheDocument();
    expect(screen.getByLabelText("Cuenta desde la que se paga")).toHaveTextContent("Sin cuentas disponibles");
    expect(screen.getByRole("button", { name: /Enviar por Interbanking/ })).toBeDisabled();
  });

  it("un lote en curso muestra desde qué cuenta se pagó", async () => {
    montar({ ...BASE, estado: "ENVIADO", enviado_por: "teso", enviado_en: "2026-09-22T11:00:00",
             cuenta_origen: { account_number: "46600513539", account_type: "CA", bank_number: "017", nombre: "Recaudación" } });
    expect(await screen.findByText(/desde 017\/46600513539\/CA · Recaudación/)).toBeInTheDocument();
    expect(api.cuentasOrigen).not.toHaveBeenCalled();     // sólo se consultan si hay que enviar
  });

  it("un pago incierto se resuelve indicando qué se verificó", async () => {
    const lote = { ...BASE, estado: "CON_ERRORES", por_estado: { INCIERTO: 1, CONFIRMADO: 1 },
                   pagos: [{ ...P1, estado: "INCIERTO", motivo: "Sin respuesta" }, { ...P2, estado: "CONFIRMADO" }] };
    api.resolverPago.mockResolvedValue({ ...lote, pagos: [{ ...P1, estado: "FALLIDO" }, lote.pagos[1]] });
    montar(lote);
    await userEvent.click(await screen.findByRole("button", { name: "Resolver" }));
    const d = screen.getByRole("dialog", { name: /Resolver el pago/ });
    await userEvent.click(within(d).getByLabelText("No salió"));
    await userEvent.type(within(d).getByRole("textbox"), "No figura en el extracto");
    await userEvent.click(within(d).getByRole("button", { name: "Registrar" }));
    expect(api.resolverPago).toHaveBeenCalledWith(3, 11, "FALLIDO", "No figura en el extracto");
  });

  it("muestra el error del servidor", async () => {
    api.aprobarLote.mockRejectedValue({ response: { data: { detail: "El lote cambió." } } });
    montar(BASE);
    await userEvent.click(await screen.findByRole("button", { name: /Aprobar/ }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Aprobar" }));
    expect(await screen.findByText("El lote cambió.")).toBeInTheDocument();
  });
});
