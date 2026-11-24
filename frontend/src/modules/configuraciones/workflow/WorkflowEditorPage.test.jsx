import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import WorkflowEditorPage from "./WorkflowEditorPage";
import * as api from "../../../api/configuraciones";
import { ordenar } from "./layout";
import { exportarPng } from "./exportar";

// React Flow necesita medir el DOM (no hay en jsdom): se reemplaza por un doble que dibuja nodos y
// aristas como botones y emite los mismos cambios que el real. Lo que se prueba es el editor, no el canvas.
vi.mock("@xyflow/react", () => ({
  ReactFlow: ({ nodes, edges, onNodesChange, onEdgesChange, onConnect, children }) => (
    <div data-testid="rf">
      {nodes.map((n) => (
        <button key={n.id} data-selected={n.selected ? "si" : "no"} data-marca={n.data.marca || ""}
                data-problemas={n.data.problemas.length}
                onClick={() => onNodesChange([{ id: n.id, type: "select", selected: true }])}>nodo {n.data.nodo.nombre}</button>
      ))}
      {edges.map((e) => (
        <button key={e.id} onClick={() => onEdgesChange([{ id: e.id, type: "select", selected: true }])}>flecha {e.label}</button>
      ))}
      <button onClick={() => onNodesChange([{ id: "ap1", type: "position", position: { x: 300, y: 90 }, dragging: false }])}>mover ap1</button>
      <button onClick={() => onNodesChange([{ id: "ap1", type: "remove" }])}>borrar ap1</button>
      <button onClick={() => onConnect(window.__conectar)}>conectar</button>
      {children}
    </div>
  ),
  Background: () => null, Controls: () => null, MiniMap: () => null,
  Panel: ({ children }) => <div>{children}</div>,
  Handle: () => null, Position: { Top: "top", Bottom: "bottom" },
}));
vi.mock("./layout", () => ({ ordenar: vi.fn() }));
vi.mock("./exportar", async (orig) => ({ ...(await orig()), exportarPng: vi.fn() }));
vi.mock("./personas", () => ({ cargarPersonas: vi.fn().mockResolvedValue({ grupos: [], usuarios: ["ana"], deSeguridad: true }) }));
vi.mock("../../../api/configuraciones", async (orig) => ({
  ...(await orig()),
  listarProcesos: vi.fn(), verProceso: vi.fn(), verVersion: vi.fn(), crearBorrador: vi.fn(), guardarBorrador: vi.fn(),
  descartarBorrador: vi.fn(), publicarVersion: vi.fn(), retirarVersion: vi.fn(), habilitarProceso: vi.fn(),
  compararVersiones: vi.fn(),
}));

const serie = (...aps) => ({
  schema: 1,
  nodos: [{ id: "inicio", tipo: "inicio", nombre: "Inicio" },
    ...aps.map((nombre, i) => ({ id: `ap${i + 1}`, tipo: "aprobacion", nombre, asignar: { tipo: "rol", valor: "APROBAR" }, cuatroOjos: true })),
    { id: "fin", tipo: "fin", nombre: "Aprobado", resultado: "APROBADO" }],
  conexiones: [
    ...aps.flatMap((_, i) => [
      { id: `e${i}`, de: i === 0 ? "inicio" : `ap${i}`, a: `ap${i + 1}`, ...(i ? { salida: "aprobado" } : {}) },
      { id: `r${i}`, de: `ap${i + 1}`, a: "inicio", salida: "rechazado" }]),
    { id: "ef", de: `ap${aps.length}`, a: "fin", salida: "aprobado" }],
});
const resumen = (id, numero, estado, extra = {}) => ({ id, numero, estado, nota: "", publicadaPor: estado === "PUBLICADA" ? "ana" : "", ...extra });
const VERSION = (id, numero, estado, grafo = serie("Tesorero")) =>
  ({ ...resumen(id, numero, estado), procesoId: 1, grafo, layout: { inicio: { x: 0, y: 0 } }, revision: 1, problemas: [], compatibleMotorActual: true });
