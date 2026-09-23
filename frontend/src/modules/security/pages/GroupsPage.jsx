import { useEffect, useMemo, useState } from "react";
import { Plus, Pencil, Trash2 } from "lucide-react";
import {
  getGroups, createGroup, updateGroup, deleteGroup, assignGroupRoles, assignGroupMembers, getRoles, getUsers,
} from "../../../api/security";
import { PermissionGate } from "../../../components/PrivateRoute";
import { useHasPermission } from "../../../context/usePermissions";
import { Alerta, Boton, Card, Field, LimpiarFiltros, Modal, PageHeader, Toolbar } from "../../../components/ui";
import { DataTable } from "../../../components/ui/DataTable";
import { Pill } from "../../../components/ui/Pill";
import { Confirmacion } from "../../../components/ui/Confirmacion";

const VACIO = { name: "", description: "", is_active: true, role_ids: [], user_ids: [] };

/** Lista de casillas con buscador, para elegir roles o integrantes. */
function Seleccion({ titulo, items, elegidos, onChange, etiqueta, detalle, buscar = false }) {
  const [q, setQ] = useState("");
  const visibles = items.filter((i) => !q || `${etiqueta(i)} ${detalle?.(i) || ""}`.toLowerCase().includes(q.toLowerCase()));
  const alternar = (id) => onChange(elegidos.includes(id) ? elegidos.filter((x) => x !== id) : [...elegidos, id]);
  return (
    <fieldset className="border border-gray-200 rounded-lg">
      <legend className="px-1 ml-2 text-xs font-medium text-gray-500">{titulo} ({elegidos.length})</legend>
      {buscar && (
        <div className="px-3 pt-2">
          <input className="input w-full text-sm" placeholder="Buscar…" value={q} onChange={(e) => setQ(e.target.value)}
                 aria-label={`Buscar ${titulo.toLowerCase()}`} />
        </div>
      )}
      <div className="max-h-56 overflow-y-auto p-2 grid sm:grid-cols-2 gap-1">
        {visibles.map((i) => (
          <label key={i.id} className="flex items-start gap-2 px-2 py-1.5 rounded hover:bg-gray-50 cursor-pointer">
            <input type="checkbox" className="mt-0.5" checked={elegidos.includes(i.id)} onChange={() => alternar(i.id)} />
            <span className="text-sm text-gray-700">
              {etiqueta(i)}
              {detalle?.(i) && <span className="block text-xs text-gray-400">{detalle(i)}</span>}
            </span>
          </label>
        ))}
        {!visibles.length && <p className="text-sm text-gray-400 px-2 py-1">Sin resultados</p>}
      </div>
    </fieldset>
  );
}

