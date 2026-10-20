import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import TransferenciasPage from "./TransferenciasPage";
import { useAuthStore } from "../../../context/authStore";
import { listarTransferencias, crearTransferencia, getCuentas, getTransferenciasLocal } from "../../../api/interbanking";

vi.mock("../../../api/interbanking", () => ({
  listarTransferencias: vi.fn(),
  crearTransferencia: vi.fn(),
  getCuentas: vi.fn(),
  getTransferenciasLocal: vi.fn(),
}));

// Por defecto no hay envíos rechazados en el registro propio.
beforeEach(() => {
  getTransferenciasLocal.mockReset().mockResolvedValue({ data: [], total: 0 });
});

const RECHAZADA = {
  id: 10,
  cuenta_origen: "11/31554660051353/CC",
  cbu_destino: "0000003100039625101366",
  monto: "100.00",
  moneda: "ARS",
  concepto: "Prueba desde el sistema",
  status: "ERROR",
  cargado_por: "csuther",
  initiated_at: "2026-10-20T13:27:11.626274+00:00",
  motivo: "1078 - El operador no tiene acceso o no existe la cuenta crédito (confection_id 10)",
};

const CUENTA = {
  bank_id: "011",
  bank_name: "Banco Nación",
  account_number: "1234567890",
  account_label: "Operativa",
  account_type: "CC",
  currency: "ARS",
};

const TRANSFERENCIA = {
  transfer_id: "TR-1",
  request_date: "2026-02-10",
  debit_account: { bank_name: "B.N.A.", account_type: "CC", account_number: "31554660300106", account_cbu: "0".repeat(22), customer_cuit: "30999255724" },
  credit_account: { bank_name: "Banco Macro", account_type: "CA", account_number: "4001234", account_cbu: "1".repeat(22), customer_cuit: "20123456789" },
  amount: 25000,
  currency: "ARS",
  transfer_type_description: "Proveedores",
  transfer_comments: "Pago agencia 42",
  status: "ACREDITADA",
};

const CBU_DESTINO = "2".repeat(22);

const conPermiso = () =>
  useAuthStore.setState({
    token: "tok",
    user: { username: "ana" },
    permissions: {
      modules: ["interbanking"],
      actions: { interbanking: ["transferencias:read", "transferencias:write"] },
    },
  });

const soloLectura = () =>
  useAuthStore.setState({
    token: "tok",
    user: { username: "ana" },
    permissions: { modules: ["interbanking"], actions: { interbanking: ["transferencias:read"] } },
  });

const campo = (etiqueta) =>
  screen.getAllByText(etiqueta)
    .find((el) => el.tagName === "LABEL")
    .parentElement.querySelector("input, select");

async function abrirFormulario(user) {
  await user.click(screen.getByRole("button", { name: /Nueva transferencia/ }));
  return screen.getByRole("heading", { name: "Nueva Transferencia" });
}

async function completarFormulario(user, { cbu = CBU_DESTINO, monto = "1500.50", comentario = "Pago agencia" } = {}) {
  await user.selectOptions(campo("Cuenta débito"), "011|1234567890|CC");
  await user.type(campo("CBU destino"), cbu);
  await user.type(campo("Monto"), monto);
  await user.type(campo("Comentario"), comentario);
}

