"""Operaciones sensibles que exigen STEP-UP: volver a pedir el código del doble factor aunque la sesión
ya esté iniciada.

Sólo rige con `TOKENSERVER_ENABLED=true`. El permiso de la ruta (mapping.py) se controla antes y aparte:
el step-up se suma, no lo reemplaza.

Cómo se cumple: el frontend manda `X-2FA-Token` con un token de step-up que emite security
(POST /api/auth/2fa/step-up con el código). Vale unos minutos (TOKENSERVER_STEPUP_MINUTOS, 5 por
defecto) y SÓLO para la sesión con la que se pidió (claim `sid` = jti de la sesión): no hay que poner el
código en cada clic, pero un token robado no sirve con otra sesión.

Sin token válido, el gateway responde 403 con un `code` que el frontend reconoce:
  - `step_up_requerido`: el usuario tiene 2FA → el modal le pide el código y reintenta.
  - `2fa_requerido`: el usuario no tiene 2FA y la regla lo bloquea → el modal le ofrece activarlo.

Qué pasa con quien NO tiene 2FA lo decide cada regla (`sin_2fa`): "bloquear", "permitir", o None =
lo que diga `TOKENSERVER_STEPUP_SIN_2FA` (la transición: hoy "permitir"). El módulo de SEGURIDAD
bloquea siempre: nadie cambia usuarios, roles, grupos, permisos ni contraseñas sin doble factor.

Para sumar una operación: agregá (método, regex, descripción) a STEP_UP_RUTAS. La regex es sobre la ruta
completa (/api/...) y se evalúa con `re.match`; la descripción es lo que ve el usuario en el modal.
"""
import re
from dataclasses import dataclass

# Métodos que no modifican nada: nunca piden step-up.
LECTURA = frozenset({"GET", "HEAD", "OPTIONS"})

# Nunca piden step-up: el login y TODO lo que el usuario necesita para enrolarse o gestionar SU PROPIO
# doble factor (/api/auth/2fa/...: enrolar, activar, códigos, desactivar, el propio step-up), además de
# refresh y logout. Ninguna de esas rutas vive bajo /api/security. Se evalúan antes que cualquier regla.
EXCEPCIONES: tuple[str, ...] = (r"^/api/auth/",)


@dataclass(frozen=True)
class Regla:
    metodos: frozenset | None   # métodos a los que aplica; None = CUALQUIER escritura (no LECTURA)
    regex: re.Pattern
    descripcion: str            # lo que ve el usuario en el modal
    sin_2fa: str | None = None  # "bloquear" | "permitir" | None (= TOKENSERVER_STEPUP_SIN_2FA)
    mensaje_sin_2fa: str = ""   # texto para quien no tiene 2FA (si la regla lo bloquea)


# ── Seguridad: UNA regla general. Cualquier escritura (todo método que no sea GET/HEAD/OPTIONS) sobre
#    /api/security/... exige step-up y, sin 2FA, se bloquea. Lo que se agregue al módulo en el futuro
#    queda cubierto solo. Incluye el cambio de la propia contraseña (no hay flujo de cambio obligatorio)
#    y el reset del 2FA de otro usuario por un admin. ──
MENSAJE_SEGURIDAD_SIN_2FA = "Para hacer cambios en Seguridad tenés que activar el doble factor."
REGLA_SEGURIDAD = Regla(
    metodos=None,
    regex=re.compile(r"^/api/security(/|$)"),
    descripcion="Hacer cambios en Seguridad",
    sin_2fa="bloquear",
    mensaje_sin_2fa=MENSAJE_SEGURIDAD_SIN_2FA,
)

# Sólo texto para el modal (la regla de arriba es la que manda): qué cambio en Seguridad se confirma.
DESCRIPCIONES_SEGURIDAD: list[tuple[str, str, str]] = [
    ("POST",   r"^/api/security/users$",                      "Crear un usuario"),
    ("PUT",    r"^/api/security/users/me/password$",          "Cambiar tu contraseña"),
    ("PUT",    r"^/api/security/users/\d+/password$",         "Cambiar la contraseña de otro usuario"),
    ("PUT",    r"^/api/security/users/\d+$",                  "Modificar un usuario"),
    ("DELETE", r"^/api/security/users/\d+/2fa$",              "Resetear el doble factor de un usuario"),
    ("DELETE", r"^/api/security/users/\d+$",                  "Dar de baja un usuario"),
    ("POST",   r"^/api/security/users/\d+/(roles|groups)$",   "Cambiar roles o grupos de un usuario"),
    ("POST",   r"^/api/security/roles(/\d+/permissions)?$",   "Crear un rol o cambiar sus permisos"),
    ("PUT",    r"^/api/security/roles/\d+$",                  "Modificar un rol"),
    ("DELETE", r"^/api/security/roles/\d+$",                  "Borrar un rol"),
    ("POST",   r"^/api/security/groups(/\d+/(roles|users))?$", "Crear un grupo o cambiar sus roles o integrantes"),
    ("PUT",    r"^/api/security/groups/\d+$",                 "Modificar un grupo"),
    ("DELETE", r"^/api/security/groups/\d+$",                 "Borrar un grupo"),
]

