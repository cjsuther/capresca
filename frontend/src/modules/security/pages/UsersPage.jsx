import { Fragment, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  searchUsers, createUser, updateUser, deleteUser, getRoles, assignRoles, adminChangePassword, getGroups, assignUserGroups,
} from "../../../api/security";
import { Card, Field, LimpiarFiltros, Toolbar } from "../../../components/ui";
import { useHasPermission } from "../../../context/usePermissions";
import { PermissionGate } from "../../../components/PrivateRoute";
import { ChangePasswordModal } from "../../../components/ChangePasswordModal";
import { Confirmacion } from "../../../components/ui/Confirmacion";
import { resetear2fa } from "../../../api/dobleFactor";
import { useAuthStore } from "../../../context/authStore";
import {
  Plus, Pencil, Trash2, UserCheck, UserX,
  ShieldCheck, ShieldOff, Check, X, ChevronDown, ChevronUp, KeyRound,
  Search, ChevronLeft, ChevronRight, ArrowUp, ArrowDown, ArrowUpDown,
} from "lucide-react";

// ── Filtros, orden y página viven en la URL (?q=&rol=&grupo=&estado=&mfa=&orden=&dir=&pagina=&tam=)
// para poder compartir el link y que sobrevivan al refresh. Lo que vale el default no se escribe.
export const TAMANIOS = [25, 50, 100];
const ORDENES = ["nombre", "username", "email", "estado"];
const DEFAULTS = { q: "", rol: "", grupo: "", estado: "", mfa: "", orden: "nombre", dir: "asc", pagina: 1, tam: 25 };
const FILTROS = ["q", "rol", "grupo", "estado", "mfa"];
const DEBOUNCE_MS = 300;

const positivo = (v, def) => {
  const n = Number.parseInt(v, 10);
  return Number.isFinite(n) && n > 0 ? n : def;
};
const entre = (v, validos, def) => (validos.includes(v) ? v : def);
const id = (v) => { const n = positivo(v, 0); return n ? String(n) : ""; };

/** Lee la URL y descarta valores inválidos (un link editado a mano no rompe la pantalla). */
export function leerFiltros(sp) {
  const tam = positivo(sp.get("tam"), DEFAULTS.tam);
  return {
    q: (sp.get("q") || "").trim(),
    rol: id(sp.get("rol")),
    grupo: id(sp.get("grupo")),
    estado: entre(sp.get("estado"), ["activo", "inactivo"], ""),
    mfa: entre(sp.get("mfa"), ["si", "no"], ""),
    orden: entre(sp.get("orden"), ORDENES, DEFAULTS.orden),
    dir: sp.get("dir") === "desc" ? "desc" : "asc",
    pagina: positivo(sp.get("pagina"), DEFAULTS.pagina),
    tam: TAMANIOS.includes(tam) ? tam : DEFAULTS.tam,
  };
}

const num = (n) => Number(n || 0).toLocaleString("es-AR");

/** Encabezado de columna que ordena el listado; un segundo clic invierte el sentido. */
function ColOrden({ campo, filtros, onOrdenar, children }) {
  const activo = filtros.orden === campo;
  const Icono = !activo ? ArrowUpDown : filtros.dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <th className="text-left px-4 py-3 font-medium"
        aria-sort={activo ? (filtros.dir === "asc" ? "ascending" : "descending") : "none"}>
      <button type="button" onClick={() => onOrdenar(campo)}
              className={`inline-flex items-center gap-1 hover:text-gray-900 ${activo ? "text-gray-900" : ""}`}>
        {children}
        <Icono size={12} className={activo ? "" : "text-gray-300"} />
      </button>
    </th>
  );
}

/** Roles que el usuario recibe por sus grupos activos y no tiene asignados directamente. */
function heredados(user) {
  const propios = new Set(user.roles.map((r) => r.id));
  const por = new Map();
  for (const g of user.groups || []) {
    if (!g.is_active) continue;
    for (const r of g.roles || []) {
      if (propios.has(r.id)) continue;
      if (!por.has(r.id)) por.set(r.id, { rol: r, grupos: [] });
      por.get(r.id).grupos.push(g.name);
    }
  }
  return [...por.values()];
}

