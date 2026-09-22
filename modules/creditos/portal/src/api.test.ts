import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, nuevoId, token } from "./api";

const API = "/api/creditos";

function respuesta(data: any, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
}

/** Reemplaza fetch por un mock. Acepta una Response fija (se clona) o una función por llamada. */
function mockFetch(r: any) {
  const f = vi.fn(typeof r === "function" ? r : async () => (r instanceof Response ? r.clone() : r));
  vi.stubGlobal("fetch", f);
  return f;
}

/** Último `init` con el que se llamó a fetch. */
const init = (f: any) => f.mock.calls.at(-1)[1] || {};
const url = (f: any) => f.mock.calls.at(-1)[0];

// ---------------------------------------------------------------------------
describe("token de sesión del portal", () => {
  it("guarda, lee y borra el token en localStorage", () => {
    expect(token.get()).toBe("");
    token.set("tok-1");
    expect(localStorage.getItem("portal_token")).toBe("tok-1");
    expect(token.get()).toBe("tok-1");
    token.clear();
    expect(token.get()).toBe("");
  });

  it("no rompe si el navegador bloquea el storage", () => {
    const err = () => { throw new Error("storage bloqueado"); };
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(err);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(err);
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(err);
    expect(token.get()).toBe("");
    expect(() => token.set("x")).not.toThrow();
    expect(() => token.clear()).not.toThrow();
    vi.restoreAllMocks();
  });
});

// ---------------------------------------------------------------------------
describe("requests JSON", () => {
  it("pega contra la API del portal y manda JSON", async () => {
    const f = mockFetch(respuesta({ ok: true }));
    await expect(api.me()).resolves.toEqual({ ok: true });
    expect(url(f)).toBe(`${API}/portal/me`);
    expect((init(f).headers as any)["Content-Type"]).toBe("application/json");
  });

  it("sin token no manda Authorization", async () => {
    const f = mockFetch(respuesta({}));
    await api.productos();
    expect((init(f).headers as any).Authorization).toBeUndefined();
  });

  it("con token manda el Bearer", async () => {
    token.set("tok-abc");
    const f = mockFetch(respuesta({}));
    await api.haberes();
    expect((init(f).headers as any).Authorization).toBe("Bearer tok-abc");
  });

  it("propaga el detalle del backend cuando falla", async () => {
    mockFetch(respuesta({ detail: "El monto supera el máximo" }, 422));
    await expect(api.simular({ producto_id: "p1", monto: 1, plazo: 1 }))
      .rejects.toThrow("El monto supera el máximo");
  });

  it("si el error no trae cuerpo usable informa el status", async () => {
    mockFetch(new Response("no-json", { status: 500 }));
    await expect(api.misSolicitudes()).rejects.toThrow("Error 500");
  });
});

// ---------------------------------------------------------------------------
describe("sesión expirada (H-159)", () => {
  it("un 401 borra el token, avisa a la app y explica el error", async () => {
    token.set("tok-viejo");
    mockFetch(respuesta({ detail: "token vencido" }, 401));
    const escucha = vi.fn();
    window.addEventListener("portal:sesion-expirada", escucha);

    await expect(api.me()).rejects.toThrow("Tu sesión expiró. Volvé a ingresar.");

    expect(token.get()).toBe("");
    expect(escucha).toHaveBeenCalledTimes(1);
    window.removeEventListener("portal:sesion-expirada", escucha);
  });

  it("también expulsa si el 401 llega en una subida o en una descarga", async () => {
    token.set("tok-viejo");
    mockFetch(respuesta({}, 401));
    const escucha = vi.fn();
    window.addEventListener("portal:sesion-expirada", escucha);

    await expect(api.docSubir("SOL-1", new File(["x"], "dni.png", { type: "image/png" }), "DNI_FRENTE"))
      .rejects.toThrow(/sesión expiró/);
    await expect(api.docAbrir("SOL-1", "doc-1")).rejects.toThrow(/sesión expiró/);

    expect(escucha).toHaveBeenCalledTimes(2);
    window.removeEventListener("portal:sesion-expirada", escucha);
  });
});

