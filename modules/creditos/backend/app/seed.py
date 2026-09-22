"""Datos de demostración para desarrollo (usuarios, organismos, líneas, clientes).

En producción los datos vienen del ETL desde los DBF (fase 3). Esto sólo permite
levantar el sistema y probar el simulador sin el backup real.
"""
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app import models

# Catálogo de ROLES (perfiles) del control de acceso. Sin él, la pantalla Seguridad → Roles queda vacía
# y los roles asignados a los usuarios (ADMG/XCR/XCJ…) no tienen su ficha en el maestro (H-142).
# Códigos = los que usan realmente los usuarios y el motor de workflow (X-prefijo operativo).
PERFILES_SEED = {
    "ADMG": "Administrador general",
    "XCR": "Créditos",
    "XCJ": "Caja / Tesorería",
    "XCA": "Contabilidad",
    "XTE": "Tesorería",
    "XSE": "Seguros",
    "XDE": "Despacho",
    "XME": "Mesa de entradas",
    # Roles del circuito de créditos con separación de funciones clara (H-150):
    "OPER": "Operador de créditos (diseña/carga)",
    "SUPE": "Supervisor de créditos (aprueba)",
}

# Grupos = bundles de roles, para armar el cuatro-ojos "con roles y grupos" (H-150). Sumar un usuario al
# grupo Supervisión le da el rol aprobador (SUPE) sin overrides puntuales; el grupo Operativa da OPER.
GRUPOS_SEED = {
    "GCRED-OP": ("Créditos — Operativa", ["OPER"]),      # diseñan/cargan y envían a revisión
    "GCRED-SUP": ("Créditos — Supervisión", ["SUPE"]),   # aprueban/publican (cierran el cuatro-ojos)
}


def seed_perfiles(db: Session) -> None:
    """Siembra el maestro de roles y los grupos del circuito de créditos (idempotente): agrega lo que
    falte sin tocar lo existente."""
    existentes = {c for (c,) in db.query(models.Perfil.codigo).all()}
    nuevos = [models.Perfil(codigo=c, denominacion=d, habilitado=True)
              for c, d in PERFILES_SEED.items() if c not in existentes]
    if nuevos:
        db.add_all(nuevos)
    grupos_ex = {c for (c,) in db.query(models.Grupo.codigo).all()}
    for cod, (nombre, roles) in GRUPOS_SEED.items():
        if cod in grupos_ex:
            continue
        db.add(models.Grupo(codigo=cod, nombre=nombre, activo=True))
        db.add_all([models.GrupoRol(grupo_codigo=cod, rol_codigo=r) for r in roles])
    db.commit()


def seed(db: Session) -> None:
    if db.query(models.Usuario).first():
        return  # ya sembrado

    db.add_all([
        models.Usuario(username="admin", nombre="Administrador",
                       password_hash=hash_password("admin123"), perfil="ADMG"),
        models.Usuario(username="creditos", nombre="Operador Créditos",
                       password_hash=hash_password("cred123"), perfil="XCR"),
        models.Usuario(username="caja", nombre="Cajero",
                       password_hash=hash_password("caja123"), perfil="XCJ"),
    ])

    org = models.Organismo(codigo="MIN-SALUD", nombre="Ministerio de Salud")
    cia = models.CompaniaSeguros(nombre="La Previsora Seguros", cuit="30500001234")
    db.add_all([org, cia])
    db.flush()

    db.add_all([
        models.LineaCredito(nombre="Personales (Francés)", cartera=1, tipo_calculo=1,
                            tna=Decimal("48"), por_afecta=Decimal("30"),
                            tasa_mora_diaria=Decimal("0.1"),
                            seguro_pct=Decimal("0.05"),  # 0,05% del saldo por cuota
                            compania_seguros_id=cia.id,
                            plazo_max=36, monto_max=Decimal("2000000")),
        models.LineaCredito(nombre="Personales AGJS (Alemán)", cartera=4, tipo_calculo=2,
                            tna=Decimal("42"), por_afecta=Decimal("30"),
                            plazo_max=48, monto_max=Decimal("3000000")),
        models.LineaCredito(nombre="Sismo (Directo)", cartera=5, tipo_calculo=3,
                            tna=Decimal("24"), por_afecta=Decimal("25"),
                            plazo_max=24, monto_max=Decimal("1000000")),
        models.LineaCredito(nombre="Deuda Salarial (Cuota fija s/interés)", cartera=17,
                            tipo_calculo=5, tna=Decimal("0"), por_afecta=Decimal("30"),
                            plazo_max=60, monto_max=Decimal("5000000")),
    ])

    # Espejo del padrón: el id es el del módulo Clientes (acá, datos de demo con ids fijos).
    from app.core.codigos import codigo_cliente
    _clientes = [
        models.Cliente(
            id=1, id_cliente=codigo_cliente(1), cuil="20123456786", dni="12345678",
            apellido_nombre="PEREZ, JUAN CARLOS", sueldo=Decimal("650000"),
            cbu="0110466420046600526713", organismo_id=org.id),
        models.Cliente(
            id=2, id_cliente=codigo_cliente(2), cuil="27234567818", dni="23456781",
            apellido_nombre="GOMEZ, MARIA LAURA", sueldo=Decimal("820000"),
            cbu="0110466420046600520531", organismo_id=org.id),
    ]
    db.add_all(_clientes); db.flush()

    db.add_all([
        models.TipoTramite(nombre="Solicitud de crédito", prefijo="CR"),
        models.TipoTramite(nombre="Pago de cuota", prefijo="PG"),
        models.TipoTramite(nombre="Trámite de seguros", prefijo="SG"),
        models.TipoTramite(nombre="Consulta / Otros", prefijo="CO"),
    ])

    db.add_all([
        models.RegimenEspecial(nombre="Renta Vitalicia Héroes de Malvinas",
                               tipo="P", monto_default=Decimal("150000")),
        models.RegimenEspecial(nombre="Excombatientes de Malvinas",
                               tipo="P", monto_default=Decimal("90000")),
        models.RegimenEspecial(nombre="Subsidio de Protección a la Familia",
                               tipo="P", monto_default=Decimal("45000")),
    ])

    from app.services.contabilidad import seed_plan_cuentas
    seed_plan_cuentas(db)
    db.commit()


def seed_config(db: Session) -> None:
    """Siembra sólo tablas de CONFIGURACIÓN (sin datos demo), para usar junto al
    ETL de datos reales: tipos de trámite, regímenes especiales, plan de cuentas."""
    from app.services.contabilidad import seed_plan_cuentas

    if not db.query(models.TipoTramite).first():
        db.add_all([
            models.TipoTramite(nombre="Solicitud de crédito", prefijo="CR"),
            models.TipoTramite(nombre="Pago de cuota", prefijo="PG"),
            models.TipoTramite(nombre="Trámite de seguros", prefijo="SG"),
            models.TipoTramite(nombre="Consulta / Otros", prefijo="CO"),
        ])
    if not db.query(models.RegimenEspecial).first():
        db.add_all([
            models.RegimenEspecial(nombre="Renta Vitalicia Héroes de Malvinas (Ley 5182)",
                                   tipo="P", monto_default=Decimal("150000")),
            models.RegimenEspecial(nombre="Excombatientes de Malvinas",
                                   tipo="P", monto_default=Decimal("90000")),
            models.RegimenEspecial(nombre="Subsidio de Protección a la Familia",
                                   tipo="P", monto_default=Decimal("45000")),
        ])
    seed_plan_cuentas(db)
    db.commit()

    from app.seed_productos import seed_productos
    seed_productos(db)
