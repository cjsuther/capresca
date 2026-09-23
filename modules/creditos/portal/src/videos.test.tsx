import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PasoVideos, VideoObligatorio, guardarVistos, leerVistos, olvidarVistos } from "./videos";

const VIDEO = { id: "video1", titulo: "Introducción", url: "/portal-creditos/videos/video1.mp4" };

/** El <video> de jsdom no reproduce: se controla el tiempo a mano. */
function reloj(video: HTMLVideoElement, duracion = 100) {
  const estado = { t: 0, rate: 1 };
  Object.defineProperty(video, "duration", { configurable: true, get: () => duracion });
  Object.defineProperty(video, "currentTime", { configurable: true, get: () => estado.t, set: (v) => { estado.t = v; } });
  Object.defineProperty(video, "playbackRate", { configurable: true, get: () => estado.rate, set: (v) => { estado.rate = v; } });
  fireEvent.loadedMetadata(video);
  const reproducirHasta = (hasta: number) => {
    for (let x = estado.t + 0.25; x <= hasta + 1e-9; x += 0.25) { estado.t = x; fireEvent.timeUpdate(video); }
  };
  return { estado, reproducirHasta };
}

function montar(props: Partial<Parameters<typeof VideoObligatorio>[0]> = {}) {
  const onCompleto = vi.fn();
  render(<VideoObligatorio video={VIDEO} numero={1} completo={false} habilitado onCompleto={onCompleto} {...props} />);
  const video = document.querySelector("video") as HTMLVideoElement;
  return { video, onCompleto };
}

describe("video obligatorio", () => {
  it("no se puede adelantar: vuelve al punto más lejano visto y lo avisa", () => {
    const { video } = montar();
    const { estado, reproducirHasta } = reloj(video);
    reproducirHasta(20);
    estado.t = 80;                       // arrastra la barra hacia adelante
    fireEvent.seeking(video);
    expect(estado.t).toBe(20);
    expect(screen.getByRole("status")).toHaveTextContent("No se puede adelantar");
  });

  it("sí se puede volver atrás", () => {
    const { video } = montar();
    const { estado, reproducirHasta } = reloj(video);
    reproducirHasta(30);
    estado.t = 5;
    fireEvent.seeking(video);
    expect(estado.t).toBe(5);
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("no se puede acelerar la reproducción", () => {
    const { video } = montar();
    const { estado } = reloj(video);
    estado.rate = 2;
    fireEvent.rateChange(video);
    expect(estado.rate).toBe(1);
  });

  it("terminar sin haberlo recorrido completo no cuenta", () => {
    const { video, onCompleto } = montar();
    const { estado, reproducirHasta } = reloj(video);
    reproducirHasta(40);
    estado.t = 100;                      // un salto que no pasó por seeking (p.ej. manipulado)
    fireEvent.ended(video);
    expect(onCompleto).not.toHaveBeenCalled();
  });

  it("visto de punta a punta cuenta como completo y muestra el avance", () => {
    const { video, onCompleto } = montar();
    const { reproducirHasta } = reloj(video);
    reproducirHasta(50);
    expect(screen.getByRole("progressbar", { name: "Progreso del video 1" })).toHaveAttribute("aria-valuenow", "50");
    reproducirHasta(100);
    fireEvent.ended(video);
    expect(onCompleto).toHaveBeenCalledWith("video1");
  });

  it("sin ver, no muestra la barra nativa: sólo el play/pausa propio (en el celular se adelantaba)", () => {
    const { video } = montar();
    expect(video.hasAttribute("controls")).toBe(false);
    const play = screen.getByRole("button", { name: "Reproducir video 1" });
    const reproducir = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(video, "paused", { configurable: true, get: () => true });
    video.play = reproducir;
    fireEvent.click(play);
    expect(reproducir).toHaveBeenCalled();
    fireEvent.play(video);
    expect(screen.getByRole("button", { name: "Pausar video 1" })).toBeInTheDocument();
  });

  it("uno ya visto vuelve a tener los controles normales", () => {
    const { video } = montar({ completo: true });
    expect(video.hasAttribute("controls")).toBe(true);
    expect(screen.queryByRole("button", { name: /Reproducir video/ })).toBeNull();
  });

  it("uno ya visto se puede recorrer libremente", () => {
    const { video, onCompleto } = montar({ completo: true });
    const { estado } = reloj(video);
    estado.t = 90;
    fireEvent.seeking(video);
    expect(estado.t).toBe(90);
    fireEvent.ended(video);
    expect(onCompleto).not.toHaveBeenCalled();   // ya estaba contado
  });

  it("bloqueado no carga el video hasta terminar el anterior", () => {
    montar({ habilitado: false });
    expect(document.querySelector("video")).toBeNull();
    expect(screen.getByText("Se habilita al terminar el anterior")).toBeInTheDocument();
  });

  it("si la pestaña pasa a segundo plano, se pausa", () => {
    const { video } = montar();
    const pause = vi.fn();
    Object.defineProperty(video, "paused", { configurable: true, get: () => false });
    video.pause = pause;
    Object.defineProperty(document, "hidden", { configurable: true, get: () => true });
    document.dispatchEvent(new Event("visibilitychange"));
    expect(pause).toHaveBeenCalled();
    Object.defineProperty(document, "hidden", { configurable: true, get: () => false });
  });
});

describe("paso de videos", () => {
  const VIDEOS = [VIDEO, { ...VIDEO, id: "video2", titulo: "Obligaciones" }];

  it("habilita cada video recién cuando el anterior está visto", () => {
    render(<PasoVideos videos={VIDEOS} vistos={["video1"]} onVisto={vi.fn()} />);
    expect(document.querySelectorAll("video")).toHaveLength(2);
    expect(screen.getByText("Te falta 1 video.")).toBeInTheDocument();
  });

  it("recuerda lo visto por ciudadano hasta enviar", () => {
    guardarVistos("u-9", ["video1"]);
    expect(leerVistos("u-9")).toEqual(["video1"]);
    expect(leerVistos("otro")).toEqual([]);
    olvidarVistos("u-9");
    expect(leerVistos("u-9")).toEqual([]);
  });
});