export default function GroupsPage() {
  const puedeEditar = useHasPermission("security", "groups:write");
  const [grupos, setGrupos] = useState([]);
  const [roles, setRoles] = useState([]);
  const [usuarios, setUsuarios] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [filtro, setFiltro] = useState("");
  const [form, setForm] = useState(null);          // null | { id?, ...VACIO }
  const [guardando, setGuardando] = useState(false);
  const [aBorrar, setABorrar] = useState(null);

  const cargar = () => {
    setCargando(true);
    Promise.all([getGroups(), getRoles(), getUsers(1, 500)])
      .then(([g, r, u]) => { setGrupos(g); setRoles(r); setUsuarios(u.data); })
      .catch(() => setError("Error al cargar los grupos"))
      .finally(() => setCargando(false));
  };
  useEffect(cargar, []);

  const filas = useMemo(() => {
    const q = filtro.trim().toLowerCase();
    if (!q) return grupos;
    return grupos.filter((g) => [g.name, g.description, ...g.roles.map((r) => r.name), ...g.users.map((u) => u.username)]
      .some((t) => (t || "").toLowerCase().includes(q)));
  }, [grupos, filtro]);

  const abrir = (g) => {
    setError("");
    setForm(g ? { id: g.id, name: g.name, description: g.description || "", is_active: g.is_active,
                  role_ids: g.roles.map((r) => r.id), user_ids: g.users.map((u) => u.id) }
              : { ...VACIO });
  };

  const guardar = async (e) => {
    e.preventDefault();
    setGuardando(true);
    setError("");
    try {
      const datos = { name: form.name.trim(), description: form.description.trim() || null, is_active: form.is_active };
      const g = form.id ? await updateGroup(form.id, datos) : await createGroup(datos);
      await assignGroupRoles(g.id, form.role_ids);
      await assignGroupMembers(g.id, form.user_ids);
      setForm(null);
      cargar();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al guardar el grupo");
    } finally {
      setGuardando(false);
    }
  };

  const borrar = async () => {
    setGuardando(true);
    try {
      await deleteGroup(aBorrar.id);
      setABorrar(null);
      cargar();
    } catch (err) {
      setError(err.response?.data?.detail || "Error al eliminar el grupo");
      setABorrar(null);
    } finally {
      setGuardando(false);
    }
  };

  const columnas = [
    { key: "name", label: "Grupo", sortable: true, render: (g) => (
      <div>
        <p className="font-medium text-gray-800">{g.name}</p>
        {g.description && <p className="text-xs text-gray-400">{g.description}</p>}
      </div>
    ) },
    { key: "is_active", label: "Estado", render: (g) => (g.is_active ? <Pill tono="ok">Activo</Pill> : <Pill>Inactivo</Pill>) },
    { key: "roles", label: "Roles del grupo", render: (g) => (
      g.roles.length
        ? <div className="flex flex-wrap gap-1">{g.roles.map((r) => <Pill key={r.id} tono="brand">{r.name}</Pill>)}</div>
        : <span className="text-gray-300">—</span>
    ) },
    { key: "users", label: "Integrantes", align: "right", sortable: true, sortValue: (g) => g.users.length,
      render: (g) => (
        <span className="tabular-nums" title={g.users.map((u) => u.username).join(", ")}>{g.users.length}</span>
      ) },
    ...(puedeEditar ? [{ key: "acciones", label: "", align: "right", render: (g) => (
      <div className="flex justify-end gap-1">
        <button onClick={() => abrir(g)} title="Editar" aria-label={`Editar ${g.name}`}
                className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg"><Pencil size={15} /></button>
        <button onClick={() => setABorrar(g)} title="Eliminar" aria-label={`Eliminar ${g.name}`}
                className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg"><Trash2 size={15} /></button>
      </div>
    ) }] : []),
  ];

  return (
    <div>
      <PageHeader titulo="Grupos de usuarios"
                  descripcion="Asigná roles a un grupo y cada integrante los hereda, además de los roles propios de cada usuario.">
        <PermissionGate moduleCode="security" action="groups:write">
          <Boton onClick={() => abrir(null)} className="flex items-center gap-2"><Plus size={16} /> Nuevo grupo</Boton>
        </PermissionGate>
      </PageHeader>

      {error && !form && <div className="mb-4"><Alerta>{error}</Alerta></div>}

      <Card padding={false}>
        <Toolbar>
          <Field label="Buscar">
            <input className="input w-64" placeholder="Grupo, rol o usuario" value={filtro} onChange={(e) => setFiltro(e.target.value)} />
          </Field>
          <LimpiarFiltros activo={!!filtro} onClear={() => setFiltro("")} />
        </Toolbar>
        {cargando
          ? <p className="px-4 py-8 text-center text-gray-400 text-sm">Cargando...</p>
          : <DataTable columns={columnas} rows={filas} rowKey={(g) => g.id} clientSort defaultSort="name"
                       emptyText={filtro ? "Ningún grupo coincide con la búsqueda" : "Todavía no hay grupos"} />}
      </Card>

      {form && (
        <Modal titulo={form.id ? `Editar grupo ${form.name}` : "Nuevo grupo"} eyebrow="Seguridad" onClose={() => setForm(null)}
               footer={<>
                 <span className="text-xs text-gray-500 mr-auto">
                   {form.user_ids.length} integrante(s) heredan {form.role_ids.length} rol(es)
                 </span>
                 <Boton variante="secundario" type="button" onClick={() => setForm(null)}>Cancelar</Boton>
                 <Boton type="submit" form="form-grupo" disabled={guardando || form.name.trim().length < 2}>
                   {guardando ? "Guardando…" : "Guardar"}
                 </Boton>
               </>}>
          <form id="form-grupo" onSubmit={guardar} className="space-y-4">
            {error && <Alerta>{error}</Alerta>}
            <div className="grid sm:grid-cols-2 gap-3">
              <Field label="Nombre">
                <input className="input w-full" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
              </Field>
              <Field label="Descripción">
                <input className="input w-full" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
              </Field>
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-600">
              <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              Activo (si está inactivo, sus integrantes no heredan los roles)
            </label>
            <Seleccion titulo="Roles del grupo" items={roles} elegidos={form.role_ids}
                       onChange={(role_ids) => setForm({ ...form, role_ids })}
                       etiqueta={(r) => r.name} detalle={(r) => r.description} />
            <Seleccion titulo="Integrantes" items={usuarios} elegidos={form.user_ids} buscar
                       onChange={(user_ids) => setForm({ ...form, user_ids })}
                       etiqueta={(u) => u.username} detalle={(u) => [u.full_name, !u.is_active && "inactivo"].filter(Boolean).join(" · ")} />
          </form>
        </Modal>
      )}

      {aBorrar && (
        <Confirmacion titulo={`Eliminar el grupo ${aBorrar.name}`} confirmar="Eliminar" ocupado={guardando}
                      mensaje={`Sus ${aBorrar.users.length} integrante(s) dejan de heredar los roles del grupo.\nLos usuarios y los roles no se borran.`}
                      onConfirmar={borrar} onCancelar={() => setABorrar(null)} />
      )}
    </div>
  );
}
