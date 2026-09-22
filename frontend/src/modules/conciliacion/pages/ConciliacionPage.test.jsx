import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ConciliacionPage from "./ConciliacionPage";
import { useAuthStore } from "../../../context/authStore";
import * as conciliacionApi from "../../../api/conciliacion";

vi.mock("../../../api/conciliacion", () => ({
  getConciliacion: vi.fn(),
  getSummary: vi.fn(),
  getAgencies: vi.fn(),
  updateRecord: vi.fn(),
  assignAgency: vi.fn(),
  removeLink: vi.fn(),
  downloadBoleta: vi.fn(),
  addAdjustment: vi.fn(),
}));

const HOY = new Date().toISOString().slice(0, 10);

const REGISTRO_A_VERIFICAR = {
  id: 1,
  agency_legal_name: "Agencia Norte SA",
  agency_number: "0001",
  tax_id: "30-11111111-9",
  importe_adeudado: 1000,
  importe_premios: 200,
  importe_depositado: 800,
  importe_neto: 0,
  status: "A_VERIFICAR",
  has_liquidacion: false,
  links: [],
};

const REGISTRO_CONSOLIDADO = {
  id: 2,
  agency_legal_name: null,
  agency_number: null,
  tax_id: null,
  importe_adeudado: 5000,
  importe_premios: 100,
  importe_depositado: 4000,
  importe_neto: 900,
  status: "CONSOLIDADO",
  has_liquidacion: true,
  links: [
    { id: 77, ib_transaction_id: "tx-9", ib_transaction_type: "transfer", ib_amount: 4000 },
    { id: 78, ib_transaction_id: "tx-10", ib_transaction_type: "batch_item", ib_amount: null },
  ],
};

const TX_SIN_ASIGNAR = {
  type: "transfer",
  id: 10,
  cbu: "0170055120000000123456",
  amount: 4000,
  concepto: "Deposito semanal de la agencia 0001 correspondiente a septiembre",
  resolved_legal_name: null,
  match_type: null,
  date: "2026-09-19",
};

const TX_ASIGNADA = {
  type: "batch_item",
  id: 11,
  cbu: null,
  amount: null,
  concepto: null,
  resolved_legal_name: "Agencia Sur SRL",
  match_type: "CBU_EXACTO",
};

const RESUMEN = {
  A_VERIFICAR: 3,
  CONSOLIDADO: 2,
  CONSOLIDADO_MANUAL: 1,
  total_importe_adeudado: 6000,
  total_importe_neto: 900,
  total_importe_depositado: 4800,
};

const AGENCIAS = [
  { client_id: 5, agency_number: "0001", legal_name: "Agencia Norte SA" },
  { client_id: 6, agency_number: "0002", legal_name: "Agencia Sur SRL" },
];

function datos({ records = [REGISTRO_A_VERIFICAR, REGISTRO_CONSOLIDADO], txs = [TX_SIN_ASIGNAR, TX_ASIGNADA] } = {}) {
  conciliacionApi.getConciliacion.mockResolvedValue({
    reconciliation_records: records,
    interbanking_transactions: txs,
  });
  conciliacionApi.getSummary.mockResolvedValue(RESUMEN);
  conciliacionApi.getAgencies.mockResolvedValue(AGENCIAS);
}

function sesion(acciones = ["read", "write", "download"]) {
  useAuthStore.setState({
    token: "tok",
    user: { username: "ana", full_name: "Ana" },
    permissions: { modules: ["conciliacion"], actions: { conciliacion: acciones } },
  });
}

function montar() {
  return render(
    <MemoryRouter>
      <ConciliacionPage />
    </MemoryRouter>
  );
}

/** Monta, espera la carga inicial y abre el panel del registro indicado. */
async function abrirRegistro(user, nombre) {
  montar();
  const celda = await screen.findByText(nombre);
  await user.click(celda);
  return screen.getByText("Detalle Registro");
}