describe("TransferenciasPage — listado", () => {
  beforeEach(() => {
    conPermiso();
    listarTransferencias.mockResolvedValue({
      transfers: [TRANSFERENCIA],
      general_data: { total_rows: 1 },
    });
    getCuentas.mockResolvedValue({ accounts: [CUENTA] });
    crearTransferencia.mockResolvedValue({ id_operacion_ib: "IB-99", status: "INICIADA" });
  });

  it("consulta el día de hoy al montar y trae las cuentas", async () => {
    const hoy = new Date().toISOString().slice(0, 10);
    render(<TransferenciasPage />);
    await waitFor(() =>
      expect(listarTransferencias).toHaveBeenCalledWith({ date_since: hoy, date_until: hoy, page: 0, rows: 500 })
    );
    expect(getCuentas).toHaveBeenCalledTimes(1);
  });

  it("lista las transferencias del rango", async () => {
    render(<TransferenciasPage />);
    expect(await screen.findByText("TR-1")).toBeInTheDocument();
    expect(screen.getByText("Pago agencia 42")).toBeInTheDocument();
    expect(within(screen.getByText("TR-1").closest("tr")).getByText("ACREDITADA")).toBeInTheDocument();
    expect(screen.getByText("1 resultados")).toBeInTheDocument();
    expect(screen.getByText("ARS 25.000,00")).toBeInTheDocument();
  });

  it("trae todas las páginas del rango, no sólo la primera", async () => {
    const tr = (id) => ({ ...TRANSFERENCIA, transfer_id: id });
    listarTransferencias
      .mockResolvedValueOnce({ transfers: [tr("P0-A"), tr("P0-B")], general_data: { total_rows: 3 } })
      .mockResolvedValueOnce({ transfers: [tr("P1-A")], general_data: { total_rows: 3 } });
    render(<TransferenciasPage />);
    expect(await screen.findByText("P1-A")).toBeInTheDocument();
    expect(screen.getByText("P0-A")).toBeInTheDocument();
    expect(listarTransferencias).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, rows: 500 }));
  });

  describe("paginador", () => {
    const muchas = (n) => Array.from({ length: n }, (_, i) => ({ ...TRANSFERENCIA, transfer_id: `T-${i + 1}` }));
    const ids = () => screen.getAllByRole("row").slice(2).map((f) => within(f).getAllByRole("cell")[1].textContent);

    it("muestra 50 por página y navega entre páginas", async () => {
      const user = userEvent.setup();
      listarTransferencias.mockResolvedValue({ transfers: muchas(120), general_data: { total_rows: 120 } });
      render(<TransferenciasPage />);
      await screen.findByText("T-1");
      expect(ids()).toHaveLength(50);
      expect(screen.getByText("1–50 de 120")).toBeInTheDocument();
      expect(screen.getByText("Página 1 de 3")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "‹ Anterior" })).toBeDisabled();

      await user.click(screen.getByRole("button", { name: "Siguiente ›" }));
      expect(ids()[0]).toBe("T-51");
      await user.click(screen.getByRole("button", { name: "Siguiente ›" }));
      expect(ids()).toHaveLength(20);
      expect(screen.getByText("101–120 de 120")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Siguiente ›" })).toBeDisabled();
    });

    it("cambia la cantidad por página y vuelve a la primera al filtrar", async () => {
      const user = userEvent.setup();
      listarTransferencias.mockResolvedValue({ transfers: muchas(120), general_data: { total_rows: 120 } });
      render(<TransferenciasPage />);
      await screen.findByText("T-1");
      await user.selectOptions(screen.getByLabelText("Filas por página"), "25");
      expect(screen.getByText("Página 1 de 5")).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Siguiente ›" }));
      expect(ids()[0]).toBe("T-26");

      fireEvent.change(screen.getByLabelText("Filtrar ID"), { target: { value: "T-11" } });
      expect(ids()).toEqual(["T-11", "T-110", "T-111", "T-112", "T-113", "T-114", "T-115", "T-116", "T-117", "T-118", "T-119"]);
      expect(screen.getByText("Página 1 de 1")).toBeInTheDocument();
    });
  });

  describe("filtros por columna", () => {
    const OTRA = {
      transfer_id: "TR-2",
      request_date: "2026-02-11T09:00:00",
      debit_account: { bank_name: "B.N.A.", account_type: "CC", account_number: "31554660052053", account_cbu: "3".repeat(22) },
      credit_account: { bank_name: "Banco Galicia", account_type: "CC", account_number: "9998887", account_cbu: "4".repeat(22) },
      amount: 1200000,
      currency: "ARS",
      transfer_type_description: "Cuentas Propias",
      transfer_comments: "HABERES SETIEMBRE",
      status: "Anulada",
    };

    beforeEach(() => {
      listarTransferencias.mockResolvedValue({ transfers: [TRANSFERENCIA, OTRA], general_data: { total_rows: 2 } });
    });

    const filas = () => screen.getAllByRole("row").slice(2).map((f) => f.textContent);
    const filtrar = (columna, valor) => fireEvent.change(screen.getByLabelText(`Filtrar ${columna}`), { target: { value: valor } });

    it.each([
      ["Fecha", "02-11", "TR-2"],
      ["ID", "tr-1", "TR-1"],
      ["Origen", "52053", "TR-2"],
      ["Destino", "macro", "TR-1"],
      ["Destino", "1".repeat(22), "TR-1"],
      ["Comentario", "haberes", "TR-2"],
      ["Comentario", "proveedores", "TR-1"],
    ])("%s = %s deja sólo %s", async (columna, valor, queda) => {
      render(<TransferenciasPage />);
      await screen.findByText("TR-2");
      filtrar(columna, valor);
      expect(filas()).toHaveLength(1);
      expect(filas()[0]).toContain(queda);
      expect(screen.getByText("1 de 2 resultados")).toBeInTheDocument();
    });

    it("filtra el monto por rango, también con formato local", async () => {
      render(<TransferenciasPage />);
      await screen.findByText("TR-2");
      filtrar("Monto desde", "100.000");
      expect(filas()).toHaveLength(2); // "100.000" sin coma = 100: entran las dos
      filtrar("Monto desde", "100.000,00");
      expect(filas()).toHaveLength(1);
      expect(filas()[0]).toContain("TR-2");
      filtrar("Monto desde", "");
      filtrar("Monto hasta", "30000");
      expect(filas()[0]).toContain("TR-1");
      expect(filas()).toHaveLength(1);
    });

    it("filtra por estado con los estados que vinieron y limpia todo", async () => {
      const user = userEvent.setup();
      render(<TransferenciasPage />);
      await screen.findByText("TR-2");
      await user.selectOptions(screen.getByLabelText("Filtrar Estado"), "Anulada");
      expect(filas()).toHaveLength(1);
      expect(filas()[0]).toContain("TR-2");
      await user.click(screen.getByRole("button", { name: "Limpiar filtros" }));
      expect(filas()).toHaveLength(2);
    });

    it("avisa cuando ninguna coincide", async () => {
      render(<TransferenciasPage />);
      await screen.findByText("TR-2");
      filtrar("ID", "no-existe");
      expect(screen.getByText("Ninguna transferencia coincide con los filtros")).toBeInTheDocument();
    });
  });

  it("muestra de qué cuenta sale y a qué cuenta va cada transferencia", async () => {
    render(<TransferenciasPage />);
    const fila = (await screen.findByText("TR-1")).closest("tr");
    const [, , origen, destino] = within(fila).getAllByRole("cell");
    expect(origen).toHaveTextContent("B.N.A.");
    expect(origen).toHaveTextContent("CC 31554660300106");
    expect(origen).toHaveTextContent(`CBU ${"0".repeat(22)}`);
    expect(origen).toHaveTextContent("CUIT 30999255724");
    expect(destino).toHaveTextContent("Banco Macro");
    expect(destino).toHaveTextContent("CA 4001234");
    expect(destino).toHaveTextContent(`CBU ${"1".repeat(22)}`);
    expect(within(fila).getByText("Proveedores")).toBeInTheDocument();
  });

  it("prefiere _status y rellena con guiones lo que falta", async () => {
    listarTransferencias.mockResolvedValue({
      transfers: [{ transfer_id: "TR-2", _status: "PROCESANDO", status: "INICIADA" }],
      general_data: {},
    });
    render(<TransferenciasPage />);
    const fila = (await screen.findByText("TR-2")).closest("tr");
    expect(within(fila).getByText("PROCESANDO")).toBeInTheDocument();
    expect(within(fila).queryByText("INICIADA")).not.toBeInTheDocument();
    expect(within(fila).getAllByText("—")).toHaveLength(3);   // origen, destino y comentario
  });

  it("avisa cuando no hay transferencias en el rango", async () => {
    listarTransferencias.mockResolvedValue({ transfers: [], general_data: {} });
    render(<TransferenciasPage />);
    expect(await screen.findByText("Sin transferencias en el rango")).toBeInTheDocument();
  });

  it("marca el listado como MOCK cuando lo indica el backend", async () => {
    listarTransferencias.mockResolvedValue({ transfers: [], general_data: {}, mock: true });
    render(<TransferenciasPage />);
    expect(await screen.findByText("MOCK")).toBeInTheDocument();
  });

  it("vuelve a consultar con el rango elegido", async () => {
    const user = userEvent.setup();
    render(<TransferenciasPage />);
    await screen.findByText("TR-1");

    fireEvent.change(campo("Desde"), { target: { value: "2026-01-01" } });
    fireEvent.change(campo("Hasta"), { target: { value: "2026-01-31" } });
    await user.click(screen.getByRole("button", { name: /Consultar/ }));

    await waitFor(() =>
      expect(listarTransferencias).toHaveBeenLastCalledWith({
        date_since: "2026-01-01", date_until: "2026-01-31", page: 0, rows: 500,
      })
    );
  });

  it("muestra el detalle del backend cuando falla el listado", async () => {
    listarTransferencias.mockRejectedValue({ response: { data: { detail: "Token vencido" } } });
    render(<TransferenciasPage />);
    expect(await screen.findByText("Token vencido")).toBeInTheDocument();
  });

  it("aplana el detail de un 422 de FastAPI", async () => {
    listarTransferencias.mockRejectedValue({
      response: { data: { detail: [{ loc: ["query", "date_since"], msg: "formato inválido" }] } },
    });
    render(<TransferenciasPage />);
    expect(await screen.findByText("query.date_since - formato inválido")).toBeInTheDocument();
  });

  it("mensaje genérico si el error no trae detail", async () => {
    listarTransferencias.mockRejectedValue(new Error("sin red"));
    render(<TransferenciasPage />);
    expect(await screen.findByText("Error al listar transferencias")).toBeInTheDocument();
  });
});

