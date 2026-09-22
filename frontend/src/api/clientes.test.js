import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import api from "./client";
import * as clientes from "./clientes";

describe("API de clientes", () => {
  let get, post, put, del;

  beforeEach(() => {
    get = vi.spyOn(api, "get").mockResolvedValue({ data: { origen: "get" } });
    post = vi.spyOn(api, "post").mockResolvedValue({ data: { origen: "post" } });
    put = vi.spyOn(api, "put").mockResolvedValue({ data: { origen: "put" } });
    del = vi.spyOn(api, "delete").mockResolvedValue({ status: 204 });
  });

  afterEach(() => vi.restoreAllMocks());

  describe("listados y búsqueda", () => {
    it("getClients manda los filtros como query params y devuelve el body", async () => {
      await expect(clientes.getClients({ search: "perez", client_type: "HUMAN" }))
        .resolves.toEqual({ origen: "get" });
      expect(get).toHaveBeenCalledWith("/clientes", { params: { search: "perez", client_type: "HUMAN" } });
    });

    it("getClients sin argumentos manda params vacíos", async () => {
      await clientes.getClients();
      expect(get).toHaveBeenCalledWith("/clientes", { params: {} });
    });

    it("searchClients usa página 1 por defecto", async () => {
      await clientes.searchClients("ana");
      expect(get).toHaveBeenCalledWith("/clientes/search", { params: { q: "ana", page: 1 } });
    });

    it("searchClients respeta la página pedida", async () => {
      await clientes.searchClients("ana", 3);
      expect(get).toHaveBeenCalledWith("/clientes/search", { params: { q: "ana", page: 3 } });
    });

    it("getClient pide el cliente por id", async () => {
      await expect(clientes.getClient(7)).resolves.toEqual({ origen: "get" });
      expect(get).toHaveBeenCalledWith("/clientes/7");
    });
  });

  describe("alta y edición", () => {
    it("createHumanClient postea a /clientes/human", async () => {
      const payload = { email: "a@b.com", profile: { first_name: "Ana" } };
      await expect(clientes.createHumanClient(payload)).resolves.toEqual({ origen: "post" });
      expect(post).toHaveBeenCalledWith("/clientes/human", payload);
    });

    it("createLegalClient postea a /clientes/legal", async () => {
      const payload = { profile: { legal_name: "ACME SA" } };
      await clientes.createLegalClient(payload);
      expect(post).toHaveBeenCalledWith("/clientes/legal", payload);
    });

    it("updateClient actualiza los datos base", async () => {
      await expect(clientes.updateClient(5, { city: "Neuquén" })).resolves.toEqual({ origen: "put" });
      expect(put).toHaveBeenCalledWith("/clientes/5", { city: "Neuquén" });
    });

    it("updateHumanProfile y updateLegalProfile pegan a subrecursos distintos", async () => {
      await clientes.updateHumanProfile(5, { first_name: "Ana" });
      await clientes.updateLegalProfile(6, { legal_name: "ACME" });
      expect(put).toHaveBeenNthCalledWith(1, "/clientes/5/human", { first_name: "Ana" });
      expect(put).toHaveBeenNthCalledWith(2, "/clientes/6/legal", { legal_name: "ACME" });
    });

    it("deactivateClient hace DELETE sobre el cliente", async () => {
      await clientes.deactivateClient(5);
      expect(del).toHaveBeenCalledWith("/clientes/5");
    });
  });

  describe("contactos y notas", () => {
    it("getContacts / addContact / removeContact usan el subrecurso contacts", async () => {
      await clientes.getContacts(1);
      expect(get).toHaveBeenCalledWith("/clientes/1/contacts");

      await clientes.addContact(1, { value: "351-555" });
      expect(post).toHaveBeenCalledWith("/clientes/1/contacts", { value: "351-555" });

      await clientes.removeContact(1, 9);
      expect(del).toHaveBeenCalledWith("/clientes/1/contacts/9");
    });

    it("addNote envuelve el texto en { content }", async () => {
      await expect(clientes.addNote(1, "llamar mañana")).resolves.toEqual({ origen: "post" });
      expect(post).toHaveBeenCalledWith("/clientes/1/notes", { content: "llamar mañana" });
    });

    it("getNotes lista las notas del cliente", async () => {
      await clientes.getNotes(1);
      expect(get).toHaveBeenCalledWith("/clientes/1/notes");
    });
  });

  describe("miembros (personas físicas vinculadas)", () => {
    it("getMembers / addMember / removeMember usan el subrecurso members", async () => {
      await clientes.getMembers(2);
      expect(get).toHaveBeenCalledWith("/clientes/2/members");

      await clientes.addMember(2, { human_client_id: 8, role: "Titular" });
      expect(post).toHaveBeenCalledWith("/clientes/2/members", { human_client_id: 8, role: "Titular" });

      await clientes.removeMember(2, 8);
      expect(del).toHaveBeenCalledWith("/clientes/2/members/8");
    });
  });

  describe("CBUs", () => {
    it("getCbus / addCbu / updateCbu / deleteCbu usan el subrecurso cbus", async () => {
      await clientes.getCbus(3);
      expect(get).toHaveBeenCalledWith("/clientes/3/cbus");

      await clientes.addCbu(3, { cbu: "0".repeat(22), alias: "mi.alias" });
      expect(post).toHaveBeenCalledWith("/clientes/3/cbus", { cbu: "0".repeat(22), alias: "mi.alias" });

      await clientes.updateCbu(3, 4, { alias: "otro" });
      expect(put).toHaveBeenCalledWith("/clientes/3/cbus/4", { alias: "otro" });

      await clientes.deleteCbu(3, 4);
      expect(del).toHaveBeenCalledWith("/clientes/3/cbus/4");
    });
  });

  it("los errores del backend se propagan al llamador", async () => {
    get.mockRejectedValueOnce({ response: { data: { detail: "No encontrado" } } });
    await expect(clientes.getClient(99)).rejects.toMatchObject({
      response: { data: { detail: "No encontrado" } },
    });
  });
});
