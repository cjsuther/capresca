import { useState } from "react";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import PanelPropiedades from "./PanelPropiedades";
import ConstructorCondicion from "./ConstructorCondicion";
import { actualizarConexion, actualizarNodo } from "./grafo";

const VARS = {
  monto: { nombre: "Monto solicitado", tipo: "numero" },
  origen: { nombre: "Origen", tipo: "opcion", opciones: ["PORTAL", "SUCURSAL"] },
};
const GRAFO = {
  nodos: [
    { id: "i", tipo: "inicio", nombre: "Inicio" },
    { id: "ap1", tipo: "aprobacion", nombre: "Analista", asignar: { tipo: "rol", valor: "APROBAR" }, cuatroOjos: true, incluir: [], excluir: ["pz.juan"] },
    { id: "d", tipo: "decision", nombre: "¿Monto alto?" },
    { id: "not", tipo: "notificacion", nombre: "Avisar", destinatarios: [{ tipo: "iniciador", valor: "" }] },
    { id: "f", tipo: "fin", nombre: "Aprobado", resultado: "APROBADO" },
  ],
  conexiones: [
    { id: "c1", de: "i", a: "ap1" }, { id: "c2", de: "ap1", a: "d", salida: "aprobado" },
    { id: "c3", de: "d", a: "f", defecto: true },
    { id: "c4", de: "d", a: "not", condicion: { modo: "todas", reglas: [{ variable: "monto", op: ">", valor: 5000000 }] } },
  ],
};
const PERSONAS = { grupos: [{ id: 4, name: "Gerencia Créditos" }], usuarios: ["ana", "beto"], deSeguridad: true };

/** El panel es controlado: este arnés aplica los cambios como lo hace el editor. */
function Arnes({ seleccion, soloLectura = false, onQuitar = () => {}, espia = () => {} }) {
  const [g, setG] = useState(GRAFO);
  return (
    <PanelPropiedades grafo={g} seleccion={seleccion} variables={VARS} personas={PERSONAS} soloLectura={soloLectura}
                      onCambiarNodo={(id, c) => { espia("nodo", id, c); setG((x) => actualizarNodo(x, id, c)); }}
                      onCambiarConexion={(id, c) => { espia("conexion", id, c); setG((x) => actualizarConexion(x, id, c)); }}
                      onQuitar={onQuitar} />
  );
}

