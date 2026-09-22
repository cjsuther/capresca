import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import EstadoPage from "./EstadoPage";
import { useAuthStore } from "../../../context/authStore";
import * as legacyApi from "../../../api/legacy";

vi.mock("../../../api/legacy", () => ({
  getStatus: vi.fn(),
  drainOutbox: vi.fn(),
}));

const ESTADO_ACTIVO = {
  integration_enabled: true,
  write_mode: "outbox",
  outbox_pending: 4,
  smb: {
    mounted: true,
    mount_root: "/mnt/legacy",
    tables_present: 5,
    tables_total: 6,
    databases: {
      QUINIELA: {
        subdir_exists: true,
        tables: { cajaliq: true, agencias: true, sorteos: false },
      },
      TOMBOLA: {
        subdir_exists: false,
        tables: { jugadas: false },
      },
    },
  },
  sync_state: [
    {
      table_name: "cajaliq",
      database: "QUINIELA",
      last_run_at: "2026-09-20T09:30:00Z",
      last_status: "OK",
      rows_seen: 1200,
      rows_changed: 12,
    },
    {
      table_name: "agencias",
      database: "QUINIELA",
      last_run_at: null,
      last_status: null,
      rows_seen: null,
      rows_changed: null,
    },
  ],
};

function sesion(acciones = ["interactions:read", "admin:read", "admin:write"]) {
  useAuthStore.setState({
    token: "tok",
    user: { username: "ana", full_name: "Ana" },
    permissions: { modules: ["legacy"], actions: { legacy: acciones } },
  });
}

function montar() {
  return render(
    <MemoryRouter>
      <EstadoPage />
    </MemoryRouter>
  );
}

describe("EstadoPage · estado de la integración", () => {
  beforeEach(() => sesion());

  it("muestra la integración activa, el montaje SMB y el modo de escritura", async () => {
    legacyApi.getStatus.mockResolvedValue(ESTADO_ACTIVO);
    montar();

    expect(await screen.findByText("ACTIVA")).toBeInTheDocument();
    expect(screen.getByText("modo escritura: outbox")).toBeInTheDocument();
    expect(screen.getByText(/\/mnt\/legacy/)).toHaveTextContent("5/6 tablas");
    expect(screen.getAllByText("Sí").length).toBeGreaterThan(0);
  });

  it("con el kill switch apagado muestra APAGADA", async () => {
    legacyApi.getStatus.mockResolvedValue({
      ...ESTADO_ACTIVO,
      integration_enabled: false,
      write_mode: "disabled",
      smb: { ...ESTADO_ACTIVO.smb, mounted: false, databases: null },
    });
    montar();

    expect(await screen.findByText("APAGADA")).toBeInTheDocument();
    expect(screen.getByText("modo escritura: disabled")).toBeInTheDocument();
    expect(screen.getAllByText("No").length).toBeGreaterThan(0);
    // sin detalle de bases no se dibuja la grilla del share
    expect(screen.queryByText("Tablas detectadas en el share")).not.toBeInTheDocument();
  });

  it("lista la sincronización por tabla con los faltantes en guiones", async () => {
    legacyApi.getStatus.mockResolvedValue(ESTADO_ACTIVO);
    montar();

    await screen.findByText("ACTIVA");
    const fila = screen.getAllByText("cajaliq").find((el) => el.closest("tr")).closest("tr");
    expect(within(fila).getByText("OK")).toBeInTheDocument();
    expect(within(fila).getByText("1200")).toBeInTheDocument();
    expect(within(fila).getByText("12")).toBeInTheDocument();

    const filaSinSync = screen.getAllByText("agencias").find((el) => el.closest("tr")).closest("tr");
    expect(within(filaSinSync).getAllByText("—")).toHaveLength(4);
  });

  it("avisa cuando todavía no corrió ninguna sincronización", async () => {
    legacyApi.getStatus.mockResolvedValue({ ...ESTADO_ACTIVO, sync_state: [] });
    montar();
    expect(
      await screen.findByText("Aún no se ejecutó ninguna sincronización.")
    ).toBeInTheDocument();
  });

  it("tolera un estado sin sync_state", async () => {
    legacyApi.getStatus.mockResolvedValue({ ...ESTADO_ACTIVO, sync_state: undefined });
    montar();
    expect(
      await screen.findByText("Aún no se ejecutó ninguna sincronización.")
    ).toBeInTheDocument();
  });

  it("detalla las tablas presentes y ausentes de cada base del share", async () => {
    legacyApi.getStatus.mockResolvedValue(ESTADO_ACTIVO);
    montar();

    const share = (await screen.findByText("Tablas detectadas en el share")).parentElement;
    expect(within(share).getByText("QUINIELA")).toBeInTheDocument();
    expect(within(share).getByText("TOMBOLA")).toBeInTheDocument();

    // la tabla ausente se marca con guión y la presente con tilde
    expect(within(screen.getByText("sorteos").closest("li")).getByText("—")).toBeInTheDocument();
    const cajaliq = within(share).getByText("cajaliq").closest("li");
    expect(within(cajaliq).getByText("✓")).toBeInTheDocument();

    // la base cuyo subdirectorio no existe aparece como "No"
    const tombola = within(share).getByText("TOMBOLA").parentElement;
    expect(within(tombola).getByText("No")).toBeInTheDocument();
  });

  it("el botón Actualizar vuelve a pedir el estado", async () => {
    legacyApi.getStatus.mockResolvedValue(ESTADO_ACTIVO);
    const user = userEvent.setup();
    montar();
    await screen.findByText("ACTIVA");

    await user.click(screen.getByRole("button", { name: /Actualizar/ }));
    await waitFor(() => expect(legacyApi.getStatus).toHaveBeenCalledTimes(2));
  });

  it("muestra el detalle del error de la API", async () => {
    legacyApi.getStatus.mockRejectedValue({ response: { data: { detail: "SMB caído" } } });
    montar();
    expect(await screen.findByText("SMB caído")).toBeInTheDocument();
    expect(screen.queryByText("ACTIVA")).not.toBeInTheDocument();
  });

  it("si el error no trae detalle usa el mensaje genérico", async () => {
    legacyApi.getStatus.mockRejectedValue(new Error("sin red"));
    montar();
    expect(await screen.findByText("Error al cargar el estado")).toBeInTheDocument();
  });
});

