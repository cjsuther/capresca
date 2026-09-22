import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AuditoriaPage from "./AuditoriaPage";
import { getAuditoria, exportAuditoria } from "../../../api/interbanking";

vi.mock("../../../api/interbanking", () => ({
  getAuditoria: vi.fn(),
  exportAuditoria: vi.fn(),
}));

const ENTRADA = {
  id: 1,
  created_at: "2026-02-10T12:00:00Z",
  username: "ana",
  user_id: 3,
  operation: "VALIDAR_CBU",
  endpoint: "/transferencias/validar",
  http_method: "POST",
  response_status: 200,
  duration_ms: 145,
  success: true,
  ip_address: "10.0.0.1",
  request_payload: { cbu: "0".repeat(22) },
  response_payload: { titular: "ACME SA" },
};

// Los <label> no están asociados por htmlFor y algunos textos se repiten en la
// cabecera de la tabla: se busca puntualmente la etiqueta del filtro.
const campo = (etiqueta) =>
  screen.getAllByText(etiqueta)
    .find((el) => el.tagName === "LABEL")
    .parentElement.querySelector("input, select");

// La celda de operación comparte texto con las opciones del filtro: se ubica la
// fila por el endpoint, que es único.
const filaDe = (endpoint) => screen.getByText(endpoint).closest("tr");

