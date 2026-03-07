import { useEffect, useState } from "react";
import { getUsers, createUser, updateUser, deleteUser, getRoles, assignRoles, adminChangePassword } from "../../../api/security";
import { PermissionGate } from "../../../components/PrivateRoute";
import { ChangePasswordModal } from "../../../components/ChangePasswordModal";
import {
  Plus, Pencil, Trash2, UserCheck, UserX,
  ShieldCheck, Check, X, ChevronDown, ChevronUp, KeyRound,
} from "lucide-react";

export default function UsersPage() {
  const [data, setData] = useState({ data: [], total: 0 });
  const [allRoles, setAllRoles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Nuevo usuario
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createForm, setCreateForm] = useState({ username: "", email: "", password: "", full_name: "" });

  // Usuario en edición
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({ email: "", full_name: "", is_active: true });

  // Panel de roles
  const [rolesPanelId, setRolesPanelId] = useState(null);
  const [selectedRoles, setSelectedRoles] = useState(new Set());

  // Modal cambio de contraseña por admin
  const [passwordTarget, setPasswordTarget] = useState(null); // { id, username }

  const load = () => {
    setLoading(true);
    Promise.all([getUsers(), getRoles()])
      .then(([u, r]) => { setData(u); setAllRoles(r); })
      .catch(() => setError("Error al cargar datos"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  // ── Crear ────────────────────────────────────────────────────
  const handleCreate = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await createUser(createForm);
      setShowCreateForm(false);
      setCreateForm({ username: "", email: "", password: "", full_name: "" });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al crear usuario");
    }
  };

  // ── Editar ───────────────────────────────────────────────────
  const startEdit = (user) => {
    setEditingId(user.id);
    setEditForm({ email: user.email, full_name: user.full_name || "", is_active: user.is_active });
    setRolesPanelId(null);
  };

  const handleUpdate = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await updateUser(editingId, editForm);
      setEditingId(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al actualizar usuario");
    }
  };

  // ── Desactivar ───────────────────────────────────────────────
  const handleDelete = async (user) => {
    if (!confirm(`¿Desactivar al usuario "${user.username}"?`)) return;
    setError("");
    try {
      await deleteUser(user.id);
      load();
    } catch {
      setError("Error al desactivar usuario");
    }
  };

  // ── Panel de roles ───────────────────────────────────────────
  const openRolesPanel = (user) => {
    if (rolesPanelId === user.id) { setRolesPanelId(null); return; }
    setRolesPanelId(user.id);
    setSelectedRoles(new Set(user.roles.map((r) => r.id)));
    setEditingId(null);
  };

  const toggleRole = (roleId) => {
    setSelectedRoles((prev) => {
      const next = new Set(prev);
      next.has(roleId) ? next.delete(roleId) : next.add(roleId);
      return next;
    });
  };

  const handleSaveRoles = async (userId) => {
    setError("");
    try {
      await assignRoles(userId, [...selectedRoles]);
      setRolesPanelId(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al guardar roles");
    }
  };

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <h2 className="text-xl font-semibold text-gray-800">Usuarios</h2>
        <PermissionGate moduleCode="security" action="users:write">
          <button
            onClick={() => { setShowCreateForm(!showCreateForm); setEditingId(null); setRolesPanelId(null); }}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700"
          >
            <Plus size={16} /> Nuevo usuario
          </button>
        </PermissionGate>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2 text-sm mb-4">
          {error}
        </div>
      )}

      {/* Formulario de creación */}
      {showCreateForm && (
        <form onSubmit={handleCreate} className="bg-white border rounded-xl p-5 mb-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Usuario</label>
            <input className="input w-full" value={createForm.username} onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })} required />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input className="input w-full" value={createForm.email} onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })} required />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Contraseña</label>
            <input type="password" className="input w-full" value={createForm.password} onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })} required />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nombre completo</label>
            <input className="input w-full" value={createForm.full_name} onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })} />
          </div>
          <div className="col-span-1 sm:col-span-2 flex gap-2 justify-end">
            <button type="button" onClick={() => setShowCreateForm(false)} className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">Cancelar</button>
            <button type="submit" className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">Crear</button>
          </div>
        </form>
      )}

      {/* Tabla de usuarios */}
      <div className="bg-white border rounded-xl overflow-x-auto">
        <table className="w-full text-sm min-w-[700px]">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Usuario</th>
              <th className="text-left px-4 py-3 font-medium">Email</th>
              <th className="text-left px-4 py-3 font-medium">Nombre</th>
              <th className="text-left px-4 py-3 font-medium">Estado</th>
              <th className="text-left px-4 py-3 font-medium">Roles</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Cargando...</td></tr>
            ) : data.data.map((user) => (
              <>
                {/* Fila principal */}
                <tr key={user.id} className={editingId === user.id || rolesPanelId === user.id ? "bg-blue-50" : "hover:bg-gray-50"}>

                  <td className="px-4 py-3 font-medium">{user.username}</td>

                  <td className="px-4 py-3 text-gray-600">
                    {editingId === user.id
                      ? <input className="input w-full text-sm" value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} />
                      : user.email
                    }
                  </td>

                  <td className="px-4 py-3 text-gray-600">
                    {editingId === user.id
                      ? <input className="input w-full text-sm" value={editForm.full_name} onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })} placeholder="Nombre completo" />
                      : (user.full_name || "—")
                    }
                  </td>

                  <td className="px-4 py-3">
                    {editingId === user.id ? (
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input type="checkbox" checked={editForm.is_active} onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })} className="rounded text-blue-600" />
                        <span className="text-sm text-gray-600">Activo</span>
                      </label>
                    ) : user.is_active
                      ? <span className="flex items-center gap-1 text-green-600"><UserCheck size={14} /> Activo</span>
                      : <span className="flex items-center gap-1 text-red-500"><UserX size={14} /> Inactivo</span>
                    }
                  </td>

                  <td className="px-4 py-3 text-gray-500">
                    {user.roles.length > 0
                      ? user.roles.map((r) => (
                        <span key={r.id} className="inline-block bg-purple-50 text-purple-700 text-xs px-2 py-0.5 rounded mr-1">{r.name}</span>
                      ))
                      : <span className="text-gray-300">—</span>
                    }
                  </td>

                  {/* Acciones */}
                  <td className="px-4 py-3">
                    <PermissionGate moduleCode="security" action="users:write">
                      <div className="flex items-center justify-end gap-1">
                        {editingId === user.id ? (
                          <>
                            <button onClick={handleUpdate} title="Guardar" className="flex items-center gap-1 px-3 py-1.5 text-xs bg-green-600 text-white rounded-lg hover:bg-green-700">
                              <Check size={13} /> Guardar
                            </button>
                            <button onClick={() => setEditingId(null)} title="Cancelar" className="p-1.5 text-gray-400 hover:text-gray-700 border rounded-lg hover:bg-gray-50">
                              <X size={14} />
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              onClick={() => openRolesPanel(user)}
                              title="Gestionar roles"
                              className="flex items-center gap-1 px-3 py-1.5 text-xs text-purple-600 border border-purple-200 rounded-lg hover:bg-purple-50"
                            >
                              <ShieldCheck size={13} />
                              Roles
                              {rolesPanelId === user.id ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                            </button>
                            <button
                              onClick={() => { setPasswordTarget(user); setEditingId(null); setRolesPanelId(null); }}
                              title="Cambiar contraseña"
                              className="p-1.5 text-gray-400 hover:text-yellow-600 hover:bg-yellow-50 rounded-lg"
                            >
                              <KeyRound size={15} />
                            </button>
                            <button onClick={() => startEdit(user)} title="Editar" className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg">
                              <Pencil size={15} />
                            </button>
                            <button onClick={() => handleDelete(user)} title="Desactivar" className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg">
                              <Trash2 size={15} />
                            </button>
                          </>
                        )}
                      </div>
                    </PermissionGate>
                  </td>
                </tr>

                {/* Panel de roles expandible */}
                {rolesPanelId === user.id && (
                  <tr key={`${user.id}-roles`}>
                    <td colSpan={6} className="px-4 pb-4 bg-purple-50 border-b">
                      <div className="pt-3">
                        <p className="text-sm font-medium text-gray-700 mb-3">Asignar roles a <strong>{user.username}</strong></p>
                        <div className="flex flex-wrap gap-3 mb-4">
                          {allRoles.map((role) => (
                            <label key={role.id} className="flex items-center gap-2 cursor-pointer bg-white border rounded-lg px-3 py-2 hover:border-purple-400 transition-colors">
                              <input
                                type="checkbox"
                                checked={selectedRoles.has(role.id)}
                                onChange={() => toggleRole(role.id)}
                                className="rounded text-purple-600"
                              />
                              <div>
                                <span className="text-sm font-medium text-gray-800">{role.name}</span>
                                {role.description && <p className="text-xs text-gray-400">{role.description}</p>}
                              </div>
                            </label>
                          ))}
                        </div>
                        <div className="flex gap-2 justify-end">
                          <button onClick={() => setRolesPanelId(null)} className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-white">
                            Cancelar
                          </button>
                          <button onClick={() => handleSaveRoles(user.id)} className="flex items-center gap-1 px-4 py-2 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700">
                            <Check size={14} /> Guardar roles
                          </button>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal cambio de contraseña por admin */}
      {passwordTarget && (
        <ChangePasswordModal
          title={`Contraseña de ${passwordTarget.username}`}
          requireCurrent={false}
          onSave={(_, newPass) => adminChangePassword(passwordTarget.id, newPass)}
          onClose={() => setPasswordTarget(null)}
        />
      )}
    </div>
  );
}
