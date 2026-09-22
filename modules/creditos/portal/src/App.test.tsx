import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { token } from "./api";

// La capa HTTP tiene sus propios tests (api.test.ts): acá se reemplaza por dobles para
// probar la pantalla del ciudadano sin red. `token` sí es el real (localStorage).
const h = vi.hoisted(() => ({
  api: {
    loginUrl: vi.fn(), me: vi.fn(), haberes: vi.fn(), productos: vi.fn(), simular: vi.fn(),
    preAprobado: vi.fn(), enviarSolicitud: vi.fn(), misSolicitudes: vi.fn(), solicitudDetalle: vi.fn(),
    docsListar: vi.fn(), docSubir: vi.fn(), docAbrir: vi.fn(), docBorrar: vi.fn(),
    misCreditos: vi.fn(), creditoDetalle: vi.fn(), notificaciones: vi.fn(),
  },
}));
vi.mock("./api", async (original) => ({ ...(await original() as any), api: h.api }));

import App from "./App";

const api = h.api;
const CIUDADANO = { sub: "u-1", email: "ana@mail.com", nombre: "Ana Prueba" };
const PRODUCTO = {
  id: "pp_1", nombre: "Crédito Personal", codigo: "CP", sistema: "FRANCES", tna: 60,
  monto_min: 100000, monto_max: 1000000, plazo_min: 6, plazo_max: 36,
};
const SIM = {
  producto: "Crédito Personal", sistema: "FRANCES", tna: 60, monto: 500000, cantidad_cuotas: 12,
  total_a_pagar: 700000, total_interes: 200000, cuota_promedio: 58333, tea: 79, cft: 95,
  elegible: true, motivos: [], afectacion: 25, cuotas: [],
};

const locationOriginal = window.location;
function stubLocation(pathname = "/", hash = "") {
  Object.defineProperty(window, "location", {
    configurable: true, writable: true,
    value: { pathname, hash, search: "", href: `http://localhost${pathname}${hash}`, assign: vi.fn() },
  });
  return window.location as any;
}

beforeEach(() => {
  stubLocation();
  vi.spyOn(window.history, "replaceState").mockImplementation(() => {});
  if (!globalThis.crypto?.randomUUID) vi.stubGlobal("crypto", { ...globalThis.crypto, randomUUID: () => "idem-fijo" });
  else vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue("idem-fijo" as any);
  api.me.mockResolvedValue(CIUDADANO);
  api.productos.mockResolvedValue([PRODUCTO]);
  api.notificaciones.mockResolvedValue([]);
  api.misSolicitudes.mockResolvedValue([]);
  api.misCreditos.mockResolvedValue([]);
  api.simular.mockResolvedValue(SIM);
  api.preAprobado.mockRejectedValue(new Error("sin pre-aprobado"));
  api.loginUrl.mockResolvedValue({ authorize_url: "https://mi.catamarca/oidc" });
});

afterEach(() => {
  vi.restoreAllMocks();
  Object.defineProperty(window, "location", { configurable: true, writable: true, value: locationOriginal });
});

/** Renderiza con sesión abierta y espera a que aparezca el portal. */
async function montarLogueado() {
  token.set("tok-ok");
  const u = userEvent.setup();
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Solicitá tu crédito" })).toBeInTheDocument();
  return u;
}

/** Completa el paso 1 (identidad + situación) y pasa a la simulación. */
async function completarDatos(u: ReturnType<typeof userEvent.setup>) {
  await u.type(screen.getByLabelText(/Apellido/), "Prueba");
  await u.type(screen.getByLabelText(/^Nombre/), "Ana");
  await u.type(screen.getByLabelText(/DNI/), "30123456");
  await u.selectOptions(screen.getByLabelText(/Situación laboral/), "AGENTE_PUBLICO");
  await u.click(screen.getByRole("button", { name: /Continuar/ }));
}

