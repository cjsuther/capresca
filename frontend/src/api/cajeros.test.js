import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import api from "./client";
import * as cajerosApi from "./cajeros";

const respuesta = (data) => Promise.resolve({ data, status: 200 });

describe("api/cajeros — reglas", () => {
  beforeEach(() => {
    api.get.mockReset();
    api.post.mockReset();
    api.put.mockReset();
    api.delete.mockReset();
  });

  it("getRules pega a /cajeros/rules sin filtros y devuelve el body", async () => {
    api.get.mockReturnValue(respuesta([{ id: 1 }]));
    const data = await cajerosApi.getRules();
    expect(api.get).toHaveBeenCalledWith("/cajeros/rules", { params: {} });
    expect(data).toEqual([{ id: 1 }]);
  });

  it("getRules propaga los filtros como query params", async () => {
    api.get.mockReturnValue(respuesta([]));
    await cajerosApi.getRules({ cajero: "7", currency: "USD" });
    expect(api.get).toHaveBeenCalledWith("/cajeros/rules", {
      params: { cajero: "7", currency: "USD" },
    });
  });

  it("createRule postea el cuerpo y devuelve la regla creada", async () => {
    api.post.mockReturnValue(respuesta({ id: 9, currency: "ARS" }));
    const regla = await cajerosApi.createRule({ currency: "ARS", amount_limit: 100 });
    expect(api.post).toHaveBeenCalledWith("/cajeros/rules", { currency: "ARS", amount_limit: 100 });
    expect(regla).toEqual({ id: 9, currency: "ARS" });
  });

  it("deleteRule llama al endpoint con el id en la URL", async () => {
    api.delete.mockReturnValue(respuesta(null));
    // TODO(bug): src/api/cajeros.js:11 — deleteRule es la única función que NO hace .then(r => r.data);
    // devuelve la respuesta axios completa mientras el resto devuelve el body. Inconsistencia de la API.
    const res = await cajerosApi.deleteRule(5);
    expect(api.delete).toHaveBeenCalledWith("/cajeros/rules/5");
    expect(res).toHaveProperty("status", 200);
  });
});

describe("api/cajeros — transacciones", () => {
  beforeEach(() => {
    api.get.mockReset();
    api.post.mockReset();
    api.put.mockReset();
    api.delete.mockReset();
  });

  it("getTransactions manda los filtros recibidos", async () => {
    api.get.mockReturnValue(respuesta([{ id: 3 }]));
    const data = await cajerosApi.getTransactions({ status: "PROCESADA", currency: "ARS" });
    expect(api.get).toHaveBeenCalledWith("/cajeros/transactions", {
      params: { status: "PROCESADA", currency: "ARS" },
    });
    expect(data).toEqual([{ id: 3 }]);
  });

  it("getTransaction pide una transacción puntual", async () => {
    api.get.mockReturnValue(respuesta({ id: 12 }));
    const tx = await cajerosApi.getTransaction(12);
    expect(api.get).toHaveBeenCalledWith("/cajeros/transactions/12");
    expect(tx).toEqual({ id: 12 });
  });

  it("createTransaction postea la transacción nueva", async () => {
    api.post.mockReturnValue(respuesta({ id: 1, status: "PROCESADA" }));
    const tx = await cajerosApi.createTransaction({ amount: 10, currency: "ARS" });
    expect(api.post).toHaveBeenCalledWith("/cajeros/transactions", { amount: 10, currency: "ARS" });
    expect(tx.status).toBe("PROCESADA");
  });

  it("authorizeTransaction usa PUT sobre /authorize sin cuerpo", async () => {
    api.put.mockReturnValue(respuesta({ id: 4, status: "AUTORIZADA" }));
    const tx = await cajerosApi.authorizeTransaction(4);
    expect(api.put).toHaveBeenCalledWith("/cajeros/transactions/4/authorize");
    expect(tx.status).toBe("AUTORIZADA");
  });

  it("rejectTransaction manda el motivo de rechazo", async () => {
    api.put.mockReturnValue(respuesta({ id: 4, status: "RECHAZADA" }));
    const tx = await cajerosApi.rejectTransaction(4, { rejection_reason: "monto erróneo" });
    expect(api.put).toHaveBeenCalledWith("/cajeros/transactions/4/reject", {
      rejection_reason: "monto erróneo",
    });
    expect(tx.status).toBe("RECHAZADA");
  });

  it("deleteTransaction devuelve el body de la respuesta", async () => {
    api.delete.mockReturnValue(respuesta({ ok: true }));
    const res = await cajerosApi.deleteTransaction(8);
    expect(api.delete).toHaveBeenCalledWith("/cajeros/transactions/8");
    expect(res).toEqual({ ok: true });
  });

  it("los errores de axios se propagan al llamador", async () => {
    api.get.mockReturnValue(Promise.reject(new Error("boom")));
    await expect(cajerosApi.getTransactions()).rejects.toThrow("boom");
  });
});

describe("api/cajeros — exports que las pantallas esperan", () => {
  // TODO(bug): src/api/cajeros.js sólo exporta reglas y transacciones, pero varias pantallas del
  // módulo importan funciones que NO existen en este archivo:
  //   OperacionesPage.jsx:2   -> getOperations
  //   SolicitudesPage.jsx:2   -> getRequests, createRequest
  //   AutorizacionesPage.jsx:2-> getRequests, approveRequest, rejectRequest
  //   LimitesPage.jsx:2       -> getMyLimit, updateLimit
  //   RelacionesPage.jsx:2    -> getRelations, createRelation, deleteRelation
  // En runtime esas pantallas explotan con "X is not a function" apenas se montan.
  // Este test documenta el estado ACTUAL del módulo de API.
  it("faltan los exports de operaciones, solicitudes, límites y relaciones", () => {
    const definidos = [
      "getRules", "createRule", "deleteRule",
      "getTransactions", "getTransaction", "createTransaction",
      "authorizeTransaction", "rejectTransaction", "deleteTransaction",
    ];
    definidos.forEach((n) => expect(typeof cajerosApi[n]).toBe("function"));

    const faltantes = [
      "getOperations", "getRequests", "createRequest", "approveRequest", "rejectRequest",
      "getMyLimit", "updateLimit", "getRelations", "createRelation", "deleteRelation",
    ];
    faltantes.forEach((n) => expect(cajerosApi[n]).toBeUndefined());
  });
});
