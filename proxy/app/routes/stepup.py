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
  - `2fa_requerido`: el usuario no tiene 2FA y la política es `TOKENSERVER_STEPUP_SIN_2FA=bloquear`
    → el modal le ofrece activarlo. Con `permitir`, a quien no tiene 2FA no se le pide nada.

Para sumar una operación: agregá (método, regex, descripción). La regex es sobre la ruta completa
(/api/...) y se evalúa con `re.match`; la descripción es lo que ve el usuario en el modal.
"""
import re

# (método, regex de la ruta, qué se está por hacer)
STEP_UP_RUTAS: list[tuple[str, str, str]] = [
    # ── Usuarios, roles, grupos y permisos (quién puede hacer qué) ──
    ("POST",   r"^/api/security/users$",                              "Crear un usuario"),
    ("PUT",    r"^/api/security/users/\d+$",                          "Modificar un usuario"),
    ("DELETE", r"^/api/security/users/\d+$",                          "Dar de baja un usuario"),
    ("PUT",    r"^/api/security/users/\d+/password$",                 "Cambiar la contraseña de otro usuario"),
    ("POST",   r"^/api/security/users/\d+/(roles|groups)$",           "Cambiar roles o grupos de un usuario"),
    ("DELETE", r"^/api/security/users/\d+/2fa$",                      "Resetear el doble factor de un usuario"),
    ("POST",   r"^/api/security/roles(/\d+/permissions)?$",           "Crear un rol o cambiar sus permisos"),
    ("PUT",    r"^/api/security/roles/\d+$",                          "Modificar un rol"),
    ("DELETE", r"^/api/security/roles/\d+$",                          "Borrar un rol"),
    ("POST",   r"^/api/security/groups(/\d+/(roles|users))?$",        "Crear un grupo o cambiar sus roles o integrantes"),
    ("PUT",    r"^/api/security/groups/\d+$",                         "Modificar un grupo"),
    ("DELETE", r"^/api/security/groups/\d+$",                         "Borrar un grupo"),

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

_COMPILADAS = [(m, re.compile(rx), desc) for m, rx, desc in STEP_UP_RUTAS]


def requiere_step_up(method: str, path: str) -> str | None:
    """Descripción de la operación si exige step-up; None si no."""
    for m, rx, desc in _COMPILADAS:
        if m == method and rx.match(path):
            return desc
    return None
