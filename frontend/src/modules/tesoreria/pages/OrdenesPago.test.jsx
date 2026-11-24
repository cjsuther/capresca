import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/tesoreria", async (orig) => ({
  ...(await orig()), listarOrdenes: vi.fn(), verOrden: vi.fn(), actosDisponibles: vi.fn(),
  confeccionarOrden: vi.fn(), anularOrden: vi.fn(), proximoNumeroOrden: vi.fn(),
}));

import {
  actosDisponibles, anularOrden, confeccionarOrden, listarOrdenes, proximoNumeroOrden, verOrden,
} from "../../../api/tesoreria";
import OrdenesPagoPage from "./OrdenesPagoPage";
import NuevaOrdenPagoPage from "./NuevaOrdenPagoPage";
import OrdenPagoPage from "./OrdenPagoPage";
import { useAuthStore } from "../../../context/authStore";

const RES = { clave: "id:7", tipo: "RES", numero: 45, anio: 2026, numeroOficial: 120, fecha: "2026-10-05", importe: 1000000 };
const DIS = { clave: "id:8", tipo: "DIS", numero: 12, anio: 2026, numeroOficial: null, fecha: "2026-10-05", importe: 500000 };
const LOTE = { id: 1, codigo: "2026-0001", producto: "PERSONAL", fecha: "2026-10-01", cantidad: 2, montoTotal: 500000,
               cerradoPor: "ana", cerradoEn: "2026-10-02T10:00:00" };
const OP = {
  id: 4, codigo: "OP-2026-00004", estado: "CONFECCIONADA", estado_pago: "PARA_APROBAR", importe: 500000, cantidad: 2,
  actos: [{ acto: RES, lotes: [LOTE], cantidad: 2, total: 500000 }], actos_texto: "Res. 120/2026", lotes: ["2026-0001"],
  lote: { id: 9, codigo: "LOT-2026-00009", estado: "PENDIENTE_APROBACION" }, creado_por: "ana", creado_en: "2026-10-06T12:00:00",
  puede_anular: true,
  pagos: [{ id: 1, beneficiario: "PEREZ JUAN", documento: "20301234569", cbu: "2850590940090418135201", monto: 300000,
            concepto: "OP-2026-00004 lote 2026-0001 Desembolso", estado: "PENDIENTE", motivo: "" }],
};

