import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/auditoria", async (orig) => ({
  ...(await orig()), listarEventos: vi.fn(), verEvento: vi.fn(), resumenAuditoria: vi.fn(),
}));

import { listarEventos, resumenAuditoria, verEvento } from "../../../api/auditoria";
import EventosPage from "./EventosPage";

const ALTA = {
  id: 2, fecha: "2026-09-22T10:05:00", usuario: "ana", usuarioId: 7, ip: "10.0.0.5", modulo: "creditos",
  operacion: "ALTA", entidad: "PPSolicitud", entidadId: "SOL-9", descripcion: "Alta en pp_solicitud",
  metodo: "POST", ruta: "/api/creditos/solicitudes", estadoHttp: 201, exito: true, origen: "MODULO",
  requestId: "req-1", cambios: { numero: [null, "SOL-9"] }, detalle: "",
};
const DENEGADO = {
  ...ALTA, id: 1, usuario: "beto", operacion: "MODIFICACION", entidad: "", entidadId: "",
  descripcion: "Acceso denegado (falta security:users:write)", estadoHttp: 403, exito: false,
  origen: "GATEWAY", cambios: {},
};
const RESUMEN = {
  total: 1234, ultimo: "2026-09-22T10:05:00", retencionDias: 1825,
  modulos: [{ valor: "creditos", cantidad: 900 }, { valor: "security", cantidad: 334 }],
  usuarios: [], operaciones: [], entidades: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  resumenAuditoria.mockResolvedValue(RESUMEN);
  listarEventos.mockResolvedValue({ items: [ALTA, DENEGADO], total: 2, limit: 50, offset: 0 });
  verEvento.mockResolvedValue({ ...ALTA, cambios: { monto: [100000, 150000], cbu: ["", "•••5201"] },
                                relacionados: [{ ...DENEGADO, id: 3, origen: "GATEWAY", exito: true }] });
});

describe("Registro de actividad", () => {
  it("muestra quién hizo qué, sobre qué registro, y lo que falló", async () => {
    render(<EventosPage />);
    const fila = (await screen.findByText("ana")).closest("tr");
    expect(within(fila).getByText("Alta")).toBeInTheDocument();
    expect(within(fila).getByText("PPSolicitud")).toBeInTheDocument();
    expect(within(fila).getByText("SOL-9")).toBeInTheDocument();
    const otra = screen.getByText("beto").closest("tr");
    expect(within(otra).getByText("falló")).toBeInTheDocument();
    expect(await screen.findByText("1.234")).toBeInTheDocument();     // total de eventos
    expect(screen.getByText("5 años")).toBeInTheDocument();           // retención
  });

  it("filtra por usuario, módulo, fechas y sólo errores", async () => {
    const u = userEvent.setup();
    render(<EventosPage />);
    await screen.findByText("ana");

    await u.type(screen.getByLabelText("Usuario"), "ana");
    await waitFor(() => expect(listarEventos).toHaveBeenLastCalledWith(
      expect.objectContaining({ usuario: "ana", limit: 50, offset: 0 })));

    await u.selectOptions(screen.getByLabelText("Módulo"), "security");
    await u.click(screen.getByLabelText(/Sólo lo que falló/));
    await waitFor(() => expect(listarEventos).toHaveBeenLastCalledWith(
      expect.objectContaining({ modulo: "security", solo_errores: true })));
  });

  it("el detalle muestra el antes y el después, con lo sensible enmascarado", async () => {
    const u = userEvent.setup();
    render(<EventosPage />);
    await u.click(await screen.findByText("ana"));

    const modal = await screen.findByRole("dialog", { name: /PPSolicitud SOL-9/ });
    expect(verEvento).toHaveBeenCalledWith(2);
    expect(within(modal).getByText("100000")).toBeInTheDocument();
    expect(within(modal).getByText("150000")).toBeInTheDocument();
    expect(within(modal).getByText("•••5201")).toBeInTheDocument();
    expect(within(modal).getByText(/Misma operación/)).toBeInTheDocument();
  });

  it("avisa si la consulta falla", async () => {
    listarEventos.mockRejectedValue({ response: { data: { detail: "Sin permiso" } } });
    render(<EventosPage />);
    expect(await screen.findByText("Sin permiso")).toBeInTheDocument();
  });
});