describe("ConciliacionPage · carga inicial", () => {
  beforeEach(() => {
    sesion();
    datos();
  });

  it("pide los datos de hoy y muestra el resumen", async () => {
    montar();

    await waitFor(() => expect(conciliacionApi.getConciliacion).toHaveBeenCalledWith(HOY));
    expect(conciliacionApi.getSummary).toHaveBeenCalledWith(HOY);
    expect(conciliacionApi.getAgencies).toHaveBeenCalled();

    expect(await screen.findByText("$ 6.000,00")).toBeInTheDocument();
    const aVerificar = screen.getByText("A Verificar").parentElement;
    expect(within(aVerificar).getByText("3")).toBeInTheDocument();
  });

  it("lista los registros con sus importes y estados", async () => {
    montar();

    expect(await screen.findByText("Agencia Norte SA")).toBeInTheDocument();
    expect(screen.getByText("0001")).toBeInTheDocument();
    expect(screen.getAllByText("A_VERIFICAR")[0]).toBeInTheDocument();
    expect(screen.getByText("CONSOLIDADO")).toBeInTheDocument();
    // el registro sin agencia muestra guiones y el badge LIQ
    expect(screen.getByText("LIQ")).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("lista las transacciones interbanking recortando CBU y concepto", async () => {
    montar();

    expect(await screen.findByText("0170055120...")).toBeInTheDocument();
    expect(screen.getByText("Deposito semanal de ...")).toBeInTheDocument();
    expect(screen.getByText("Sin asignar")).toBeInTheDocument();
    expect(screen.getByText("Agencia Sur SRL")).toBeInTheDocument();
    expect(screen.getByText("CBU_EXACTO")).toBeInTheDocument();
    expect(screen.getByText("transfer")).toBeInTheDocument();
    expect(screen.getByText("batch_item")).toBeInTheDocument();
  });

  it("muestra los estados vacíos cuando no hay datos del día", async () => {
    datos({ records: [], txs: [] });
    montar();

    expect(await screen.findByText("Sin registros")).toBeInTheDocument();
    expect(screen.getByText("Sin transacciones")).toBeInTheDocument();
  });

  it("recarga al cambiar la fecha y con el botón Cargar", async () => {
    const user = userEvent.setup();
    const { container } = montar();
    await screen.findByText("Agencia Norte SA");

    fireEvent.change(container.querySelector('input[type="date"]'), {
      target: { value: "2026-01-15" },
    });
    await waitFor(() => expect(conciliacionApi.getConciliacion).toHaveBeenCalledWith("2026-01-15"));

    await user.click(screen.getByRole("button", { name: "Cargar" }));
    await waitFor(() => expect(conciliacionApi.getConciliacion).toHaveBeenCalledTimes(3));
  });
});

describe("ConciliacionPage · errores de carga", () => {
  beforeEach(() => sesion());

  it("muestra el detalle que informa la API", async () => {
    conciliacionApi.getConciliacion.mockRejectedValue({
      response: { data: { detail: "Fecha fuera de rango" } },
    });
    conciliacionApi.getSummary.mockResolvedValue(RESUMEN);
    conciliacionApi.getAgencies.mockResolvedValue([]);
    montar();

    expect(await screen.findByText("Fecha fuera de rango")).toBeInTheDocument();
    expect(screen.getByText("Sin registros")).toBeInTheDocument();
  });

  it("si el error no trae detalle muestra un mensaje genérico", async () => {
    conciliacionApi.getConciliacion.mockRejectedValue(new Error("sin red"));
    conciliacionApi.getSummary.mockResolvedValue(RESUMEN);
    conciliacionApi.getAgencies.mockResolvedValue([]);
    montar();

    expect(await screen.findByText("Error al cargar datos")).toBeInTheDocument();
  });
});

describe("ConciliacionPage · panel del registro", () => {
  beforeEach(() => {
    sesion();
    datos();
  });

  it("abre el detalle del registro y lo cierra con la X", async () => {
    const user = userEvent.setup();
    await abrirRegistro(user, "Agencia Norte SA");

    expect(screen.getByText("30-11111111-9")).toBeInTheDocument();
    expect(screen.getByDisplayValue("1000")).toBeInTheDocument();
    expect(screen.getByDisplayValue("200")).toBeInTheDocument();

    const panel = screen.getByText("Detalle Registro").closest("div");
    await user.click(within(panel).getByRole("button"));
    expect(screen.queryByText("Detalle Registro")).not.toBeInTheDocument();
  });

  it("avisa que los importes vienen de Liquidaciones y lista los vínculos", async () => {
    const user = userEvent.setup();
    await abrirRegistro(user, "CONSOLIDADO");

    expect(
      screen.getByText(/cargados automáticamente desde el módulo de Liquidaciones/)
    ).toBeInTheDocument();
    expect(screen.getByText("Transacciones vinculadas")).toBeInTheDocument();
    expect(screen.getByText("tx-9")).toBeInTheDocument();
    expect(screen.getByText("tx-10")).toBeInTheDocument();
    // sólo el vínculo con importe lo muestra
    expect(screen.getAllByText("$ 4.000,00").length).toBeGreaterThan(0);
  });

  it("sin permiso de escritura no ofrece editar, ajustar ni desvincular", async () => {
    sesion(["read"]);
    const user = userEvent.setup();
    await abrirRegistro(user, "CONSOLIDADO");

    expect(screen.queryByText("Editar importes")).not.toBeInTheDocument();
    expect(screen.queryByText("Ajuste manual")).not.toBeInTheDocument();
    expect(screen.queryByTitle("Eliminar vínculo")).not.toBeInTheDocument();
    // el detalle en sí sigue visible
    expect(screen.getByText("Transacciones vinculadas")).toBeInTheDocument();
  });

  it("con permiso de escritura guarda los importes editados y cierra el panel", async () => {
    conciliacionApi.updateRecord.mockResolvedValue({});
    const user = userEvent.setup();
    await abrirRegistro(user, "Agencia Norte SA");

    const adeudado = screen.getByDisplayValue("1000");
    await user.clear(adeudado);
    await user.type(adeudado, "1500");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() =>
      expect(conciliacionApi.updateRecord).toHaveBeenCalledWith(1, {
        importe_adeudado: 1500,
        importe_premios: 200,
      })
    );
    await waitFor(() => expect(screen.queryByText("Detalle Registro")).not.toBeInTheDocument());
    expect(conciliacionApi.getConciliacion).toHaveBeenCalledTimes(2);
  });

  it("muestra el error de la API al guardar y deja el panel abierto", async () => {
    conciliacionApi.updateRecord.mockRejectedValue({
      response: { data: { detail: "El registro está consolidado" } },
    });
    const user = userEvent.setup();
    await abrirRegistro(user, "Agencia Norte SA");

    await user.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByText("El registro está consolidado")).toBeInTheDocument();
    expect(screen.getByText("Detalle Registro")).toBeInTheDocument();
  });

  it("si el error al guardar no trae detalle usa el mensaje genérico", async () => {
    conciliacionApi.updateRecord.mockRejectedValue(new Error("timeout"));
    const user = userEvent.setup();
    await abrirRegistro(user, "Agencia Norte SA");

    await user.click(screen.getByRole("button", { name: "Guardar" }));
    expect(await screen.findByText("Error al actualizar")).toBeInTheDocument();
  });
});

