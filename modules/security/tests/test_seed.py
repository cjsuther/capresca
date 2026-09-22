"""Seed de datos iniciales: módulos, permisos, roles y usuario admin."""
import pytest

from app import seed as seed_mod
from app.models.module import Module
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.services.auth_service import verify_password


@pytest.fixture
def correr_seed(db, monkeypatch):
    """Ejecuta el seed contra la sesión de test (usa SessionLocal directamente)."""

    def _correr():
        monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db)
        seed_mod.run()
        db.expire_all()

    return _correr


def test_seed_crea_todos_los_modulos(correr_seed, db):
    correr_seed()
    codigos = {m.code for m in db.query(Module).all()}
    assert codigos == {m["code"] for m in seed_mod.MODULES}
    assert all(m.is_active for m in db.query(Module).all())


def test_seed_crea_los_permisos_de_cada_modulo(correr_seed, db):
    correr_seed()
    esperados = {code for perms in seed_mod.PERMISSIONS.values() for code, _ in perms}
    assert {p.code for p in db.query(Permission).all()} == esperados


def test_seed_crea_los_permisos_de_creditos_por_area(correr_seed, db):
    correr_seed()
    creditos = db.query(Module).filter_by(code="creditos").one()
    codigos = {p.code for p in db.query(Permission).filter_by(module_id=creditos.id).all()}
    for area, _label in seed_mod.CREDITOS_AREAS:
        assert f"{area}:read" in codigos and f"{area}:write" in codigos
    assert "aprobaciones:aprobar" in codigos and "aprobaciones:supervisar" in codigos


def test_creditos_publica_una_sola_area(correr_seed, db):
    """Las áreas de CCyPP que no se migraron no tienen permisos: sólo `creditos:*` y las de aprobación."""
    correr_seed()
    creditos = db.query(Module).filter_by(code="creditos").one()
    codigos = {p.code for p in db.query(Permission).filter_by(module_id=creditos.id).all()}
    assert codigos == {"creditos:read", "creditos:write", "aprobaciones:aprobar", "aprobaciones:supervisar",
                       "heredadas:read"}


def test_el_seed_retira_los_permisos_de_areas_de_creditos_descartadas(correr_seed, db):
    """Una base sembrada antes de la poda tiene `caja:read`, `general:write`... asignados a roles y usuarios:
    el seed los borra (con sus asignaciones) y no toca los permisos vigentes."""
    from app.models.permission import UserPermission
    correr_seed()
    creditos = db.query(Module).filter_by(code="creditos").one()
    viejo = Permission(module_id=creditos.id, code="caja:write", description="Créditos · operar caja")
    db.add(viejo)
    db.flush()
    rol = Role(name="cajero-ccypp", description="rol con un permiso retirado")
    rol.permissions = [viejo, db.query(Permission).filter_by(module_id=creditos.id, code="creditos:read").one()]
    db.add(rol)
    admin = db.query(User).filter_by(username="admin").one()
    db.add(UserPermission(user_id=admin.id, permission_id=viejo.id, granted=True))
    db.commit()
    creditos_id, admin_id = creditos.id, admin.id   # el seed cierra la sesión y desprende las instancias

    correr_seed()

    assert db.query(Permission).filter_by(module_id=creditos_id, code="caja:write").first() is None
    assert db.query(UserPermission).filter_by(user_id=admin_id).count() == 0
    rol = db.query(Role).filter_by(name="cajero-ccypp").one()
    assert [p.code for p in rol.permissions] == ["creditos:read"]


def test_configuraciones_tiene_un_par_de_permisos_por_catalogo(correr_seed, db):
    correr_seed()
    mod = db.query(Module).filter_by(code="configuraciones").one()
    codigos = {p.code for p in db.query(Permission).filter_by(module_id=mod.id).all()}
    assert codigos == {f"{c}:{a}" for c in ("impuestos", "indices", "feriados", "workflow") for a in ("read", "write")}


def test_tesoreria_separa_armar_enviar_y_aprobar(correr_seed, db):
    correr_seed()
    mod = db.query(Module).filter_by(code="tesoreria").one()
    codigos = {p.code for p in db.query(Permission).filter_by(module_id=mod.id).all()}
    assert codigos == {"lotes:read", "lotes:write", "lotes:enviar", "aprobaciones:aprobar", "aprobaciones:supervisar"}


def test_seguridad_tiene_permisos_para_grupos(correr_seed, db):
    correr_seed()
    mod = db.query(Module).filter_by(code="security").one()
    codigos = {p.code for p in db.query(Permission).filter_by(module_id=mod.id).all()}
    assert {"groups:read", "groups:write"} <= codigos


def test_creditos_tiene_el_permiso_de_pantallas_heredadas_pero_admin_no_lo_recibe(correr_seed, db):
    """Las pantallas viejas quedan ocultas: el permiso existe para asignarlo a mano, no viene puesto."""
    correr_seed()
    mod = db.query(Module).filter_by(code="creditos").one()
    heredadas = db.query(Permission).filter_by(module_id=mod.id, code="heredadas:read").one()
    admin = db.query(Role).filter_by(name="admin").one()
    assert heredadas not in admin.permissions
    assert any(p.code == "creditos:read" for p in admin.permissions)      # el resto sí