function montar(ruta, acciones = ["lotes:read", "lotes:write"]) {
  useAuthStore.setState({ token: "t", user: { username: "ana" },
                          permissions: { modules: ["tesoreria"], actions: { tesoreria: acciones } } });
  render(
    <MemoryRouter initialEntries={[ruta]}>
      <Routes>
        <Route path="/modules/tesoreria/ordenes" element={<OrdenesPagoPage />} />
        <Route path="/modules/tesoreria/ordenes/nueva" element={<NuevaOrdenPagoPage />} />
        <Route path="/modules/tesoreria/ordenes/:id" element={<OrdenPagoPage />} />
        <Route path="/modules/tesoreria/lotes/:id" element={<p>lote de pagos</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  listarOrdenes.mockResolvedValue({ items: [OP] });
  verOrden.mockResolvedValue(OP);
  actosDisponibles.mockResolvedValue({ items: [
    { acto: RES, lotes: [LOTE], cantidad: 2, total: 500000 },
    { acto: DIS, lotes: [{ ...LOTE, id: 2, codigo: "2026-0002" }], cantidad: 1, total: 100000 },
  ] });
  confeccionarOrden.mockResolvedValue(OP);
  proximoNumeroOrden.mockResolvedValue({ anio: 2026, numero: 4, codigo: "OP-2026-00004" });
  anularOrden.mockResolvedValue({ ...OP, estado: "ANULADA", estado_pago: "ANULADA", puede_anular: false,
                                  anulada_por: "ana", anulada_en: "2026-10-06T13:00:00", motivo_anulacion: "Error" });
});

describe("Órdenes de pago", () => {
  it("lista las órdenes vigentes con sus actos, lotes y estado", async () => {
    montar("/modules/tesoreria/ordenes");
    const fila = (await screen.findByText("OP-2026-00004")).closest("tr");
    expect(within(fila).getByText("Res. 120/2026")).toBeInTheDocument();
    expect(within(fila).getByText("2026-0001")).toBeInTheDocument();
    expect(within(fila).getByText("Confeccionada · por aprobar")).toBeInTheDocument();
    expect(listarOrdenes).toHaveBeenCalledWith({ estado: "CONFECCIONADA" });
  });

  it("sin permiso de carga no ofrece confeccionar", async () => {
    montar("/modules/tesoreria/ordenes", ["lotes:read"]);
    await screen.findByText("OP-2026-00004");
    expect(screen.queryByRole("button", { name: /Nueva orden de pago/ })).toBeNull();
  });

  it("confecciona con las resoluciones elegidas; las que no tienen N° oficial no se eligen", async () => {
    const u = userEvent.setup();
    montar("/modules/tesoreria/ordenes/nueva");
    expect(await screen.findByLabelText("Elegir Disp. 12/2026")).toBeDisabled();
    expect(screen.getByText(/no se paga en borrador/)).toBeInTheDocument();
    await u.click(screen.getByLabelText("Elegir Res. 120/2026"));
    expect(screen.getByText(/1 acto\(s\) · 2 transferencia\(s\)/)).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: /Confeccionar orden de pago/ }));
    const dlg = await screen.findByRole("dialog", { name: "Confeccionar la orden de pago" });
    await u.click(within(dlg).getByRole("button", { name: "Confeccionar" }));
    await waitFor(() => expect(confeccionarOrden).toHaveBeenCalledWith(["id:7"], 4));
    expect(await screen.findByText("Orden de pago OP-2026-00004")).toBeInTheDocument();
  });

  it("muestra el motivo si Créditos no deja confeccionar", async () => {
    confeccionarOrden.mockRejectedValue({ response: { data: { detail: "La orden de pago no se puede armar completa. SOL-1: falta CBU" } } });
    const u = userEvent.setup();
    montar("/modules/tesoreria/ordenes/nueva");
    await u.click(await screen.findByLabelText("Elegir Res. 120/2026"));
    await u.click(screen.getByRole("button", { name: /Confeccionar orden de pago/ }));
    await u.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Confeccionar" }));
    expect(await screen.findByText(/falta CBU/)).toBeInTheDocument();
  });

  it("el detalle lleva al lote de pagos para aprobar y pagar", async () => {
    const u = userEvent.setup();
    montar("/modules/tesoreria/ordenes/4");
    expect(await screen.findByText("PEREZ JUAN")).toBeInTheDocument();
    expect(screen.getByText(/Lote 2026-0001 \(PERSONAL, 2\)/)).toBeInTheDocument();
    await u.click(screen.getByRole("link", { name: /Aprobar y pagar/ }));
    expect(await screen.findByText("lote de pagos")).toBeInTheDocument();
  });

  it("se anula con motivo antes de pagar", async () => {
    const u = userEvent.setup();
    montar("/modules/tesoreria/ordenes/4");
    await u.click(await screen.findByRole("button", { name: /Anular orden/ }));
    const dlg = await screen.findByRole("dialog", { name: "Anular la orden OP-2026-00004" });
    const boton = within(dlg).getByRole("button", { name: "Anular orden" });
    expect(boton).toBeDisabled();
    await u.type(within(dlg).getByLabelText("Motivo"), "Error");
    await u.click(boton);
    await waitFor(() => expect(anularOrden).toHaveBeenCalledWith(4, "Error"));
    expect(await screen.findByText(/Anulada por ana/)).toBeInTheDocument();
  });

  describe("N° de orden de pago", () => {
    const elegirRes = async (u) => {
      await u.click(await screen.findByLabelText("Elegir Res. 120/2026"));
      return screen.getByLabelText("N° de orden de pago");
    };
    const confirmar = async (u) => {
      await u.click(screen.getByRole("button", { name: /Confeccionar orden de pago/ }));
      return within(await screen.findByRole("dialog", { name: "Confeccionar la orden de pago" }));
    };

    it("viene precargado con el siguiente número y muestra el código", async () => {
      const u = userEvent.setup();
      montar("/modules/tesoreria/ordenes/nueva");
      const campo = await elegirRes(u);
      await waitFor(() => expect(campo).toHaveValue(4));
      expect(screen.getByTestId("codigo-orden")).toHaveTextContent("OP-2026-00004");
      const dlg = await confirmar(u);
      expect(dlg.getByText(/Se confecciona la orden OP-2026-00004 con Res\. 120\/2026/)).toBeInTheDocument();
    });

    it("se puede cambiar antes de confirmar y se manda el elegido", async () => {
      const u = userEvent.setup();
      montar("/modules/tesoreria/ordenes/nueva");
      const campo = await elegirRes(u);
      await waitFor(() => expect(campo).toHaveValue(4));
      await u.clear(campo);
      await u.type(campo, "12");
      expect(screen.getByTestId("codigo-orden")).toHaveTextContent("OP-2026-00012");
      await u.click((await confirmar(u)).getByRole("button", { name: "Confeccionar" }));
      await waitFor(() => expect(confeccionarOrden).toHaveBeenCalledWith(["id:7"], 12));
    });

    it("vacío lo asigna Tesorería (no manda número)", async () => {
      const u = userEvent.setup();
      montar("/modules/tesoreria/ordenes/nueva");
      const campo = await elegirRes(u);
      await waitFor(() => expect(campo).toHaveValue(4));
      await u.clear(campo);
      expect(screen.getByText("Se asigna el siguiente número del año")).toBeInTheDocument();
      await u.click((await confirmar(u)).getByRole("button", { name: "Confeccionar" }));
      await waitFor(() => expect(confeccionarOrden).toHaveBeenCalledWith(["id:7"], null));
    });

    it("un número inválido no deja confeccionar", async () => {
      const u = userEvent.setup();
      montar("/modules/tesoreria/ordenes/nueva");
      const campo = await elegirRes(u);
      await waitFor(() => expect(campo).toHaveValue(4));
      await u.clear(campo);
      await u.type(campo, "0");
      expect(screen.getByRole("alert")).toHaveTextContent("entero entre 1 y 99999");
      expect(screen.getByRole("button", { name: /Confeccionar orden de pago/ })).toBeDisabled();
    });

    it("si el número ya existe muestra el 409 al lado del campo y ofrece el siguiente libre", async () => {
      confeccionarOrden.mockRejectedValueOnce({ response: { status: 409, data: { detail: "Ya existe la OP-2026-00004." } } });
      const u = userEvent.setup();
      montar("/modules/tesoreria/ordenes/nueva");
      const campo = await elegirRes(u);
      await waitFor(() => expect(campo).toHaveValue(4));
      proximoNumeroOrden.mockResolvedValue({ anio: 2026, numero: 5, codigo: "OP-2026-00005" });
      await u.click((await confirmar(u)).getByRole("button", { name: "Confeccionar" }));
      expect(await screen.findByRole("alert")).toHaveTextContent("Ya existe la OP-2026-00004.");
      expect(campo).toHaveAttribute("aria-invalid", "true");
      await u.click(await screen.findByRole("button", { name: "Usar el siguiente libre: OP-2026-00005" }));
      expect(campo).toHaveValue(5);
      expect(screen.queryByRole("alert")).toBeNull();
      await u.click((await confirmar(u)).getByRole("button", { name: "Confeccionar" }));
      await waitFor(() => expect(confeccionarOrden).toHaveBeenLastCalledWith(["id:7"], 5));
    });
  });
});