// ---------------------------------------------------------------------------
describe("endpoints del portal", () => {
  beforeEach(() => token.set("tok-ok"));

  it("simular manda el cuerpo con producto, monto y plazo", async () => {
    const f = mockFetch(respuesta({ cuota_promedio: 100 }));
    await api.simular({ producto_id: "pp_1", monto: 500000, plazo: 12, sueldo: 900000 });
    expect(url(f)).toBe(`${API}/portal/simular`);
    expect(init(f).method).toBe("POST");
    expect(JSON.parse(init(f).body)).toEqual({ producto_id: "pp_1", monto: 500000, plazo: 12, sueldo: 900000 });
  });

  it("pre-aprobado consulta el máximo que califica", async () => {
    const f = mockFetch(respuesta({ monto_maximo: 800000 }));
    await expect(api.preAprobado({ producto_id: "pp_1", plazo: 24, sueldo: 900000, afectacion_max: 30 }))
      .resolves.toEqual({ monto_maximo: 800000 });
    expect(url(f)).toBe(`${API}/portal/pre-aprobado`);
  });

  it("enviar solicitud viaja con Idempotency-Key (doble clic = una sola solicitud)", async () => {
    const f = mockFetch(respuesta({ numero: "SOL-7" }));
    await api.enviarSolicitud({ producto_id: "pp_1", monto: 100, plazo: 6, cbu: "0".repeat(22) }, "idem-123");
    expect((init(f).headers as any)["Idempotency-Key"]).toBe("idem-123");
    expect(init(f).method).toBe("POST");
  });

  it("el detalle de una solicitud y el de un crédito usan su identificador en la URL", async () => {
    const f = mockFetch(respuesta({}));
    await api.solicitudDetalle("SOL-7");
    expect(url(f)).toBe(`${API}/portal/solicitudes/SOL-7`);
    await api.creditoDetalle("CR-9");
    expect(url(f)).toBe(`${API}/portal/creditos/CR-9`);
  });

  it("listados: solicitudes, créditos y notificaciones", async () => {
    const f = mockFetch(respuesta([]));
    await api.misSolicitudes();
    expect(url(f)).toBe(`${API}/portal/solicitudes`);
    await api.misCreditos();
    expect(url(f)).toBe(`${API}/portal/creditos`);
    await api.notificaciones();
    expect(url(f)).toBe(`${API}/portal/notificaciones`);
  });

  it("loginUrl no necesita token (todavía no hay sesión)", async () => {
    token.clear();
    const f = mockFetch(respuesta({ authorize_url: "https://mi.catamarca/oidc" }));
    await expect(api.loginUrl()).resolves.toEqual({ authorize_url: "https://mi.catamarca/oidc" });
    expect(url(f)).toBe(`${API}/portal/auth/login`);
    expect((init(f).headers as any).Authorization).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
describe("documentos adjuntos", () => {
  beforeEach(() => token.set("tok-ok"));

  it("la subida va multipart: sin Content-Type manual y con archivo + tipo", async () => {
    const f = mockFetch(respuesta({ id: "doc-1" }));
    const file = new File(["contenido"], "recibo.pdf", { type: "application/pdf" });
    await expect(api.docSubir("SOL-7", file, "RECIBO")).resolves.toEqual({ id: "doc-1" });

    expect(url(f)).toBe(`${API}/portal/solicitudes/SOL-7/documentos`);
    const cfg = init(f);
    expect(cfg.method).toBe("POST");
    expect((cfg.headers as any)["Content-Type"]).toBeUndefined();      // lo pone el navegador con el boundary
    expect((cfg.headers as any).Authorization).toBe("Bearer tok-ok");
    expect(cfg.body).toBeInstanceOf(FormData);
    expect((cfg.body as FormData).get("tipo")).toBe("RECIBO");
    expect((cfg.body as FormData).get("archivo")).toBe(file);
  });

  it("una subida rechazada explica el motivo del backend", async () => {
    mockFetch(respuesta({ detail: "Formato no permitido" }, 415));
    const file = new File(["x"], "virus.exe", { type: "application/octet-stream" });
    await expect(api.docSubir("SOL-7", file, "OTRO")).rejects.toThrow("Formato no permitido");
  });

  it("listar y borrar documentos", async () => {
    const f = mockFetch(respuesta({ items: [], puede_subir: true }));
    await expect(api.docsListar("SOL-7")).resolves.toEqual({ items: [], puede_subir: true });
    expect(url(f)).toBe(`${API}/portal/solicitudes/SOL-7/documentos`);

    mockFetch(respuesta({}));
    await api.docBorrar("SOL-7", "doc-1");
    expect(init(vi.mocked(fetch)).method).toBe("DELETE");
  });
});

// ---------------------------------------------------------------------------
describe("descarga autenticada de un adjunto", () => {
  const crear = vi.fn(() => "blob:portal/1");
  const revocar = vi.fn();
  const abrir = vi.fn();

  beforeEach(() => {
    token.set("tok-ok");
    vi.stubGlobal("URL", Object.assign(Object.create(URL), URL, { createObjectURL: crear, revokeObjectURL: revocar }));
    vi.stubGlobal("open", abrir);
  });
  afterEach(() => vi.useRealTimers());

  it("abre el archivo en otra pestaña y libera la URL temporal", async () => {
    vi.useFakeTimers();
    const f = mockFetch(new Response("pdf", { status: 200, headers: { "Content-Type": "application/pdf" } }));
    await api.docAbrir("SOL-7", "doc-1");

    expect(url(f)).toBe(`${API}/portal/solicitudes/SOL-7/documentos/doc-1`);
    expect((init(f).headers as any).Authorization).toBe("Bearer tok-ok");
    expect(abrir).toHaveBeenCalledWith("blob:portal/1", "_blank");

    expect(revocar).not.toHaveBeenCalled();
    vi.advanceTimersByTime(60000);
    expect(revocar).toHaveBeenCalledWith("blob:portal/1");
  });

  it("si el archivo no está no abre nada", async () => {
    mockFetch(new Response("", { status: 404 }));
    await expect(api.docAbrir("SOL-7", "doc-x")).rejects.toThrow("Error 404");
    expect(abrir).not.toHaveBeenCalled();
  });
});


describe("nuevoId (clave de idempotencia)", () => {
  const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

  it("sin HTTPS (no hay crypto.randomUUID) igual genera un UUID v4 válido y distinto cada vez", () => {
    const original = globalThis.crypto.randomUUID;
    Object.defineProperty(globalThis.crypto, "randomUUID", { configurable: true, value: undefined });
    try {
      const a = nuevoId(), b = nuevoId();
      expect(a).toMatch(UUID);
      expect(b).toMatch(UUID);
      expect(a).not.toBe(b);
    } finally {
      Object.defineProperty(globalThis.crypto, "randomUUID", { configurable: true, value: original });
    }
  });

  it("con randomUUID disponible lo usa", () => {
    const spy = vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue("11111111-1111-4111-8111-111111111111" as any);
    expect(nuevoId()).toBe("11111111-1111-4111-8111-111111111111");
    spy.mockRestore();
  });
});
