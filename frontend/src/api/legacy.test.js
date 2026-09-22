import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import api from "./client";
import {
  getInteractions,
  getInteraction,
  getDatabases,
  getStatus,
  triggerSync,
  getOutbox,
  drainOutbox,
} from "./legacy";

describe("API del módulo legacy", () => {
  let get;
  let post;

  beforeEach(() => {
    get = vi.spyOn(api, "get").mockResolvedValue({ data: { items: [], total: 0 } });
    post = vi.spyOn(api, "post").mockResolvedValue({ data: { drained: 3 } });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("lista interacciones con los filtros como query params", async () => {
    await expect(
      getInteractions({ page: 2, page_size: 50, direction: "OUT" })
    ).resolves.toEqual({ items: [], total: 0 });
    expect(get).toHaveBeenCalledWith("/legacy/interactions", {
      params: { page: 2, page_size: 50, direction: "OUT" },
    });
  });

  it("trae una interacción puntual", async () => {
    await getInteraction(15);
    expect(get).toHaveBeenCalledWith("/legacy/interactions/15");
  });

  it("lista las bases de datos espejadas", async () => {
    await getDatabases();
    expect(get).toHaveBeenCalledWith("/legacy/databases");
  });

  it("trae el estado de la integración", async () => {
    await getStatus();
    expect(get).toHaveBeenCalledWith("/legacy/status");
  });

  it("fuerza la sincronización de una tabla", async () => {
    await expect(triggerSync("cajaliq")).resolves.toEqual({ drained: 3 });
    expect(post).toHaveBeenCalledWith("/legacy/sync/cajaliq");
  });

  it("lista y drena el outbox de escrituras", async () => {
    await getOutbox({ status: "PENDING" });
    expect(get).toHaveBeenCalledWith("/legacy/outbox", { params: { status: "PENDING" } });

    await expect(drainOutbox()).resolves.toEqual({ drained: 3 });
    expect(post).toHaveBeenCalledWith("/legacy/outbox/drain");
  });

  it("propaga el error de la API", async () => {
    get.mockRejectedValueOnce({ response: { data: { detail: "integración apagada" } } });
    await expect(getStatus()).rejects.toMatchObject({
      response: { data: { detail: "integración apagada" } },
    });
  });
});
