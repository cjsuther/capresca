import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ConfigurarCreditosPage from "./ConfigurarCreditosPage";
import { creditos } from "../../../../api/creditos";
import { useAuthStore } from "../../../../context/authStore";

vi.mock("../../../../api/creditos", () => ({
  creditos: {
    ppCatalogo: vi.fn(), ppFamilias: vi.fn(), ppCrear: vi.fn(), ppGuardarConfig: vi.fn(),
    ppEstado: vi.fn(), ppPublicarDirecto: vi.fn(), ppBorrar: vi.fn(), ppPreview: vi.fn(),
    ppSimListar: vi.fn(), ppSimGuardar: vi.fn(), ppSimBorrar: vi.fn(), ppRaw: vi.fn(),
    ppVersiones: vi.fn(), impuestos: vi.fn(), indices: vi.fn(), ctoSegmentos: vi.fn(),
    editarDisponibilidad: vi.fn(),
  },
}));

const CFG = {
  sistema: "FRANCES", modalidad: "FIJA", tna: 52, baseDias: "ACT/365", frecuencia: "MENSUAL",
  montoMin: 100000, montoMax: 5000000, plazoMin: 6, plazoMax: 60, graciaCapital: 0,
  cargoOtorg: 2, moraTNA: 120, tnaNegociable: false, tnaMin: 0, tnaMax: 0,
};

const comp = (codigo, nombre, extra = {}) => ({
  codigo, nombre, categoria: "CORE", multiple: false, requerido: true, orden: 1, activo: true,
  config: {}, ...extra,
});

const BORRADOR = {
  id: "p1", nombre: "Préstamo Personal", codigo: "CP-1", grupo: "LENDING", familia: "PERSONALES",
  version: 1, estado: "BORRADOR", publicadas: [], cfg: { ...CFG }, vigentePortal: null,
  componentes: [
    comp("TERM_AMOUNT", "Montos y plazos", { orden: 1 }),
    comp("INTEREST", "Interés", { orden: 2 }),
    comp("REPAYMENT_SCHEDULE", "Cronograma", { orden: 3, config: { diaPago: 5, primerVencimientoDias: 30, ajusteFinDeSemana: "SIGUIENTE_HABIL", tipoCuota: "VENCIDA" } }),
    comp("AVAILABILITY", "Disponibilidad", { orden: 4, requerido: false, activo: true, config: { canales: ["SUCURSAL"], segmentos: [] } }),
    comp("TAX", "Impuestos", { orden: 5, requerido: false, multiple: true, activo: false, config: { items: [] } }),
  ],
};
const PUBLICADO = { ...BORRADOR, id: "p2", nombre: "Personal Publicado", codigo: "CP-2", estado: "PUBLICADO", publicadas: [1], vigentePortal: 1 };

// El cronograma del backend cierra: Σ capital = monto y saldo final 0 (si no, el builder bloquea publicar).
const PREVIEW = {
  rows: [
    { numero_cuota: 1, fecha_vencimiento: "2026-04-05", saldo_inicial: 1200000, capital: 600000, interes: 52000, cargos: 1000, total: 653000, saldo_final: 600000 },
    { numero_cuota: 2, fecha_vencimiento: "2026-05-05", saldo_inicial: 600000, capital: 600000, interes: 26000, cargos: 1000, total: 627000, saldo_final: 0 },
  ],
  resumen: { totalCuotas: 1280000, totalInteres: 78000, totalCargos: 2000, tea: 66, cft: 71 },
};

const sesion = (acciones) =>
  useAuthStore.setState({ token: "tok", user: { username: "ana" },
    permissions: { modules: ["creditos"], actions: { creditos: acciones } } });

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  sesion(["creditos:read", "creditos:write"]);
  creditos.ppCatalogo.mockResolvedValue({ items: [BORRADOR, PUBLICADO], permisos: { edita: true, aprueba: true }, usuario: "ana" });
  creditos.ppFamilias.mockResolvedValue({ items: [{ id: "f1", grupo: "LENDING", nombre: "PERSONALES" }] });
  creditos.impuestos.mockResolvedValue({ items: [{ codigo: "IVA", nombre: "IVA", base: "INTERES", alicuota: 21 }] });
  creditos.indices.mockResolvedValue({ items: [{ codigo: "BADLAR", nombre: "Badlar", valor: 45 }] });
  creditos.ctoSegmentos.mockResolvedValue({ segmentos: ["AGENTE_PUBLICO"], canales: ["SUCURSAL", "WEB"] });
  creditos.ppPreview.mockResolvedValue(PREVIEW);
  creditos.ppSimListar.mockResolvedValue({ items: [] });
  creditos.ppGuardarConfig.mockResolvedValue(BORRADOR);
  creditos.ppPublicarDirecto.mockResolvedValue({ producto: { ...BORRADOR, estado: "PUBLICADO" }, needs_approval: false });
  creditos.ppCrear.mockResolvedValue({ ...BORRADOR, id: "p3", nombre: "Nueva" });
  creditos.ppVersiones.mockResolvedValue({ items: [
    { version: 1, cfg: { ...CFG }, componentes: BORRADOR.componentes },
    { version: 2, cfg: { ...CFG, tna: 60 }, componentes: BORRADOR.componentes },
  ] });
  creditos.ppRaw.mockResolvedValue({ id: "p1", cfg: CFG });
});

