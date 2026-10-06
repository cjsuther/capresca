import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SolicitudesCreditoPage from "./SolicitudesCreditoPage";
import { creditos } from "../../../../api/creditos";
import { searchClients } from "../../../../api/clientes";
import { useAuthStore } from "../../../../context/authStore";

vi.mock("../../../../api/creditos", () => ({
  creditos: {
    ppSolicitudes: vi.fn(), ppSolicitud: vi.fn(), ppSolicitudCrear: vi.fn(), ppSolicitudEstado: vi.fn(),
    ppSolicitudPromover: vi.fn(), ppSolicitudDocs: vi.fn(), ppSolicitudDocAbrir: vi.fn(), ppSolicitudDocArchivo: vi.fn(), ppSolicitudDocsAlCliente: vi.fn(),
    ppSimPreview: vi.fn(), ppOferta: vi.fn(), ctoSegmentos: vi.fn(), ctoOriginar: vi.fn(),
  },
}));
vi.mock("../../../../api/clientes", () => ({ searchClients: vi.fn() }));

const CLIENTE = { id: 7, code: "PH-7", human_profile: { first_name: "Ana", last_name: "Perez", document_number: "30123456" } };

const SOL_EVALUACION = {
  id: "s1", numero: "SOL-1", clienteNombre: "PEREZ, ANA", solicitanteTipo: "REGISTRADO",
  monto: 1000000, plazo: 24, estado: "EN_EVALUACION", productoId: "pp_1", relacion: "ESTANDAR",
  evaluacion: { elegible: true, cuota_estimada: 62000, tna_ofrecida: 58 }, datosAdicionales: {},
};
const SOL_EXPRESS = {
  ...SOL_EVALUACION, id: "s2", numero: "SOL-2", clienteNombre: "GOMEZ, LUIS",
  solicitanteTipo: "NO_REGISTRADO", estado: "EN_EVALUACION",
};
const SOL_APROBADA = {
  ...SOL_EVALUACION, id: "s3", numero: "SOL-3", estado: "APROBADA",
  resolucion: { numero: 45, fecha: "2026-06-10" },
  datosLiquidacion: { aplica: true, lista: true, items: [{ campo: "cbu", label: "CBU", ok: true, requerido: true, valor: "000…" }], faltantes: [] },
};

const LISTA = (items) => ({
  items, estados: ["BORRADOR", "EN_EVALUACION", "APROBADA"], permisos: { edita: true, aprueba: true },
});

const SIMULACION = { cuotaPromedio: 62000, totalCuotas: 1488000, cantidadCuotas: 24, tna: 58, elegible: true, motivos: [], cuotas: [
  { numero_cuota: 1, fecha_vencimiento: "2026-04-10", capital: 30000, interes: 32000, total: 62000 },
] };

const sesion = (acciones) =>
  useAuthStore.setState({ token: "tok", user: { username: "ana" },
    permissions: { modules: ["creditos"], actions: { creditos: acciones } } });

const montar = () => render(<MemoryRouter><SolicitudesCreditoPage /></MemoryRouter>);

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["creditos:read", "creditos:write"]);
  creditos.ppSolicitudes.mockResolvedValue(LISTA([SOL_EVALUACION, SOL_EXPRESS]));
  creditos.ppOferta.mockResolvedValue({ items: [{ id: "pp_1", nombre: "PERSONAL", codigo: "CP" }] });
  creditos.ctoSegmentos.mockResolvedValue({ segmentos: ["AGENTE_PUBLICO"], canales: ["SUCURSAL"], canalBackoffice: "SUCURSAL", decimalesMostrar: 2 });
  creditos.ppSimPreview.mockResolvedValue(SIMULACION);
  creditos.ppSolicitudDocs.mockResolvedValue({ items: [] });
  creditos.ppSolicitudCrear.mockResolvedValue({ ...SOL_EVALUACION, estado: "BORRADOR" });
  creditos.ppSolicitudEstado.mockResolvedValue({ ...SOL_EVALUACION, estado: "APROBADA" });
  creditos.ppSolicitudPromover.mockResolvedValue({ solicitud: { ...SOL_EXPRESS, solicitanteTipo: "REGISTRADO" } });
  creditos.ctoOriginar.mockResolvedValue({ numeroContrato: "CTO-9" });
  searchClients.mockResolvedValue({ data: [CLIENTE] });
});