describe("ConciliacionPage · ajustes manuales", () => {
  beforeEach(() => {
    sesion();
    datos();
  });

  // El panel tiene 3 inputs numéricos: adeudado, premios y el importe del ajuste.
  const inputAjuste = () => screen.getAllByRole("spinbutton")[2];

  it("exige una justificación", async () => {
    const user = userEvent.setup();
    await abrirRegistro(user, "Agencia Norte SA");

    await user.click(screen.getByRole("button", { name: "Cargar ajuste" }));

    expect(await screen.findByText("Ingresá una justificación")).toBeInTheDocument();
    expect(conciliacionApi.addAdjustment).not.toHaveBeenCalled();
  });

  it("exige un importe numérico", async () => {
    const user = userEvent.setup();
    await abrirRegistro(user, "Agencia Norte SA");

    await user.type(screen.getByPlaceholderText("Motivo del ajuste"), "diferencia de caja");
    await user.click(screen.getByRole("button", { name: "Cargar ajuste" }));

    expect(await screen.findByText("Ingresá un importe válido")).toBeInTheDocument();
    expect(conciliacionApi.addAdjustment).not.toHaveBeenCalled();
  });

  it("carga el ajuste con importe negativo y recarga la grilla", async () => {
    conciliacionApi.addAdjustment.mockResolvedValue({ id: 3 });
    const user = userEvent.setup();
    await abrirRegistro(user, "Agencia Norte SA");

    await user.type(inputAjuste(), "-250.5");
    await user.type(screen.getByPlaceholderText("Motivo del ajuste"), "  diferencia de caja  ");
    await user.click(screen.getByRole("button", { name: "Cargar ajuste" }));

    await waitFor(() =>
      expect(conciliacionApi.addAdjustment).toHaveBeenCalledWith(1, -250.5, "diferencia de caja")
    );
    await waitFor(() => expect(screen.queryByText("Detalle Registro")).not.toBeInTheDocument());
    expect(conciliacionApi.getConciliacion).toHaveBeenCalledTimes(2);
  });

  it("muestra el error de la API al cargar el ajuste", async () => {
    conciliacionApi.addAdjustment.mockRejectedValue({
      response: { data: { detail: "Ajuste no permitido" } },
    });
    const user = userEvent.setup();
    await abrirRegistro(user, "Agencia Norte SA");

    await user.type(inputAjuste(), "10");
    await user.type(screen.getByPlaceholderText("Motivo del ajuste"), "ok");
    await user.click(screen.getByRole("button", { name: "Cargar ajuste" }));

    expect(await screen.findByText("Ajuste no permitido")).toBeInTheDocument();
  });

  it("si el error del ajuste no trae detalle usa el mensaje genérico", async () => {
    conciliacionApi.addAdjustment.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    await abrirRegistro(user, "Agencia Norte SA");

    await user.type(inputAjuste(), "10");
    await user.type(screen.getByPlaceholderText("Motivo del ajuste"), "ok");
    await user.click(screen.getByRole("button", { name: "Cargar ajuste" }));

    expect(await screen.findByText("Error al cargar el ajuste")).toBeInTheDocument();
  });
});