export default function UsersPage() {
  const [data, setData] = useState({ items: [], total: 0, pages: 1 });
  const [searchParams, setSearchParams] = useSearchParams();
  const filtros = leerFiltros(searchParams);
  const [texto, setTexto] = useState(filtros.q);   // lo tipeado; llega a la URL con debounce
  const [recarga, setRecarga] = useState(0);
  const [allRoles, setAllRoles] = useState([]);
  const [allGroups, setAllGroups] = useState([]);
  const verGrupos = useHasPermission("security", "groups:read");
  const editarGrupos = useHasPermission("security", "groups:write");
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
  const [selectedGroups, setSelectedGroups] = useState(new Set());

  // Modal cambio de contraseña por admin
  const [passwordTarget, setPasswordTarget] = useState(null); // { id, username }

  // Doble factor: marca en la lista y reset por un administrador
  const mfaHabilitado = useAuthStore((s) => s.mfa?.habilitado);
  const [reset2faTarget, setReset2faTarget] = useState(null);
  const [reseteando, setReseteando] = useState(false);

  /** Cambia filtros/orden/página en la URL. Todo cambio que no sea de página vuelve a la primera. */
  const actualizar = (cambios, { replace = false } = {}) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      for (const [k, v] of Object.entries(cambios)) {
        if (v === "" || v === null || v === undefined || String(v) === String(DEFAULTS[k])) next.delete(k);
        else next.set(k, String(v));
      }
      if (!("pagina" in cambios)) next.delete("pagina");
      return next;
    }, { replace });
  };

  const hayFiltros = FILTROS.some((k) => filtros[k] !== "");
  const limpiarFiltros = () => {
    setTexto("");
    actualizar({ q: "", rol: "", grupo: "", estado: "", mfa: "" });
  };

  const ordenar = (campo) =>
    actualizar({ orden: campo, dir: filtros.orden === campo && filtros.dir === "asc" ? "desc" : "asc" });

  // Búsqueda con debounce: se escribe en la URL (sin apilar historial) cuando se deja de tipear.
  useEffect(() => {
    if (texto.trim() === filtros.q) return undefined;
    const t = setTimeout(() => actualizar({ q: texto.trim() }, { replace: true }), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [texto]); // eslint-disable-line react-hooks/exhaustive-deps

  // Si la URL cambia por fuera (atrás/adelante, limpiar), el cuadro de búsqueda la sigue.
  useEffect(() => {
    if (texto.trim() !== filtros.q) setTexto(filtros.q);
  }, [filtros.q]); // eslint-disable-line react-hooks/exhaustive-deps

  // Catálogos para los selects y el panel de roles: una sola vez.
  useEffect(() => {
    Promise.all([getRoles(), verGrupos ? getGroups() : Promise.resolve([])])
      .then(([r, g]) => { setAllRoles(r); setAllGroups(g); })
      .catch(() => setError("Error al cargar datos"));
  }, [verGrupos]);

  // La página de usuarios: cada vez que cambian filtros, orden o página (o tras un alta/edición).
  const clave = JSON.stringify(filtros);
  useEffect(() => {
    let vigente = true;
    setLoading(true);
    searchUsers({
      q: filtros.q,
      role_id: filtros.rol,
      group_id: verGrupos ? filtros.grupo : "",
      estado: filtros.estado,
      mfa: filtros.mfa === "" ? "" : filtros.mfa === "si",
      sort: filtros.orden,
      order: filtros.dir,
      page: filtros.pagina,
      page_size: filtros.tam,
    })
      .then((d) => { if (vigente) setData(d); })
      .catch(() => { if (vigente) setError("Error al cargar datos"); })
      .finally(() => { if (vigente) setLoading(false); });
    return () => { vigente = false; };   // una respuesta vieja no pisa la de los filtros nuevos
  }, [clave, recarga]); // eslint-disable-line react-hooks/exhaustive-deps

  // Página fuera de rango (link viejo, o se dio de baja el último de la última página): ir a la última.
  useEffect(() => {
    if (!loading && data.items.length === 0 && data.total > 0 && filtros.pagina > data.pages) {
      actualizar({ pagina: data.pages }, { replace: true });
    }
  }, [loading, data]); // eslint-disable-line react-hooks/exhaustive-deps

  const load = () => setRecarga((n) => n + 1);

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

  // ── Reset del doble factor ───────────────────────────────────
  const handleReset2fa = async () => {
    setError("");
    setReseteando(true);
    try {
      await resetear2fa(reset2faTarget.id);
      setReset2faTarget(null);
      load();
    } catch (err) {
      setReset2faTarget(null);
      setError(err.response?.data?.detail || "No se pudo resetear el doble factor");
    } finally {
      setReseteando(false);
    }
  };

  // ── Panel de roles ───────────────────────────────────────────
  const openRolesPanel = (user) => {
    if (rolesPanelId === user.id) { setRolesPanelId(null); return; }
    setRolesPanelId(user.id);
    setSelectedRoles(new Set(user.roles.map((r) => r.id)));
    setSelectedGroups(new Set((user.groups || []).map((g) => g.id)));
    setEditingId(null);
  };

  const toggleRole = (roleId) => {
    setSelectedRoles((prev) => {
      const next = new Set(prev);
      next.has(roleId) ? next.delete(roleId) : next.add(roleId);
      return next;
    });
  };

  const toggleGroup = (groupId) => {
    setSelectedGroups((prev) => {
      const next = new Set(prev);
      next.has(groupId) ? next.delete(groupId) : next.add(groupId);
      return next;
    });
  };

  const handleSaveRoles = async (userId) => {
    setError("");
    try {
      await assignRoles(userId, [...selectedRoles]);
      if (editarGrupos) await assignUserGroups(userId, [...selectedGroups]);
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
        <form onSubmit={handleCreate} className="bg-surface border rounded-xl p-5 mb-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
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

      {/* Tabla de usuarios con su barra de filtros */}
      <Card padding={false}>
        <Toolbar>
          <Field label="Buscar" className="flex-1 min-w-[220px]">
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input type="search" className="input w-full pl-9" placeholder="Nombre, usuario o email"
                     aria-label="Buscar usuarios" value={texto} onChange={(e) => setTexto(e.target.value)} />
            </div>
          </Field>
          <Field label="Rol">
            <select className="input" aria-label="Filtrar por rol" value={filtros.rol}
                    onChange={(e) => actualizar({ rol: e.target.value })}>
              <option value="">Todos</option>
              {allRoles.map((r) => <option key={r.id} value={String(r.id)}>{r.name}</option>)}
            </select>
          </Field>
          {verGrupos && (
            <Field label="Grupo">
              <select className="input" aria-label="Filtrar por grupo" value={filtros.grupo}
                      onChange={(e) => actualizar({ grupo: e.target.value })}>
                <option value="">Todos</option>
                {allGroups.map((g) => <option key={g.id} value={String(g.id)}>{g.name}</option>)}
              </select>
            </Field>
          )}
          <Field label="Estado">
            <select className="input" aria-label="Filtrar por estado" value={filtros.estado}
                    onChange={(e) => actualizar({ estado: e.target.value })}>
              <option value="">Todos</option>
              <option value="activo">Activos</option>
              <option value="inactivo">Inactivos</option>
            </select>
          </Field>
          {mfaHabilitado && (
            <Field label="Doble factor">
              <select className="input" aria-label="Filtrar por doble factor" value={filtros.mfa}
                      onChange={(e) => actualizar({ mfa: e.target.value })}>
                <option value="">Todos</option>
                <option value="si">Con 2FA</option>
                <option value="no">Sin 2FA</option>
              </select>
            </Field>
          )}
          <LimpiarFiltros activo={hayFiltros || texto.trim() !== ""} onClear={limpiarFiltros} />
        </Toolbar>

      <div className="overflow-x-auto">
        <table className="w-full text-sm min-w-[700px]">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <ColOrden campo="username" filtros={filtros} onOrdenar={ordenar}>Usuario</ColOrden>
              <ColOrden campo="email" filtros={filtros} onOrdenar={ordenar}>Email</ColOrden>
              <ColOrden campo="nombre" filtros={filtros} onOrdenar={ordenar}>Nombre</ColOrden>
              <ColOrden campo="estado" filtros={filtros} onOrdenar={ordenar}>Estado</ColOrden>
              <th className="text-left px-4 py-3 font-medium">Roles</th>
              <th className="text-left px-4 py-3 font-medium">Grupos</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Cargando...</td></tr>
            ) : data.items.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-10 text-center text-gray-400">
                {hayFiltros ? (
                  <>
                    <p>Ningún usuario coincide con los filtros.</p>
                    <button type="button" onClick={limpiarFiltros}
                            className="mt-2 text-sm text-blue-600 hover:underline">Limpiar filtros</button>
                  </>
                ) : "Todavía no hay usuarios."}
              </td></tr>
            ) : data.items.map((user) => (
              <Fragment key={user.id}>
                {/* Fila principal */}
                <tr className={editingId === user.id || rolesPanelId === user.id ? "bg-blue-50" : "hover:bg-gray-50"}>

                  <td className="px-4 py-3 font-medium">
                    {user.username}
                    {mfaHabilitado && user.totp_activo && (
                      <span title="Doble factor activo"
                            className="ml-2 inline-flex items-center gap-0.5 text-xs text-green-700 bg-green-50 px-1.5 py-0.5 rounded">
                        <ShieldCheck size={11} /> 2FA
                      </span>
                    )}
                  </td>

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
                    {user.roles.length > 0 || heredados(user).length > 0
                      ? <>
                        {user.roles.map((r) => (
                          <span key={r.id} className="inline-block bg-purple-50 text-purple-700 text-xs px-2 py-0.5 rounded mr-1">{r.name}</span>
                        ))}
                        {heredados(user).map(({ rol, grupos }) => (
                          <span key={`h-${rol.id}`} title={`Heredado de: ${grupos.join(", ")}`}
                                className="inline-block border border-dashed border-purple-300 text-purple-600 text-xs px-2 py-0.5 rounded mr-1">
                            {rol.name}
                          </span>
                        ))}
                      </>
                      : <span className="text-gray-300">—</span>
                    }
                  </td>

                  <td className="px-4 py-3 text-gray-500">
                    {(user.groups || []).length > 0
                      ? user.groups.map((g) => (
                        <span key={g.id} className={`inline-block text-xs px-2 py-0.5 rounded mr-1 ${
                          g.is_active ? "bg-blue-50 text-blue-700" : "bg-gray-100 text-gray-400 line-through"}`}>{g.name}</span>
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
                            {mfaHabilitado && user.totp_activo && (
                              <button
                                onClick={() => setReset2faTarget(user)}
                                title="Resetear doble factor"
                                aria-label={`Resetear doble factor de ${user.username}`}
                                className="p-1.5 text-gray-400 hover:text-orange-600 hover:bg-orange-50 rounded-lg"
                              >
                                <ShieldOff size={15} />
                              </button>
                            )}
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
                    <td colSpan={7} className="px-4 pb-4 bg-purple-50 border-b">
                      <div className="pt-3">
                        <p className="text-sm font-medium text-gray-700 mb-3">Asignar roles a <strong>{user.username}</strong></p>
                        <div className="flex flex-wrap gap-3 mb-4">
                          {allRoles.map((role) => (
                            <label key={role.id} className="flex items-center gap-2 cursor-pointer bg-surface border rounded-lg px-3 py-2 hover:border-purple-400 transition-colors">
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
                        {editarGrupos && (
                          <>
                            <p className="text-sm font-medium text-gray-700 mb-3">
                              Grupos <span className="font-normal text-gray-500">(hereda los roles de cada grupo activo)</span>
                            </p>
                            <div className="flex flex-wrap gap-3 mb-4">
                              {allGroups.length === 0 && <span className="text-sm text-gray-400">No hay grupos creados</span>}
                              {allGroups.map((group) => (
                                <label key={group.id} className="flex items-center gap-2 cursor-pointer bg-surface border rounded-lg px-3 py-2 hover:border-blue-400 transition-colors">
                                  <input
                                    type="checkbox"
                                    checked={selectedGroups.has(group.id)}
                                    onChange={() => toggleGroup(group.id)}
                                    className="rounded text-blue-600"
                                    aria-label={`Grupo ${group.name}`}
                                  />
                                  <div>
                                    <span className="text-sm font-medium text-gray-800">{group.name}</span>
                                    <p className="text-xs text-gray-400">
                                      {group.roles.length ? group.roles.map((r) => r.name).join(", ") : "sin roles"}
                                      {!group.is_active && " · inactivo"}
                                    </p>
                                  </div>
                                </label>
                              ))}
                            </div>
                          </>
                        )}
                        <div className="flex gap-2 justify-end">
                          <button onClick={() => setRolesPanelId(null)} className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-surface">
                            Cancelar
                          </button>
                          <button onClick={() => handleSaveRoles(user.id)} className="flex items-center gap-1 px-4 py-2 text-sm bg-purple-600 text-white rounded-lg hover:bg-purple-700">
                            <Check size={14} /> {editarGrupos ? "Guardar roles y grupos" : "Guardar roles"}
                          </button>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      </Card>

      {/* Paginador */}
      <div className="flex flex-wrap items-center justify-between gap-3 mt-4">
        <p className="text-sm text-gray-500 tabular-nums" aria-live="polite">
          {data.total === 0
            ? "Sin resultados"
            : `${num((filtros.pagina - 1) * filtros.tam + 1)}–${num(Math.min(filtros.pagina * filtros.tam, data.total))} de ${num(data.total)} usuarios`}
        </p>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-gray-500">
            Por página
            <select className="input py-1" value={filtros.tam} aria-label="Usuarios por página"
                    onChange={(e) => actualizar({ tam: Number(e.target.value) })}>
              {TAMANIOS.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <div className="flex items-center gap-1">
            <button type="button" aria-label="Página anterior" disabled={filtros.pagina <= 1 || loading}
                    onClick={() => actualizar({ pagina: filtros.pagina - 1 })}
                    className="p-2 rounded-lg border border-gray-300 text-gray-600 enabled:hover:bg-gray-50 disabled:opacity-40">
              <ChevronLeft size={16} />
            </button>
            <span className="text-sm text-gray-600 tabular-nums px-2">
              {num(filtros.pagina)} de {num(data.pages || 1)}
            </span>
            <button type="button" aria-label="Página siguiente" disabled={filtros.pagina >= (data.pages || 1) || loading}
                    onClick={() => actualizar({ pagina: filtros.pagina + 1 })}
                    className="p-2 rounded-lg border border-gray-300 text-gray-600 enabled:hover:bg-gray-50 disabled:opacity-40">
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
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

      {/* Reset del doble factor (queda en Auditoría) */}
      {reset2faTarget && (
        <Confirmacion
          titulo={`Resetear el doble factor de ${reset2faTarget.username}`}
          mensaje={"Se borran su app autenticadora y sus códigos de recuperación, y se le levanta el bloqueo.\n" +
                   "Hacelo sólo después de verificar su identidad por otro medio. En el próximo ingreso se vuelve a enrolar."}
          confirmar="Resetear"
          ocupado={reseteando}
          onConfirmar={handleReset2fa}
          onCancelar={() => setReset2faTarget(null)}
        />
      )}
    </div>
  );
}