describe("Solicitudes de crédito · listado", () => {
  it("lista con estado, cuota estimada y marca de express", async () => {
    montar();
    expect(await screen.findByText("SOL-1")).toBeInTheDocument();
    expect(screen.getByText("express")).toBeInTheDocument();
    expect(screen.getAllByText("EN_EVALUACION").length).toBeGreaterThan(0);
  });

  it("filtra por estado y por texto", async () => {
    const u = userEvent.setup();
    montar();
    await screen.findByText("SOL-1");

    await u.click(screen.getByRole("button", { name: "APROBADA" }));
    await waitFor(() => expect(creditos.ppSolicitudes).toHaveBeenLastCalledWith({ estado: "APROBADA", q: "" }));

    await u.type(screen.getByLabelText("Buscar cliente o número"), "perez");
    await waitFor(() => expect(creditos.ppSolicitudes).toHaveBeenLastCalledWith({ estado: "APROBADA", q: "perez" }));
  });
});

describe("Solicitudes de crédito · deep link del inbox", () => {
  it("abre directo la solicitud que manda el Inbox de aprobaciones", async () => {
    sessionStorage.setItem("solicitud_abrir", "s3");
    creditos.ppSolicitud.mockResolvedValue({ ...SOL_APROBADA, clienteNombre: "RIOS, EVA" });
    montar();

    expect(await screen.findByRole("dialog", { name: "RIOS, EVA" })).toBeInTheDocument();
    expect(creditos.ppSolicitud).toHaveBeenCalledWith("s3");
    // se consume una sola vez: volver a la pantalla no la reabre
    expect(sessionStorage.getItem("solicitud_abrir")).toBeNull();
  });

  it("sin deep link no pide ninguna solicitud", async () => {
    montar();
    await screen.findByText("SOL-1");
    expect(creditos.ppSolicitud).not.toHaveBeenCalled();
  });
});

describe("Solicitudes de crédito · documentación adjunta", () => {
  it("los documentos del solicitante se ven dentro de la página", async () => {
    globalThis.URL.createObjectURL = vi.fn(() => "blob:dni");
    globalThis.URL.revokeObjectURL = vi.fn();
    creditos.ppSolicitudDocs.mockResolvedValue({ items: [
      { id: "doc-1", tipo: "DNI_FRENTE", nombre: "dni frente.png", tamano: 900000 },
      { id: "doc-2", tipo: "RECIBO", nombre: "recibo.pdf", tamano: 180000 },
    ] });
    creditos.ppSolicitudDocArchivo.mockResolvedValue(new Blob(["x"], { type: "image/png" }));
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-1"));
    const detalle = await screen.findByRole("dialog", { name: "PEREZ, ANA" });
    await u.click(await within(detalle).findByRole("button", { name: "dni frente.png" }));
    const visor = await screen.findByRole("dialog", { name: /DNI/ });
    expect(await within(visor).findByRole("img")).toHaveAttribute("src", "blob:dni");
    expect(creditos.ppSolicitudDocArchivo).toHaveBeenCalledWith("s1", "doc-1");
    expect(creditos.ppSolicitudDocAbrir).not.toHaveBeenCalled();   // ya no abre otra pestaña
  });
});

