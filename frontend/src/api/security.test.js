import { beforeEach, describe, expect, it, vi } from "vitest";

// El cliente HTTP se reemplaza por un doble: verificamos verbo, URL y payload.
vi.mock("./client", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import api from "./client";
import {
  getUsers, createUser, updateUser, deleteUser, assignRoles,
  adminChangePassword, changeMyPassword,
  getRoles, createRole, updateRole, deleteRole,
  assignPermissions, getPermissions, getModules,
} from "./security";

const respuesta = (data) => Promise.resolve({ data, status: 200 });

describe("api/security — usuarios", () => {
  beforeEach(() => {
    api.get.mockReset();
    api.post.mockReset();
    api.put.mockReset();
    api.delete.mockReset();
  });

  it("getUsers pagina con valores por defecto y devuelve el body", async () => {
    api.get.mockReturnValue(respuesta({ data: [{ id: 1 }], total: 1 }));

    await expect(getUsers()).resolves.toEqual({ data: [{ id: 1 }], total: 1 });
    expect(api.get).toHaveBeenCalledWith("/security/users", { params: { page: 1, per_page: 20 } });
  });

  it("getUsers respeta la página y el tamaño pedidos", async () => {
    api.get.mockReturnValue(respuesta({ data: [], total: 0 }));

    await getUsers(3, 50);
    expect(api.get).toHaveBeenCalledWith("/security/users", { params: { page: 3, per_page: 50 } });
  });

  it("createUser postea el formulario completo", async () => {
    api.post.mockReturnValue(respuesta({ id: 7, username: "ana" }));
    const form = { username: "ana", email: "ana@x.com", password: "secreta", full_name: "Ana" };

    await expect(createUser(form)).resolves.toEqual({ id: 7, username: "ana" });
    expect(api.post).toHaveBeenCalledWith("/security/users", form);
  });

  it("updateUser usa PUT sobre el id del usuario", async () => {
    api.put.mockReturnValue(respuesta({ id: 7, email: "nuevo@x.com" }));

    await expect(updateUser(7, { email: "nuevo@x.com" })).resolves.toEqual({ id: 7, email: "nuevo@x.com" });
    expect(api.put).toHaveBeenCalledWith("/security/users/7", { email: "nuevo@x.com" });
  });

  it("deleteUser usa DELETE sobre el id del usuario", async () => {
    api.delete.mockReturnValue(respuesta({ ok: true }));

    await expect(deleteUser(9)).resolves.toEqual({ ok: true });
    expect(api.delete).toHaveBeenCalledWith("/security/users/9");
  });

  it("assignRoles manda los ids en el campo role_ids", async () => {
    api.post.mockReturnValue(respuesta({ id: 4, roles: [] }));

    await assignRoles(4, [1, 2, 3]);
    expect(api.post).toHaveBeenCalledWith("/security/users/4/roles", { role_ids: [1, 2, 3] });
  });

  it("adminChangePassword sólo manda new_password", async () => {
    api.put.mockReturnValue(respuesta(null));

    await adminChangePassword(4, "nueva-clave");
    expect(api.put).toHaveBeenCalledWith("/security/users/4/password", { new_password: "nueva-clave" });
  });

  it("changeMyPassword manda la actual y la nueva al endpoint /me", async () => {
    api.put.mockReturnValue(respuesta(null));

    await changeMyPassword("vieja", "nueva");
    expect(api.put).toHaveBeenCalledWith("/security/users/me/password", {
      current_password: "vieja",
      new_password: "nueva",
    });
  });
});

describe("api/security — roles, permisos y módulos", () => {
  beforeEach(() => {
    api.get.mockReset();
    api.post.mockReset();
    api.put.mockReset();
    api.delete.mockReset();
  });

  it("getRoles devuelve la lista del body", async () => {
    api.get.mockReturnValue(respuesta([{ id: 1, name: "admin" }]));

    await expect(getRoles()).resolves.toEqual([{ id: 1, name: "admin" }]);
    expect(api.get).toHaveBeenCalledWith("/security/roles");
  });

  it("createRole y updateRole apuntan a /security/roles", async () => {
    api.post.mockReturnValue(respuesta({ id: 2 }));
    api.put.mockReturnValue(respuesta({ id: 2, name: "cajero" }));

    await createRole({ name: "cajero", description: "" });
    await updateRole(2, { name: "cajero", description: "caja" });

    expect(api.post).toHaveBeenCalledWith("/security/roles", { name: "cajero", description: "" });
    expect(api.put).toHaveBeenCalledWith("/security/roles/2", { name: "cajero", description: "caja" });
  });

  it("deleteRole devuelve la respuesta cruda (no el body)", async () => {
    api.delete.mockReturnValue(respuesta({ ok: true }));

    const res = await deleteRole(5);
    expect(api.delete).toHaveBeenCalledWith("/security/roles/5");
    expect(res.status).toBe(200);
  });

  it("assignPermissions manda los ids en permission_ids", async () => {
    api.post.mockReturnValue(respuesta({ id: 5, permissions: [] }));

    await assignPermissions(5, [10, 11]);
    expect(api.post).toHaveBeenCalledWith("/security/roles/5/permissions", { permission_ids: [10, 11] });
  });

  it("getPermissions y getModules consultan sus endpoints", async () => {
    api.get.mockReturnValueOnce(respuesta([{ id: 1, code: "users:read" }]));
    api.get.mockReturnValueOnce(respuesta([{ id: 1, code: "security" }]));

    await expect(getPermissions()).resolves.toEqual([{ id: 1, code: "users:read" }]);
    await expect(getModules()).resolves.toEqual([{ id: 1, code: "security" }]);
    expect(api.get).toHaveBeenNthCalledWith(1, "/security/permissions");
    expect(api.get).toHaveBeenNthCalledWith(2, "/security/modules");
  });
});
