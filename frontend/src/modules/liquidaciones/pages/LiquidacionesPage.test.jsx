import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LiquidacionesPage from "./LiquidacionesPage";
import { useAuthStore } from "../../../context/authStore";
import * as liqApi from "../../../api/liquidaciones";

vi.mock("../../../api/liquidaciones", () => ({
  getBatches: vi.fn(),
  getBatchDetalle: vi.fn(),
  getBatchValidaciones: vi.fn(),
  getBatchArchivos: vi.fn(),
  processZip: vi.fn(),
  uploadZip: vi.fn(),
  retryConciliacion: vi.fn(),
  getArchivoUrl: vi.fn((batchId, archivoId) => `/api/liquidaciones/batches/${batchId}/archivos/${archivoId}`),
}));

const LOTE_VALIDADO = {
  id: 1,
  zip_filename: "LIQ_20260919.zip",
  operation_date: "2026-09-19",
  resumen_number: "R-4455",
  total_detail_records: 120,
  total_agencies: 3,
  status: "VALIDADO",
  processed_at: "2026-09-19T10:00:00Z",
  error_message: null,
};
const LOTE_ENVIADO = {
  id: 2,
  zip_filename: "LIQ_20260918.zip",
  operation_date: "2026-09-18",
  resumen_number: "R-4454",
  total_detail_records: 90,
  total_agencies: 2,
  status: "ENVIADO_CONCILIACION",
  processed_at: "2026-09-18T10:00:00Z",
};
const LOTE_ERROR = {
  id: 3,
  zip_filename: "LIQ_rota.zip",
  operation_date: null,
  resumen_number: null,
  total_detail_records: null,
  total_agencies: null,
  status: "ERROR",
  processed_at: null,
  error_message: "El ZIP no contiene el DBF de resumen",
};
const LOTE_PROCESANDO = {
  id: 4,
  zip_filename: "LIQ_20260920.zip",
  operation_date: "2026-09-20",
  resumen_number: "R-4456",
  total_detail_records: 0,
  total_agencies: 0,
  status: "PROCESANDO",
  processed_at: null,
};

const LOTES = [LOTE_VALIDADO, LOTE_ENVIADO, LOTE_ERROR, LOTE_PROCESANDO];

const DETALLE = [
  { id: 1, n_agen: "0002", recaudacion: 500, premios: 100, comision: 50, total: 350 },
  { id: 2, n_agen: "0001", recaudacion: 1000, premios: 200, comision: 100, total: 700 },
  { id: 3, n_agen: "0001", recaudacion: 300, premios: 0, comision: 30, total: 270 },
];

const VALIDACIONES = [
  { id: 1, validation_type: "TOTAL_CONTROL", passed: true, detail_message: "Totales coinciden" },
  { id: 2, validation_type: "CUIT_FALTANTE", passed: false, detail_message: "Falta CUIT de 0003" },
  { id: 3, validation_type: "DETAIL_VS_SUMMARY", passed: true, detail_message: "0001 OK" },
  { id: 4, validation_type: "DETAIL_VS_SUMMARY", passed: true, detail_message: "0002 OK" },
  { id: 5, validation_type: "DETAIL_VS_SUMMARY", passed: false, detail_message: "0003 difiere" },
];

const ARCHIVOS = [
  { id: 10, file_type: "PDF_RESUMEN", original_filename: "resumen.pdf" },
  { id: 11, file_type: "DBF_DETALLE", original_filename: "detalle.dbf" },
];

function sesion(acciones = ["liq:read", "liq:write", "liq:download"]) {
  useAuthStore.setState({
    token: "tok",
    user: { username: "ana", full_name: "Ana" },
    permissions: { modules: ["liquidaciones"], actions: { liquidaciones: acciones } },
  });
}

function montar() {
  return render(
    <MemoryRouter>
      <LiquidacionesPage />
    </MemoryRouter>
  );
}

function detalleOk() {
  liqApi.getBatchDetalle.mockResolvedValue(DETALLE);
  liqApi.getBatchValidaciones.mockResolvedValue(VALIDACIONES);
  liqApi.getBatchArchivos.mockResolvedValue(ARCHIVOS);
}

async function abrirModal(user) {
  montar();
  await screen.findByText("LIQ_20260919.zip");
  await user.click(screen.getByRole("button", { name: "Procesar ZIP" }));
  return screen.getByText("Procesar Liquidación");
}