describe("Solicitudes de crédito · crear el cliente desde la solicitud", () => {
  const EXPRESS_PORTAL = {
    ...SOL_EXPRESS, clienteNombre: "PEREZ, JUAN CARLOS",
    clienteDatos: { apellido_nombre: "PEREZ, JUAN CARLOS", dni: "30123456", cuil: "", email: "juan@example.com" },
    datosAdicionales: { portal_email: "juan@example.com" },
  };

  beforeEach(() => {
    creditos.ppSolicitudes.mockResolvedValue(LISTA([EXPRESS_PORTAL]));
    creditos.ppSolicitudDocs.mockResolvedValue({ items: [
      { id: "doc-1", tipo: "DNI_FRENTE", nombre: "dni.png", tamano: 1000 },
      { id: "doc-2", tipo: "RECIBO", nombre: "recibo.pdf", tamano: 1000 },
    ] });
  });

  it("Crear cliente abre el alta en otra solapa y el detalle sigue a la vista", async () => {
    const abrir = vi.spyOn(window, "open").mockReturnValue(null);
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-2"));
    const detalle = await screen.findByRole("dialog", { name: "PEREZ, JUAN CARLOS" });
    await u.click(within(detalle).getByRole("button", { name: "Crear cliente" }));
    expect(abrir).toHaveBeenCalledWith("/modules/creditos/solicitudes-credito/s2/alta-cliente", "_blank");
    expect(screen.getByRole("dialog", { name: "PEREZ, JUAN CARLOS" })).toBeInTheDocument();
    abrir.mockRestore();
  });

  it("cuando la otra solapa crea el cliente, el detalle se actualiza", async () => {
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-2"));
    const detalle = await screen.findByRole("dialog", { name: "PEREZ, JUAN CARLOS" });
    const canal = new BroadcastChannel("creditos-solicitudes");
    canal.postMessage({ tipo: "cliente-vinculado", texto: "Cliente creado en el módulo Clientes y vinculado a la solicitud.",
                        clienteId: 4321, solicitud: { ...EXPRESS_PORTAL, solicitanteTipo: "REGISTRADO", clienteId: 4321 } });
    canal.close();
    expect(await within(detalle).findByRole("link", { name: "Ver ficha del cliente" })).toHaveAttribute("href", "/modules/clientes/4321");
    expect(within(detalle).queryByRole("button", { name: "Crear cliente" })).toBeNull();
  });

  it("con el cliente ya vinculado, guarda los documentos en su ficha", async () => {
    creditos.ppSolicitudes.mockResolvedValue(LISTA([{ ...EXPRESS_PORTAL, solicitanteTipo: "REGISTRADO", clienteId: 4321 }]));
    creditos.ppSolicitudDocsAlCliente.mockResolvedValue({ clienteId: 4321, guardados: 0, repetidos: 2 });
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-2"));
    const detalle = await screen.findByRole("dialog", { name: "PEREZ, JUAN CARLOS" });
    expect(within(detalle).queryByRole("button", { name: "Crear cliente" })).toBeNull();
    await u.click(await within(detalle).findByRole("button", { name: "Guardar en el cliente" }));
    expect(await within(detalle).findByText(/0 nuevo\(s\), 2 ya estaba\(n\)/)).toBeInTheDocument();
    expect(creditos.ppSolicitudDocsAlCliente).toHaveBeenCalledWith("s2");
  });
});