const PROCESO = (con = {}) => ({
  id: 1, modulo: "tesoreria", objeto: "LOTE_PAGO", nombre: "Aprobación de lote de pagos", descripcion: "", habilitado: true,
  publicada: resumen(10, 1, "PUBLICADA"), borrador: null, variables: { importe_total: { nombre: "Importe", tipo: "numero" } },
  versiones: [resumen(10, 1, "PUBLICADA")], ...con,
});
const conBorrador = () => PROCESO({ borrador: resumen(11, 2, "BORRADOR"), versiones: [resumen(11, 2, "BORRADOR"), resumen(10, 1, "PUBLICADA")] });

let versiones;
beforeEach(() => {
  vi.clearAllMocks();
  versiones = { 10: VERSION(10, 1, "PUBLICADA"), 11: VERSION(11, 2, "BORRADOR") };
  api.listarProcesos.mockResolvedValue({ procesos: [PROCESO()], puede: { editar: true, publicar: true } });
  api.verProceso.mockResolvedValue(PROCESO());
  api.verVersion.mockImplementation(async (id) => versiones[id]);
  api.guardarBorrador.mockImplementation(async (id, d) => ({ ...versiones[id], revision: d.revision + 1 }));
  api.compararVersiones.mockResolvedValue({ diff: { iguales: false, resumen: ["+ aprobacion «Gerencia»"], nodos: { agregados: ["ap2"], modificados: [] } } });
});
afterEach(() => vi.useRealTimers());

const nodo = (nombre) => screen.findByRole("button", { name: `nodo ${nombre}` });