# Resto de los módulos: (método, regex de la ruta, qué se está por hacer). Sin 2FA rige
# TOKENSERVER_STEPUP_SIN_2FA.
STEP_UP_RUTAS: list[tuple[str, str, str]] = [
    # ── Tesorería: lotes de pago (mueven plata) ──
    ("POST",   r"^/api/tesoreria/lotes/\d+/aprobar$",                 "Aprobar un lote de pagos"),
    ("POST",   r"^/api/tesoreria/lotes/\d+/(enviar|reintentar-fallidos)$", "Enviar pagos al banco"),
    ("POST",   r"^/api/tesoreria/lotes/\d+/pagos/\d+/(reintentar|resolver)$", "Reintentar o resolver un pago"),
    ("POST",   r"^/api/tesoreria/ordenes-pago/\d+/anular$",           "Anular una orden de pago"),

    # ── Interbanking: transferencias y credenciales del banco ──
    ("POST",   r"^/api/interbanking/transferencias$",                 "Enviar una transferencia"),
    ("POST",   r"^/api/interbanking/config$",                         "Cambiar las credenciales de Interbanking"),

    # ── Configuraciones: impuestos, índices y workflow de aprobaciones ──
    ("POST",   r"^/api/configuraciones/(impuestos|indices|workflow)(/|$)",  "Cambiar la configuración"),
    ("PUT",    r"^/api/configuraciones/(impuestos|indices|workflow)(/|$)",  "Cambiar la configuración"),
    ("PATCH",  r"^/api/configuraciones/(impuestos|indices|workflow)(/|$)",  "Cambiar la configuración"),
    ("DELETE", r"^/api/configuraciones/(impuestos|indices|workflow)(/|$)",  "Cambiar la configuración"),

    # ── Créditos: aprobar, desembolsar, cobrar/cancelar, reversar, CBU de destino ──
    ("POST",   r"^/api/creditos/aprobaciones/pendientes/[^/]+/aprobar$",    "Aprobar en el workflow de créditos"),
    ("POST",   r"^/api/creditos/contratos/[^/]+/desembolsar$",              "Desembolsar un crédito"),
    ("POST",   r"^/api/creditos/contratos/liquidar-lote$",                  "Liquidar un lote de créditos"),
    ("POST",   r"^/api/creditos/contratos/lotes-liquidacion/[^/]+/(cerrar|reabrir)$", "Cerrar o reabrir un lote de liquidación"),
    ("POST",   r"^/api/creditos/contratos/[^/]+/actividad/[^/]+/reversar$", "Reversar un movimiento de un contrato"),
    ("POST",   r"^/api/creditos/creditos/[^/]+/cancelar$",                  "Cancelar un crédito"),
    ("PUT",    r"^/api/creditos/solicitudes/[^/]+/cbu$",                    "Cambiar el CBU de una solicitud"),

    # ── Clientes: CBU a donde se paga ──
    ("POST",   r"^/api/clientes/\d+/cbus$",                           "Agregar un CBU de cliente"),
    ("PUT",    r"^/api/clientes/\d+/cbus/\d+$",                       "Modificar un CBU de cliente"),
    ("DELETE", r"^/api/clientes/\d+/cbus/\d+$",                       "Borrar un CBU de cliente"),

    # ── Conciliación: ajustes manuales de importes ──
    ("POST",   r"^/api/conciliacion/records/\d+/adjustments$",        "Cargar un ajuste de conciliación"),

    # ── Cajeros: autorizar y anular transacciones, reglas de autorización ──
    ("PUT",    r"^/api/cajeros/transactions/\d+/authorize$",          "Autorizar una transacción de cajero"),
    ("DELETE", r"^/api/cajeros/transactions/\d+$",                    "Anular una transacción de cajero"),
    ("POST",   r"^/api/cajeros/rules$",                               "Cambiar las reglas de autorización de cajeros"),
    ("DELETE", r"^/api/cajeros/rules/\d+$",                           "Cambiar las reglas de autorización de cajeros"),

    # ── Contabilidad: anular asientos y cerrar/reabrir ejercicios ──
    ("POST",   r"^/api/contabilidad/asientos/\d+/anular$",            "Anular un asiento"),
    ("DELETE", r"^/api/contabilidad/asientos/\d+$",                   "Borrar un asiento"),
    ("POST",   r"^/api/contabilidad/ejercicios/\d+/(cerrar|reabrir)$", "Cerrar o reabrir un ejercicio contable"),
]

REGLAS: list[Regla] = [REGLA_SEGURIDAD] + [
    Regla(metodos=frozenset({m}), regex=re.compile(rx), descripcion=desc) for m, rx, desc in STEP_UP_RUTAS
]
_EXCEPCIONES = [re.compile(rx) for rx in EXCEPCIONES]
_DESCRIPCIONES_SEGURIDAD = [(m, re.compile(rx), d) for m, rx, d in DESCRIPCIONES_SEGURIDAD]


def _aplica(regla: Regla, method: str) -> bool:
    if method in LECTURA:
        return False
    return regla.metodos is None or method in regla.metodos


def regla_step_up(method: str, path: str) -> Regla | None:
    """La regla de step-up que corresponde a la operación, o None si no pide step-up."""
    method = method.upper()
    if method in LECTURA or any(rx.match(path) for rx in _EXCEPCIONES):
        return None
    for regla in REGLAS:
        if _aplica(regla, method) and regla.regex.match(path):
            return regla
    return None


def describir(regla: Regla, method: str, path: str) -> str:
    """Texto del modal: para Seguridad, el cambio puntual si se conoce; si no, el de la regla."""
    if regla is REGLA_SEGURIDAD:
        for m, rx, d in _DESCRIPCIONES_SEGURIDAD:
            if m == method.upper() and rx.match(path):
                return d
    return regla.descripcion


def requiere_step_up(method: str, path: str) -> str | None:
    """Descripción de la operación si exige step-up; None si no."""
    regla = regla_step_up(method, path)
    return describir(regla, method, path) if regla else None