describe("AuditoriaPage", () => {
  beforeEach(() => {
    getAuditoria.mockResolvedValue({ data: [ENTRADA], total: 1 });
    exportAuditoria.mockResolvedValue({ data: new Blob(["csv"]) });
  });

  it("consulta la primera página al montar", async () => {
    render(<AuditoriaPage />);
    await waitFor(() => expect(getAuditoria).toHaveBeenCalledWith({ page: 1, per_page: 50 }));
  });

  it("muestra 'Cargando...' hasta que responde el backend", async () => {
    let resolver;
    getAuditoria.mockReturnValueOnce(new Promise((r) => { resolver = r; }));
    render(<AuditoriaPage />);
    expect(screen.getByText("Cargando...")).toBeInTheDocument();
    resolver({ data: [], total: 0 });
    expect(await screen.findByText("Sin registros")).toBeInTheDocument();
  });

  it("lista las operaciones auditadas", async () => {
    render(<AuditoriaPage />);
    await screen.findByText("/transferencias/validar");
    const fila = filaDe("/transferencias/validar");
    expect(within(fila).getByText("VALIDAR_CBU")).toBeInTheDocument();
    expect(within(fila).getByText("ana")).toBeInTheDocument();
    expect(within(fila).getByText("145")).toBeInTheDocument();
    expect(within(fila).getByText("Éxito")).toBeInTheDocument();
  });

  it("cae al user_id y a guiones cuando faltan datos", async () => {
    getAuditoria.mockResolvedValue({
      data: [{ ...ENTRADA, username: null, response_status: null, duration_ms: null, success: false }],
      total: 1,
    });
    render(<AuditoriaPage />);
    const fila = (await screen.findByText("/transferencias/validar")).closest("tr");
    expect(within(fila).getByText("3")).toBeInTheDocument();
    expect(within(fila).getByText("Error")).toBeInTheDocument();
    expect(within(fila).getAllByText("—")).toHaveLength(2);
  });

  it("avisa cuando no hay registros", async () => {
    getAuditoria.mockResolvedValue({ data: [], total: 0 });
    render(<AuditoriaPage />);
    expect(await screen.findByText("Sin registros")).toBeInTheDocument();
  });

  it("un error del backend deja la tabla vacía sin romper la pantalla", async () => {
    getAuditoria.mockRejectedValue(new Error("500"));
    render(<AuditoriaPage />);
    expect(await screen.findByText("Sin registros")).toBeInTheDocument();
  });

  it("manda los filtros completados y descarta los vacíos", async () => {
    const user = userEvent.setup();
    render(<AuditoriaPage />);
    await screen.findByText("/transferencias/validar");

    await user.type(campo("Usuario ID"), "3");
    await user.selectOptions(campo("Operación"), "OBTENER_TOKEN");
    await user.selectOptions(campo("Resultado"), "true");
    fireEvent.change(campo("Desde"), { target: { value: "2026-02-01" } });
    fireEvent.change(campo("Hasta"), { target: { value: "2026-02-28" } });
    await user.click(screen.getByRole("button", { name: "Filtrar" }));

    await waitFor(() =>
      expect(getAuditoria).toHaveBeenLastCalledWith({
        page: 1,
        per_page: 50,
        user_id: "3",
        operation: "OBTENER_TOKEN",
        success: "true",
        date_from: "2026-02-01",
        date_to: "2026-02-28",
      })
    );
  });

  // TODO(bug): AuditoriaPage.jsx:85 — "Filtrar" hace setPage(1) y load() en el mismo
  // handler. Estando en otra página, load() usa el `page` viejo capturado en el closure
  // y además el cambio de página dispara el useEffect: salen DOS consultas, la primera
  // con la página equivocada. El test fija el comportamiento actual.
  it("filtrar desde otra página dispara dos consultas, la primera con la página vieja", async () => {
    getAuditoria.mockResolvedValue({ data: [ENTRADA], total: 120 });
    const user = userEvent.setup();
    render(<AuditoriaPage />);
    await screen.findByText("/transferencias/validar");

    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await waitFor(() => expect(getAuditoria).toHaveBeenLastCalledWith({ page: 2, per_page: 50 }));

    getAuditoria.mockClear();
    await user.click(screen.getByRole("button", { name: "Filtrar" }));

    await waitFor(() => expect(getAuditoria).toHaveBeenCalledTimes(2));
    expect(getAuditoria).toHaveBeenNthCalledWith(1, { page: 2, per_page: 50 });
    expect(getAuditoria).toHaveBeenNthCalledWith(2, { page: 1, per_page: 50 });
  });

  it("sin paginación cuando hay 50 registros o menos", async () => {
    render(<AuditoriaPage />);
    await screen.findByText("/transferencias/validar");
    expect(screen.queryByRole("button", { name: "Siguiente" })).not.toBeInTheDocument();
  });

  it("pagina hacia adelante y hacia atrás", async () => {
    getAuditoria.mockResolvedValue({ data: [ENTRADA], total: 120 });
    const user = userEvent.setup();
    render(<AuditoriaPage />);
    await screen.findByText("/transferencias/validar");

    expect(screen.getByText("120 registros")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await waitFor(() => expect(getAuditoria).toHaveBeenLastCalledWith({ page: 2, per_page: 50 }));
    expect(screen.getByText("Página 2")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Anterior" }));
    await waitFor(() => expect(getAuditoria).toHaveBeenLastCalledWith({ page: 1, per_page: 50 }));
  });

  it("deshabilita 'Siguiente' en la última página", async () => {
    getAuditoria.mockResolvedValue({ data: [ENTRADA], total: 60 });
    const user = userEvent.setup();
    render(<AuditoriaPage />);
    await screen.findByText("/transferencias/validar");

    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled());
  });

  it("abre el detalle de una entrada y lo cierra con la cruz", async () => {
    const user = userEvent.setup();
    render(<AuditoriaPage />);
    await user.click(await screen.findByText("/transferencias/validar"));

    expect(await screen.findByRole("heading", { name: "VALIDAR_CBU" })).toBeInTheDocument();
    expect(screen.getByText("POST")).toBeInTheDocument();
    expect(screen.getByText("10.0.0.1")).toBeInTheDocument();
    expect(screen.getByText("145ms")).toBeInTheDocument();
    expect(screen.getByText("Request Payload")).toBeInTheDocument();
    expect(screen.getByText("Response Payload")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "×" }));
    expect(screen.queryByRole("heading", { name: "VALIDAR_CBU" })).not.toBeInTheDocument();
  });

  it("el detalle muestra el mensaje de error y omite los payloads vacíos", async () => {
    getAuditoria.mockResolvedValue({
      data: [{ ...ENTRADA, success: false, error_message: "CBU inexistente", request_payload: null, response_payload: null, ip_address: null }],
      total: 1,
    });
    const user = userEvent.setup();
    render(<AuditoriaPage />);
    await user.click(await screen.findByText("/transferencias/validar"));

    expect(await screen.findByText("CBU inexistente")).toBeInTheDocument();
    expect(screen.queryByText("Request Payload")).not.toBeInTheDocument();
    expect(screen.queryByText("Response Payload")).not.toBeInTheDocument();
  });

  it("el detalle se cierra al hacer click fuera del modal", async () => {
    const user = userEvent.setup();
    const { container } = render(<AuditoriaPage />);
    await user.click(await screen.findByText("/transferencias/validar"));
    await screen.findByRole("heading", { name: "VALIDAR_CBU" });

    await user.click(container.querySelector(".fixed.inset-0"));
    expect(screen.queryByRole("heading", { name: "VALIDAR_CBU" })).not.toBeInTheDocument();
  });
});

describe("AuditoriaPage — exportación", () => {
  let crearUrl, revocarUrl, click;

  beforeEach(() => {
    getAuditoria.mockResolvedValue({ data: [ENTRADA], total: 1 });
    exportAuditoria.mockResolvedValue({ data: new Blob(["csv"]) });
    crearUrl = vi.fn(() => "blob:auditoria");
    revocarUrl = vi.fn();
    window.URL.createObjectURL = crearUrl;
    window.URL.revokeObjectURL = revocarUrl;
    click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  });

  afterEach(() => click.mockRestore());

  it("descarga el CSV con los filtros activos", async () => {
    const user = userEvent.setup();
    render(<AuditoriaPage />);
    await screen.findByText("/transferencias/validar");

    await user.type(campo("Usuario ID"), "3");
    await user.click(screen.getByRole("button", { name: /Exportar CSV/ }));

    await waitFor(() => expect(exportAuditoria).toHaveBeenCalledWith({ user_id: "3" }));
    expect(crearUrl).toHaveBeenCalledTimes(1);
    expect(click).toHaveBeenCalledTimes(1);
    expect(revocarUrl).toHaveBeenCalledWith("blob:auditoria");
  });
});
