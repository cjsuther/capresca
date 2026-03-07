import api from "./client";

export const getUsers = (page = 1, perPage = 20) =>
  api.get("/security/users", { params: { page, per_page: perPage } }).then((r) => r.data);

export const createUser = (data) =>
  api.post("/security/users", data).then((r) => r.data);

export const updateUser = (id, data) =>
  api.put(`/security/users/${id}`, data).then((r) => r.data);

export const deleteUser = (id) =>
  api.delete(`/security/users/${id}`).then((r) => r.data);

export const assignRoles = (id, roleIds) =>
  api.post(`/security/users/${id}/roles`, { role_ids: roleIds }).then((r) => r.data);

export const adminChangePassword = (id, newPassword) =>
  api.put(`/security/users/${id}/password`, { new_password: newPassword });

export const changeMyPassword = (currentPassword, newPassword) =>
  api.put("/security/users/me/password", { current_password: currentPassword, new_password: newPassword });

export const getRoles = () =>
  api.get("/security/roles").then((r) => r.data);

export const createRole = (data) =>
  api.post("/security/roles", data).then((r) => r.data);

export const updateRole = (id, data) =>
  api.put(`/security/roles/${id}`, data).then((r) => r.data);

export const deleteRole = (id) =>
  api.delete(`/security/roles/${id}`);

export const assignPermissions = (roleId, permissionIds) =>
  api.post(`/security/roles/${roleId}/permissions`, { permission_ids: permissionIds }).then((r) => r.data);

export const getPermissions = () =>
  api.get("/security/permissions").then((r) => r.data);

export const getModules = () =>
  api.get("/security/modules").then((r) => r.data);