describe("ConciliacionPage · vínculos y boleta", () => {
  beforeEach(() => {
    sesion();
    datos();
  });

  it("desvincula una transacción y recarga", async () => {
    conciliacionApi.removeLink.mockResolvedValue({});
    const user = userEvent.setup();
    await abrirRegistro(user, "CONSOLIDADO");

    await user.click(screen.getAllByTitle("Eliminar vínculo")[0]);

    await waitFor(() => expect(conciliacionApi.removeLink).toHaveBeenCalledWith(77));
    await waitFor(() => expect(conciliacionApi.getConciliacion).toHaveBeenCalledTimes(2));
  });

  it("muestra el error al desvincular", async () => {
    conciliacionApi.removeLink.mockRejectedValue({
      response: { data: { detail: "Vínculo inexistente" } },
    });
    const user = userEvent.setup();
    await abrirRegistro(user, "CONSOLIDADO");

    await user.click(screen.getAllByTitle("Eliminar vínculo")[1]);
    expect(await screen.findByText("Vínculo inexistente")).toBeInTheDocument();
  });

  it("no ofrece la boleta mientras el registro está A_VERIFICAR", async () => {
    const user = userEvent.setup();
    await abrirRegistro(user, "Agencia Norte SA");

    expect(screen.queryByRole("button", { name: /Descargar Boleta/ })).not.toBeInTheDocument();
  });

  it("descarga la boleta de un registro consolidado", async () => {
    conciliacionApi.downloadBoleta.mockResolvedValue(undefined);
    const user = userEvent.setup();
    await abrirRegistro(user, "CONSOLIDADO");

    await user.click(screen.getByRole("button", { name: /Descargar Boleta/ }));
    await waitFor(() => expect(conciliacionApi.downloadBoleta).toHaveBeenCalledWith(2));
  });

  it("muestra el error si falla la descarga de la boleta", async () => {
    conciliacionApi.downloadBoleta.mockRejectedValue({
      response: { data: { detail: "Boleta no generada" } },
    });
    const user = userEvent.setup();
    await abrirRegistro(user, "CONSOLIDADO");

    await user.click(screen.getByRole("button", { name: /Descargar Boleta/ }));
    expect(await screen.findByText("Boleta no generada")).toBeInTheDocument();
  });

  it("si el error de la boleta no trae detalle usa el mensaje genérico", async () => {
    conciliacionApi.downloadBoleta.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    await abrirRegistro(user, "CONSOLIDADO");

    await user.click(screen.getByRole("button", { name: /Descargar Boleta/ }));
    expect(await screen.findByText("No se pudo descargar la boleta")).toBeInTheDocument();
  });

  it("no ofrece la boleta sin el permiso de descarga", async () => {
    // El gateway exige conciliacion:download para GET /records/{id}/boleta: sin el permiso, el
    // botón no se muestra (antes se ofrecía y el usuario se comía un 403).
    sesion(["read"]);
    const user = userEvent.setup();
    await abrirRegistro(user, "CONSOLIDADO");

    expect(screen.queryByRole("button", { name: /Descargar Boleta/ })).not.toBeInTheDocument();
  });
});