const abrirLinea = async (u, nombre = "Préstamo Personal") => u.click(await screen.findByText(nombre));

describe("Configurar Créditos · catálogo", () => {
  it("lista las líneas con su estado y marca las que no se ofrecen", async () => {
    render(<ConfigurarCreditosPage />);
    expect(await screen.findByText("Préstamo Personal")).toBeInTheDocument();
    // "Borrador"/"Publicado" también son opciones del filtro: se miran en la tabla.
    const tabla = screen.getByRole("table");
    expect(within(tabla).getByText("Borrador")).toBeInTheDocument();
    expect(within(tabla).getByText("Publicado")).toBeInTheDocument();
    expect(within(tabla).getByText("no ofrecido")).toBeInTheDocument();
  });

  it("filtra por estado", async () => {
    const u = userEvent.setup();
    render(<ConfigurarCreditosPage />);
    await screen.findByText("Préstamo Personal");

    await u.selectOptions(screen.getByLabelText("Estado"), "PUBLICADO");
    expect(screen.queryByText("Préstamo Personal")).toBeNull();
    expect(screen.getByText("Personal Publicado")).toBeInTheDocument();
  });

  it("crea una línea nueva eligiendo copiar o derivar", async () => {
    const u = userEvent.setup();
    render(<ConfigurarCreditosPage />);
    await screen.findByText("Préstamo Personal");

    await u.click(screen.getByRole("button", { name: /Nueva línea/ }));
    const modal = await screen.findByRole("dialog", { name: "Nueva línea de crédito" });
    await u.type(within(modal).getByLabelText("Nombre"), "Personal 2027");
    await u.selectOptions(within(modal).getByLabelText("Basar en"), "p1");
    await u.click(within(modal).getByRole("radio", { checked: false }));   // derivar (hereda)
    await u.click(within(modal).getByRole("button", { name: "Crear y diseñar" }));

    await waitFor(() => expect(creditos.ppCrear).toHaveBeenCalledWith(
      expect.objectContaining({ nombre: "Personal 2027", padre_id: "p1" })));
  });

  it("en sólo lectura no se crean líneas", async () => {
    sesion(["creditos:read"]);
    render(<ConfigurarCreditosPage />);
    await screen.findByText("Préstamo Personal");
    expect(screen.queryByRole("button", { name: /Nueva línea/ })).toBeNull();
  });
});

