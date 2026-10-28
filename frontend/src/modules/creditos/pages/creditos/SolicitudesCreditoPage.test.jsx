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
    ppDatosCliente: vi.fn(), ppPreAprobado: vi.fn(), ppSolicitudEditar: vi.fn(),
    ppRequisitosLinea: vi.fn(), ppSolicitudDocSubir: vi.fn(), ppSolicitudDocQuitar: vi.fn(),
  },
}));
vi.mock("../../../../api/clientes", () => ({ searchClients: vi.fn() }));

const CLIENTE = { id: 7, code: "PH-7", human_profile: { first_name: "Ana", last_name: "Perez", document_number: "30123456" } };

const SOL_EVALUACION = {
  id: "s1", numero: "SOL-1", clienteNombre: "PEREZ, ANA", clienteCuil: "27301234564", solicitanteTipo: "REGISTRADO",
  monto: 1000000, plazo: 24, estado: "EN_EVALUACION", productoId: "pp_1", relacion: "ESTANDAR",
  productoNombre: "PERSONAL", productoCodigo: "CP",
  evaluacion: { elegible: true, cuota_estimada: 62000, tna_ofrecida: 58 }, datosAdicionales: {},
};
const SOL_EXPRESS = {
  ...SOL_EVALUACION, id: "s2", numero: "SOL-2", clienteNombre: "GOMEZ, LUIS", clienteCuil: "20289991113",
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

// Como la devuelve /contratos/oferta: las condiciones de la versión vigente vienen en `cfg`.
const LINEA = { id: "pp_1", nombre: "PERSONAL", codigo: "CP", cfg: { montoMin: 100000, montoMax: 5000000, plazoMin: 6, plazoMax: 48 } };
const CBU = "0110599520000001234567";
const PADRON = { cliente_id: 7, nombre: "PEREZ, ANA", cuil: "27301234564", fecha_nacimiento: "1980-05-10",
                 antiguedad_meses: 120, sueldo: 900000, cbu: CBU };

const sesion = (acciones) =>
  useAuthStore.setState({ token: "tok", user: { username: "ana" },
    permissions: { modules: ["creditos"], actions: { creditos: acciones } } });

/** El paso de documentación: la línea de estos tests no pide nada, se sigue de largo. */
async function pasarDocumentacion(u, modal) {
  await within(modal).findByText("Esta línea no pide documentación.");
  await u.click(within(modal).getByRole("button", { name: "Continuar →" }));
}

const montar = () => render(<MemoryRouter><SolicitudesCreditoPage /></MemoryRouter>);

beforeEach(() => {
  vi.clearAllMocks();
  sesion(["creditos:read", "creditos:write"]);
  creditos.ppSolicitudes.mockResolvedValue(LISTA([SOL_EVALUACION, SOL_EXPRESS]));
  creditos.ppOferta.mockResolvedValue({ items: [LINEA] });
  creditos.ppDatosCliente.mockResolvedValue(PADRON);
  creditos.ppPreAprobado.mockResolvedValue({ monto_maximo: 1500000, monto_min: 100000, cuota: 90000, afectacion: 30, afectacion_max: 30, plazo: 24 });
  creditos.ctoSegmentos.mockResolvedValue({ segmentos: ["AGENTE_PUBLICO"], canales: ["SUCURSAL"], canalBackoffice: "SUCURSAL", decimalesMostrar: 2 });
  creditos.ppSimPreview.mockResolvedValue(SIMULACION);
  creditos.ppSolicitudDocs.mockResolvedValue({ items: [] });
  creditos.ppRequisitosLinea.mockResolvedValue({ documentos: [], campos: [] });
  creditos.ppSolicitud.mockResolvedValue({});
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

  it("muestra la línea de crédito de cada solicitud", async () => {
    creditos.ppSolicitudes.mockResolvedValue(LISTA([SOL_EVALUACION, { ...SOL_EXPRESS, productoNombre: "JUBILADOS", productoCodigo: "LP-JUB-01" }]));
    montar();
    await screen.findByText("SOL-1");
    expect(screen.getByRole("columnheader", { name: /Línea/ })).toBeInTheDocument();
    expect(screen.getByText("SOL-1").closest("tr")).toHaveTextContent("PERSONAL");
    expect(screen.getByText("SOL-2").closest("tr")).toHaveTextContent("JUBILADOS");
    expect(within(screen.getByText("SOL-2").closest("tr")).getByText("JUBILADOS")).toHaveAttribute("title", "LP-JUB-01");
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

  it("muestra el CUIL y filtra por columna", async () => {
    const u = userEvent.setup();
    montar();
    await screen.findByText("SOL-1");
    expect(screen.getByText("27-30123456-4")).toBeInTheDocument();

    await u.type(screen.getByLabelText("Filtrar CUIL"), "28999");
    expect(screen.queryByText("SOL-1")).toBeNull();
    expect(screen.getByText("SOL-2")).toBeInTheDocument();
    expect(within(screen.getByLabelText("Filtrar Elegible")).getAllByRole("option").map((o) => o.textContent))
      .toEqual(["Todos", "Sí"]);
  });
});

describe("Solicitudes de crédito · detalle", () => {
  it("muestra los datos que el ciudadano cargó en el portal", async () => {
    // Regresión: el detalle no mostraba DNI, situación laboral, antigüedad, sueldo ni afectación.
    const DEL_PORTAL = {
      ...SOL_EXPRESS, origen: "PORTAL", canal: "WEB", clienteCuil: "20301234563", segmento: "AGENTE_PUBLICO",
      antiguedadMeses: 30,
      datosAdicionales: { sueldo_declarado: 850000, afectacion: 7.3, consentimiento: { terminos: true, datos: true, fecha: "2026-10-01" } },
    };
    creditos.ppSolicitudes.mockResolvedValue(LISTA([DEL_PORTAL]));
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-2"));

    const dato = (t) => screen.getByText(t, { selector: "dt" }).nextSibling.textContent;
    expect(dato("Origen")).toBe("Portal web");
    expect(dato("CUIL")).toBe("20-30123456-3");
    expect(dato("Situación laboral")).toBe("Empleado público provincial");
    expect(dato("Antigüedad laboral")).toBe("2 años y 6 meses");
    expect(dato("Sueldo neto declarado")).toMatch(/850\.000/);
    expect(dato("Afectación (cuota / sueldo)")).toBe("7,3%");
    expect(dato("Términos y tratamiento de datos")).toBe("Aceptados el 1/10/2026");
  });
});

describe("Solicitudes de crédito · observar", () => {
  const DEL_PORTAL = { ...SOL_EXPRESS, origen: "PORTAL", canal: "WEB" };

  it("pide la explicación y manda los documentos marcados (los faltantes ya vienen marcados)", async () => {
    creditos.ppSolicitudes.mockResolvedValue(LISTA([DEL_PORTAL]));
    creditos.ppSolicitudDocs.mockResolvedValue({
      items: [], faltantes: ["Certificado de servicios"],
      pedidos: [{ tipo: "DNI_FRENTE", titulo: "DNI (frente)", obligatorio: true },
                { tipo: "CERTIFICADO_SERVICIOS", titulo: "Certificado de servicios", obligatorio: true }],
    });
    creditos.ppSolicitudEstado.mockResolvedValue({ ...DEL_PORTAL, estado: "OBSERVADA" });
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-2"));
    await screen.findByText(/Falta documentación obligatoria/);

    await u.click(screen.getByRole("button", { name: "Observar" }));
    const dialogo = screen.getByRole("dialog", { name: "Observar solicitud" });
    expect(within(dialogo).getByLabelText(/Certificado de servicios/)).toBeChecked();
    expect(within(dialogo).getByRole("button", { name: "Observar" })).toBeDisabled();   // sin explicación no
    await u.type(within(dialogo).getByLabelText("Explicación para el solicitante"), "Falta el certificado.");
    await u.click(within(dialogo).getByLabelText("Corregir el CBU de acreditación"));
    await u.click(within(dialogo).getByRole("button", { name: "Observar" }));

    await waitFor(() => expect(creditos.ppSolicitudEstado).toHaveBeenCalledWith("s2", "observar", "", "", {
      detalle: "Falta el certificado.", documentos: ["CERTIFICADO_SERVICIOS"], corregir_cbu: true }));
  });

  it("una solicitud de sucursal no se observa", async () => {
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-1"));
    expect(screen.queryByRole("button", { name: "Observar" })).toBeNull();
  });

  it("muestra el historial de observaciones", async () => {
    creditos.ppSolicitudes.mockResolvedValue(LISTA([{ ...DEL_PORTAL, estado: "OBSERVADA", datosAdicionales: {
      correcciones: [{ detalle: "El DNI está borroso.", documentos: ["DNI_FRENTE"], cbu: false,
                       fecha: "2026-10-05T10:00:00", por: "asesor", respondida: null }] } }]));
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-2"));
    expect(screen.getByText("El DNI está borroso.")).toBeInTheDocument();
    expect(screen.getByText("Esperando al solicitante")).toBeInTheDocument();
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

  it("muestra lo que pidió la línea: sus datos, sus documentos y lo que falta", async () => {
    creditos.ppSolicitudes.mockResolvedValue(LISTA([{ ...SOL_EVALUACION, datosAdicionales: { requisitos: [
      { codigo: "COBERTURA", etiqueta: "Obra social", tipo: "UNICA", valores: ["OSEP"] },
      { codigo: "TRATAMIENTO", etiqueta: "Tipo de tratamiento", tipo: "MULTIPLE", valores: ["Cirugía", "Óptica"] },
    ] } }]));
    creditos.ppSolicitudDocs.mockResolvedValue({
      items: [{ id: "doc-1", tipo: "ORDEN_MEDICA", titulo: "Orden médica", nombre: "orden.pdf", tamano: 1000 }],
      faltantes: ["DNI (frente)"],
    });
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-1"));
    const detalle = await screen.findByRole("dialog", { name: "PEREZ, ANA" });

    expect(within(detalle).getByText("Obra social").nextSibling).toHaveTextContent("OSEP");
    expect(within(detalle).getByText("Tipo de tratamiento").nextSibling).toHaveTextContent("Cirugía, Óptica");
    expect(await within(detalle).findByText("Orden médica")).toBeInTheDocument();
    expect(within(detalle).getByText("Falta documentación obligatoria: DNI (frente).")).toBeInTheDocument();
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
    await pasarDocumentacion(u, modal);
    await u.click(within(modal).getByRole("button", { name: /Crear y enviar a evaluación/ }));

    await waitFor(() => expect(creditos.ppSolicitudCrear).toHaveBeenCalledWith(expect.objectContaining({
      solicitante_tipo: "REGISTRADO", cliente_id: 7, producto_id: "pp_1", monto_solicitado: 1000000,
      datos_adicionales: expect.objectContaining({ cbu: CBU, sueldo_declarado: 900000 }),
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

describe("Solicitudes de crédito · alta con los datos del padrón", () => {
  const abrirConCliente = async (u) => {
    montar();
    await screen.findByText("SOL-1");
    await u.click(screen.getByRole("button", { name: /Nueva solicitud/ }));
    const modal = await screen.findByRole("dialog", { name: "Nueva solicitud" });
    await u.type(within(modal).getByPlaceholderText(/Buscar cliente/), "perez");
    await u.click(await screen.findByText(/Perez, Ana/));
    return modal;
  };

  it("precarga nacimiento, antigüedad y sueldo del padrón", async () => {
    const u = userEvent.setup();
    const modal = await abrirConCliente(u);
    await waitFor(() => expect(within(modal).getByLabelText(/Fecha de nacimiento/)).toHaveValue("1980-05-10"));
    expect(creditos.ppDatosCliente).toHaveBeenCalledWith(7);
    expect(within(modal).getByLabelText(/Antigüedad laboral/)).toHaveValue(10);
    expect(within(modal).getByLabelText("Sueldo neto")).toHaveValue("900.000,00");
  });

  it("con el sueldo dice cuánto puede pedir y las cuotas van del mínimo al máximo de la línea", async () => {
    const u = userEvent.setup();
    const modal = await abrirConCliente(u);
    await waitFor(() => expect(within(modal).getByLabelText("Sueldo neto")).toHaveValue("900.000,00"));
    await u.click(within(modal).getByRole("button", { name: "Continuar →" }));
    expect(await within(modal).findByText(/Puede pedir hasta/)).toBeInTheDocument();
    expect(creditos.ppPreAprobado).toHaveBeenCalledWith({ producto_id: "pp_1", plazo: 24, sueldo: 900000 });
    const cuotas = within(modal).getByRole("slider", { name: "Cuotas" });
    expect(cuotas).toHaveAttribute("min", "6");
    expect(cuotas).toHaveAttribute("max", "48");
    await u.click(within(modal).getByRole("button", { name: "Usar el máximo" }));
    await waitFor(() => expect(creditos.ppSimPreview).toHaveBeenLastCalledWith("pp_1",
      expect.objectContaining({ monto: 1500000, sueldo: 900000 })));
  });

  it("sin CBU de 22 dígitos no se envía a evaluación", async () => {
    creditos.ppDatosCliente.mockResolvedValue({ ...PADRON, cbu: null });
    const u = userEvent.setup();
    const modal = await abrirConCliente(u);
    await waitFor(() => expect(creditos.ppDatosCliente).toHaveBeenCalled());
    await u.click(within(modal).getByRole("button", { name: "Continuar →" }));
    await screen.findByText("Elegible con estos datos.");
    await u.click(within(modal).getByRole("button", { name: "Continuar →" }));
    await pasarDocumentacion(u, modal);
    const enviar = within(modal).getByRole("button", { name: /Crear y enviar a evaluación/ });
    expect(enviar).toBeDisabled();
    await u.type(within(modal).getByLabelText("CBU"), "01105995");
    expect(within(modal).getByText("Faltan 14 dígito(s).")).toBeInTheDocument();
    await u.type(within(modal).getByLabelText("CBU"), "20000001234567");
    expect(enviar).toBeEnabled();
  });
});

describe("Solicitudes de crédito · express que ya está en el padrón", () => {
  it("sugiere vincularla al cliente del padrón y la vincula", async () => {
    creditos.ppSolicitudes.mockResolvedValue(LISTA([SOL_EXPRESS]));
    creditos.ppSolicitud.mockResolvedValue({ ...SOL_EXPRESS, clienteEnPadron: { id: 26797, nombre: "CONTRERAS, TERESA LAURA", documento: "23486996" } });
    creditos.ppSolicitudPromover.mockResolvedValue({ solicitud: { ...SOL_EXPRESS, solicitanteTipo: "REGISTRADO", clienteNombre: "CONTRERAS, TERESA LAURA" }, clienteId: 26797 });
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-2"));
    expect(await screen.findByText(/ya está en el padrón de clientes/)).toHaveTextContent("CONTRERAS, TERESA LAURA (23486996)");
    await u.click(screen.getByRole("button", { name: "Vincular a este cliente" }));
    await waitFor(() => expect(creditos.ppSolicitudPromover).toHaveBeenCalledWith("s2", { cliente_id: 26797 }));
    expect(await screen.findAllByText(/Cliente CONTRERAS, TERESA LAURA vinculado/)).not.toHaveLength(0);
    expect(screen.queryByText(/ya está en el padrón de clientes/)).toBeNull();
  });

  it("si no está en el padrón no sugiere nada", async () => {
    creditos.ppSolicitudes.mockResolvedValue(LISTA([SOL_EXPRESS]));
    creditos.ppSolicitud.mockResolvedValue({ ...SOL_EXPRESS, clienteEnPadron: null });
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-2"));
    await waitFor(() => expect(creditos.ppSolicitud).toHaveBeenCalledWith("s2"));
    expect(screen.queryByText(/ya está en el padrón de clientes/)).toBeNull();
  });
});

describe("Solicitudes de crédito · forma de cobro", () => {
  const COBRO = { modalidad: "CODIGO_DESCUENTO", codigoDescuento: "4521", conceptoRecibo: "CAPRESCA PREST PERSONAL",
                  detalle: "Se descuenta desde el mes siguiente." };

  it("al final del alta avisa cómo le viene la cuota en el recibo", async () => {
    creditos.ppOferta.mockResolvedValue({ items: [{ ...LINEA, cobro: COBRO }] });
    creditos.ppSimPreview.mockResolvedValue({ ...SIMULACION, primeraCuota: 62000 });
    const u = userEvent.setup();
    montar();
    await screen.findByText("SOL-1");
    await u.click(screen.getByRole("button", { name: /Nueva solicitud/ }));
    const modal = await screen.findByRole("dialog", { name: "Nueva solicitud" });
    await u.type(within(modal).getByPlaceholderText(/Buscar cliente/), "perez");
    await u.click(await screen.findByText(/Perez, Ana/));
    await u.click(within(modal).getByRole("button", { name: "Continuar →" }));
    await screen.findByText("Elegible con estos datos.");
    expect(within(modal).queryByRole("note")).toBeNull();          // recién al final
    await u.click(within(modal).getByRole("button", { name: "Continuar →" }));
    await pasarDocumentacion(u, modal);
    const aviso = within(modal).getByRole("note", { name: /cómo se cobra/i });
    expect(aviso).toHaveTextContent("La cuota de $62.000,00 se descuenta directamente del sueldo");
    expect(aviso).toHaveTextContent("«CAPRESCA PREST PERSONAL», código de descuento 4521");
    expect(aviso).toHaveTextContent("Se descuenta desde el mes siguiente.");
  });

  it("una línea sin forma de cobro no avisa nada", async () => {
    const u = userEvent.setup();
    montar();
    await screen.findByText("SOL-1");
    await u.click(screen.getByRole("button", { name: /Nueva solicitud/ }));
    const modal = await screen.findByRole("dialog", { name: "Nueva solicitud" });
    await u.type(within(modal).getByPlaceholderText(/Buscar cliente/), "perez");
    await u.click(await screen.findByText(/Perez, Ana/));
    await u.click(within(modal).getByRole("button", { name: "Continuar →" }));
    await screen.findByText("Elegible con estos datos.");
    await u.click(within(modal).getByRole("button", { name: "Continuar →" }));
    await pasarDocumentacion(u, modal);
    expect(within(modal).queryByRole("note")).toBeNull();
  });

  it("el detalle muestra lo que se le avisó", async () => {
    creditos.ppSolicitudes.mockResolvedValue(LISTA([{ ...SOL_EVALUACION, datosAdicionales: { cobro: COBRO } }]));
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-1"));
    expect(await screen.findByRole("note", { name: /lo que se le avisó/ })).toHaveTextContent("código de descuento 4521");
  });
});

describe("Solicitudes de crédito · modificar", () => {
  it("una en evaluación se modifica (también el CBU) y muestra quién y cuándo", async () => {
    creditos.ppSolicitud.mockResolvedValue(SOL_EVALUACION);
    creditos.ppSolicitudEditar.mockResolvedValue({
      ...SOL_EVALUACION, editable: true, datosAdicionales: { cbu: CBU },
      ultimaModificacion: { por: "ana", en: "2026-10-08T10:30:00", campos: ["cbu"] } });
    creditos.ppSolicitudes.mockResolvedValue(LISTA([{ ...SOL_EVALUACION, editable: true }]));
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-1"));
    await u.click(await screen.findByRole("button", { name: "Modificar" }));
    const modal = await screen.findByRole("dialog", { name: "Modificar solicitud" });
    // Se abre por encima del detalle: va después en el DOM (mismo z-index).
    const dialogos = screen.getAllByRole("dialog");
    expect(dialogos[dialogos.length - 1]).toBe(modal);
    expect(within(modal).getByText(/las aprobaciones que ya tuviera se reinician/)).toBeInTheDocument();
    await screen.findByText("Elegible con estos datos.");
    // Regresión: los rangos de la línea vienen en `cfg`; leídos mal, el monto quedaba NaN y todo daba 422.
    await waitFor(() => expect(creditos.ppSimPreview).toHaveBeenLastCalledWith("pp_1",
      expect.objectContaining({ monto: 1000000, plazo: 24 })));
    expect(within(modal).getByRole("slider", { name: "Cuotas" })).toHaveAttribute("max", "48");
    await u.type(within(modal).getByLabelText("CBU"), CBU);
    await u.click(within(modal).getByRole("button", { name: "Guardar cambios" }));
    await waitFor(() => expect(creditos.ppSolicitudEditar).toHaveBeenCalledWith("s1", expect.objectContaining({ cbu: CBU, plazo_solicitado: 24 })));
    expect(await screen.findByText(/Modificada por/)).toHaveTextContent("Modificada por ana el");
    expect(screen.getByText(/Modificada por/)).toHaveTextContent("(cbu)");
  });

  it("una aprobada no se modifica", async () => {
    creditos.ppSolicitudes.mockResolvedValue(LISTA([{ ...SOL_APROBADA, editable: false }]));
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-3"));
    await screen.findByRole("dialog");
    expect(screen.queryByRole("button", { name: "Modificar" })).toBeNull();
  });
});

describe("Solicitudes de crédito · historial de modificaciones", () => {
  it("muestra quién cambió qué, con el valor anterior y el nuevo", async () => {
    creditos.ppSolicitudes.mockResolvedValue(LISTA([{ ...SOL_EVALUACION, editable: true, datosAdicionales: { modificaciones: [
      { por: "ana", en: "2026-10-08T10:30:00", estado: "BORRADOR", campos: ["monto"],
        cambios: { monto: { antes: 1000000, despues: 900000 } } },
      { por: "luis", en: "2026-10-08T11:00:00", estado: "EN_EVALUACION", campos: ["plazo", "producto_id"],
        cambios: { plazo: { antes: 24, despues: 36 }, producto_id: { antes: "pp_x", despues: "pp_1" } } },
    ] } }]));
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-1"));
    const boton = await screen.findByRole("button", { name: /Historial de modificaciones \(2\)/ });
    expect(boton).toHaveAttribute("aria-expanded", "false");          // arranca colapsado
    expect(boton).toHaveTextContent("última: luis");
    expect(screen.queryByText("Antes")).toBeNull();
    await u.click(boton);
    const hist = boton.parentElement;
    const items = within(hist).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("luis");                       // la más nueva arriba
    const fila = (item, campo) => within(item).getByText(campo).closest("tr");
    expect(within(items[0]).getAllByRole("columnheader").map((x) => x.textContent)).toEqual(["Campo", "Antes", "Ahora"]);
    expect(within(fila(items[0], "Cuotas")).getAllByRole("cell").map((x) => x.textContent)).toEqual(["Cuotas", "24 cuotas", "36 cuotas"]);
    expect(fila(items[0], "Línea")).toHaveTextContent("PERSONAL");    // la línea con su nombre, no el id
    expect(items[1]).toHaveTextContent("ana");
    expect(within(fila(items[1], "Monto")).getAllByRole("cell").map((x) => x.textContent))
      .toEqual(["Monto", "$1.000.000,00", "$900.000,00"]);
    await u.click(boton);
    expect(screen.queryByRole("listitem", { name: /luis/ })).toBeNull();
    expect(boton).toHaveAttribute("aria-expanded", "false");
  });

  it("sin modificaciones no hay historial", async () => {
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-1"));
    await screen.findByRole("dialog");
    expect(screen.queryByText(/Historial de modificaciones/)).toBeNull();
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
    expect(within(modal).getByText(/Lote 2026-0003 · abierto/)).toBeInTheDocument();
    expect(within(modal).getByText(/espera que lo verifiquen y lo cierren/)).toBeInTheDocument();
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

  it("en un lote cerrado tampoco se puede anular", async () => {
    creditos.ppSolicitudes.mockResolvedValue(LISTA([{ ...SOL_APROBADA, resolucion: null,
      lote: { id: 3, codigo: "2026-0003", estado: "CERRADO", resolucion: null } }]));
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-3"));

    const modal = await screen.findByRole("dialog", { name: "PEREZ, ANA" });
    expect(within(modal).getByText(/Lote 2026-0003 · cerrado/)).toBeInTheDocument();
    expect(within(modal).getByText(/Está en un lote cerrado: no se modifica/)).toBeInTheDocument();
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

describe("Solicitudes de crédito · documentación de sucursal (la misma que el portal)", () => {
  const PEDIDOS = [
    { tipo: "DNI_FRENTE", titulo: "DNI (frente)", ayuda: "", obligatorio: true },
    { tipo: "PRESUPUESTO", titulo: "Presupuesto del prestador", ayuda: "Con membrete", obligatorio: false },
  ];
  const CAMPOS = [{ codigo: "COBERTURA", etiqueta: "Obra social", ayuda: "", tipo: "UNICA",
                    opciones: ["OSEP", "PAMI"], obligatorio: true }];
  const dni = () => new File(["png"], "dni.png", { type: "image/png" });

  async function hastaDocumentacion(u) {
    montar();
    await screen.findByText("SOL-1");
    await u.click(screen.getByRole("button", { name: /Nueva solicitud/ }));
    const modal = await screen.findByRole("dialog", { name: "Nueva solicitud" });
    await u.type(within(modal).getByPlaceholderText(/Buscar cliente/), "perez");
    await u.click(await screen.findByText(/Perez, Ana/));
    await u.click(within(modal).getByRole("button", { name: "Continuar →" }));
    await screen.findByText("Elegible con estos datos.");
    await u.click(within(modal).getByRole("button", { name: "Continuar →" }));
    await within(modal).findByText("DNI (frente)");
    return modal;
  }

  beforeEach(() => {
    creditos.ppRequisitosLinea.mockResolvedValue({ documentos: PEDIDOS, campos: CAMPOS });
    creditos.ppSolicitudDocSubir.mockResolvedValue({ id: "d1" });
  });

  it("pide los datos y la documentación de la línea, los adjunta y recién ahí la envía", async () => {
    const u = userEvent.setup();
    const modal = await hastaDocumentacion(u);
    expect(creditos.ppRequisitosLinea).toHaveBeenCalledWith("pp_1");
    expect(within(modal).getByText("Con membrete")).toBeInTheDocument();
    const seguir = within(modal).getByRole("button", { name: "Continuar →" });
    expect(seguir).toBeDisabled();                                   // falta la obra social
    await u.selectOptions(within(modal).getByLabelText("Obra social"), "PAMI");
    expect(seguir).toBeEnabled();

    // Sin el DNI se puede guardar como borrador, pero no enviar.
    await u.click(seguir);
    expect(within(modal).getByText(/Falta adjuntar: DNI \(frente\)/)).toBeInTheDocument();
    expect(within(modal).getByRole("button", { name: /Crear y enviar a evaluación/ })).toBeDisabled();

    await u.click(within(modal).getByRole("button", { name: "← Volver" }));
    await u.upload(within(modal).getByLabelText("Archivo de DNI (frente)"), dni());
    expect(within(modal).getByText("dni.png")).toBeInTheDocument();
    await u.click(within(modal).getByRole("button", { name: "Continuar →" }));
    await u.click(within(modal).getByRole("button", { name: /Crear y enviar a evaluación/ }));

    await waitFor(() => expect(creditos.ppSolicitudEstado).toHaveBeenCalledWith("s1", "enviar", "", ""));
    expect(creditos.ppSolicitudCrear).toHaveBeenCalledWith(expect.objectContaining({ respuestas: { COBERTURA: ["PAMI"] } }));
    expect(creditos.ppSolicitudDocSubir).toHaveBeenCalledWith("s1", "DNI_FRENTE", expect.any(File));
    expect(creditos.ppSolicitudDocSubir).toHaveBeenCalledTimes(1);   // el opcional no se adjuntó
    expect(creditos.ppSolicitudDocSubir.mock.invocationCallOrder[0])
      .toBeLessThan(creditos.ppSolicitudEstado.mock.invocationCallOrder[0]);
  });

  it("no acepta un archivo que no es imagen ni PDF", async () => {
    const u = userEvent.setup();
    const modal = await hastaDocumentacion(u);
    fireEvent.change(within(modal).getByLabelText("Archivo de DNI (frente)"),
                     { target: { files: [new File(["x"], "dni.docx", { type: "application/msword" })] } });
    expect(within(modal).getByText(/DNI \(frente\): Formato no permitido/)).toBeInTheDocument();
    expect(within(modal).queryByText("dni.docx")).toBeNull();
  });

  it("si un archivo no se pudo adjuntar, no la envía y lo avisa en el detalle", async () => {
    creditos.ppSolicitudDocSubir.mockRejectedValue(new Error("El archivo supera el máximo de 5 MB."));
    const u = userEvent.setup();
    const modal = await hastaDocumentacion(u);
    await u.selectOptions(within(modal).getByLabelText("Obra social"), "OSEP");
    await u.upload(within(modal).getByLabelText("Archivo de DNI (frente)"), dni());
    await u.click(within(modal).getByRole("button", { name: "Continuar →" }));
    await u.click(within(modal).getByRole("button", { name: /Crear y enviar a evaluación/ }));
    const detalle = await screen.findByRole("dialog", { name: "PEREZ, ANA" });
    expect(await within(detalle).findByText(/quedó en borrador: no se pudo adjuntar DNI \(frente\)/)).toBeInTheDocument();
    expect(creditos.ppSolicitudEstado).not.toHaveBeenCalled();
  });

  it("en el detalle de un borrador se adjunta lo que falta y se puede quitar", async () => {
    const BORRADOR = { ...SOL_EVALUACION, estado: "BORRADOR", editable: true };
    creditos.ppSolicitudes.mockResolvedValue(LISTA([BORRADOR]));
    creditos.ppSolicitudDocs.mockResolvedValue({ items: [], pedidos: PEDIDOS, faltantes: ["DNI (frente)"], puedeAdjuntar: true });
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-1"));
    const detalle = await screen.findByRole("dialog", { name: "PEREZ, ANA" });
    const enviar = await within(detalle).findByRole("button", { name: "Enviar a evaluación" });
    await within(detalle).findByText("Documentación (la misma que pide el portal)");
    expect(enviar).toBeDisabled();

    creditos.ppSolicitudDocs.mockResolvedValue({
      items: [{ id: "d1", tipo: "DNI_FRENTE", titulo: "DNI (frente)", nombre: "dni.png", tamano: 3 }],
      pedidos: PEDIDOS, faltantes: [], puedeAdjuntar: true });
    await u.upload(within(detalle).getByLabelText("Archivo de DNI (frente)"), dni());
    await waitFor(() => expect(creditos.ppSolicitudDocSubir).toHaveBeenCalledWith("s1", "DNI_FRENTE", expect.any(File)));
    await waitFor(() => expect(enviar).toBeEnabled());
    expect(within(detalle).getByRole("button", { name: "Quitar" })).toBeInTheDocument();
  });

  it("en evaluación el documento se reemplaza pero no se quita", async () => {
    creditos.ppSolicitudes.mockResolvedValue(LISTA([{ ...SOL_EVALUACION, origen: "SUCURSAL" }]));
    creditos.ppSolicitudDocs.mockResolvedValue({
      items: [{ id: "d1", tipo: "DNI_FRENTE", titulo: "DNI (frente)", nombre: "dni.png", tamano: 3 }],
      pedidos: PEDIDOS, faltantes: [], puedeAdjuntar: true });
    const u = userEvent.setup();
    montar();
    await u.click(await screen.findByText("SOL-1"));
    const detalle = await screen.findByRole("dialog", { name: "PEREZ, ANA" });
    await within(detalle).findByText("Documentación (la misma que pide el portal)");
    expect(within(detalle).getAllByRole("button", { name: "Reemplazar" })).toHaveLength(1);
    expect(within(detalle).queryByRole("button", { name: "Quitar" })).toBeNull();
    expect(within(detalle).getByText(/se reemplaza, no se quita/)).toBeInTheDocument();
  });
});