describe("Editor gráfico del workflow", () => {
  it("muestra los procesos y la versión publicada en sólo lectura", async () => {
    render(<WorkflowEditorPage />);
    expect(await screen.findByRole("button", { name: /Aprobación de lote de pagos/ })).toHaveAttribute("aria-current", "true");
    await nodo("Tesorero");
    expect(screen.getByText("PUBLICADA")).toBeInTheDocument();
    expect(screen.queryByRole("toolbar", { name: "Agregar nodo" })).toBeNull();
    expect(screen.getByRole("button", { name: "Nuevo borrador" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retirar" })).toBeInTheDocument();
  });

  it("crea un borrador desde la publicada y lo abre editable", async () => {
    api.crearBorrador.mockResolvedValue(versiones[11]);
    api.verProceso.mockResolvedValueOnce(PROCESO()).mockResolvedValue(conBorrador());
    const u = userEvent.setup();
    render(<WorkflowEditorPage />);
    await u.click(await screen.findByRole("button", { name: "Nuevo borrador" }));
    await waitFor(() => expect(api.crearBorrador).toHaveBeenCalledWith(1));
    expect(await screen.findByRole("toolbar", { name: "Agregar nodo" })).toBeInTheDocument();
    expect(screen.getByText("BORRADOR")).toBeInTheDocument();
  });

  it("agrega una aprobación, la marca con errores en vivo y guarda solo (autosave)", async () => {
    api.verProceso.mockResolvedValue(conBorrador());
    const u = userEvent.setup();
    render(<WorkflowEditorPage />);
    await nodo("Tesorero");
    await u.click(within(screen.getByRole("toolbar", { name: "Agregar nodo" })).getByRole("button", { name: /Aprobación/ }));
    const nuevo = await nodo("Aprobación");
    expect(nuevo).toHaveAttribute("data-selected", "si");
    expect(Number(nuevo.dataset.problemas)).toBeGreaterThan(0);                  // huérfano y sin salidas
    expect(screen.getByRole("region", { name: "Validación" })).toHaveTextContent(/no se alcanza desde el Inicio/);
    expect(screen.getByRole("button", { name: "Publicar…" })).toBeDisabled();
    await waitFor(() => expect(api.guardarBorrador).toHaveBeenCalledTimes(1), { timeout: 3000 });
    const [id, datos] = api.guardarBorrador.mock.calls[0];
    expect(id).toBe(11);
    expect(datos.revision).toBe(1);
    expect(datos.grafo.nodos.map((n) => n.id)).toContain("ap2");
    expect(await screen.findByText("Guardado")).toBeInTheDocument();
  });

  it("mover, borrar y conectar en el diagrama cambian el grafo; las revisiones se encadenan", async () => {
    api.verProceso.mockResolvedValue(conBorrador());
    const u = userEvent.setup();
    render(<WorkflowEditorPage />);
    await nodo("Tesorero");
    await u.click(screen.getByRole("button", { name: "mover ap1" }));
    await waitFor(() => expect(api.guardarBorrador).toHaveBeenCalledTimes(1), { timeout: 3000 });
    expect(api.guardarBorrador.mock.calls[0][1].layout.ap1).toEqual({ x: 300, y: 90 });
    await u.click(screen.getByRole("button", { name: "borrar ap1" }));
    expect(screen.queryByRole("button", { name: "nodo Tesorero" })).toBeNull();
    window.__conectar = { source: "inicio", target: "fin" };
    await u.click(screen.getByRole("button", { name: "conectar" }));
    await waitFor(() => expect(api.guardarBorrador).toHaveBeenCalledTimes(2), { timeout: 3000 });
    const [, datos] = api.guardarBorrador.mock.calls[1];
    expect(datos.revision).toBe(2);                                              // la que devolvió el primer guardado
    expect(datos.grafo.conexiones).toEqual([{ id: "c1", de: "inicio", a: "fin" }]);
  });

  it("un conflicto de revisión deja el borrador en sólo lectura y lo explica", async () => {
    api.verProceso.mockResolvedValue(conBorrador());
    api.guardarBorrador.mockRejectedValue({ response: { status: 409, data: { detail: "Otro usuario guardó este borrador" } } });
    const u = userEvent.setup();
    render(<WorkflowEditorPage />);
    await nodo("Tesorero");
    await u.click(screen.getByRole("button", { name: "mover ap1" }));
    expect(await screen.findByText(/Otro usuario cambió este borrador/, {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByText("Otro usuario guardó este borrador")).toBeInTheDocument();
    expect(screen.queryByRole("toolbar", { name: "Agregar nodo" })).toBeNull();
  });

  it("publicar muestra los cambios, avisa si hay menos aprobaciones y manda la nota", async () => {
    versiones[10] = VERSION(10, 1, "PUBLICADA", serie("Tesorero", "Gerencia"));
    api.verProceso.mockResolvedValue(conBorrador());
    api.publicarVersion.mockResolvedValue({});
    const u = userEvent.setup();
    render(<WorkflowEditorPage />);
    await nodo("Tesorero");
    await u.click(screen.getByRole("button", { name: "Publicar…" }));
    const modal = await screen.findByRole("dialog");
    expect(within(modal).getByText("+ aprobacion «Gerencia»")).toBeInTheDocument();
    expect(within(modal).getByText(/menos aprobaciones que la vigente/)).toBeInTheDocument();
    await u.type(within(modal).getByLabelText(/Qué cambia/), "Saco gerencia");
    await u.click(within(modal).getByRole("button", { name: "Publicar" }));
    await waitFor(() => expect(api.publicarVersion).toHaveBeenCalledWith(11, "Saco gerencia"));
    expect(api.compararVersiones).toHaveBeenCalledWith(10, 11);
  });

  it("si la API rechaza la publicación, el modal muestra los problemas", async () => {
    api.verProceso.mockResolvedValue(conBorrador());
    api.publicarVersion.mockRejectedValue({ response: { data: { detail: { mensaje: "Todavía no se puede publicar", problemas: ["«X» es una decisión"] } } } });
    const u = userEvent.setup();
    render(<WorkflowEditorPage />);
    await nodo("Tesorero");
    await u.click(screen.getByRole("button", { name: "Publicar…" }));
    const modal = await screen.findByRole("dialog");
    await u.click(within(modal).getByRole("button", { name: "Publicar" }));
    expect(await within(modal).findByText(/Todavía no se puede publicar · «X» es una decisión/)).toBeInTheDocument();
  });

  it("un borrador con decisión se guarda pero no se publica, y lo avisa", async () => {
    const g = serie("Tesorero");
    g.nodos.push({ id: "dec1", tipo: "decision", nombre: "¿Importe alto?" });
    versiones[11] = VERSION(11, 2, "BORRADOR", g);
    api.verProceso.mockResolvedValue(conBorrador());
    render(<WorkflowEditorPage />);
    expect(await screen.findByText(/todavía no publicar/)).toBeInTheDocument();
    expect(screen.getByText(/«¿Importe alto\?» es una decisión/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Publicar…" })).toBeDisabled();
  });

  it("retirar y deshabilitar se confirman", async () => {
    api.retirarVersion.mockResolvedValue({});
    api.habilitarProceso.mockResolvedValue({});
    const u = userEvent.setup();
    render(<WorkflowEditorPage />);
    await nodo("Tesorero");
    await u.click(screen.getByRole("button", { name: "Retirar" }));
    const conf = screen.getByRole("dialog", { name: "Retirar la versión publicada" });
    expect(conf).toHaveTextContent(/se DESHABILITA/);
    await u.click(within(conf).getByRole("button", { name: "Retirar" }));
    await waitFor(() => expect(api.retirarVersion).toHaveBeenCalledWith(10));
    await u.click(await screen.findByRole("button", { name: "Deshabilitar" }));
    await u.click(within(screen.getByRole("dialog", { name: "Deshabilitar el workflow" })).getByRole("button", { name: "Deshabilitar" }));
    await waitFor(() => expect(api.habilitarProceso).toHaveBeenCalledWith(1, false));
  });

  it("descartar el borrador se confirma", async () => {
    api.verProceso.mockResolvedValue(conBorrador());
    api.descartarBorrador.mockResolvedValue(null);
    const u = userEvent.setup();
    render(<WorkflowEditorPage />);
    await nodo("Tesorero");
    await u.click(screen.getByRole("button", { name: "Descartar borrador" }));
    await u.click(within(screen.getByRole("dialog", { name: "Descartar el borrador" })).getByRole("button", { name: "Descartar" }));
    await waitFor(() => expect(api.descartarBorrador).toHaveBeenCalledWith(11));
  });

  it("comparar con otra versión lista los cambios y marca los nodos", async () => {
    versiones[11] = VERSION(11, 2, "BORRADOR", serie("Tesorero", "Gerencia"));
    api.verProceso.mockResolvedValue(conBorrador());
    const u = userEvent.setup();
    render(<WorkflowEditorPage />);
    await nodo("Gerencia");
    await u.selectOptions(screen.getByLabelText("Comparar con"), "10");
    expect(await screen.findByText("Cambios de v1 a v2")).toBeInTheDocument();
    expect(await nodo("Gerencia")).toHaveAttribute("data-marca", "agregado");
  });

  it("ordenar usa ELK y exportar genera el PNG", async () => {
    api.verProceso.mockResolvedValue(conBorrador());
    ordenar.mockResolvedValue({ inicio: { x: 0, y: 0 }, ap1: { x: 0, y: 150 }, fin: { x: 0, y: 300 } });
    const u = userEvent.setup();
    render(<WorkflowEditorPage />);
    await nodo("Tesorero");
    await u.click(screen.getByRole("button", { name: /Ordenar/ }));
    await waitFor(() => expect(api.guardarBorrador).toHaveBeenCalled(), { timeout: 3000 });
    expect(api.guardarBorrador.mock.lastCall[1].layout.ap1).toEqual({ x: 0, y: 150 });
    await u.click(screen.getByRole("button", { name: /PNG/ }));
    expect(exportarPng).toHaveBeenCalledWith(expect.anything(), expect.any(Array), "workflow-tesoreria-LOTE_PAGO-v2.png");
  });

  it("sin permiso de escritura es sólo lectura y no ofrece acciones", async () => {
    api.listarProcesos.mockResolvedValue({ procesos: [PROCESO()], puede: { editar: false, publicar: false } });
    api.verProceso.mockResolvedValue(conBorrador());
    render(<WorkflowEditorPage />);
    await nodo("Tesorero");
    expect(screen.getByText(/requiere el permiso configuraciones:workflow:write/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Nuevo borrador|Publicar|Retirar|Descartar|Deshabilitar/ })).toBeNull();
    expect(screen.queryByRole("toolbar", { name: "Agregar nodo" })).toBeNull();
  });

  it("al elegir un nodo se ven sus propiedades", async () => {
    api.verProceso.mockResolvedValue(conBorrador());
    const u = userEvent.setup();
    render(<WorkflowEditorPage />);
    await u.click(await nodo("Tesorero"));
    expect(screen.getByLabelText("Propiedades de Tesorero")).toBeInTheDocument();
    await act(async () => {});
  });
});
