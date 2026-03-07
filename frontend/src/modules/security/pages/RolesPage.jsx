import { useEffect, useState } from "react";
import {
  getRoles, createRole, updateRole, deleteRole,
  getPermissions, assignPermissions,
} from "../../../api/security";
import { PermissionGate } from "../../../components/PrivateRoute";
import { Plus, Pencil, Trash2, Key, Check, X, ChevronDown, ChevronUp } from "lucide-react";

export default function RolesPage() {
  const [roles, setRoles] = useState([]);
  const [allPermissions, setAllPermissions] = useState([]);
  const [loading, setLoading] = useState(true);

  // Nuevo rol
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createForm, setCreateForm] = useState({ name: "", description: "" });

  // Rol en edición (nombre/descripción)
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({ name: "", description: "" });

  // Rol con panel de permisos abierto
  const [permsPanelId, setPermsPanelId] = useState(null);
  // Permisos seleccionados (set de ids) por rol en edición
  const [selectedPerms, setSelectedPerms] = useState(new Set());

  const [error, setError] = useState("");

  const load = () => {
    setLoading(true);
    Promise.all([getRoles(), getPermissions()])
      .then(([r, p]) => { setRoles(r); setAllPermissions(p); })
      .catch(() => setError("Error al cargar datos"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  // ── Crear rol ────────────────────────────────────────────────
  const handleCreate = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await createRole(createForm);
      setShowCreateForm(false);
      setCreateForm({ name: "", description: "" });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al crear rol");
    }
  };

  // ── Editar nombre/descripción ────────────────────────────────
  const startEdit = (role) => {
    setEditingId(role.id);
    setEditForm({ name: role.name, description: role.description || "" });
    setPermsPanelId(null);
  };

  const handleUpdate = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await updateRole(editingId, editForm);
      setEditingId(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al actualizar rol");
    }
  };

  // ── Eliminar rol ─────────────────────────────────────────────
  const handleDelete = async (role) => {
    if (!confirm(`¿Eliminar el rol "${role.name}"? Esta acción no se puede deshacer.`)) return;
    setError("");
    try {
      await deleteRole(role.id);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al eliminar rol");
    }
  };

  // ── Panel de permisos ────────────────────────────────────────
  const openPermsPanel = (role) => {
    if (permsPanelId === role.id) {
      setPermsPanelId(null);
      return;
    }
    setPermsPanelId(role.id);
    setSelectedPerms(new Set(role.permissions.map((p) => p.id)));
    setEditingId(null);
  };

  const togglePerm = (permId) => {
    setSelectedPerms((prev) => {
      const next = new Set(prev);
      next.has(permId) ? next.delete(permId) : next.add(permId);
      return next;
    });
  };

  const handleSavePerms = async (roleId) => {
    setError("");
    try {
      await assignPermissions(roleId, [...selectedPerms]);
      setPermsPanelId(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al guardar permisos");
    }
  };

  // Agrupar permisos por módulo para mostrarlos ordenados
  const permsByModule = allPermissions.reduce((acc, p) => {
    // El module_id lo usamos para agrupar, pero mostramos el prefijo del código
    const module = p.code.split(":")[0];
    if (!acc[module]) acc[module] = [];
    acc[module].push(p);
    return acc;
  }, {});

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-800">Roles</h2>
        <PermissionGate moduleCode="security" action="roles:write">
          <button
            onClick={() => { setShowCreateForm(!showCreateForm); setEditingId(null); setPermsPanelId(null); }}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700"
          >
            <Plus size={16} /> Nuevo rol
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
        <form onSubmit={handleCreate} className="bg-white border rounded-xl p-5 mb-4 flex gap-4 flex-wrap items-end">
          <div className="flex-1 min-w-36">
            <label className="block text-sm font-medium text-gray-700 mb-1">Nombre</label>
            <input
              className="input w-full"
              value={createForm.name}
              onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
              required
            />
          </div>
          <div className="flex-1 min-w-36">
            <label className="block text-sm font-medium text-gray-700 mb-1">Descripción</label>
            <input
              className="input w-full"
              value={createForm.description}
              onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
            />
          </div>
          <div className="flex gap-2">
            <button type="button" onClick={() => setShowCreateForm(false)} className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">
              Cancelar
            </button>
            <button type="submit" className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              Crear
            </button>
          </div>
        </form>
      )}

      {/* Lista de roles */}
      <div className="grid gap-3">
        {loading ? (
          <p className="text-gray-400 text-sm">Cargando...</p>
        ) : roles.map((role) => (
          <div key={role.id} className="bg-white border rounded-xl overflow-hidden">

            {/* Cabecera del rol */}
            <div className="px-5 py-4">
              {editingId === role.id ? (
                /* Formulario de edición inline */
                <form onSubmit={handleUpdate} className="flex gap-3 flex-wrap items-end">
                  <div className="flex-1 min-w-36">
                    <label className="block text-xs font-medium text-gray-600 mb-1">Nombre</label>
                    <input
                      className="input w-full"
                      value={editForm.name}
                      onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                      required
                    />
                  </div>
                  <div className="flex-1 min-w-36">
                    <label className="block text-xs font-medium text-gray-600 mb-1">Descripción</label>
                    <input
                      className="input w-full"
                      value={editForm.description}
                      onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                    />
                  </div>
                  <div className="flex gap-2">
                    <button type="submit" className="flex items-center gap-1 px-3 py-2 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700">
                      <Check size={14} /> Guardar
                    </button>
                    <button type="button" onClick={() => setEditingId(null)} className="flex items-center gap-1 px-3 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-50">
                      <X size={14} /> Cancelar
                    </button>
                  </div>
                </form>
              ) : (
                /* Vista normal */
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-800">{role.name}</span>
                      <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                        {role.permissions?.length ?? 0} permisos
                      </span>
                    </div>
                    {role.description && (
                      <p className="text-sm text-gray-500 mt-0.5">{role.description}</p>
                    )}
                  </div>

                  <PermissionGate moduleCode="security" action="roles:write">
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => openPermsPanel(role)}
                        title="Gestionar permisos"
                        className="flex items-center gap-1 px-3 py-1.5 text-xs text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50"
                      >
                        <Key size={13} />
                        Permisos
                        {permsPanelId === role.id ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                      </button>
                      <button
                        onClick={() => startEdit(role)}
                        title="Editar"
                        className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg"
                      >
                        <Pencil size={15} />
                      </button>
                      <button
                        onClick={() => handleDelete(role)}
                        title="Eliminar"
                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </PermissionGate>
                </div>
              )}

              {/* Tags de permisos actuales (solo cuando no está en modo edición de permisos) */}
              {editingId !== role.id && permsPanelId !== role.id && role.permissions?.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {role.permissions.map((p) => (
                    <span key={p.id} className="bg-blue-50 text-blue-700 text-xs px-2 py-0.5 rounded">
                      {p.code}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Panel de edición de permisos */}
            {permsPanelId === role.id && (
              <div className="border-t bg-gray-50 px-5 py-4">
                <p className="text-sm font-medium text-gray-700 mb-3">Seleccionar permisos</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-y-1 gap-x-4 mb-4">
                  {Object.entries(permsByModule).map(([module, perms]) => (
                    <div key={module}>
                      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mt-2 mb-1">{module}</p>
                      {perms.map((p) => (
                        <label key={p.id} className="flex items-center gap-2 cursor-pointer py-0.5 group">
                          <input
                            type="checkbox"
                            checked={selectedPerms.has(p.id)}
                            onChange={() => togglePerm(p.id)}
                            className="rounded text-blue-600"
                          />
                          <span className="text-sm text-gray-700 group-hover:text-gray-900">{p.code}</span>
                          {p.description && (
                            <span className="text-xs text-gray-400 hidden group-hover:inline">{p.description}</span>
                          )}
                        </label>
                      ))}
                    </div>
                  ))}
                </div>
                <div className="flex gap-2 justify-end">
                  <button
                    onClick={() => setPermsPanelId(null)}
                    className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-white"
                  >
                    Cancelar
                  </button>
                  <button
                    onClick={() => handleSavePerms(role.id)}
                    className="flex items-center gap-1 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  >
                    <Check size={14} /> Guardar permisos
                  </button>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
