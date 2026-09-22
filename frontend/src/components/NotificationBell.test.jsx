import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api/notifications", () => ({
  getNotifications: vi.fn(),
  getUnreadCount: vi.fn(),
  markAsRead: vi.fn(),
  markAllAsRead: vi.fn(),
}));

import { getNotifications, getUnreadCount, markAsRead, markAllAsRead } from "../api/notifications";
import { NotificationBell } from "./NotificationBell";

const ahora = () => new Date().toISOString();

const aviso = (extra = {}) => ({
  id: 1,
  title: "Conciliación lista",
  message: "Se consolidó el día de ayer",
  is_read: false,
  created_at: ahora(),
  redirect_path: null,
  ...extra,
});

function montar() {
  return render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <Routes>
        <Route path="/dashboard" element={<><NotificationBell /><p>tablero</p></>} />
        <Route path="/modules/conciliacion/dias" element={<p>pantalla de conciliación</p>} />
      </Routes>
    </MemoryRouter>
  );
}

const abrirCampana = () => screen.getByTitle("Notificaciones");

describe("NotificationBell", () => {
  beforeEach(() => {
    getUnreadCount.mockResolvedValue({ count: 0 });
    getNotifications.mockResolvedValue({ data: [], unread_count: 0 });
    markAsRead.mockResolvedValue({});
    markAllAsRead.mockResolvedValue({});
  });

  it("no muestra badge cuando no hay pendientes", async () => {
    montar();
    await waitFor(() => expect(getUnreadCount).toHaveBeenCalled());
    expect(abrirCampana()).toHaveTextContent("");
  });

  it("muestra el conteo de no leídas al montar", async () => {
    getUnreadCount.mockResolvedValue({ count: 3 });
    montar();
    expect(await screen.findByText("3")).toBeInTheDocument();
  });

  it("corta el badge en 99+ cuando hay muchísimas", async () => {
    getUnreadCount.mockResolvedValue({ count: 250 });
    montar();
    expect(await screen.findByText("99+")).toBeInTheDocument();
  });

  it("si falla el conteo deja el badge en cero sin romper", async () => {
    getUnreadCount.mockRejectedValue(new Error("502"));
    montar();
    await waitFor(() => expect(getUnreadCount).toHaveBeenCalled());
    expect(screen.queryByText("0")).not.toBeInTheDocument();
    expect(screen.getByText("tablero")).toBeInTheDocument();
  });

  it("al abrir pide las últimas 10 y las lista", async () => {
    const user = userEvent.setup();
    getNotifications.mockResolvedValue({
      data: [aviso(), aviso({ id: 2, title: "Pago acreditado", is_read: true })],
      unread_count: 1,
    });
    montar();

    await user.click(abrirCampana());

    expect(getNotifications).toHaveBeenCalledWith({ limit: 10 });
    expect(await screen.findByText("Conciliación lista")).toBeInTheDocument();
    expect(screen.getByText("Pago acreditado")).toBeInTheDocument();
    expect(screen.getByText("Notificaciones")).toBeInTheDocument();
  });

  it("muestra el vacío cuando no hay notificaciones", async () => {
    const user = userEvent.setup();
    montar();

    await user.click(abrirCampana());
    expect(await screen.findByText("Sin notificaciones")).toBeInTheDocument();
    expect(screen.queryByText("Marcar todas como leídas")).not.toBeInTheDocument();
  });

  it("si falla la carga abre el panel vacío igual", async () => {
    const user = userEvent.setup();
    getNotifications.mockRejectedValue(new Error("500"));
    montar();

    await user.click(abrirCampana());
    expect(await screen.findByText("Sin notificaciones")).toBeInTheDocument();
  });

  it("un segundo click sobre la campana cierra el panel", async () => {
    const user = userEvent.setup();
    montar();

    await user.click(abrirCampana());
    expect(await screen.findByText("Sin notificaciones")).toBeInTheDocument();

    await user.click(abrirCampana());
    expect(screen.queryByText("Sin notificaciones")).not.toBeInTheDocument();
  });

  it("un click fuera del panel lo cierra", async () => {
    const user = userEvent.setup();
    montar();

    await user.click(abrirCampana());
    expect(await screen.findByText("Sin notificaciones")).toBeInTheDocument();

    await user.click(screen.getByText("tablero"));
    await waitFor(() => expect(screen.queryByText("Sin notificaciones")).not.toBeInTheDocument());
  });

  it("marcar una la deja leída y baja el contador", async () => {
    const user = userEvent.setup();
    getNotifications.mockResolvedValue({ data: [aviso()], unread_count: 2 });
    montar();

    await user.click(abrirCampana());
    await user.click(await screen.findByText("Conciliación lista"));

    expect(markAsRead).toHaveBeenCalledWith(1);
    // El panel se cierra y el badge pasa de 2 a 1
    expect(screen.queryByText("Conciliación lista")).not.toBeInTheDocument();
    expect(await screen.findByText("1")).toBeInTheDocument();
  });

  it("clickear una ya leída no descuenta del contador", async () => {
    const user = userEvent.setup();
    getNotifications.mockResolvedValue({ data: [aviso({ is_read: true })], unread_count: 5 });
    montar();

    await user.click(abrirCampana());
    await user.click(await screen.findByText("Conciliación lista"));

    expect(markAsRead).toHaveBeenCalledWith(1);
    expect(await screen.findByText("5")).toBeInTheDocument();
  });

  it("navega al redirect_path de la notificación", async () => {
    const user = userEvent.setup();
    getNotifications.mockResolvedValue({
      data: [aviso({ redirect_path: "/modules/conciliacion/dias" })],
      unread_count: 1,
    });
    montar();

    await user.click(abrirCampana());
    await user.click(await screen.findByText("Conciliación lista"));

    expect(await screen.findByText("pantalla de conciliación")).toBeInTheDocument();
  });

  it("marcar todas como leídas vacía el contador y apaga los puntos", async () => {
    const user = userEvent.setup();
    getNotifications.mockResolvedValue({ data: [aviso(), aviso({ id: 2 })], unread_count: 2 });
    montar();

    await user.click(abrirCampana());
    await user.click(await screen.findByText("Marcar todas como leídas"));

    expect(markAllAsRead).toHaveBeenCalledTimes(1);
    await waitFor(() =>
      expect(screen.queryByText("Marcar todas como leídas")).not.toBeInTheDocument()
    );
    expect(screen.queryByText("2")).not.toBeInTheDocument();
  });

  it("muestra la antigüedad en minutos, horas y días", async () => {
    const user = userEvent.setup();
    const hace = (segundos) => new Date(Date.now() - segundos * 1000).toISOString();
    getNotifications.mockResolvedValue({
      data: [
        aviso({ id: 1, title: "Recién", created_at: hace(5) }),
        aviso({ id: 2, title: "Minutos", created_at: hace(600) }),
        aviso({ id: 3, title: "Horas", created_at: hace(7200) }),
        aviso({ id: 4, title: "Días", created_at: hace(3 * 86400) }),
      ],
      unread_count: 4,
    });
    montar();

    await user.click(abrirCampana());
    expect(await screen.findByText("Hace un momento")).toBeInTheDocument();
    expect(screen.getByText("Hace 10 min")).toBeInTheDocument();
    expect(screen.getByText("Hace 2 h")).toBeInTheDocument();
    expect(screen.getByText("Hace 3 d")).toBeInTheDocument();
  });
});

describe("NotificationBell — refresco periódico", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    getUnreadCount.mockResolvedValue({ count: 0 });
    getNotifications.mockResolvedValue({ data: [], unread_count: 0 });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("consulta el conteo cada 30 segundos y corta al desmontar", async () => {
    getUnreadCount.mockResolvedValueOnce({ count: 0 }).mockResolvedValue({ count: 4 });
    const { unmount } = montar();

    expect(getUnreadCount).toHaveBeenCalledTimes(1);

    await act(async () => { vi.advanceTimersByTime(30000); });
    expect(getUnreadCount).toHaveBeenCalledTimes(2);
    expect(screen.getByText("4")).toBeInTheDocument();

    await act(async () => { vi.advanceTimersByTime(60000); });
    expect(getUnreadCount).toHaveBeenCalledTimes(4);

    unmount();
    await act(async () => { vi.advanceTimersByTime(120000); });
    expect(getUnreadCount).toHaveBeenCalledTimes(4);
  });
});