describe("Solicitudes de crédito · alta", () => {
  it("el asistente exige elegir cliente del padrón antes de continuar", async () => {
    const u = userEvent.setup();
    montar();
    await screen.findByText("SOL-1");

    await u.click(screen.getByRole("button", { name: /Nueva solicitud/ }));
    const modal = await screen.findByRole("dialog", { name: "Nueva solicitud" });
    expect(within(modal).getByRole("button", { name: "Continuar →" })).toBeDisabled();

    await u.type(within(modal).getByPlaceholderText(/Buscar cliente/), "perez");
    await u.click(await screen.findByText(/Perez, Ana/));
    expect(within(modal).getByRole("button", { name: "Continuar →" })).toBeEnabled();
  });

  it("simula en vivo en el paso 2 y crea la solicitud enviándola a evaluación", async () => {
    const u = userEvent.setup();
    montar();
    await screen.findByText("SOL-1");

    await u.click(screen.getByRole("button", { name: /Nueva solicitud/ }));
    const modal = await screen.findByRole("dialog", { name: "Nueva solicitud" });
    await u.type(within(modal).getByPlaceholderText(/Buscar cliente/), "perez");
    await u.click(await screen.findByText(/Perez, Ana/));
    await u.click(within(modal).getByRole("button", { name: "Continuar →" }));

    await waitFor(() => expect(creditos.ppSimPreview).toHaveBeenCalledWith("pp_1", expect.objectContaining({ monto: 1000000, plazo: 24 })));
    expect(await screen.findByText("Elegible con estos datos.")).toBeInTheDocument();

    await u.click(within(modal).getByRole("button", { name: "Continuar →" }));
    await u.click(within(modal).getByRole("button", { name: /Crear y enviar a evaluación/ }));

    await waitFor(() => expect(creditos.ppSolicitudCrear).toHaveBeenCalledWith(expect.objectContaining({
      solicitante_tipo: "REGISTRADO", cliente_id: 7, producto_id: "pp_1", monto_solicitado: 1000000,
    })));
    expect(creditos.ppSolicitudEstado).toHaveBeenCalledWith("s1", "enviar", "", "");
  });

  it("una simulación no elegible bloquea el avance", async () => {
    creditos.ppSimPreview.mockResolvedValue({ ...SIMULACION, elegible: false, motivos: ["Edad fuera de rango"] });
    const u = userEvent.setup();
    montar();
    await screen.findByText("SOL-1");

    await u.click(screen.getByRole("button", { name: /Nueva solicitud/ }));
    const modal = await screen.findByRole("dialog", { name: "Nueva solicitud" });
    await u.type(within(modal).getByPlaceholderText(/Buscar cliente/), "perez");
    await u.click(await screen.findByText(/Perez, Ana/));
    await u.click(within(modal).getByRole("button", { name: "Continuar →" }));

    expect(await screen.findByText(/Edad fuera de rango/)).toBeInTheDocument();
    expect(within(modal).getByRole("button", { name: "Continuar →" })).toBeDisabled();
  });

  it("pide la fecha de nacimiento y valida la edad que sale de ella", async () => {
    const u = userEvent.setup();
    montar();
    await screen.findByText("SOL-1");

    await u.click(screen.getByRole("button", { name: /Nueva solicitud/ }));
    const modal = await screen.findByRole("dialog", { name: "Nueva solicitud" });
    await u.type(within(modal).getByPlaceholderText(/Buscar cliente/), "perez");
    await u.click(await screen.findByText(/Perez, Ana/));

    const nac = within(modal).getByLabelText(/Fecha de nacimiento/);
    fireEvent.change(nac, { target: { value: `${new Date().getFullYear() - 15}-01-01` } });
    expect(within(modal).getByText("La edad debe estar entre 18 y 99 años.")).toBeInTheDocument();
    expect(within(modal).getByRole("button", { name: "Continuar →" })).toBeDisabled();

    fireEvent.change(nac, { target: { value: `${new Date().getFullYear() - 40}-01-01` } });
    expect(within(modal).getByText("40 años")).toBeInTheDocument();     // la edad se calcula, no se carga
    expect(within(modal).getByRole("button", { name: "Continuar →" })).toBeEnabled();
  });
});

