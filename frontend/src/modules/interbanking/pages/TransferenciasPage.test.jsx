import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import TransferenciasPage from "./TransferenciasPage";
import { useAuthStore } from "../../../context/authStore";
import { listarTransferencias, crearTransferencia, getCuentas } from "../../../api/interbanking";

vi.mock("../../../api/interbanking", () => ({
  listarTransferencias: vi.fn(),
  crearTransferencia: vi.fn(),
  getCuentas: vi.fn(),
}));

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
  debit_account: { cbu: "0".repeat(22) },
  credit_account: { cbu: "1".repeat(22) },
  amount: 25000,
  currency: "ARS",
  comments: "Pago agencia 42",
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
      expect(listarTransferencias).toHaveBeenCalledWith({ date_since: hoy, date_until: hoy })
    );
    expect(getCuentas).toHaveBeenCalledTimes(1);
  });

  it("lista las transferencias del rango", async () => {
    render(<TransferenciasPage />);
    expect(await screen.findByText("TR-1")).toBeInTheDocument();
    expect(screen.getByText("Pago agencia 42")).toBeInTheDocument();
    expect(screen.getByText("ACREDITADA")).toBeInTheDocument();
    expect(screen.getByText("1 resultados")).toBeInTheDocument();
    expect(screen.getByText("ARS 25.000,00")).toBeInTheDocument();
  });

  it("prefiere _status y rellena con guiones lo que falta", async () => {
    listarTransferencias.mockResolvedValue({
      transfers: [{ transfer_id: "TR-2", _status: "PROCESANDO", status: "INICIADA" }],
      general_data: {},
    });
    render(<TransferenciasPage />);
    expect(await screen.findByText("PROCESANDO")).toBeInTheDocument();
    expect(screen.queryByText("INICIADA")).not.toBeInTheDocument();
    const fila = screen.getByText("TR-2").closest("tr");
    expect(within(fila).getAllByText("—")).toHaveLength(3);   // CBUs + comentario
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
        date_since: "2026-01-01", date_until: "2026-01-31",
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
});