def test_seed_crea_los_tres_roles(correr_seed, db):
    correr_seed()
    assert {r.name for r in db.query(Role).all()} == {"admin", "cajero", "supervisor"}


def test_el_rol_admin_recibe_todos_los_permisos(correr_seed, db):
    """Todos menos los que se dejan fuera a propósito (pantallas heredadas de Créditos)."""
    correr_seed()
    admin = db.query(Role).filter_by(name="admin").one()
    assert len(admin.permissions) == db.query(Permission).count() - len(seed_mod.FUERA_DEL_ADMIN)


def test_los_roles_operativos_reciben_su_subconjunto(correr_seed, db):
    correr_seed()
    cajero = db.query(Role).filter_by(name="cajero").one()
    supervisor = db.query(Role).filter_by(name="supervisor").one()
    assert {p.code for p in cajero.permissions} == {
        "transactions:read", "transactions:write", "transactions:delete", "clients:read"}
    assert {p.code for p in supervisor.permissions} == {
        "transactions:read", "transactions:read_all", "transactions:authorize",
        "rules:read", "rules:write", "clients:read"}


def test_el_usuario_admin_queda_operativo(correr_seed, db, client):
    correr_seed()
    admin = db.query(User).filter_by(username="admin").one()
    assert admin.is_active and verify_password("Admin1234!", admin.hashed_password)
    assert [r.name for r in admin.roles] == ["admin"]

    r = client.post("/api/auth/login", json={"username": "admin", "password": "Admin1234!"})
    assert r.status_code == 200
    assert set(r.json()["permissions"]["modules"]) == {m["code"] for m in seed_mod.MODULES}


def test_el_seed_es_idempotente(correr_seed, db):
    correr_seed()
    conteos = (db.query(Module).count(), db.query(Permission).count(),
               db.query(Role).count(), db.query(User).count())
    correr_seed()
    assert (db.query(Module).count(), db.query(Permission).count(),
            db.query(Role).count(), db.query(User).count()) == conteos
    admin = db.query(User).filter_by(username="admin").one()
    assert [r.name for r in admin.roles] == ["admin"]  # no duplica la asignación


def test_el_seed_agrega_permisos_nuevos_a_un_rol_admin_preexistente(correr_seed, db):
    """Rama de admin_role ya existente: suma los permisos que le faltan sin pisar los que tiene."""
    db.add(Role(name="admin", description="preexistente"))
    db.commit()

    correr_seed()
    admin = db.query(Role).filter_by(name="admin").one()
    assert admin.description == "preexistente"
    assert len(admin.permissions) == db.query(Permission).count() - len(seed_mod.FUERA_DEL_ADMIN)


def test_el_codigo_de_permiso_es_unico_por_modulo(correr_seed, db):
    """Cada módulo tiene su propio catálogo: un código ya usado por otro módulo no impide crearlo acá.

    Antes `permissions.code` era UNIQUE GLOBAL y el seed reusaba en silencio el permiso ajeno, con lo
    que el permiso quedaba colgado del módulo equivocado y el gateway resolvía mal el acceso.
    """
    ajeno = Module(code="modulo-ajeno", name="Ajeno", is_active=True)
    db.add(ajeno)
    db.flush()
    db.add(Permission(module_id=ajeno.id, code="users:read", description="mismo código, otro módulo"))
    db.commit()
    ajeno_id = ajeno.id  # el seed cierra la sesión y desprende las instancias

    correr_seed()

    con_ese_codigo = db.query(Permission).filter_by(code="users:read").all()
    assert len(con_ese_codigo) == 2                      # uno por módulo, sin pisarse
    security = db.query(Module).filter_by(code="security").one()
    modulos = {p.module_id for p in con_ese_codigo}
    assert modulos == {ajeno_id, security.id}


def test_el_seed_reusa_los_modulos_ya_existentes(correr_seed, db):
    db.add(Module(code="security", name="Seguridad renombrada", is_active=True))
    db.commit()

    correr_seed()
    modulos = db.query(Module).filter_by(code="security").all()
    assert len(modulos) == 1 and modulos[0].name == "Seguridad renombrada"


def test_el_seed_aborta_con_exit_1_ante_un_error(db, monkeypatch, capsys):
    """PERMISSIONS con un módulo que no está en MODULES: KeyError → rollback + sys.exit(1)."""
    monkeypatch.setattr(seed_mod, "SessionLocal", lambda: db)
    monkeypatch.setattr(seed_mod, "PERMISSIONS", {"inexistente": [("x:read", "x")]})

    with pytest.raises(SystemExit) as exc:
        seed_mod.run()
    assert exc.value.code == 1
    assert "[seed] Error" in capsys.readouterr().err

    db.expire_all()
    assert db.query(Permission).count() == 0