describe("Panel de propiedades", () => {
  it("sin selección explica qué hacer", () => {
    render(<Arnes seleccion={null} />);
    expect(screen.getByText(/Elegí un nodo o una flecha/)).toBeInTheDocument();
  });

  it("aprobación: cambia a grupo de Seguridad, cuatro-ojos y usuarios", async () => {
    const espia = vi.fn();
    const u = userEvent.setup();
    render(<Arnes seleccion={{ tipo: "nodo", id: "ap1" }} espia={espia} />);
    await u.selectOptions(screen.getByLabelText("Tipo de aprobador"), "grupo");
    expect(screen.getByText(/no publicar hasta el motor nuevo/)).toBeInTheDocument();
    await u.selectOptions(screen.getByLabelText("Grupo"), "Gerencia Créditos");
    expect(espia).toHaveBeenLastCalledWith("nodo", "ap1", { asignar: { tipo: "grupo", valor: "Gerencia Créditos", id: 4 } });
    await u.click(screen.getByLabelText(/Cuatro-ojos/));
    expect(espia).toHaveBeenLastCalledWith("nodo", "ap1", { cuatroOjos: false });
    await u.type(screen.getByLabelText(/Además aprueban/), "beto{Enter}");
    expect(espia).toHaveBeenLastCalledWith("nodo", "ap1", { incluir: ["beto"] });
    await u.click(screen.getByRole("button", { name: "Quitar pz.juan" }));
    expect(espia).toHaveBeenLastCalledWith("nodo", "ap1", { excluir: [] });
  });

  it("decisión: lista sus caminos en castellano", () => {
    render(<Arnes seleccion={{ tipo: "nodo", id: "d" }} />);
    expect(screen.getByText(/si no se cumple ninguna/)).toBeInTheDocument();
    expect(screen.getByText(/Monto solicitado es mayor que 5.000.000/)).toBeInTheDocument();
  });

  it("flecha de una decisión: pasar a «si no» y volver a condición", async () => {
    const espia = vi.fn();
    const u = userEvent.setup();
    render(<Arnes seleccion={{ tipo: "conexion", id: "c4" }} espia={espia} />);
    expect(screen.getByText(/De/)).toHaveTextContent("De ¿Monto alto? a Avisar");
    await u.click(screen.getByLabelText(/Camino «si no»/));
    expect(espia).toHaveBeenLastCalledWith("conexion", "c4", { defecto: true, condicion: undefined });
    expect(screen.queryByRole("group", { name: "Condición" })).toBeNull();
  });

  it("notificación: agrega un destinatario por rol y escribe el mensaje", async () => {
    const espia = vi.fn();
    const u = userEvent.setup();
    render(<Arnes seleccion={{ tipo: "nodo", id: "not" }} espia={espia} />);
    await u.click(screen.getByRole("button", { name: /Destinatario/ }));
    await u.selectOptions(screen.getByLabelText("Rol 2"), "SUPERVISAR");
    expect(espia).toHaveBeenLastCalledWith("nodo", "not", { destinatarios: [{ tipo: "iniciador", valor: "" }, { tipo: "rol", valor: "SUPERVISAR" }] });
    await u.type(screen.getByLabelText("Mensaje"), "Hola");
    expect(espia).toHaveBeenLastCalledWith("nodo", "not", { mensaje: "Hola" });
  });

  it("fin: elige el resultado; el Inicio no se puede quitar", async () => {
    const onQuitar = vi.fn();
    const u = userEvent.setup();
    const { unmount } = render(<Arnes seleccion={{ tipo: "nodo", id: "f" }} onQuitar={onQuitar} />);
    await u.selectOptions(screen.getByLabelText("Termina"), "RECHAZADO");
    await u.click(screen.getByRole("button", { name: /Quitar/ }));
    expect(onQuitar).toHaveBeenCalledWith({ tipo: "nodo", id: "f" });
    unmount();
    render(<Arnes seleccion={{ tipo: "nodo", id: "i" }} />);
    expect(screen.queryByRole("button", { name: /Quitar/ })).toBeNull();
  });

  it("en sólo lectura no se puede cambiar nada", () => {
    render(<Arnes seleccion={{ tipo: "nodo", id: "ap1" }} soloLectura />);
    expect(screen.getByLabelText("Nombre")).toBeDisabled();
    expect(screen.getByLabelText("Tipo de aprobador")).toBeDisabled();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("Constructor de condiciones", () => {
  function Cond({ inicial, espia }) {
    const [c, setC] = useState(inicial);
    return <ConstructorCondicion condicion={c} variables={VARS} onChange={(x) => { espia(x); setC(x); }} />;
  }

  it("agrega reglas, cambia variable/operador/valor y combina con «alguna»", async () => {
    const espia = vi.fn();
    const u = userEvent.setup();
    render(<Cond inicial={{ modo: "todas", reglas: [] }} espia={espia} />);
    await u.click(screen.getByRole("button", { name: /Agregar regla/ }));
    await u.selectOptions(screen.getByLabelText("Operador 1"), ">");
    const valor = screen.getByLabelText("Valor 1");
    await u.clear(valor);
    await u.type(valor, "5.000.000");
    await u.tab();
    expect(espia).toHaveBeenLastCalledWith({ modo: "todas", reglas: [{ variable: "monto", op: ">", valor: 5000000 }] });
    await u.click(screen.getByRole("button", { name: /Agregar regla/ }));
    await u.selectOptions(screen.getByLabelText("Variable 2"), "origen");
    await u.selectOptions(screen.getByLabelText("Operador 2"), "en");
    await u.click(within(screen.getByRole("group", { name: "Valor 2" })).getByLabelText("SUCURSAL"));
    await u.selectOptions(screen.getByLabelText("Modo de la condición"), "alguna");
    expect(espia).toHaveBeenLastCalledWith({ modo: "alguna", reglas: [
      { variable: "monto", op: ">", valor: 5000000 }, { variable: "origen", op: "en", valor: ["PORTAL", "SUCURSAL"] }] });
    await u.click(screen.getByRole("button", { name: "Quitar regla 1" }));
    expect(espia.mock.lastCall[0].reglas).toHaveLength(1);
  });

  it("sin variables lo dice", () => {
    render(<ConstructorCondicion condicion={null} variables={{}} onChange={() => {}} />);
    expect(screen.getByText(/no declara variables/)).toBeInTheDocument();
  });
});