describe("LiquidacionesPage · listado de lotes", () => {
  beforeEach(() => {
    sesion();
    liqApi.getBatches.mockResolvedValue(LOTES);
  });

  it("pide los lotes al montar y muestra las estadísticas por estado", async () => {
    montar();

    await waitFor(() => expect(liqApi.getBatches).toHaveBeenCalledWith({}));
    expect(await screen.findByText("LIQ_20260919.zip")).toBeInTheDocument();

    const total = screen.getByText("Total Lotes").parentElement;
    expect(within(total).getByText("4")).toBeInTheDocument();
    for (const etiqueta of ["Validados", "Enviados", "Con Error", "Procesando"]) {
      expect(within(screen.getByText(etiqueta).parentElement).getByText("1")).toBeInTheDocument();
    }
  });

  it("abrevia el estado ENVIADO_CONCILIACION en la grilla", async () => {
    montar();
    expect(await screen.findByText("ENVIADO")).toBeInTheDocument();
    expect(screen.queryByText("ENVIADO_CONCILIACION")).not.toBeInTheDocument();
    expect(screen.getByText("VALIDADO")).toBeInTheDocument();
    expect(screen.getByText("ERROR")).toBeInTheDocument();
    expect(screen.getByText("PROCESANDO")).toBeInTheDocument();
  });

  it("sin lotes muestra el estado vacío y oculta las estadísticas", async () => {
    liqApi.getBatches.mockResolvedValue([]);
    montar();

    expect(await screen.findByText("Sin lotes procesados")).toBeInTheDocument();
    expect(screen.queryByText("Total Lotes")).not.toBeInTheDocument();
  });

  it("el botón Actualizar vuelve a pedir los lotes", async () => {
    const user = userEvent.setup();
    montar();
    await screen.findByText("LIQ_20260919.zip");

    await user.click(screen.getByRole("button", { name: "Actualizar" }));
    await waitFor(() => expect(liqApi.getBatches).toHaveBeenCalledTimes(2));
  });

  it("muestra el detalle del error de la API", async () => {
    liqApi.getBatches.mockRejectedValue({ response: { data: { detail: "Servicio caído" } } });
    montar();
    expect(await screen.findByText("Servicio caído")).toBeInTheDocument();
  });

  it("si el error no trae detalle usa el mensaje genérico", async () => {
    liqApi.getBatches.mockRejectedValue(new Error("sin red"));
    montar();
    expect(await screen.findByText("Error al cargar lotes")).toBeInTheDocument();
  });

  it("sin permiso liq:write no ofrece procesar ZIP", async () => {
    sesion(["liq:read"]);
    montar();
    await screen.findByText("LIQ_20260919.zip");
    expect(screen.queryByRole("button", { name: "Procesar ZIP" })).not.toBeInTheDocument();
  });
});