describe("TransferenciasPage — transferencias que dieron error", () => {
  beforeEach(() => {
    conPermiso();
    listarTransferencias.mockResolvedValue({ transfers: [TRANSFERENCIA], general_data: { total_rows: 1 } });
    getCuentas.mockResolvedValue({ accounts: [] });
    getTransferenciasLocal.mockResolvedValue({ data: [RECHAZADA], total: 1 });
  });

  it("las trae del registro propio para el mismo rango y muestra el motivo", async () => {
    const hoy = new Date().toISOString().slice(0, 10);
    render(<TransferenciasPage />);
    const fila = (await screen.findByText("Intento 10")).closest("tr");

    expect(getTransferenciasLocal).toHaveBeenCalledWith(
      expect.objectContaining({ status: "ERROR", date_since: hoy, date_until: hoy }));
    expect(within(fila).getByText("ERROR")).toBeInTheDocument();
    expect(within(fila).getByText(/1078 - El operador no tiene acceso/)).toBeInTheDocument();
    expect(fila).toHaveTextContent("2026-10-20");
    expect(fila).toHaveTextContent("Banco 11 · CC 31554660051353");
    expect(fila).toHaveTextContent("CBU 0000003100039625101366");
    expect(fila).toHaveTextContent("ARS 100,00");
    expect(fila).toHaveTextContent("Cargó: csuther");
    expect(screen.getByText("TR-1")).toBeInTheDocument();
    expect(screen.getByText("2 resultados")).toBeInTheDocument();
  });

  it("el filtro de estado deja ver sólo las que dieron error", async () => {
    const user = userEvent.setup();
    render(<TransferenciasPage />);
    await screen.findByText("Intento 10");

    await user.selectOptions(screen.getByLabelText("Filtrar Estado"), "ERROR");
    expect(screen.queryByText("TR-1")).not.toBeInTheDocument();
    expect(screen.getByText("Intento 10")).toBeInTheDocument();
  });

  it("filtra por el motivo del error", async () => {
    const user = userEvent.setup();
    render(<TransferenciasPage />);
    await screen.findByText("Intento 10");

    await user.type(screen.getByLabelText("Filtrar Motivo del error"), "1078");
    expect(screen.getByText("Intento 10")).toBeInTheDocument();
    expect(screen.queryByText("TR-1")).not.toBeInTheDocument();

    await user.clear(screen.getByLabelText("Filtrar Motivo del error"));
    await user.type(screen.getByLabelText("Filtrar Motivo del error"), "1005");
    expect(screen.queryByText("Intento 10")).not.toBeInTheDocument();
  });

  it("se pueden ocultar", async () => {
    const user = userEvent.setup();
    render(<TransferenciasPage />);
    await screen.findByText("Intento 10");

    await user.click(screen.getByLabelText("Incluir las que dieron error"));
    await waitFor(() => expect(screen.queryByText("Intento 10")).not.toBeInTheDocument());
    expect(screen.getByText("TR-1")).toBeInTheDocument();
    expect(screen.queryByLabelText("Filtrar Motivo del error")).not.toBeInTheDocument();
  });
});