// ---------------------------------------------------------------------------
describe("arranque de sesión", () => {
  it("sin token muestra el login de Mi Catamarca", async () => {
    render(<App />);
    expect(await screen.findByRole("button", { name: /Ingresar con Mi Catamarca/ })).toBeInTheDocument();
    expect(api.me).not.toHaveBeenCalled();
  });

  it("con token válido entra al portal con el nombre del ciudadano", async () => {
    token.set("tok-ok");
    render(<App />);
    expect(await screen.findByText("Ana Prueba")).toBeInTheDocument();
    expect(api.me).toHaveBeenCalled();
  });

  it("si el token no sirve lo descarta y vuelve al login", async () => {
    token.set("tok-roto");
    api.me.mockRejectedValue(new Error("401"));
    render(<App />);
    expect(await screen.findByRole("button", { name: /Ingresar con Mi Catamarca/ })).toBeInTheDocument();
    expect(token.get()).toBe("");
  });

  it("captura el token del callback OIDC y limpia la URL", async () => {
    stubLocation("/ingreso", "#token=tok-callback&state=x");
    render(<App />);
    expect(await screen.findByText("Ana Prueba")).toBeInTheDocument();
    expect(token.get()).toBe("tok-callback");
    expect(window.history.replaceState).toHaveBeenCalledWith({}, "", "/");
  });

  it("H-159: un 401 a mitad de sesión devuelve al login sin recargar", async () => {
    token.set("tok-ok");
    render(<App />);
    expect(await screen.findByText("Ana Prueba")).toBeInTheDocument();
    fireEvent(window, new Event("portal:sesion-expirada"));
    expect(await screen.findByRole("button", { name: /Ingresar con Mi Catamarca/ })).toBeInTheDocument();
  });

  it("Salir borra el token y vuelve al login", async () => {
    const u = await montarLogueado();
    await u.click(screen.getByRole("button", { name: "Salir" }));
    expect(await screen.findByRole("button", { name: /Ingresar con Mi Catamarca/ })).toBeInTheDocument();
    expect(token.get()).toBe("");
  });
});

// ---------------------------------------------------------------------------
describe("login", () => {
  it("redirige al autorizador de Mi Catamarca", async () => {
    const u = userEvent.setup();
    render(<App />);
    await u.click(await screen.findByRole("button", { name: /Ingresar con Mi Catamarca/ }));
    await waitFor(() => expect(window.location.href).toBe("https://mi.catamarca/oidc"));
  });

  it("si el pedido falla lo avisa y deja reintentar", async () => {
    api.loginUrl.mockRejectedValue(new Error("Mi Catamarca no responde"));
    const u = userEvent.setup();
    render(<App />);
    await u.click(await screen.findByRole("button", { name: /Ingresar con Mi Catamarca/ }));
    expect(await screen.findByText(/Mi Catamarca no responde/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Ingresar con Mi Catamarca/ })).toBeEnabled();
  });
});