describe("LiquidacionesPage · procesar un lote nuevo", () => {
  beforeEach(() => {
    sesion();
    liqApi.getBatches.mockResolvedValue(LOTES);
  });

  it("sube un ZIP, cierra el modal y recarga los lotes", async () => {
    liqApi.uploadZip.mockResolvedValue({ batch_id: 9 });
    const user = userEvent.setup();
    const { container } = render(
      <MemoryRouter>
        <LiquidacionesPage />
      </MemoryRouter>
    );
    await screen.findByText("LIQ_20260919.zip");
    await user.click(screen.getByRole("button", { name: "Procesar ZIP" }));

    const input = container.querySelector('input[type="file"]');
    const archivo = new File(["contenido"], "lote.zip", { type: "application/zip" });
    await user.upload(input, archivo);

    await waitFor(() => expect(liqApi.uploadZip).toHaveBeenCalledWith(archivo));
    await waitFor(() => expect(screen.queryByText("Procesar Liquidación")).not.toBeInTheDocument());
    expect(liqApi.getBatches).toHaveBeenCalledTimes(2);
  });

  it("muestra el error de la subida y deja el modal abierto", async () => {
    liqApi.uploadZip.mockRejectedValue({ response: { data: { detail: "ZIP corrupto" } } });
    const user = userEvent.setup();
    const { container } = montar();
    await screen.findByText("LIQ_20260919.zip");
    await user.click(screen.getByRole("button", { name: "Procesar ZIP" }));

    const input = container.querySelector('input[type="file"]');
    await user.upload(input, new File(["x"], "lote.zip", { type: "application/zip" }));

    expect(await screen.findByText("ZIP corrupto")).toBeInTheDocument();
    expect(screen.getByText("Procesar Liquidación")).toBeInTheDocument();
    // el input queda limpio para poder reintentar con el mismo archivo
    expect(input.value).toBe("");
  });

  it("si el error de subida no trae detalle usa el mensaje genérico", async () => {
    liqApi.uploadZip.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    const { container } = montar();
    await screen.findByText("LIQ_20260919.zip");
    await user.click(screen.getByRole("button", { name: "Procesar ZIP" }));

    await user.upload(
      container.querySelector('input[type="file"]'),
      new File(["x"], "lote.zip", { type: "application/zip" })
    );
    expect(await screen.findByText("Error al subir archivo")).toBeInTheDocument();
  });

  it("procesa un ZIP por ruta recortando los espacios", async () => {
    liqApi.processZip.mockResolvedValue({ batch_id: 9 });
    const user = userEvent.setup();
    await abrirModal(user);

    await user.click(screen.getByRole("button", { name: /Ruta del archivo/ }));
    const ruta = screen.getByPlaceholderText("/data/externalfiles/archive.zip");
    expect(screen.getByRole("button", { name: "Procesar" })).toBeDisabled();

    await user.type(ruta, "  /data/externalfiles/lote.zip  ");
    await user.click(screen.getByRole("button", { name: "Procesar" }));

    await waitFor(() =>
      expect(liqApi.processZip).toHaveBeenCalledWith("/data/externalfiles/lote.zip")
    );
    await waitFor(() => expect(screen.queryByText("Procesar Liquidación")).not.toBeInTheDocument());
    expect(liqApi.getBatches).toHaveBeenCalledTimes(2);
  });

  it("muestra el error al procesar por ruta", async () => {
    liqApi.processZip.mockRejectedValue({ response: { data: { detail: "Ruta inexistente" } } });
    const user = userEvent.setup();
    await abrirModal(user);

    await user.click(screen.getByRole("button", { name: /Ruta del archivo/ }));
    await user.type(screen.getByPlaceholderText("/data/externalfiles/archive.zip"), "/x.zip");
    await user.click(screen.getByRole("button", { name: "Procesar" }));

    expect(await screen.findByText("Ruta inexistente")).toBeInTheDocument();
  });

  it("si el error de la ruta no trae detalle usa el mensaje genérico", async () => {
    liqApi.processZip.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    await abrirModal(user);

    await user.click(screen.getByRole("button", { name: /Ruta del archivo/ }));
    await user.type(screen.getByPlaceholderText("/data/externalfiles/archive.zip"), "/x.zip");
    await user.click(screen.getByRole("button", { name: "Procesar" }));

    expect(await screen.findByText("Error al procesar archivo")).toBeInTheDocument();
  });

  it("se puede cerrar el modal sin procesar nada", async () => {
    const user = userEvent.setup();
    const { container } = montar();
    await screen.findByText("LIQ_20260919.zip");
    await user.click(screen.getByRole("button", { name: "Procesar ZIP" }));
    expect(screen.getByText("Procesar Liquidación")).toBeInTheDocument();

    const cerrar = screen.getByText("Procesar Liquidación").parentElement.querySelector("button");
    await user.click(cerrar);
    expect(screen.queryByText("Procesar Liquidación")).not.toBeInTheDocument();

    // y también tocando el fondo oscurecido
    await user.click(screen.getByRole("button", { name: "Procesar ZIP" }));
    await user.click(container.querySelector(".bg-black\\/30"));
    expect(screen.queryByText("Procesar Liquidación")).not.toBeInTheDocument();
  });
});

