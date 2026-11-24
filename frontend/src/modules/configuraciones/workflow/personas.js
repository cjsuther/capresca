import api from "../../../api/client";

/**
 * Grupos y usuarios de Seguridad para los selectores del editor. Si el usuario no tiene permiso de
 * lectura en Seguridad (o Seguridad no responde), vuelve vacío y el editor deja escribir el nombre a mano.
 */
export async function cargarPersonas() {
  const [grupos, usuarios] = await Promise.allSettled([
    api.get("/security/groups").then((r) => r.data),
    api.get("/security/users", { params: { page: 1, per_page: 500 } }).then((r) => r.data),
  ]);
  const listaGrupos = grupos.status === "fulfilled" && Array.isArray(grupos.value) ? grupos.value : [];
  const crudos = usuarios.status === "fulfilled" ? (usuarios.value?.data ?? usuarios.value) : [];
  return {
    grupos: listaGrupos.filter((g) => g?.name).map((g) => ({ id: g.id, name: g.name }))
      .sort((a, b) => a.name.localeCompare(b.name)),
    usuarios: (Array.isArray(crudos) ? crudos : []).map((u) => u?.username).filter(Boolean).sort(),
    deSeguridad: grupos.status === "fulfilled" || usuarios.status === "fulfilled",
  };
}