describe("TransferenciasPage — permisos", () => {
  beforeEach(() => {
    listarTransferencias.mockResolvedValue({ transfers: [], general_data: {} });
    getCuentas.mockResolvedValue({ accounts: [CUENTA] });
  });

  it("sin transferencias:write no se ofrece el alta", async () => {
    soloLectura();
    render(<TransferenciasPage />);
    await screen.findByText("Sin transferencias en el rango");
    expect(screen.queryByRole("button", { name: /Nueva transferencia/ })).not.toBeInTheDocument();
  });

  it("con transferencias:write aparece el botón de alta", async () => {
    conPermiso();
    render(<TransferenciasPage />);
    expect(await screen.findByRole("button", { name: /Nueva transferencia/ })).toBeInTheDocument();
  });
});

describe("TransferenciasPage — alta de transferencia", () => {
  beforeEach(() => {
    conPermiso();
    listarTransferencias.mockResolvedValue({ transfers: [], general_data: {} });
    getCuentas.mockResolvedValue({ accounts: [CUENTA] });
    crearTransferencia.mockResolvedValue({ id_operacion_ib: "IB-99", status: "INICIADA" });
  });

  it("abre y cierra el modal", async () => {
    const user = userEvent.setup();
    render(<TransferenciasPage />);
    await screen.findByText("Sin transferencias en el rango");

    await abrirFormulario(user);
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("heading", { name: "Nueva Transferencia" })).not.toBeInTheDocument();
  });

  it("al elegir la cuenta débito completa banco, tipo y moneda", async () => {
    const user = userEvent.setup();
    render(<TransferenciasPage />);
    await screen.findByText("Sin transferencias en el rango");
    await abrirFormulario(user);

    await user.selectOptions(campo("Cuenta débito"), "011|1234567890|CC");
    expect(screen.getByText(/Cuenta: 1234567890 · Tipo: CC/)).toBeInTheDocument();
    expect(screen.getByText(/BCRA: 011/)).toBeInTheDocument();
  });

  it("no deja confirmar con un CBU de menos de 22 dígitos", async () => {
    const user = userEvent.setup();
    render(<TransferenciasPage />);
    await screen.findByText("Sin transferencias en el rango");
    await abrirFormulario(user);

    await completarFormulario(user, { cbu: "12345" });
    expect(screen.getByRole("button", { name: "Crear transferencia" })).toBeDisabled();
  });

  it("descarta los caracteres no numéricos del CBU destino", async () => {
    const user = userEvent.setup();
    render(<TransferenciasPage />);
    await screen.findByText("Sin transferencias en el rango");
    await abrirFormulario(user);

    await user.type(campo("CBU destino"), "01-70 ab99");
    expect(campo("CBU destino")).toHaveValue("017099");
  });

  it("no deja confirmar sin comentario", async () => {
    const user = userEvent.setup();
    render(<TransferenciasPage />);
    await screen.findByText("Sin transferencias en el rango");
    await abrirFormulario(user);

    await user.selectOptions(campo("Cuenta débito"), "011|1234567890|CC");
    await user.type(campo("CBU destino"), CBU_DESTINO);
    await user.type(campo("Monto"), "100");
    expect(screen.getByRole("button", { name: "Crear transferencia" })).toBeDisabled();
  });

  it("crea la transferencia, muestra el comprobante y recarga el listado", async () => {
    const user = userEvent.setup();
    render(<TransferenciasPage />);
    await screen.findByText("Sin transferencias en el rango");
    await abrirFormulario(user);
    await completarFormulario(user);

    await user.click(screen.getByRole("button", { name: "Crear transferencia" }));

    await waitFor(() => expect(crearTransferencia).toHaveBeenCalledTimes(1));
    expect(crearTransferencia).toHaveBeenCalledWith({
      cuenta_debito_account_number: "1234567890",
      cuenta_debito_account_type: "CC",
      cuenta_debito_bank_id: "011",
      cbu_destino: CBU_DESTINO,
      monto: 1500.5,
      moneda: "ARS",
      comentario: "Pago agencia",
    });

    expect(await screen.findByText("Transferencia creada")).toBeInTheDocument();
    expect(screen.getByText(/IB-99/)).toBeInTheDocument();
    expect(screen.getByText(/INICIADA/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Nueva Transferencia" })).not.toBeInTheDocument();
    await waitFor(() => expect(listarTransferencias).toHaveBeenCalledTimes(2));
  });

  it("el comprobante se puede cerrar", async () => {
    const user = userEvent.setup();
    render(<TransferenciasPage />);
    await screen.findByText("Sin transferencias en el rango");
    await abrirFormulario(user);
    await completarFormulario(user);
    await user.click(screen.getByRole("button", { name: "Crear transferencia" }));
    await screen.findByText("Transferencia creada");

    await user.click(screen.getByRole("button", { name: "Cerrar" }));
    expect(screen.queryByText("Transferencia creada")).not.toBeInTheDocument();
  });

  it("muestra el error del backend al crear", async () => {
    crearTransferencia.mockRejectedValue({ response: { data: { detail: "Saldo insuficiente" } } });
    const user = userEvent.setup();
    render(<TransferenciasPage />);
    await screen.findByText("Sin transferencias en el rango");
    await abrirFormulario(user);
    await completarFormulario(user);

    await user.click(screen.getByRole("button", { name: "Crear transferencia" }));
    expect(await screen.findByText("Saldo insuficiente")).toBeInTheDocument();
    expect(screen.queryByText("Transferencia creada")).not.toBeInTheDocument();
  });

  it("mensaje genérico si el error de alta no trae detail", async () => {
    crearTransferencia.mockRejectedValue(new Error("sin red"));
    const user = userEvent.setup();
    render(<TransferenciasPage />);
    await screen.findByText("Sin transferencias en el rango");
    await abrirFormulario(user);
    await completarFormulario(user);

    await user.click(screen.getByRole("button", { name: "Crear transferencia" }));
    expect(await screen.findByText("Error al crear transferencia")).toBeInTheDocument();
  });

  it("si no se pudieron traer las cuentas avisa cómo cargarlas", async () => {
    getCuentas.mockRejectedValue(new Error("sin red"));
    const user = userEvent.setup();
    render(<TransferenciasPage />);
    await screen.findByText("Sin transferencias en el rango");
    await abrirFormulario(user);

    expect(screen.getByText(/No hay cuentas cargadas/)).toBeInTheDocument();
  });

  it("acepta las cuentas devueltas como array plano", async () => {
    getCuentas.mockResolvedValue([CUENTA]);
    const user = userEvent.setup();
    render(<TransferenciasPage />);
    await screen.findByText("Sin transferencias en el rango");
    await abrirFormulario(user);

    expect(screen.queryByText(/No hay cuentas cargadas/)).not.toBeInTheDocument();
    expect(within(campo("Cuenta débito")).getAllByRole("option")).toHaveLength(2);
  });

  it("cada cuenta del combo empieza por su número", async () => {
    getCuentas.mockResolvedValue([CUENTA, { ...CUENTA, account_number: "9876543210", account_label: "" }]);
    const user = userEvent.setup();
    render(<TransferenciasPage />);
    await screen.findByText("Sin transferencias en el rango");
    await abrirFormulario(user);

    const textos = within(campo("Cuenta débito")).getAllByRole("option").slice(1).map((o) => o.textContent);
    expect(textos).toEqual(["1234567890 · Operativa · Banco Nación · CC (ARS)", "9876543210 · Banco Nación · CC (ARS)"]);
  });
});