describe("LiquidacionesPage · detalle del lote", () => {
  beforeEach(() => {
    sesion();
    liqApi.getBatches.mockResolvedValue(LOTES);
    detalleOk();
  });

  async function abrirLote(user, archivo = "LIQ_20260919.zip") {
    montar();
    await user.click(await screen.findByText(archivo));
    return screen.findByText(/Detalle Lote #/);
  }

  it("pide detalle, validaciones y archivos del lote elegido", async () => {
    const user = userEvent.setup();
    await abrirLote(user);

    await waitFor(() => expect(liqApi.getBatchDetalle).toHaveBeenCalledWith(1));
    expect(liqApi.getBatchValidaciones).toHaveBeenCalledWith(1);
    expect(liqApi.getBatchArchivos).toHaveBeenCalledWith(1);
    expect(screen.getByText("Detalle Lote #1")).toBeInTheDocument();
  });

  it("agrupa el detalle por agencia y suma los totales", async () => {
    const user = userEvent.setup();
    await abrirLote(user);

    expect(await screen.findByText("Resumen por Agencia (2)")).toBeInTheDocument();
    // 0001 suma 700 + 270 y queda primera por orden alfabético
    expect(screen.getByText("$ 970,00")).toBeInTheDocument();
    expect(screen.getByText("$ 350,00")).toBeInTheDocument();
    const agencias = screen.getAllByText(/^000[12]$/).map((el) => el.textContent);
    expect(agencias).toEqual(["0001", "0002"]);
  });

  it("muestra las validaciones fallidas y colapsa las DETAIL_VS_SUMMARY exitosas", async () => {
    const user = userEvent.setup();
    await abrirLote(user);

    expect(await screen.findByText("Falta CUIT de 0003")).toBeInTheDocument();
    expect(screen.getByText("Totales coinciden")).toBeInTheDocument();
    expect(screen.getByText("0003 difiere")).toBeInTheDocument();
    // las dos que pasaron se resumen en una sola línea
    expect(screen.getByText("DETAIL_VS_SUMMARY: 2 agencias OK")).toBeInTheDocument();
    expect(screen.queryByText("0001 OK")).not.toBeInTheDocument();
  });

  it("lista sólo los archivos PDF con su enlace de descarga", async () => {
    const user = userEvent.setup();
    await abrirLote(user);

    const enlace = await screen.findByRole("link", { name: /resumen.pdf/ });
    expect(enlace).toHaveAttribute("href", "/api/liquidaciones/batches/1/archivos/10");
    expect(screen.queryByText("detalle.dbf")).not.toBeInTheDocument();
  });

  it("muestra el mensaje de error del lote fallido", async () => {
    const user = userEvent.setup();
    await abrirLote(user, "LIQ_rota.zip");

    expect(await screen.findByText("El ZIP no contiene el DBF de resumen")).toBeInTheDocument();
    expect(screen.getByText("Detalle Lote #3")).toBeInTheDocument();
  });

  it("si falla la carga del detalle el panel igual se abre sin secciones", async () => {
    liqApi.getBatchDetalle.mockRejectedValue(new Error("500"));
    const user = userEvent.setup();
    await abrirLote(user);

    expect(await screen.findByText("Detalle Lote #1")).toBeInTheDocument();
    expect(screen.queryByText("Validaciones")).not.toBeInTheDocument();
    expect(screen.queryByText(/Resumen por Agencia/)).not.toBeInTheDocument();
    expect(screen.queryByText("Archivos")).not.toBeInTheDocument();
  });

  it("cierra el panel con la X", async () => {
    const user = userEvent.setup();
    await abrirLote(user);
    await screen.findByText("Resumen por Agencia (2)");

    const cabecera = screen.getByText("Detalle Lote #1").parentElement;
    await user.click(within(cabecera).getByRole("button"));
    expect(screen.queryByText("Detalle Lote #1")).not.toBeInTheDocument();
  });
});

describe("LiquidacionesPage · reenvío a conciliación", () => {
  beforeEach(() => {
    sesion();
    liqApi.getBatches.mockResolvedValue(LOTES);
    detalleOk();
  });

  async function abrirLote(user, archivo) {
    montar();
    await user.click(await screen.findByText(archivo));
    await screen.findByText(/Detalle Lote #/);
  }

  it("sólo ofrece reenviar los lotes VALIDADO", async () => {
    const user = userEvent.setup();
    await abrirLote(user, "LIQ_20260918.zip");
    expect(screen.queryByRole("button", { name: /Reenviar a Conciliación/ })).not.toBeInTheDocument();
  });

  it("sin permiso liq:write no ofrece reenviar aunque esté VALIDADO", async () => {
    sesion(["liq:read"]);
    const user = userEvent.setup();
    await abrirLote(user, "LIQ_20260919.zip");
    expect(screen.queryByRole("button", { name: /Reenviar a Conciliación/ })).not.toBeInTheDocument();
  });

  it("reenvía, recarga los lotes y cierra el panel", async () => {
    liqApi.retryConciliacion.mockResolvedValue({ ok: true });
    const user = userEvent.setup();
    await abrirLote(user, "LIQ_20260919.zip");

    await user.click(await screen.findByRole("button", { name: /Reenviar a Conciliación/ }));

    await waitFor(() => expect(liqApi.retryConciliacion).toHaveBeenCalledWith(1));
    await waitFor(() => expect(screen.queryByText("Detalle Lote #1")).not.toBeInTheDocument());
    expect(liqApi.getBatches).toHaveBeenCalledTimes(2);
  });

  it("muestra el error si falla el reenvío", async () => {
    liqApi.retryConciliacion.mockRejectedValue({
      response: { data: { detail: "Conciliación no disponible" } },
    });
    const user = userEvent.setup();
    await abrirLote(user, "LIQ_20260919.zip");

    await user.click(await screen.findByRole("button", { name: /Reenviar a Conciliación/ }));
    expect(await screen.findByText("Conciliación no disponible")).toBeInTheDocument();
    expect(screen.getByText("Detalle Lote #1")).toBeInTheDocument();
  });

  it("si el error del reenvío no trae detalle usa el mensaje genérico", async () => {
    liqApi.retryConciliacion.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    await abrirLote(user, "LIQ_20260919.zip");

    await user.click(await screen.findByRole("button", { name: /Reenviar a Conciliación/ }));
    expect(await screen.findByText("Error al reenviar")).toBeInTheDocument();
  });
});