describe("Solicitudes de crédito · resolución", () => {
  it("rechazar exige el motivo en la observación", async () => {
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-1"));

    const modal = await screen.findByRole("dialog", { name: "PEREZ, ANA" });
    await u.click(within(modal).getByRole("button", { name: "Rechazar" }));
    expect(await screen.findByText("Para rechazar, escribí el motivo en Observación.")).toBeInTheDocument();
    expect(creditos.ppSolicitudEstado).not.toHaveBeenCalled();

    await u.type(within(modal).getByLabelText(/Observación del asesor/), "no califica");
    await u.click(within(modal).getByRole("button", { name: "Rechazar" }));
    await waitFor(() => expect(creditos.ppSolicitudEstado).toHaveBeenCalledWith("s1", "rechazar", "no califica", "no califica"));
  });

  it("una express no se puede aprobar hasta vincular el cliente del padrón", async () => {
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-2"));

    const modal = await screen.findByRole("dialog", { name: "GOMEZ, LUIS" });
    expect(within(modal).getByRole("button", { name: "Aprobar" })).toBeDisabled();
    expect(within(modal).getByText(/El cliente no está en el padrón/)).toBeInTheDocument();

    await u.click(within(modal).getByRole("button", { name: "Vincular existente" }));
    const vinc = await screen.findByRole("dialog", { name: /Vincular cliente/ });
    await u.type(within(vinc).getByPlaceholderText(/Buscar cliente/), "perez");
    await u.click(await screen.findByText(/Perez, Ana/));

    await waitFor(() => expect(creditos.ppSolicitudPromover).toHaveBeenCalledWith("s2", { cliente_id: 7 }));
  });

  it("anular pide confirmación", async () => {
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-1"));

    const modal = await screen.findByRole("dialog", { name: "PEREZ, ANA" });
    await u.click(within(modal).getByRole("button", { name: "Anular" }));
    const confirmacion = await screen.findByRole("dialog", { name: "Anular solicitud" });
    expect(creditos.ppSolicitudEstado).not.toHaveBeenCalled();

    await u.click(within(confirmacion).getByRole("button", { name: "Anular" }));
    await waitFor(() => expect(creditos.ppSolicitudEstado).toHaveBeenCalledWith("s1", "anular", "", ""));
  });

  it("una aprobada no se origina sola: se origina al liquidar su lote", async () => {
    creditos.ppSolicitudes.mockResolvedValue(LISTA([{ ...SOL_APROBADA, resolucion: null,
      lote: { id: 3, codigo: "2026-0003", estado: "ABIERTO", resolucion: null } }]));
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-3"));

    const modal = await screen.findByRole("dialog", { name: "PEREZ, ANA" });
    expect(within(modal).queryByRole("button", { name: "Originar contrato" })).toBeNull();
    expect(within(modal).getByText(/Lote 2026-0003 · esperando resolución/)).toBeInTheDocument();
    expect(within(modal).getByText(/Espera que Despacho le asigne/)).toBeInTheDocument();
  });

  it("en un lote con resolución muestra el N° oficial y no se puede anular", async () => {
    creditos.ppSolicitudes.mockResolvedValue(LISTA([{ ...SOL_APROBADA,
      lote: { id: 3, codigo: "2026-0003", estado: "CON_RESOLUCION",
              resolucion: { numero: 45, anio: 2026, numeroOficial: 120, fecha: "2026-06-10" } } }]));
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-3"));

    const modal = await screen.findByRole("dialog", { name: "PEREZ, ANA" });
    expect(within(modal).getByText("Resolución N° 120/2026 · 10/6/2026")).toBeInTheDocument();
    expect(within(modal).getByText(/no se modifica/)).toBeInTheDocument();
    expect(within(modal).getByRole("link", { name: /Créditos → Lotes/ })).toHaveAttribute("href", "/modules/creditos/liquidacion-lote");
    expect(within(modal).getByRole("button", { name: "Anular" })).toBeDisabled();
  });

  it("si no se puede liquidar dice qué le falta para entrar a un lote", async () => {
    creditos.ppSolicitudes.mockResolvedValue(LISTA([{ ...SOL_APROBADA, resolucion: null, lote: null,
      faltaParaLote: ["CBU de acreditación (22 dígitos)"] }]));
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-3"));

    const modal = await screen.findByRole("dialog", { name: "PEREZ, ANA" });
    expect(within(modal).getByText(/No entra a ningún lote.*falta CBU de acreditación/)).toBeInTheDocument();
  });

  it("muestra la resolución que la otorga", async () => {
    creditos.ppSolicitudes.mockResolvedValue(LISTA([SOL_APROBADA]));
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-3"));

    const modal = await screen.findByRole("dialog", { name: "PEREZ, ANA" });
    expect(within(modal).getByText(/Resolución N° 45/)).toBeInTheDocument();
  });

  it("en sólo lectura no se ofrecen acciones", async () => {
    sesion(["creditos:read"]);
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-1"));

    expect(screen.queryByRole("button", { name: /Nueva solicitud/ })).toBeNull();
    const modal = await screen.findByRole("dialog", { name: "PEREZ, ANA" });
    expect(within(modal).getByRole("button", { name: "Aprobar" })).toBeDisabled();
    expect(within(modal).getByRole("button", { name: "Anular" })).toBeDisabled();
  });
});