describe("Configurar Créditos · builder", () => {
  it("abre la línea con sus componentes y las tasas calculadas por el backend", async () => {
    const u = userEvent.setup();
    render(<ConfigurarCreditosPage />);
    await abrirLinea(u);

    expect(await screen.findByRole("heading", { name: "Préstamo Personal" })).toBeInTheDocument();
    // El nombre está en la paleta y como título del editor abierto.
    expect(screen.getAllByText("Montos y plazos").length).toBe(2);
    await waitFor(() => expect(creditos.ppPreview).toHaveBeenCalled());
    expect(await screen.findByText("66.00%")).toBeInTheDocument();   // TEA del backend
    expect(screen.getByText("71.00%")).toBeInTheDocument();          // CFT
  });

  it("editar una condición del componente de interés recalcula", async () => {
    const u = userEvent.setup();
    render(<ConfigurarCreditosPage />);
    await abrirLinea(u);

    await u.click(await screen.findByText("Interés"));
    const tna = screen.getByLabelText("Tasa nominal anual (%)");
    await u.clear(tna);
    await u.type(tna, "70");
    await waitFor(() => expect(creditos.ppPreview).toHaveBeenLastCalledWith(expect.objectContaining({ tna: 70 })));
  });

  it("marca los errores de validación del componente", async () => {
    const u = userEvent.setup();
    render(<ConfigurarCreditosPage />);
    await abrirLinea(u);

    const montoMin = await screen.findByLabelText("Monto mínimo");
    await u.clear(montoMin);
    await u.type(montoMin, "9000000");                            // mayor que el máximo
    expect(await screen.findByText(/Monto mínimo > máximo/)).toBeInTheDocument();
  });

  it("guarda el borrador con la configuración completa", async () => {
    const u = userEvent.setup();
    render(<ConfigurarCreditosPage />);
    await abrirLinea(u);

    await u.click(await screen.findByRole("button", { name: /Guardar y seguir después/ }));
    await waitFor(() => expect(creditos.ppGuardarConfig).toHaveBeenCalledWith("p1", expect.objectContaining({
      sistema: "FRANCES", componentes: expect.any(Array),
    })));
    expect(await screen.findByText("Borrador guardado.")).toBeInTheDocument();
  });

  it("publicar avisa cuando queda pendiente el cuatro-ojos", async () => {
    creditos.ppPublicarDirecto.mockResolvedValue({ needs_approval: true });
    const u = userEvent.setup();
    render(<ConfigurarCreditosPage />);
    await abrirLinea(u);

    // El botón se habilita recién cuando el cronograma del backend valida (Σ capital, saldo 0).
    await screen.findByText("66.00%");
    await waitFor(() => expect(screen.getByRole("button", { name: "Publicar" })).toBeEnabled());
    await u.click(screen.getByRole("button", { name: "Publicar" }));
    expect(await screen.findByText(/requiere la aprobación de otra persona/)).toBeInTheDocument();
  });

  it("una línea publicada se duplica como préstamo independiente", async () => {
    const u = userEvent.setup();
    render(<ConfigurarCreditosPage />);
    await abrirLinea(u, "Personal Publicado");

    await u.click(await screen.findByRole("button", { name: /Duplicar/ }));
    const modal = await screen.findByRole("dialog", { name: /Duplicar como préstamo nuevo/ });
    await u.click(within(modal).getByRole("button", { name: "Crear copia" }));
    await waitFor(() => expect(creditos.ppCrear).toHaveBeenCalledWith(
      expect.objectContaining({ copiar_de: "p2", nombre: "Personal Publicado — copia" })));
  });

  it("retirar una línea publicada pide confirmación", async () => {
    creditos.ppEstado.mockResolvedValue({ ...PUBLICADO, estado: "RETIRADO" });
    const u = userEvent.setup();
    render(<ConfigurarCreditosPage />);
    await abrirLinea(u, "Personal Publicado");

    await u.click(await screen.findByRole("button", { name: "Retirar línea" }));
    const dialogo = await screen.findByRole("dialog", { name: "Retirar línea" });
    expect(creditos.ppEstado).not.toHaveBeenCalled();
    await u.click(within(dialogo).getByRole("button", { name: "Retirar" }));
    await waitFor(() => expect(creditos.ppEstado).toHaveBeenCalledWith("p2", "retirar"));
  });

  it("la disponibilidad se puede guardar aunque la línea esté publicada", async () => {
    creditos.editarDisponibilidad.mockResolvedValue(PUBLICADO);
    const u = userEvent.setup();
    render(<ConfigurarCreditosPage />);
    await abrirLinea(u, "Personal Publicado");

    await u.click(await screen.findByText("Disponibilidad"));
    await u.click(screen.getByRole("button", { name: "WEB" }));
    await u.click(screen.getByRole("button", { name: "Guardar disponibilidad" }));

    await waitFor(() => expect(creditos.editarDisponibilidad).toHaveBeenCalledWith("p2",
      expect.objectContaining({ activo: true, canales: ["SUCURSAL", "WEB"] })));
  });

  it("la prueba en vivo muestra validaciones y cronograma", async () => {
    const u = userEvent.setup();
    render(<ConfigurarCreditosPage />);
    await abrirLinea(u);

    await u.click(await screen.findByRole("button", { name: /Probar en vivo/ }));
    expect(await screen.findByText("Prueba en vivo")).toBeInTheDocument();
    expect(screen.getByText(/Cronograma proyectado/)).toBeInTheDocument();
    expect(screen.getByText("Σ capital = monto")).toBeInTheDocument();
  });

  it("comparar versiones muestra las diferencias", async () => {
    const u = userEvent.setup();
    render(<ConfigurarCreditosPage />);
    await abrirLinea(u);

    await u.click(await screen.findByRole("button", { name: /Comparar/ }));
    const modal = await screen.findByRole("dialog", { name: "Comparar versiones" });
    expect(within(modal).getByText("TNA %")).toBeInTheDocument();
    expect(within(modal).getByText("60")).toBeInTheDocument();
  });

  it("el inspector muestra el JSON de la línea", async () => {
    const u = userEvent.setup();
    render(<ConfigurarCreditosPage />);
    await abrirLinea(u);

    await u.click(await screen.findByRole("button", { name: "Datos" }));
    await waitFor(() => expect(creditos.ppRaw).toHaveBeenCalledWith("p1"));
    expect(await screen.findByRole("dialog", { name: /inspector/ })).toBeInTheDocument();
  });

  it("en sólo lectura el builder no deja editar ni publicar", async () => {
    sesion(["creditos:read"]);
    const u = userEvent.setup();
    render(<ConfigurarCreditosPage />);
    await abrirLinea(u);

    expect(await screen.findByLabelText("Monto mínimo")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Publicar" })).toBeDisabled();
  });
});
