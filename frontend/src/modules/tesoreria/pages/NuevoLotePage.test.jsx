import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/tesoreria", async (orig) => ({ ...(await orig()), crearLote: vi.fn() }));

import { crearLote } from "../../../api/tesoreria";
import NuevoLotePage from "./NuevoLotePage";

const CBU = "2850590940090418135201";

function montar() {
  render(
    <MemoryRouter initialEntries={["/nuevo"]}>
      <Routes>
        <Route path="/nuevo" element={<NuevoLotePage />} />
        <Route path="/modules/tesoreria/lotes/:id" element={<p>detalle del lote</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("NuevoLotePage", () => {
  beforeEach(() => { vi.clearAllMocks(); crearLote.mockResolvedValue({ id: 9 }); });

  it("carga a mano y crea el lote", async () => {
    montar();
    await userEvent.type(screen.getByPlaceholderText(/Pago a proveedores/), "Proveedores");
    await userEvent.type(screen.getByLabelText("Beneficiario 1"), "ACME SA");
    await userEvent.type(screen.getByLabelText("CBU 1"), CBU);
    await userEvent.type(screen.getByLabelText("Monto 1"), "1.500,50");
    expect(screen.getByText(/1 pago\(s\) válidos/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Crear lote" }));
    await waitFor(() => expect(crearLote).toHaveBeenCalledWith({
      descripcion: "Proveedores",
      pagos: [{ beneficiario: "ACME SA", documento: "", cbu: CBU, monto: 1500.5, concepto: "" }],
    }));
    expect(await screen.findByText("detalle del lote")).toBeInTheDocument();
  });

  it("no manda filas inválidas", async () => {
    montar();
    await userEvent.type(screen.getByPlaceholderText(/Pago a proveedores/), "X");
    await userEvent.type(screen.getByLabelText("Beneficiario 1"), "ACME");
    await userEvent.type(screen.getByLabelText("CBU 1"), "123");
    await userEvent.type(screen.getByLabelText("Monto 1"), "10");
    await userEvent.click(screen.getByRole("button", { name: "Crear lote" }));
    expect(screen.getByText("El CBU debe tener 22 dígitos")).toBeInTheDocument();
    expect(crearLote).not.toHaveBeenCalled();
  });

  it("importa un CSV", async () => {
    montar();
    const archivo = new File([`ANA;27111111113;${CBU};100;Reintegro\nBETO;;${CBU};200;`], "pagos.csv", { type: "text/csv" });
    fireEvent.change(screen.getByTestId("archivo-csv"), { target: { files: [archivo] } });
    expect(await screen.findByText(/Se importaron 2 fila/)).toBeInTheDocument();
    expect(screen.getByLabelText("Beneficiario 2")).toHaveValue("BETO");
    expect(screen.getByText(/2 pago\(s\) válidos/)).toHaveTextContent("300");
  });
});