// ---------------------------------------------------------------------------
describe("paso 1 · tus datos", () => {
  it("exige apellido y nombre", async () => {
    const u = await montarLogueado();
    await u.click(screen.getByRole("button", { name: /Continuar/ }));
    expect(screen.getByText("Cargá tu apellido y nombre.")).toBeInTheDocument();
  });

  it("valida el largo del DNI", async () => {
    const u = await montarLogueado();
    await u.type(screen.getByLabelText(/Apellido/), "Prueba");
    await u.type(screen.getByLabelText(/^Nombre/), "Ana");
    await u.type(screen.getByLabelText(/DNI/), "123");
    await u.click(screen.getByRole("button", { name: /Continuar/ }));
    expect(screen.getByText("El DNI debe tener 7 u 8 dígitos.")).toBeInTheDocument();
  });

  it("el DNI descarta lo que no sean dígitos", async () => {
    await montarLogueado();
    const dni = screen.getByLabelText(/DNI/) as HTMLInputElement;
    fireEvent.change(dni, { target: { value: "30.123.456" } });
    expect(dni.value).toBe("30123456");
  });

  it("exige la situación laboral", async () => {
    const u = await montarLogueado();
    await u.type(screen.getByLabelText(/Apellido/), "Prueba");
    await u.type(screen.getByLabelText(/^Nombre/), "Ana");
    await u.type(screen.getByLabelText(/DNI/), "30123456");
    await u.click(screen.getByRole("button", { name: /Continuar/ }));
    expect(screen.getByText("Elegí tu situación laboral para continuar.")).toBeInTheDocument();
  });

  it("con los datos completos pasa a la simulación", async () => {
    const u = await montarLogueado();
    await completarDatos(u);
    expect(await screen.findByText("Elegí el crédito")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
describe("adjuntos del paso 1 (H-162)", () => {
  const archivo = (nombre: string, tipo: string, tam = 1000) => {
    const f = new File(["x"], nombre, { type: tipo });
    Object.defineProperty(f, "size", { value: tam });
    return f;
  };
  const inputArchivo = () => document.querySelector('input[type="file"]') as HTMLInputElement;
  const listaDocs = () => document.querySelector(".p-docs-list") as HTMLElement | null;

  it("acepta una imagen y la lista con su tipo", async () => {
    await montarLogueado();
    fireEvent.change(inputArchivo(), { target: { files: [archivo("dni.png", "image/png", 2048)] } });
    await waitFor(() => expect(listaDocs()).not.toBeNull());
    expect(within(listaDocs()!).getByText("DNI (frente)")).toBeInTheDocument();
    expect(within(listaDocs()!).getByText(/dni\.png · 2 KB/)).toBeInTheDocument();
  });

  it("rechaza formatos que no son imagen ni PDF", async () => {
    await montarLogueado();
    fireEvent.change(inputArchivo(), { target: { files: [archivo("planilla.xlsx", "application/vnd.ms-excel")] } });
    expect(await screen.findByText("Formato no permitido (JPG, PNG o PDF).")).toBeInTheDocument();
  });

  it("rechaza archivos de más de 5 MB", async () => {
    await montarLogueado();
    fireEvent.change(inputArchivo(), { target: { files: [archivo("recibo.pdf", "application/pdf", 6 * 1024 * 1024)] } });
    expect(await screen.findByText("El archivo supera los 5 MB.")).toBeInTheDocument();
  });

  it("permite quitar un adjunto elegido", async () => {
    const u = await montarLogueado();
    fireEvent.change(inputArchivo(), { target: { files: [archivo("dni.pdf", "application/pdf")] } });
    await u.click(await screen.findByRole("button", { name: "Quitar documento" }));
    expect(screen.queryByText(/dni\.pdf/)).toBeNull();
    expect(listaDocs()).toBeNull();
  });
});

// ---------------------------------------------------------------------------
describe("paso 2 · simulación", () => {
  it("simula sola al entrar (sin apretar nada) y muestra los totales", async () => {
    const u = await montarLogueado();
    await completarDatos(u);
    await waitFor(() => expect(api.simular).toHaveBeenCalled());
    expect(api.simular.mock.calls[0][0]).toMatchObject({ producto_id: "pp_1", monto: 500000, plazo: 12, segmento: "AGENTE_PUBLICO" });
    expect(await screen.findByText("Total a pagar")).toBeInTheDocument();
    expect(screen.getByText(/CFT anual/)).toBeInTheDocument();
  });

  it("avisa cuando el ciudadano no califica y enumera los motivos", async () => {
    api.simular.mockResolvedValue({ ...SIM, elegible: false, motivos: ["Antigüedad insuficiente"] });
    const u = await montarLogueado();
    await completarDatos(u);
    expect(await screen.findByText("Antigüedad insuficiente")).toBeInTheDocument();
    expect(screen.getByText(/No podés enviar la solicitud/)).toBeInTheDocument();
  });

  it("el pre-aprobado ofrece el máximo y lo aplica al monto", async () => {
    api.preAprobado.mockResolvedValue({ monto_maximo: 800000, monto_min: 100000, cuota: 40000, afectacion: 28, plazo: 12 });
    const u = await montarLogueado();
    await u.type(screen.getByLabelText(/Sueldo neto/), "900000");
    await completarDatos(u);
    await u.click(await screen.findByRole("button", { name: "Usar el máximo" }));
    await waitFor(() => expect(api.simular).toHaveBeenCalledWith(expect.objectContaining({ monto: 800000 })));
  });

  it("si el sueldo no alcanza lo dice en lugar de ofrecer un máximo", async () => {
    api.preAprobado.mockResolvedValue({ monto_maximo: 0, monto_min: 100000, cuota: 0, afectacion: 0, plazo: 12 });
    const u = await montarLogueado();
    await u.type(screen.getByLabelText(/Sueldo neto/), "100000");
    await completarDatos(u);
    expect(await screen.findByText(/la cuota supera tu margen/)).toBeInTheDocument();
  });

  it("se puede volver al paso 1 sin perder los datos", async () => {
    const u = await montarLogueado();
    await completarDatos(u);
    await u.click(await screen.findByRole("button", { name: /Volver/ }));
    expect((screen.getByLabelText(/Apellido/) as HTMLInputElement).value).toBe("Prueba");
  });
});

// ---------------------------------------------------------------------------
describe("paso 3 · confirmación y envío", () => {
  async function llegarAConfirmacion() {
    const u = await montarLogueado();
    await completarDatos(u);
    await u.click(await screen.findByRole("button", { name: /Continuar/ }));
    expect(await screen.findByText("Revisá y confirmá tu solicitud")).toBeInTheDocument();
    return u;
  }

  it("no deja enviar sin CBU completo ni aceptaciones", async () => {
    const u = await llegarAConfirmacion();
    const enviar = screen.getByRole("button", { name: /Confirmar y enviar/ });
    expect(enviar).toBeDisabled();
    await u.type(screen.getByLabelText(/CBU/), "123");
    expect(screen.getByText("Faltan 19 dígito(s).")).toBeInTheDocument();
    expect(enviar).toBeDisabled();
  });

  it("con CBU y las dos aceptaciones envía la solicitud y muestra el número", async () => {
    api.enviarSolicitud.mockResolvedValue({ numero: "SOL-7" });
    const u = await llegarAConfirmacion();
    await u.type(screen.getByLabelText(/CBU/), "2".repeat(22));
    await u.click(screen.getByRole("checkbox", { name: /términos y condiciones/ }));
    await u.click(screen.getByRole("checkbox", { name: /tratamiento de mis datos/ }));
    await u.click(screen.getByRole("button", { name: /Confirmar y enviar/ }));

    await waitFor(() => expect(api.enviarSolicitud).toHaveBeenCalled());
    const [cuerpo, idem] = api.enviarSolicitud.mock.calls[0];
    expect(cuerpo).toMatchObject({ producto_id: "pp_1", cbu: "2".repeat(22), acepta_terminos: true, acepta_datos: true, dni: "30123456" });
    expect(idem).toBe("idem-fijo");
    expect(await screen.findByText(/Solicitud SOL-7 enviada/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Mis solicitudes" })).toBeInTheDocument();
  });

  it("sube los adjuntos elegidos y avisa si alguno falla", async () => {
    api.enviarSolicitud.mockResolvedValue({ numero: "SOL-8" });
    api.docSubir.mockRejectedValue(new Error("upload caído"));
    const u = await montarLogueado();
    const f = new File(["x"], "dni.pdf", { type: "application/pdf" });
    fireEvent.change(document.querySelector('input[type="file"]')!, { target: { files: [f] } });
    await completarDatos(u);
    await u.click(await screen.findByRole("button", { name: /Continuar/ }));
    await u.type(await screen.findByLabelText(/CBU/), "2".repeat(22));
    await u.click(screen.getByRole("checkbox", { name: /términos y condiciones/ }));
    await u.click(screen.getByRole("checkbox", { name: /tratamiento de mis datos/ }));
    await u.click(screen.getByRole("button", { name: /Confirmar y enviar/ }));

    await waitFor(() => expect(api.docSubir).toHaveBeenCalledWith("SOL-8", f, "DNI_FRENTE"));
    expect(await screen.findByText(/No se pudieron adjuntar 1 archivo/)).toBeInTheDocument();
  });

  it("si el backend rechaza el envío lo muestra y no borra el formulario", async () => {
    api.enviarSolicitud.mockRejectedValue(new Error("Ya tenés una solicitud en curso"));
    const u = await llegarAConfirmacion();
    await u.type(screen.getByLabelText(/CBU/), "2".repeat(22));
    await u.click(screen.getByRole("checkbox", { name: /términos y condiciones/ }));
    await u.click(screen.getByRole("checkbox", { name: /tratamiento de mis datos/ }));
    await u.click(screen.getByRole("button", { name: /Confirmar y enviar/ }));
    expect(await screen.findByText(/Ya tenés una solicitud en curso/)).toBeInTheDocument();
    expect(screen.getByText("Revisá y confirmá tu solicitud")).toBeInTheDocument();
  });

  it("no se puede enviar si la simulación dice que no califica", async () => {
    api.simular.mockResolvedValue({ ...SIM, elegible: false, motivos: ["Edad máxima superada"] });
    const u = await montarLogueado();
    await completarDatos(u);
    await u.click(await screen.findByRole("button", { name: /Continuar/ }));
    await u.type(await screen.findByLabelText(/CBU/), "2".repeat(22));
    await u.click(screen.getByRole("checkbox", { name: /términos y condiciones/ }));
    await u.click(screen.getByRole("checkbox", { name: /tratamiento de mis datos/ }));
    expect(screen.getByRole("button", { name: /Confirmar y enviar/ })).toBeDisabled();
    expect(screen.getByText(/No cumplís las condiciones de este crédito: no se puede enviar\./)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
describe("borrador del trámite", () => {
  it("guarda el borrador en el dispositivo y lo ofrece al volver", async () => {
    const u = await montarLogueado();
    await u.type(screen.getByLabelText(/Apellido/), "Prueba");
    await u.click(screen.getByRole("button", { name: "Guardar borrador" }));
    expect(screen.getByText(/Borrador guardado/)).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem("portal_borrador_u-1")!)).toMatchObject({ apellido: "Prueba" });

    // Vuelve a entrar: el borrador está esperando y se puede retomar.
    cleanup();
    const u2 = await montarLogueado();
    await u2.click(await screen.findByRole("button", { name: "Retomar" }));
    expect((screen.getByLabelText(/Apellido/) as HTMLInputElement).value).toBe("Prueba");
  });

  it("descartar borra el borrador guardado", async () => {
    localStorage.setItem("portal_borrador_u-1", JSON.stringify({ apellido: "Vieja", savedAt: new Date().toISOString() }));
    const u = await montarLogueado();
    await u.click(await screen.findByRole("button", { name: "Descartar" }));
    expect(localStorage.getItem("portal_borrador_u-1")).toBeNull();
    expect(screen.queryByRole("button", { name: "Retomar" })).toBeNull();
  });
});

// ---------------------------------------------------------------------------
describe("mis solicitudes", () => {
  const SOL = {
    numero: "SOL-1", estado: "EN_EVALUACION", producto: "Crédito Personal", monto: 500000,
    plazo: 12, cuota_estimada: 58333, tna: 60, fecha: "2026-03-01", motivo_rechazo: "",
  };

  it("lista las solicitudes con su estado en castellano", async () => {
    api.misSolicitudes.mockResolvedValue([SOL]);
    const u = await montarLogueado();
    await u.click(screen.getByRole("button", { name: "Mis solicitudes" }));
    expect(await screen.findByText("SOL-1")).toBeInTheDocument();
    expect(screen.getByText("En evaluación")).toBeInTheDocument();
  });

  it("muestra el motivo del rechazo en la fila", async () => {
    api.misSolicitudes.mockResolvedValue([{ ...SOL, estado: "RECHAZADA", motivo_rechazo: "Sin margen de afectación" }]);
    const u = await montarLogueado();
    await u.click(screen.getByRole("button", { name: "Mis solicitudes" }));
    expect(await screen.findByText("Rechazada")).toBeInTheDocument();
    expect(screen.getByText("Sin margen de afectación")).toBeInTheDocument();
  });

  it("al abrir el detalle muestra el seguimiento del expediente y el cronograma", async () => {
    api.misSolicitudes.mockResolvedValue([SOL]);
    api.solicitudDetalle.mockResolvedValue({
      ...SOL, estado: "APROBADA", sistema: "FRANCES", destino: "VIVIENDA", segmento: "AGENTE_PUBLICO",
      edad: 40, antiguedad_meses: 60, sueldo: 900000, afectacion: 25, total_a_pagar: 700000,
      cuotas: [{ numero: 1, vencimiento: "2026-04-10", capital: 30000, interes: 28333, cargos: 0, impuestos: 0, total: 58333 }],
    });
    const u = await montarLogueado();
    await u.click(screen.getByRole("button", { name: "Mis solicitudes" }));
    await u.click(await screen.findByText("SOL-1"));

    const pasos = await screen.findByRole("list", { name: "Estado del trámite" });
    expect(within(pasos).getByText("Enviada")).toBeInTheDocument();
    expect(within(pasos).getByText("Otorgada")).toBeInTheDocument();
    expect(await screen.findByText("Total a pagar")).toBeInTheDocument();
    expect(screen.getByText(/Sistema Francés · TNA 60%/)).toBeInTheDocument();
  });

  it("el expediente rechazado corta en tres pasos y explica el motivo", async () => {
    api.misSolicitudes.mockResolvedValue([SOL]);
    api.solicitudDetalle.mockResolvedValue({
      ...SOL, estado: "RECHAZADA", motivo_rechazo: "Deuda en otra entidad", sistema: "FRANCES", destino: "",
      segmento: "", edad: null, antiguedad_meses: null, sueldo: null, afectacion: null, total_a_pagar: 0, cuotas: [],
    });
    const u = await montarLogueado();
    await u.click(screen.getByRole("button", { name: "Mis solicitudes" }));
    await u.click(await screen.findByText("SOL-1"));

    const pasos = await screen.findByRole("list", { name: "Estado del trámite" });
    expect(within(pasos).getAllByRole("listitem")).toHaveLength(3);
    expect(await screen.findByText(/Motivo del rechazo: Deuda en otra entidad/)).toBeInTheDocument();
  });

  it("informa cuando el listado no se puede traer", async () => {
    api.misSolicitudes.mockRejectedValue(new Error("Error 503"));
    const u = await montarLogueado();
    await u.click(screen.getByRole("button", { name: "Mis solicitudes" }));
    expect(await screen.findByText(/Error 503/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
describe("mis créditos", () => {
  const CRED = {
    contrato: "CR-9", producto: "Crédito Personal", monto: 500000, saldo: 300000, estado: "ACTIVO",
    tna: 60, plazo: 12, cuotas_pagadas: 4, cuotas_total: 12, progreso: 33, en_mora: false,
    proxima: { numero: 5, vencimiento: "2026-04-10", total: 58333, vencida: false },
  };

  it("sin créditos otorgados lo dice con todas las letras", async () => {
    const u = await montarLogueado();
    await u.click(screen.getByRole("button", { name: "Mis créditos" }));
    expect(await screen.findByText(/Todavía no tenés créditos otorgados/)).toBeInTheDocument();
  });

  it("lista el crédito con su avance y la próxima cuota", async () => {
    api.misCreditos.mockResolvedValue([CRED]);
    const u = await montarLogueado();
    await u.click(screen.getByRole("button", { name: "Mis créditos" }));
    expect(await screen.findByText("CR-9")).toBeInTheDocument();
    expect(screen.getByText("Activo")).toBeInTheDocument();
    expect(screen.getByText("4/12")).toBeInTheDocument();
  });

  it("la mora pisa el estado del crédito", async () => {
    api.misCreditos.mockResolvedValue([{ ...CRED, en_mora: true }]);
    const u = await montarLogueado();
    await u.click(screen.getByRole("button", { name: "Mis créditos" }));
    expect(await screen.findByText("En mora")).toBeInTheDocument();
    expect(screen.queryByText("Activo")).toBeNull();
  });

  it("el detalle abre el estado de cuenta cuota por cuota", async () => {
    api.misCreditos.mockResolvedValue([CRED]);
    api.creditoDetalle.mockResolvedValue({
      ...CRED, fecha_alta: "2025-12-01",
      cuotas: [
        { numero: 1, vencimiento: "2026-01-10", total: 58333, pagado: 58333, estado: "PAGADA", vencida: false },
        { numero: 2, vencimiento: "2026-02-10", total: 58333, pagado: 0, estado: "PENDIENTE", vencida: true },
      ],
    });
    const u = await montarLogueado();
    await u.click(screen.getByRole("button", { name: "Mis créditos" }));
    await u.click(await screen.findByText("CR-9"));
    expect(await screen.findByText("Monto otorgado")).toBeInTheDocument();
    expect(screen.getByText("Pagada")).toBeInTheDocument();
    expect(screen.getByText("Vencida")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
describe("notificaciones", () => {
  it("la campana muestra cuántas hay y las despliega", async () => {
    api.notificaciones.mockResolvedValue([
      { tipo: "mora", titulo: "Cuota vencida", detalle: "La cuota 3 venció el 10/03", fecha: "2026-03-11", contrato: "CR-9" },
    ]);
    const u = await montarLogueado();
    const campana = await screen.findByRole("button", { name: "Notificaciones" });
    expect(within(campana).getByText("1")).toBeInTheDocument();
    await u.click(campana);
    expect(screen.getByText("Cuota vencida")).toBeInTheDocument();
    expect(screen.getByText("La cuota 3 venció el 10/03")).toBeInTheDocument();
  });

  it("sin notificaciones no molesta con el contador", async () => {
    const u = await montarLogueado();
    await u.click(await screen.findByRole("button", { name: "Notificaciones" }));
    expect(screen.getByText("No tenés notificaciones.")).toBeInTheDocument();
  });
});