describe("ConciliacionPage · panel de la transacción", () => {
  beforeEach(() => {
    sesion();
    datos();
  });

  async function abrirTx(user, texto = "0170055120...") {
    montar();
    await user.click(await screen.findByText(texto));
    return screen.getByText("Detalle Transacción");
  }

  it("muestra el detalle completo de la transacción", async () => {
    const user = userEvent.setup();
    await abrirTx(user);

    expect(screen.getByText("2026-09-19")).toBeInTheDocument();
    expect(screen.getByText("0170055120000000123456")).toBeInTheDocument();
    expect(
      screen.getByText("Deposito semanal de la agencia 0001 correspondiente a septiembre")
    ).toBeInTheDocument();
    expect(screen.getByText("Asignación actual")).toBeInTheDocument();
  });

  it("una transacción ya asignada muestra la agencia y omite fecha y concepto", async () => {
    const user = userEvent.setup();
    await abrirTx(user, "batch_item");

    const panel = screen.getByText("Detalle Transacción").closest("div").parentElement;
    expect(within(panel).getByText("Agencia Sur SRL")).toBeInTheDocument();
    expect(within(panel).queryByText("Fecha")).not.toBeInTheDocument();
    expect(within(panel).queryByText("Concepto")).not.toBeInTheDocument();
    expect(within(panel).queryByText("Sin asignar")).not.toBeInTheDocument();
  });

  it("seleccionar una transacción cierra el detalle del registro", async () => {
    const user = userEvent.setup();
    montar();
    await user.click(await screen.findByText("Agencia Norte SA"));
    expect(screen.getByText("Detalle Registro")).toBeInTheDocument();

    await user.click(screen.getByText("0170055120..."));
    expect(screen.queryByText("Detalle Registro")).not.toBeInTheDocument();
    expect(screen.getByText("Detalle Transacción")).toBeInTheDocument();
  });

  it("el botón Confirmar arranca deshabilitado hasta elegir una agencia", async () => {
    const user = userEvent.setup();
    await abrirTx(user);

    const confirmar = screen.getByRole("button", { name: "Confirmar" });
    expect(confirmar).toBeDisabled();

    await user.selectOptions(screen.getByRole("combobox"), "5");
    expect(confirmar).toBeEnabled();
  });

  it("asigna la agencia elegida y avisa el éxito", async () => {
    conciliacionApi.assignAgency.mockResolvedValue({});
    const user = userEvent.setup();
    await abrirTx(user);

    await user.selectOptions(screen.getByRole("combobox"), "6");
    await user.click(screen.getByRole("button", { name: "Confirmar" }));

    await waitFor(() => expect(conciliacionApi.assignAgency).toHaveBeenCalledWith("transfer", 10, 6));
    expect(await screen.findByText("Agencia asignada correctamente")).toBeInTheDocument();
    expect(conciliacionApi.getConciliacion).toHaveBeenCalledTimes(2);
  });

  it("muestra el error al asignar la agencia", async () => {
    conciliacionApi.assignAgency.mockRejectedValue({
      response: { data: { detail: "CBU ya asignado" } },
    });
    const user = userEvent.setup();
    await abrirTx(user);

    await user.selectOptions(screen.getByRole("combobox"), "5");
    await user.click(screen.getByRole("button", { name: "Confirmar" }));

    expect(await screen.findByText("CBU ya asignado")).toBeInTheDocument();
    expect(screen.queryByText("Agencia asignada correctamente")).not.toBeInTheDocument();
  });

  it("si el error de asignación no trae detalle usa el mensaje genérico", async () => {
    conciliacionApi.assignAgency.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    await abrirTx(user);

    await user.selectOptions(screen.getByRole("combobox"), "5");
    await user.click(screen.getByRole("button", { name: "Confirmar" }));

    expect(await screen.findByText("Error al asignar agencia")).toBeInTheDocument();
  });

  it("sin permiso de escritura no ofrece asignar agencia", async () => {
    sesion(["read"]);
    const user = userEvent.setup();
    await abrirTx(user);

    expect(screen.queryByText("Asignar Agencia")).not.toBeInTheDocument();
  });
});
