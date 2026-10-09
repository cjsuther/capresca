import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { DataTable } from "./DataTable";

const FILAS = [
  { id: 1, nombre: "Pérez, Ana", cuil: "27-30123456-4", estado: "APROBADA" },
  { id: 2, nombre: "Gómez, Luis", cuil: "20-28999111-3", estado: "RECHAZADA" },
  { id: 3, nombre: "Perello, Juan", cuil: "", estado: "APROBADA" },
];
const COLUMNAS = [
  { key: "nombre", label: "Cliente", filtro: "texto" },
  { key: "cuil", label: "CUIL", filtro: "texto" },
  { key: "estado", label: "Estado", filtro: "opciones" },
];
const nombres = () => screen.getAllByRole("row").slice(2).map((r) => within(r).getAllByRole("cell")[0].textContent);

describe("DataTable · filtros por columna", () => {
  it("sin columnas filtrables no agrega la fila de filtros", () => {
    render(<DataTable columns={[{ key: "nombre", label: "Cliente" }]} rows={FILAS} rowKey={(r) => r.id} />);
    expect(screen.queryByLabelText("Filtrar Cliente")).toBeNull();
  });

  it("el texto filtra sin distinguir mayúsculas ni acentos", async () => {
    render(<DataTable columns={COLUMNAS} rows={FILAS} rowKey={(r) => r.id} />);
    await userEvent.type(screen.getByLabelText("Filtrar Cliente"), "PERE");
    expect(nombres()).toEqual(["Pérez, Ana", "Perello, Juan"]);
  });

  it("un CUIL se encuentra con o sin guiones", async () => {
    render(<DataTable columns={COLUMNAS} rows={FILAS} rowKey={(r) => r.id} />);
    const cuil = screen.getByLabelText("Filtrar CUIL");
    await userEvent.type(cuil, "30123456");
    expect(nombres()).toEqual(["Pérez, Ana"]);
    await userEvent.clear(cuil);
    await userEvent.type(cuil, "20-289");
    expect(nombres()).toEqual(["Gómez, Luis"]);
  });

  it("las opciones salen de las filas y se combinan con los demás filtros", async () => {
    render(<DataTable columns={COLUMNAS} rows={FILAS} rowKey={(r) => r.id} />);
    const estado = screen.getByLabelText("Filtrar Estado");
    expect(within(estado).getAllByRole("option").map((o) => o.textContent)).toEqual(["Todos", "APROBADA", "RECHAZADA"]);
    await userEvent.selectOptions(estado, "APROBADA");
    await userEvent.type(screen.getByLabelText("Filtrar Cliente"), "juan");
    expect(nombres()).toEqual(["Perello, Juan"]);
  });

  it("si nada coincide muestra el texto de vacío", async () => {
    render(<DataTable columns={COLUMNAS} rows={FILAS} rowKey={(r) => r.id} emptyText="Sin solicitudes." />);
    await userEvent.type(screen.getByLabelText("Filtrar Cliente"), "zzz");
    expect(screen.getByText("Sin solicitudes.")).toBeInTheDocument();
  });
});
