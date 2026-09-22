# Rediseño IAM — Usuario → Grupo → Rol → Permiso (con grants directos y vigencia)

## Modelo objetivo
```
Usuario ──┬─(directo)────────────────────────► Permiso        (usuario_permiso)
          ├─(directo)──────────────► Rol ──────► Permiso        (usuario_rol / rol_permiso)
          └─► Grupo ──► Rol ────────────────────► Permiso        (usuario_grupo / grupo_rol / rol_permiso)
```
- **Permiso** = (pantalla/ruta, nivel) con nivel ∈ {CONSULTA, ESCRITURA, TOTAL}. Es la capacidad atómica.
- **Rol** = bundle nombrado de permisos (p.ej. "Cajero", "Supervisor Créditos").
- **Grupo** = bundle de roles (p.ej. "Sucursal Centro", "Área Créditos").
- Un **Usuario** puede recibir acceso por CUALQUIER vía a la vez: grupos, roles directos y permisos directos.

## Lo que ya existe = subconjunto (migración aditiva, no reescribir)
| Hoy | En el modelo nuevo |
|---|---|
| `perfiles` (maeperfil) | **Rol** (catálogo de roles) |
| `perfil_permiso` | **rol_permiso** |
| `usuario_perfil` (multi-perfil) | **usuario_rol** (roles directos) |
| `usuarios.perfil` (principal) | rol principal — se conserva para **JWT y workflow** |

**Tablas nuevas:** `grupo`, `grupo_rol`, `usuario_grupo`, `usuario_permiso`.

## Vigencia temporal (enfermedad / vacaciones)
Cada asignación **a nivel de usuario** lleva `vigente_desde` y `vigente_hasta` (ambos nullable):
- `usuario_grupo(usuario, grupo, desde, hasta)`
- `usuario_rol(usuario, rol, desde, hasta)`
- `usuario_permiso(usuario, ruta, nivel, desde, hasta)`

`hasta = null` → **sin vencimiento**. Una fila está **vigente** si `desde ≤ hoy ≤ hasta` (con nulls = abierto).
Ejemplo: cubrir a alguien de vacaciones = darle un rol/grupo con `hasta` = fin de la licencia; se apaga solo.
(Las relaciones estructurales `grupo_rol` y `rol_permiso` quedan permanentes; la vigencia es de la persona.)

## Resolución del acceso efectivo (allow-only, unión, máximo)
Para un usuario en la fecha `hoy`:
1. **Roles** = `usuario_rol` vigentes  ∪  roles de los `usuario_grupo` vigentes (vía `grupo_rol`).
2. **Permisos** = `rol_permiso` de esos roles  ∪  `usuario_permiso` directos vigentes.
3. **Nivel efectivo por pantalla** = **MAX** entre todas las fuentes (el acceso más alto gana).
4. **Admin**: se mantiene el bypass ADMG (rol/grupo administrador = acceso total).
5. **Legacy safe**: usuario sin ninguna asignación configurada = sin restricciones (como hoy).

Es **aditivo** (allow-only): no hay "deny". Cubrir/quitar accesos = agregar/vencer asignaciones.

## Enforcement (ya montado, sólo cambia la fuente)
- `nivel_efectivo(user, ruta)` pasa a resolver todo el grafo con la regla de arriba (hoy resuelve sólo roles).
- El front (menú/rutas/botones) y el guard de backend `requiere_permiso` **no cambian** — consumen el nivel efectivo.

## Pantallas (Seguridad)
- **Roles** (hoy "Perfiles"): permisos por pantalla del rol (ya está) + qué usuarios lo tienen.
- **Grupos** (nueva): roles que agrupa + usuarios miembros (con vigencia).
- **Usuarios** (editor): grupos, roles directos y permisos directos del usuario, **cada uno con vigencia opcional**;
  vista de "acceso efectivo resultante" (read-only) para ver el resultado de la unión.

## Fases sugeridas
1. **Modelo + resolución**: tablas nuevas + `nivel_efectivo` resolviendo el grafo (compatible hacia atrás).
2. **Grupos**: ABM de grupos + asignación grupo↔rol y usuario↔grupo.
3. **Vigencia**: columnas desde/hasta en las asignaciones de usuario + filtrado por fecha + "vence el…".
4. **Permisos directos** al usuario + pantalla de "acceso efectivo".
5. **Nomenclatura**: renombrar "Perfiles" → "Roles" en el menú (o mantener el alias).

## Decisiones abiertas
- ¿Renombramos "Perfiles" → "Roles" o mantenemos "Perfiles" como sinónimo de Rol?
- ¿La vigencia va sólo en las asignaciones de usuario (recomendado) o también en grupo_rol/rol_permiso?
- ¿El workflow/cuatro-ojos sigue usando el rol **principal**, o la unión de roles del usuario?
