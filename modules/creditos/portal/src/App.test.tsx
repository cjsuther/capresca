import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { token } from "./api";

// La capa HTTP tiene sus propios tests (api.test.ts): acá se reemplaza por dobles para
// probar la pantalla del ciudadano sin red. `token` sí es el real (localStorage).
const h = vi.hoisted(() => ({
  api: {
    loginUrl: vi.fn(), evidenciaIngreso: vi.fn(), me: vi.fn(), haberes: vi.fn(), productos: vi.fn(), simular: vi.fn(),
    preAprobado: vi.fn(), enviarSolicitud: vi.fn(), misSolicitudes: vi.fn(), solicitudDetalle: vi.fn(),
    docsListar: vi.fn(), docSubir: vi.fn(), docAbrir: vi.fn(), docBorrar: vi.fn(),
    misCreditos: vi.fn(), creditoDetalle: vi.fn(), notificaciones: vi.fn(), videos: vi.fn(),
    requisitos: vi.fn(), corregirCbu: vi.fn(), reenviar: vi.fn(),
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

const VIDEOS = [
  { id: "video1", titulo: "Video 1", url: "/portal-creditos/videos/video1.mp4" },
  { id: "video2", titulo: "Video 2", url: "/portal-creditos/videos/video2.mp4" },
  { id: "video3", titulo: "Video 3", url: "/portal-creditos/videos/video3.mp4" },
];

const locationOriginal = window.location;
function stubLocation(pathname = "/", hash = "") {
  Object.defineProperty(window, "location", {
    configurable: true, writable: true,
    value: { pathname, hash, search: "", href: `http://localhost${pathname}${hash}`, assign: vi.fn() },
  });
  return window.location as any;
}

/** La respuesta de /requisitos: los documentos (obligatorios salvo que se diga) y los datos de la línea. */
const conDocs = (documentos: any[], campos: any[] = []) =>
  ({ campos, documentos: documentos.map((d) => ({ obligatorio: true, ...d })) });

const DOCS_PEDIDOS = [
  { tipo: "DNI_FRENTE", titulo: "DNI (frente)", ayuda: "" },
  { tipo: "DNI_DORSO", titulo: "DNI (dorso)", ayuda: "" },
  { tipo: "SELFIE_DNI", titulo: "Selfie con el DNI en la mano", ayuda: "Una foto tuya sosteniendo el DNI." },
  { tipo: "RECIBO", titulo: "Recibo de sueldo", ayuda: "" },
  { tipo: "CERTIFICADO_SERVICIOS", titulo: "Certificado de servicios", ayuda: "" },
  { tipo: "CONSTANCIA_CBU", titulo: "Constancia de CBU", ayuda: "" },
];

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
  api.videos.mockResolvedValue(VIDEOS);
  api.requisitos.mockResolvedValue(conDocs(DOCS_PEDIDOS));
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

const archivo = (nombre: string, tipo: string, tam = 1000) => {
  const f = new File(["x"], nombre, { type: tipo });
  Object.defineProperty(f, "size", { value: tam });
  return f;
};
const ETIQUETA: Record<string, string> = { DNI_FRENTE: "DNI (frente)", DNI_DORSO: "DNI (dorso)",
                                           SELFIE_DNI: "Selfie con el DNI en la mano", RECIBO: "Recibo de sueldo",
                                           CERTIFICADO_SERVICIOS: "Certificado de servicios",
                                           CONSTANCIA_CBU: "Constancia de CBU" };
const casillero = (tipo: string) => screen.getByLabelText(`Adjuntar ${ETIQUETA[tipo]}`) as HTMLInputElement;

/** Adjunta un archivo en el casillero del documento indicado (paso 3). */
async function adjuntar(_u: ReturnType<typeof userEvent.setup>, tipo: string, f: File) {
  fireEvent.change(casillero(tipo), { target: { files: [f] } });
}

/** Adjunta toda la documentación obligatoria (los seis documentos del paso 3). */
async function adjuntarRequeridos(u: ReturnType<typeof userEvent.setup>) {
  const docs = { DNI_FRENTE: archivo("dni-frente.jpg", "image/jpeg"), DNI_DORSO: archivo("dni-dorso.jpg", "image/jpeg"),
                 SELFIE_DNI: archivo("selfie.jpg", "image/jpeg"), RECIBO: archivo("recibo.pdf", "application/pdf"),
                 CERTIFICADO_SERVICIOS: archivo("certificado.pdf", "application/pdf"),
                 CONSTANCIA_CBU: archivo("cbu.pdf", "application/pdf") };
  for (const [t, f] of Object.entries(docs)) await adjuntar(u, t, f);
  return docs;
}

/** Datos + simulación → paso 3 (documentación). */
async function llegarADocumentacion(u: ReturnType<typeof userEvent.setup>) {
  await completarDatos(u);
  await u.click(await screen.findByRole("button", { name: /Continuar/ }));
  expect(await screen.findByText(/Adjuntá una imagen o PDF/)).toBeInTheDocument();
}

/** Completa el paso 1 (identidad + situación + nacimiento y contacto) y pasa a la simulación. */
const NACIMIENTO = `${new Date().getFullYear() - 40}-01-01`;

async function completarDatos(u: ReturnType<typeof userEvent.setup>) {
  await u.type(screen.getByLabelText(/Apellido/), "Prueba");
  await u.type(screen.getByLabelText(/^Nombre/), "Ana");
  await u.type(screen.getByLabelText(/^CUIL/), "20301234563");
  await u.selectOptions(screen.getByLabelText(/Situación laboral/), "AGENTE_PUBLICO");
  fireEvent.change(screen.getByLabelText(/Fecha de nacimiento/), { target: { value: NACIMIENTO } });
  await u.clear(screen.getByLabelText(/Email/));
  await u.type(screen.getByLabelText(/Email/), "ana@example.com");
  await u.type(screen.getByLabelText(/Teléfono/), "3834123456");
  await u.click(screen.getByRole("button", { name: /Continuar/ }));
}

// ---------------------------------------------------------------------------
describe("paso 1 · datos del solicitante", () => {
  it("el email arranca vacío, aunque Mi Catamarca traiga uno", async () => {
    // El correo de la cuenta de Mi Catamarca puede no ser el que usa: lo escribe él.
    await montarLogueado();
    expect(screen.getByLabelText(/Email/)).toHaveValue("");
  });

  it("el teléfono no lleva un número de ejemplo adentro", async () => {
    await montarLogueado();
    expect(screen.getByLabelText(/Teléfono/)).not.toHaveAttribute("placeholder");
  });

  it("la antigüedad admite hasta dos dígitos de años", async () => {
    const u = await montarLogueado();
    const campo = screen.getByLabelText(/Antigüedad/);
    await u.type(campo, "123");
    expect(campo).toHaveValue(12);          // es un campo numérico: no deja pasar el tercer dígito
    expect(campo).toHaveAttribute("max", "99");
  });

  it("el sueldo se muestra con formato de moneda y dos decimales", async () => {
    const u = await montarLogueado();
    const campo = screen.getByLabelText(/Sueldo neto/);
    await u.type(campo, "900000");
    await u.tab();                                   // al salir del campo se formatea
    // El formato es-AR separa el símbolo con un espacio duro.
    expect((campo as HTMLInputElement).value.replace(/\u00a0/g, " ")).toBe("$ 900.000,00");

    await u.click(campo);                            // al volver a editarlo, el número pelado
    expect(campo).toHaveValue("900000");
  });

  it("el sueldo formateado viaja como número al simular", async () => {
    const u = await montarLogueado();
    await u.type(screen.getByLabelText(/Sueldo neto/), "1.234.567,89");
    await u.tab();
    await completarDatos(u);
    await waitFor(() => expect(api.simular).toHaveBeenCalledWith(
      expect.objectContaining({ sueldo: 1234567.89 })));
  });
});

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

  it("si el ingreso falla muestra lo que se le mandó a Mi Catamarca y lo que respondió", async () => {
    api.evidenciaIngreso.mockResolvedValue({
      intento: "a".repeat(32), fecha: "2026-10-16T15:38:01Z", resultado: "ERROR",
      error: "HTTPStatusError: Client error '403 Forbidden'",
      llamadas: [{
        paso: "token", metodo: "POST", url: "https://api-mi.catamarca.gob.ar/openid/token/",
        estado_http: 403, duracion_ms: 85, error: "", fecha: "2026-10-16T15:38:01Z",
        solicitud: { headers: { accept: "application/json" },
                     datos: { grant_type: "authorization_code", client_id: "023709", client_secret: "[oculto, 40 caracteres]" } },
        respuesta: { headers: { "cf-mitigated": "challenge" }, cuerpo: "<title>Just a moment...</title>" },
      }],
    });
    stubLocation("/ingreso", "#error=sso&evidencia=" + "a".repeat(32));
    render(<App />);
    expect(await screen.findByText(/No se pudo completar el ingreso/)).toBeInTheDocument();
    expect(api.evidenciaIngreso).toHaveBeenCalledWith("a".repeat(32));
    expect(await screen.findByText("POST https://api-mi.catamarca.gob.ar/openid/token/")).toBeInTheDocument();
    expect(screen.getByText("403")).toBeInTheDocument();
    expect(screen.getByLabelText("Enviado en el paso 1")).toHaveTextContent('"client_id": "023709"');
    expect(screen.getByLabelText("Enviado en el paso 1")).toHaveTextContent("[oculto, 40 caracteres]");
    expect(screen.getByLabelText("Recibido en el paso 1")).toHaveTextContent('"cf-mitigated": "challenge"');
    expect(screen.getByLabelText("Recibido en el paso 1")).toHaveTextContent("Just a moment...");
  });

  it("un error sin evidencia sólo muestra el aviso", async () => {
    stubLocation("/ingreso", "#error=sso");
    render(<App />);
    expect(await screen.findByText(/No se pudo completar el ingreso/)).toBeInTheDocument();
    expect(api.evidenciaIngreso).not.toHaveBeenCalled();
    expect(screen.queryByRole("region", { name: "Detalle técnico del ingreso" })).toBeNull();
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

  it("valida el largo del CUIL", async () => {
    const u = await montarLogueado();
    await u.type(screen.getByLabelText(/Apellido/), "Prueba");
    await u.type(screen.getByLabelText(/^Nombre/), "Ana");
    await u.type(screen.getByLabelText(/^CUIL/), "123");
    await u.click(screen.getByRole("button", { name: /Continuar/ }));
    expect(screen.getByText("El CUIL debe tener 11 dígitos.")).toBeInTheDocument();
  });

  it("valida el dígito verificador del CUIL", async () => {
    const u = await montarLogueado();
    await u.type(screen.getByLabelText(/Apellido/), "Prueba");
    await u.type(screen.getByLabelText(/^Nombre/), "Ana");
    await u.type(screen.getByLabelText(/^CUIL/), "20301234560");
    await u.click(screen.getByRole("button", { name: /Continuar/ }));
    expect(screen.getByText("El CUIL no es válido: revisá los números.")).toBeInTheDocument();
  });

  it("el CUIL descarta lo que no sean dígitos y se muestra con guiones", async () => {
    await montarLogueado();
    const cuil = screen.getByLabelText(/^CUIL/) as HTMLInputElement;
    fireEvent.change(cuil, { target: { value: "20.30123456.3" } });
    expect(cuil.value).toBe("20-30123456-3");
  });

  it("exige la situación laboral", async () => {
    const u = await montarLogueado();
    await u.type(screen.getByLabelText(/Apellido/), "Prueba");
    await u.type(screen.getByLabelText(/^Nombre/), "Ana");
    await u.type(screen.getByLabelText(/^CUIL/), "20301234563");
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
describe("paso 3 · documentación", () => {
  const slot = (tipo: string) => screen.getByLabelText(`Adjuntar ${ETIQUETA[tipo]}`).closest("li") as HTMLElement;

  it("el paso 1 ya no pide documentación", async () => {
    await montarLogueado();
    expect(document.querySelector('input[type="file"]')).toBeNull();
  });

  it("pide exactamente los seis documentos del trámite (sin otros tipos)", async () => {
    const u = await montarLogueado();
    await llegarADocumentacion(u);
    const lista = screen.getByRole("list", { name: "Documentación requerida" });
    expect(within(lista).getAllByRole("listitem")).toHaveLength(6);
    expect(document.querySelectorAll('input[type="file"]')).toHaveLength(6);
    expect(within(lista).getByText("Selfie con el DNI en la mano")).toBeInTheDocument();
    expect(within(lista).getByText("Certificado de servicios")).toBeInTheDocument();
    expect(within(lista).getByText("Constancia de CBU")).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Tipo de documento" })).toBeNull();
    expect(screen.queryByText("Otro")).toBeNull();
  });

  it("cada casillero guarda un solo archivo: adjuntar de nuevo lo reemplaza", async () => {
    const u = await montarLogueado();
    await llegarADocumentacion(u);
    await adjuntar(u, "DNI_FRENTE", archivo("dni.png", "image/png", 2048));
    expect(within(slot("DNI_FRENTE")).getByText(/dni\.png · 2 KB/)).toBeInTheDocument();
    expect(within(slot("DNI_FRENTE")).getByText("Cambiar")).toBeInTheDocument();
    await adjuntar(u, "DNI_FRENTE", archivo("dni-mejor.jpg", "image/jpeg"));
    expect(within(slot("DNI_FRENTE")).getByText(/dni-mejor\.jpg/)).toBeInTheDocument();
    expect(screen.queryByText(/dni\.png/)).toBeNull();
    expect(screen.getByText("Te faltan 5 documentos.")).toBeInTheDocument();
  });

  it("rechaza formatos que no son imagen ni PDF", async () => {
    const u = await montarLogueado();
    await llegarADocumentacion(u);
    await adjuntar(u, "RECIBO", archivo("planilla.xlsx", "application/vnd.ms-excel"));
    expect(await screen.findByText("Recibo de sueldo: formato no permitido (JPG, PNG o PDF).")).toBeInTheDocument();
    expect(within(slot("RECIBO")).getByText("Falta adjuntar")).toBeInTheDocument();
  });

  it("rechaza archivos de más de 5 MB", async () => {
    const u = await montarLogueado();
    await llegarADocumentacion(u);
    await adjuntar(u, "RECIBO", archivo("recibo.pdf", "application/pdf", 6 * 1024 * 1024));
    expect(await screen.findByText("Recibo de sueldo: el archivo supera los 5 MB.")).toBeInTheDocument();
  });

  it("permite quitar un adjunto elegido", async () => {
    const u = await montarLogueado();
    await llegarADocumentacion(u);
    await adjuntar(u, "DNI_DORSO", archivo("dorso.pdf", "application/pdf"));
    await u.click(await screen.findByRole("button", { name: "Quitar DNI (dorso)" }));
    expect(screen.queryByText(/dorso\.pdf/)).toBeNull();
    expect(within(slot("DNI_DORSO")).getByText("Falta adjuntar")).toBeInTheDocument();
  });

  it("no deja seguir si falta alguno de los documentos", async () => {
    const u = await montarLogueado();
    await llegarADocumentacion(u);
    await adjuntar(u, "DNI_FRENTE", archivo("dni.jpg", "image/jpeg"));
    expect(screen.getByText("Te faltan 5 documentos.")).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: /Continuar/ }));
    expect(screen.getByText("Falta adjuntar: DNI (dorso), Selfie con el DNI en la mano, Recibo de sueldo, "
                            + "Certificado de servicios, Constancia de CBU.")).toBeInTheDocument();
    expect(screen.queryByText(/Mirá los videos/)).toBeNull();
  });

  it("con los seis documentos pasa a los videos", async () => {
    const u = await montarLogueado();
    await llegarADocumentacion(u);
    await adjuntarRequeridos(u);
    const lista = screen.getByRole("list", { name: "Documentación requerida" });
    expect(within(lista).queryByText("Falta adjuntar")).toBeNull();
    await u.click(screen.getByRole("button", { name: /Continuar/ }));
    expect(await screen.findByText(/Mirá los videos/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
describe("paso 4 · videos", () => {
  /** Simula ver un video completo: avanza el tiempo de a poco y dispara el final. */
  function verCompleto(video: HTMLVideoElement, duracion = 10) {
    let t = 0;
    Object.defineProperty(video, "duration", { configurable: true, get: () => duracion });
    Object.defineProperty(video, "currentTime", { configurable: true, get: () => t, set: (v) => { t = v; } });
    fireEvent.loadedMetadata(video);
    for (let x = 0.25; x <= duracion; x += 0.25) { t = x; fireEvent.timeUpdate(video); }
    fireEvent.ended(video);
  }
  const videosEnPantalla = () => Array.from(document.querySelectorAll("video")) as HTMLVideoElement[];

  async function llegarAVideos() {
    const u = await montarLogueado();
    await llegarADocumentacion(u);
    await adjuntarRequeridos(u);
    await u.click(screen.getByRole("button", { name: /Continuar/ }));
    expect(await screen.findByText(/Mirá los videos/)).toBeInTheDocument();
    return u;
  }

  it("muestra los tres videos en orden; sólo el primero se puede reproducir", async () => {
    await llegarAVideos();
    expect(screen.getByRole("article", { name: "Video 1: Video 1" })).toBeInTheDocument();
    expect(videosEnPantalla()).toHaveLength(1);
    expect(within(screen.getByRole("article", { name: "Video 2: Video 2" })).getByText("Se habilita al terminar el anterior")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Continuar/ })).toBeDisabled();
  });

  it("al terminar cada video se habilita el siguiente y, con los tres, se puede continuar", async () => {
    const u = await llegarAVideos();
    for (let i = 1; i <= 3; i++) {
      verCompleto(videosEnPantalla()[i - 1]);
      await waitFor(() => expect(within(screen.getByRole("article", { name: `Video ${i}: Video ${i}` })).getByText("Visto")).toBeInTheDocument());
    }
    expect(screen.getByText("✓ Viste todos los videos.")).toBeInTheDocument();
    await u.click(screen.getByRole("button", { name: /Continuar/ }));
    expect(await screen.findByText("Revisá y confirmá tu solicitud")).toBeInTheDocument();
  });

  it("lo visto se recuerda si se recarga la página", async () => {
    await llegarAVideos();
    verCompleto(videosEnPantalla()[0]);
    await waitFor(() => expect(JSON.parse(localStorage.getItem("portal_videos_u-1")!)).toEqual(["video1"]));
  });


  // La documentación que se pide la configura cada oficina (Créditos → Parámetros).
  it("pide sólo los documentos configurados", async () => {
    api.requisitos.mockResolvedValue(conDocs([
      { tipo: "DNI_FRENTE", titulo: "DNI (frente)", ayuda: "" },
      { tipo: "RECIBO", titulo: "Recibo de sueldo", ayuda: "" },
    ]));
    const u = await montarLogueado();
    await llegarADocumentacion(u);

    expect(screen.getByLabelText("Adjuntar DNI (frente)")).toBeInTheDocument();
    expect(screen.getByLabelText("Adjuntar Recibo de sueldo")).toBeInTheDocument();
    expect(screen.queryByLabelText("Adjuntar Constancia de CBU")).not.toBeInTheDocument();

    await adjuntar(u, "DNI_FRENTE", archivo("dni.jpg", "image/jpeg"));
    await adjuntar(u, "RECIBO", archivo("recibo.pdf", "application/pdf"));
    await u.click(screen.getByRole("button", { name: /Continuar/ }));
    expect(await screen.findByText(/Mirá los videos/)).toBeInTheDocument();
  });

  it("si no se pide ninguno, el paso no aparece", async () => {
    api.requisitos.mockResolvedValue(conDocs([]));
    const u = await montarLogueado();
    await completarDatos(u);
    await u.click(await screen.findByRole("button", { name: /Continuar/ }));

    // De la simulación se pasa derecho a los videos, y la guía no muestra el paso.
    expect(await screen.findByText(/Mirá los videos/)).toBeInTheDocument();
    expect(screen.queryByText("Documentación")).not.toBeInTheDocument();
  });

  it("si la lista no se pudo cargar, no deja pasar de largo el requisito", async () => {
    api.requisitos.mockRejectedValue(new Error("sin red"));
    const u = await montarLogueado();
    await completarDatos(u);
    await u.click(await screen.findByRole("button", { name: /Continuar/ }));

    expect(await screen.findByText(/No se pudo cargar lo que pide este crédito/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Continuar/ })).toBeDisabled();
  });

  // Con el paso omitido desde Parámetros de créditos, el backend devuelve la lista vacía.
  it("si el paso está omitido, de la documentación se pasa derecho a confirmar", async () => {
    api.videos.mockResolvedValue([]);
    const u = await montarLogueado();
    await llegarADocumentacion(u);
    await adjuntarRequeridos(u);
    await u.click(screen.getByRole("button", { name: /Continuar/ }));

    expect(await screen.findByText("Revisá y confirmá tu solicitud")).toBeInTheDocument();
    expect(screen.queryByText(/Mirá los videos/)).not.toBeInTheDocument();
    // La guía de pasos tampoco lo muestra.
    expect(screen.queryByText("Videos")).not.toBeInTheDocument();
  });

  it("si los videos no se pueden cargar no deja continuar", async () => {
    api.videos.mockRejectedValue(new Error("caído"));
    await llegarAVideos();
    expect(screen.getByText(/No se pudieron cargar los videos/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Continuar/ })).toBeDisabled();
  });
});

// ---------------------------------------------------------------------------
describe("paso 2 · simulación", () => {
  it("en un sitio sin HTTPS (sin crypto.randomUUID) simula y deja continuar", async () => {
    // Regresión: servido por HTTP en una IP, randomUUID no existe; el error se tapaba y no aparecía
    // ni la simulación ni el botón "Continuar".
    vi.spyOn(globalThis.crypto, "randomUUID").mockRestore?.();
    const original = globalThis.crypto.randomUUID;
    Object.defineProperty(globalThis.crypto, "randomUUID", { configurable: true, value: undefined });
    try {
      const u = await montarLogueado();
      await completarDatos(u);
      expect(await screen.findByText("Total a pagar")).toBeInTheDocument();
      await u.click(await screen.findByRole("button", { name: /Continuar/ }));
      expect(await screen.findByText(/Adjuntá una imagen o PDF/)).toBeInTheDocument();
    } finally {
      Object.defineProperty(globalThis.crypto, "randomUUID", { configurable: true, value: original });
    }
  });

  it("si la simulación falla lo avisa en vez de quedar trabado", async () => {
    api.simular.mockRejectedValue(new Error("El módulo Configuraciones no está disponible"));
    const u = await montarLogueado();
    await completarDatos(u);
    expect(await screen.findByText(/No pudimos calcular tu crédito: El módulo Configuraciones no está disponible/)).toBeInTheDocument();
  });

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
    api.preAprobado.mockResolvedValue({ monto_maximo: 0, monto_min: 100000, cuota: 0, afectacion: 0, plazo: 12, afectacion_max: 25 });
    const u = await montarLogueado();
    await u.type(screen.getByLabelText(/Sueldo neto/), "100000");
    await completarDatos(u);
    // El tope que muestra es el de la línea (25%), no un 30% fijo del portal.
    expect(await screen.findByText(/la cuota se pasa del 25% de tu sueldo/)).toBeInTheDocument();
    expect(api.preAprobado).toHaveBeenCalledWith(expect.not.objectContaining({ afectacion_max: expect.anything() }));
  });

  it("se puede volver al paso 1 sin perder los datos", async () => {
    const u = await montarLogueado();
    await completarDatos(u);
    await u.click(await screen.findByRole("button", { name: /Volver/ }));
    expect((screen.getByLabelText(/Apellido/) as HTMLInputElement).value).toBe("Prueba");
  });
});

// ---------------------------------------------------------------------------
describe("paso 5 · confirmación y envío", () => {
  /** Recorre los pasos 1–4 con los videos ya vistos (quedan guardados en el dispositivo). */
  async function llegarAConfirmacion() {
    localStorage.setItem("portal_videos_u-1", JSON.stringify(VIDEOS.map((v) => v.id)));
    const u = await montarLogueado();
    await llegarADocumentacion(u);
    const docs = await adjuntarRequeridos(u);
    await u.click(screen.getByRole("button", { name: /Continuar/ }));
    await u.click(await screen.findByRole("button", { name: /Continuar/ }));
    expect(await screen.findByText("Revisá y confirmá tu solicitud")).toBeInTheDocument();
    return { u, docs };
  }

  it("con código de descuento avisa cómo le viene la cuota en el recibo", async () => {
    api.productos.mockResolvedValue([{ ...PRODUCTO, cobro: { modalidad: "CODIGO_DESCUENTO", codigoDescuento: "4521",
      conceptoRecibo: "CAPRESCA PREST PERSONAL", detalle: "Se descuenta desde el mes siguiente." } }]);
    api.simular.mockResolvedValue({ ...SIM, cuotas: [{ numero: 1, vencimiento: "2026-11-10", capital: 40000, interes: 20000, cargos: 0, impuestos: 0, total: 60000 }] });
    await llegarAConfirmacion();
    const aviso = screen.getByRole("note", { name: "Cómo se cobra la cuota" });
    expect(aviso).toHaveTextContent("La cuota de $ 60.000,00 se descuenta directamente de tu sueldo");
    expect(aviso).toHaveTextContent("«CAPRESCA PREST PERSONAL», código de descuento 4521");
    expect(aviso).toHaveTextContent("Se descuenta desde el mes siguiente.");
  });

  it("sin forma de cobro configurada no avisa nada", async () => {
    await llegarAConfirmacion();
    expect(screen.queryByRole("note", { name: "Cómo se cobra la cuota" })).toBeNull();
  });

  it("no deja enviar sin CBU completo ni aceptaciones", async () => {
    const { u } = await llegarAConfirmacion();
    const enviar = screen.getByRole("button", { name: /Confirmar y enviar/ });
    expect(enviar).toBeDisabled();
    await u.type(screen.getByLabelText(/CBU/), "123");
    expect(screen.getByText("Faltan 19 dígito(s).")).toBeInTheDocument();
    expect(enviar).toBeDisabled();
  });

  it("con CBU y las dos aceptaciones envía la solicitud y muestra el número", async () => {
    api.enviarSolicitud.mockResolvedValue({ numero: "SOL-7" });
    const { u } = await llegarAConfirmacion();
    await u.type(screen.getByLabelText(/CBU/), "2".repeat(22));
    await u.click(screen.getByRole("checkbox", { name: /términos y condiciones/ }));
    await u.click(screen.getByRole("checkbox", { name: /tratamiento de mis datos/ }));
    await u.click(screen.getByRole("button", { name: /Confirmar y enviar/ }));

    await waitFor(() => expect(api.enviarSolicitud).toHaveBeenCalled());
    const [cuerpo, idem] = api.enviarSolicitud.mock.calls[0];
    expect(cuerpo).toMatchObject({ producto_id: "pp_1", cbu: "2".repeat(22), acepta_terminos: true, acepta_datos: true, cuil: "20301234563",
                                   videos_vistos: ["video1", "video2", "video3"] });
    expect(idem).toBe("idem-fijo");
    expect(await screen.findByText(/Solicitud SOL-7 enviada/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Mis solicitudes" })).toBeInTheDocument();
    // la próxima solicitud vuelve a pedir los videos
    expect(localStorage.getItem("portal_videos_u-1")).toBeNull();
  });

  it("sube los adjuntos elegidos y avisa si alguno falla", async () => {
    api.enviarSolicitud.mockResolvedValue({ numero: "SOL-8" });
    api.docSubir.mockRejectedValueOnce(new Error("upload caído")).mockResolvedValue({});
    const { u, docs } = await llegarAConfirmacion();
    await u.type(screen.getByLabelText(/CBU/), "2".repeat(22));
    await u.click(screen.getByRole("checkbox", { name: /términos y condiciones/ }));
    await u.click(screen.getByRole("checkbox", { name: /tratamiento de mis datos/ }));
    await u.click(screen.getByRole("button", { name: /Confirmar y enviar/ }));

    await waitFor(() => expect(api.docSubir).toHaveBeenCalledTimes(6));
    expect(api.docSubir).toHaveBeenCalledWith("SOL-8", docs.DNI_FRENTE, "DNI_FRENTE");
    expect(api.docSubir).toHaveBeenCalledWith("SOL-8", docs.SELFIE_DNI, "SELFIE_DNI");
    expect(api.docSubir).toHaveBeenCalledWith("SOL-8", docs.RECIBO, "RECIBO");
    expect(api.docSubir).toHaveBeenCalledWith("SOL-8", docs.CERTIFICADO_SERVICIOS, "CERTIFICADO_SERVICIOS");
    expect(api.docSubir).toHaveBeenCalledWith("SOL-8", docs.CONSTANCIA_CBU, "CONSTANCIA_CBU");
    expect(await screen.findByText(/No se pudieron adjuntar 1 archivo/)).toBeInTheDocument();
  });

  it("si el backend rechaza el envío lo muestra y no borra el formulario", async () => {
    api.enviarSolicitud.mockRejectedValue(new Error("Ya tenés una solicitud en curso"));
    const { u } = await llegarAConfirmacion();
    await u.type(screen.getByLabelText(/CBU/), "2".repeat(22));
    await u.click(screen.getByRole("checkbox", { name: /términos y condiciones/ }));
    await u.click(screen.getByRole("checkbox", { name: /tratamiento de mis datos/ }));
    await u.click(screen.getByRole("button", { name: /Confirmar y enviar/ }));
    expect(await screen.findByText(/Ya tenés una solicitud en curso/)).toBeInTheDocument();
    expect(screen.getByText("Revisá y confirmá tu solicitud")).toBeInTheDocument();
  });

  it("no se puede enviar si la simulación dice que no califica", async () => {
    api.simular.mockResolvedValue({ ...SIM, elegible: false, motivos: ["Edad máxima superada"] });
    const { u } = await llegarAConfirmacion();
    await u.type(screen.getByLabelText(/CBU/), "2".repeat(22));
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

  it("un borrador guardado en los videos se retoma en Documentación (los archivos no se guardan)", async () => {
    localStorage.setItem("portal_borrador_u-1", JSON.stringify({ paso: 5, apellido: "Prueba", nombre: "Ana", cuil: "20301234563",
      segmento: "AGENTE_PUBLICO", prodId: "pp_1", savedAt: new Date().toISOString() }));
    const u = await montarLogueado();
    await u.click(await screen.findByRole("button", { name: "Retomar" }));
    expect(await screen.findByText(/Adjuntá una imagen o PDF/)).toBeInTheDocument();
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
describe("solicitud observada: corregir y reenviar", () => {
  const SOL = {
    numero: "SOL-9", estado: "OBSERVADA", producto: "Crédito Personal", monto: 500000,
    plazo: 12, cuota_estimada: 58333, tna: 60, fecha: "2026-03-01", motivo_rechazo: "",
  };
  const BASE = {
    ...SOL, sistema: "FRANCES", destino: "", segmento: "", fecha_nacimiento: null, edad: null, antiguedad_meses: null,
    sueldo: null, afectacion: null, total_a_pagar: 700000, cuotas: [], puede_adjuntar: true,
  };
  const DOCS = (corregido: boolean) => [
    { tipo: "DNI_FRENTE", titulo: "DNI (frente)", ayuda: "", obligatorio: true,
      adjunto: { id: "d1", nombre: corregido ? "dni-nuevo.png" : "dni.png" }, observado: true, corregido },
    { tipo: "RECIBO", titulo: "Recibo de sueldo", ayuda: "", obligatorio: true,
      adjunto: { id: "d2", nombre: "recibo.pdf" }, observado: false, corregido: false },
  ];
  const OBS = (pendientes: string[], cbu = false) => ({
    detalle: "La foto del DNI está borrosa.", fecha: "2026-10-05", cbu, cbu_corregido: false,
    cbu_actual: "2850590940090418135201", pendientes,
  });

  async function abrir() {
    api.misSolicitudes.mockResolvedValue([SOL]);
    const u = await montarLogueado();
    await u.click(screen.getByRole("button", { name: "Mis solicitudes" }));
    expect(await screen.findByText("Tenés que corregir")).toBeInTheDocument();
    await u.click(screen.getByText("SOL-9"));
    return u;
  }

  it("muestra la explicación del asesor y no deja reenviar con algo pendiente", async () => {
    api.solicitudDetalle.mockResolvedValue({ ...BASE, documentacion: DOCS(false), observacion: OBS(["DNI (frente)"]) });
    await abrir();
    expect(await screen.findByText("La foto del DNI está borrosa.")).toBeInTheDocument();
    expect(screen.getByText("Falta: DNI (frente).")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reenviar solicitud" })).toBeDisabled();
    // Sólo se reemplaza lo observado: el recibo no se toca.
    expect(screen.getByLabelText("Reemplazar DNI (frente)")).toBeInTheDocument();
    expect(screen.queryByLabelText(/Recibo de sueldo/)).toBeNull();
  });

  it("reemplaza el documento observado y reenvía", async () => {
    api.solicitudDetalle
      .mockResolvedValueOnce({ ...BASE, documentacion: DOCS(false), observacion: OBS(["DNI (frente)"]) })
      .mockResolvedValue({ ...BASE, documentacion: DOCS(true), observacion: OBS([]) });
    api.docSubir.mockResolvedValue({});
    api.reenviar.mockResolvedValue({ ...SOL, estado: "EN_EVALUACION" });
    const u = await abrir();

    const archivo = new File(["x"], "dni-nuevo.png", { type: "image/png" });
    await u.upload(await screen.findByLabelText("Reemplazar DNI (frente)"), archivo);
    await waitFor(() => expect(api.docSubir).toHaveBeenCalledWith("SOL-9", archivo, "DNI_FRENTE"));
    expect(await screen.findByText(/✓ Corregido/)).toBeInTheDocument();

    await u.click(screen.getByRole("button", { name: "Reenviar solicitud" }));
    await waitFor(() => expect(api.reenviar).toHaveBeenCalledWith("SOL-9"));
    expect(await screen.findByText("Listo: la solicitud SOL-9 volvió a evaluación.")).toBeInTheDocument();
  });

  it("corrige el CBU cuando el asesor lo pide", async () => {
    api.solicitudDetalle.mockResolvedValue({ ...BASE, documentacion: DOCS(true), observacion: OBS(["el CBU"], true) });
    api.corregirCbu.mockResolvedValue({ ok: true });
    const u = await abrir();
    const campo = await screen.findByLabelText("CBU corregido");
    await u.clear(campo);
    await u.type(campo, "0110599520000001234567");
    await u.click(screen.getByRole("button", { name: "Guardar CBU" }));
    await waitFor(() => expect(api.corregirCbu).toHaveBeenCalledWith("SOL-9", "0110599520000001234567"));
  });

  it("en evaluación deja adjuntar el documento que no llegó", async () => {
    api.solicitudDetalle.mockResolvedValue({ ...BASE, estado: "EN_EVALUACION", observacion: null, documentacion: [
      { tipo: "CERTIFICADO_SERVICIOS", titulo: "Certificado de servicios", ayuda: "", obligatorio: true,
        adjunto: null, observado: false, corregido: false }] });
    await abrir();
    expect(await screen.findByLabelText("Adjuntar Certificado de servicios")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reenviar solicitud" })).toBeNull();
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
      fecha_nacimiento: NACIMIENTO, edad: 40, antiguedad_meses: 60, sueldo: 900000, afectacion: 25, total_a_pagar: 700000,
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
      segmento: "", fecha_nacimiento: null, edad: null, antiguedad_meses: null, sueldo: null, afectacion: null, total_a_pagar: 0, cuotas: [],
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

describe("paso 3 · lo que pide cada línea", () => {
  const SALUD = conDocs(
    [{ tipo: "ORDEN_MEDICA", titulo: "Orden médica", ayuda: "Firmada por el profesional" },
     { tipo: "PRESUPUESTO", titulo: "Presupuesto del prestador", ayuda: "", obligatorio: false }],
    [{ codigo: "COBERTURA", etiqueta: "Obra social", ayuda: "", tipo: "UNICA",
       opciones: ["OSEP", "PAMI", "Sin cobertura"], obligatorio: true },
     { codigo: "TRATAMIENTO", etiqueta: "Tipo de tratamiento", ayuda: "", tipo: "MULTIPLE",
       opciones: ["Cirugía", "Odontología", "Óptica"], obligatorio: false }]);

  beforeEach(() => {
    api.requisitos.mockResolvedValue(SALUD);
    api.videos.mockResolvedValue([]);          // sin videos: de acá se pasa a confirmar
  });

  async function llegarAlPaso3() {
    const u = await montarLogueado();
    await completarDatos(u);
    await u.click(await screen.findByRole("button", { name: /Continuar/ }));
    expect(await screen.findByText("Datos del crédito")).toBeInTheDocument();
    return u;
  }

  it("pide lo de la línea elegida, con sus combos y sus documentos", async () => {
    await llegarAlPaso3();
    expect(api.requisitos).toHaveBeenCalledWith("pp_1");
    expect(screen.getByRole("combobox", { name: /Obra social/ })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Óptica" })).toBeInTheDocument();
    expect(screen.getByLabelText("Adjuntar Orden médica")).toBeInTheDocument();
    expect(screen.getByText("(opcional)", { selector: ".p-doc-meta .p-fine" })).toBeInTheDocument();
  });

  it("no deja seguir sin el combo obligatorio ni sin el documento obligatorio", async () => {
    const u = await llegarAlPaso3();
    await u.click(screen.getByRole("button", { name: /Continuar/ }));
    expect(screen.getByText("Completá: Obra social.")).toBeInTheDocument();

    await u.selectOptions(screen.getByRole("combobox", { name: /Obra social/ }), "PAMI");
    await u.click(screen.getByRole("button", { name: /Continuar/ }));
    expect(screen.getByText("Falta adjuntar: Orden médica.")).toBeInTheDocument();
  });

  it("el documento opcional y el combo opcional se pueden saltear, y lo elegido viaja con la solicitud", async () => {
    api.enviarSolicitud.mockResolvedValue({ numero: "SOL-9" });
    api.docSubir.mockResolvedValue({});
    const u = await llegarAlPaso3();
    await u.selectOptions(screen.getByRole("combobox", { name: /Obra social/ }), "OSEP");
    await u.click(screen.getByRole("checkbox", { name: "Óptica" }));
    await u.click(screen.getByRole("checkbox", { name: "Cirugía" }));
    fireEvent.change(screen.getByLabelText("Adjuntar Orden médica"),
                     { target: { files: [archivo("orden.pdf", "application/pdf")] } });
    await u.click(screen.getByRole("button", { name: /Continuar/ }));

    expect(await screen.findByText("Revisá y confirmá tu solicitud")).toBeInTheDocument();
    expect(screen.getByText("Tipo de tratamiento").parentElement).toHaveTextContent("Óptica, Cirugía");
    await u.type(screen.getByLabelText(/CBU/), "2".repeat(22));
    await u.click(screen.getByRole("checkbox", { name: /términos y condiciones/ }));
    await u.click(screen.getByRole("checkbox", { name: /tratamiento de mis datos/ }));
    await u.click(screen.getByRole("button", { name: /Confirmar y enviar/ }));

    await waitFor(() => expect(api.enviarSolicitud).toHaveBeenCalled());
    expect(api.enviarSolicitud.mock.calls[0][0].respuestas).toEqual({ COBERTURA: ["OSEP"], TRATAMIENTO: ["Óptica", "Cirugía"] });
    await waitFor(() => expect(api.docSubir).toHaveBeenCalledTimes(1));
    expect(api.docSubir.mock.calls[0][2]).toBe("ORDEN_MEDICA");
  });

  it("una línea que no pide nada saltea el paso", async () => {
    api.requisitos.mockResolvedValue(conDocs([]));
    const u = await montarLogueado();
    await completarDatos(u);
    await u.click(await screen.findByRole("button", { name: /Continuar/ }));
    expect(await screen.findByText("Revisá y confirmá tu solicitud")).toBeInTheDocument();
  });
});

describe("espera después de un rechazo", () => {
  it("con un rechazo reciente no muestra el formulario y dice desde cuándo puede volver a pedir", async () => {
    api.me.mockResolvedValue({ ...CIUDADANO,
      espera_rechazo: "Tu solicitud SOL-3 fue rechazada el 01/10/2026. Podés volver a solicitar un crédito desde el 31/10/2026." });
    await montarLogueado();
    expect(await screen.findByText(/Podés volver a solicitar un crédito desde el 31\/10\/2026/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/^CUIL/)).toBeNull();
  });
});
