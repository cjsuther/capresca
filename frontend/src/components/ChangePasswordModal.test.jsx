import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ChangePasswordModal } from "./ChangePasswordModal";

// TODO(bug): los <label> del modal no están asociados a sus <input> (falta htmlFor/id),
// así que los campos se ubican por posición y no por etiqueta accesible.
function montar(props = {}) {
  const onSave = props.onSave ?? vi.fn().mockResolvedValue(undefined);
  const onClose = props.onClose ?? vi.fn();
  const requireCurrent = props.requireCurrent ?? false;
  const { container } = render(
    <ChangePasswordModal
      title={props.title ?? "Cambiar mi contraseña"}
      requireCurrent={requireCurrent}
      onSave={onSave}
      onClose={onClose}
    />
  );
  const inputs = () => [...container.querySelectorAll('input[type="password"]')];
  const base = requireCurrent ? 1 : 0;
  const campos = {
    actual: () => inputs()[0],
    nueva: () => inputs()[base],
    confirmar: () => inputs()[base + 1],
    todos: inputs,
  };
  return { onSave, onClose, campos };
}

const botonGuardar = () => screen.getByRole("button", { name: "Cambiar contraseña" });

describe("ChangePasswordModal", () => {
  it("muestra el título y sólo dos campos cuando no se pide la contraseña actual", () => {
    const { campos } = montar({ title: "Contraseña de ana" });

    expect(screen.getByText("Contraseña de ana")).toBeInTheDocument();
    expect(campos.todos()).toHaveLength(2);
    expect(screen.queryByText("Contraseña actual")).not.toBeInTheDocument();
    expect(screen.getByText("Nueva contraseña")).toBeInTheDocument();
    expect(screen.getByText("Confirmar contraseña")).toBeInTheDocument();
  });

  it("agrega el campo de contraseña actual cuando requireCurrent está activo", () => {
    const { campos } = montar({ requireCurrent: true });

    expect(campos.todos()).toHaveLength(3);
    expect(screen.getByText("Contraseña actual")).toBeInTheDocument();
  });

  it("rechaza contraseñas de menos de 6 caracteres sin llamar a la API", async () => {
    const user = userEvent.setup();
    const { onSave, onClose, campos } = montar();

    await user.type(campos.nueva(), "12345");
    await user.type(campos.confirmar(), "12345");
    await user.click(botonGuardar());

    expect(screen.getByText("La contraseña debe tener al menos 6 caracteres")).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("rechaza cuando la confirmación no coincide", async () => {
    const user = userEvent.setup();
    const { onSave, campos } = montar();

    await user.type(campos.nueva(), "secreta123");
    await user.type(campos.confirmar(), "secreta124");
    await user.click(botonGuardar());

    expect(screen.getByText("Las contraseñas no coinciden")).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
  });

  it("guarda con la contraseña actual y la nueva, y cierra al terminar", async () => {
    const user = userEvent.setup();
    const { onSave, onClose, campos } = montar({ requireCurrent: true });

    await user.type(campos.actual(), "vieja123");
    await user.type(campos.nueva(), "secreta123");
    await user.type(campos.confirmar(), "secreta123");
    await user.click(botonGuardar());

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(onSave).toHaveBeenCalledWith("vieja123", "secreta123");
  });

  it("muestra el detalle de error que devuelve la API y no cierra", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockRejectedValue({
      response: { data: { detail: "La contraseña actual es incorrecta" } },
    });
    const { onClose, campos } = montar({ requireCurrent: true, onSave });

    await user.type(campos.actual(), "mala");
    await user.type(campos.nueva(), "secreta123");
    await user.type(campos.confirmar(), "secreta123");
    await user.click(botonGuardar());

    expect(await screen.findByText("La contraseña actual es incorrecta")).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("usa un mensaje genérico si el error no trae detalle", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockRejectedValue(new Error("network"));
    const { campos } = montar({ onSave });

    await user.type(campos.nueva(), "secreta123");
    await user.type(campos.confirmar(), "secreta123");
    await user.click(botonGuardar());

    expect(await screen.findByText("Error al cambiar la contraseña")).toBeInTheDocument();
  });

  it("deshabilita el botón mientras guarda y lo rehabilita al fallar", async () => {
    const user = userEvent.setup();
    let rechazar;
    const onSave = vi.fn(() => new Promise((_, reject) => { rechazar = () => reject(new Error("boom")); }));
    const { campos } = montar({ onSave });

    await user.type(campos.nueva(), "secreta123");
    await user.type(campos.confirmar(), "secreta123");
    await user.click(botonGuardar());

    const guardando = await screen.findByRole("button", { name: "Guardando..." });
    expect(guardando).toBeDisabled();

    rechazar();
    expect(await screen.findByRole("button", { name: "Cambiar contraseña" })).toBeEnabled();
  });

  it("cierra desde Cancelar y desde la X del header sin guardar", async () => {
    const user = userEvent.setup();
    const { onSave, onClose } = montar();

    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(onClose).toHaveBeenCalledTimes(1);

    // El primer botón del DOM es la X del header (sin texto)
    await user.click(screen.getAllByRole("button")[0]);
    expect(onClose).toHaveBeenCalledTimes(2);
    expect(onSave).not.toHaveBeenCalled();
  });
});