describe("EstadoPage · outbox", () => {
  beforeEach(() => sesion());

  it("muestra el pendiente y drena con permiso admin:write", async () => {
    legacyApi.getStatus.mockResolvedValue(ESTADO_ACTIVO);
    legacyApi.drainOutbox.mockResolvedValue({ drained: 4 });
    const user = userEvent.setup();
    montar();

    expect(await screen.findByText("4")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Drenar outbox" }));

    await waitFor(() => expect(legacyApi.drainOutbox).toHaveBeenCalled());
    // tras drenar se refresca el estado
    await waitFor(() => expect(legacyApi.getStatus).toHaveBeenCalledTimes(2));
  });

  it("sin permiso admin:write no ofrece drenar", async () => {
    sesion(["interactions:read"]);
    legacyApi.getStatus.mockResolvedValue(ESTADO_ACTIVO);
    montar();

    expect(await screen.findByText("Outbox pendiente")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Drenar outbox" })).not.toBeInTheDocument();
  });

  it("con el outbox vacío el botón queda deshabilitado", async () => {
    legacyApi.getStatus.mockResolvedValue({ ...ESTADO_ACTIVO, outbox_pending: 0 });
    montar();

    expect(await screen.findByRole("button", { name: "Drenar outbox" })).toBeDisabled();
  });

  it("muestra el error si falla el drenado", async () => {
    legacyApi.getStatus.mockResolvedValue(ESTADO_ACTIVO);
    legacyApi.drainOutbox.mockRejectedValue({
      response: { data: { detail: "Escritura deshabilitada" } },
    });
    const user = userEvent.setup();
    montar();

    await user.click(await screen.findByRole("button", { name: "Drenar outbox" }));
    expect(await screen.findByText("Escritura deshabilitada")).toBeInTheDocument();
  });

  it("si el error del drenado no trae detalle usa el mensaje genérico", async () => {
    legacyApi.getStatus.mockResolvedValue(ESTADO_ACTIVO);
    legacyApi.drainOutbox.mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    montar();

    await user.click(await screen.findByRole("button", { name: "Drenar outbox" }));
    expect(await screen.findByText("Error al drenar el outbox")).toBeInTheDocument();
  });
});
