"""Archivo de alta de cuentas de terceros para Interbanking.

Interbanking no tiene API para dar de alta cuentas destino: se suben con un TXT desde el portal
(Administración > Cuenta > Alta y Modificación desde Archivo, diseño "Carga de cuentas para todo tipo de
transferencias") y otro administrador las autoriza (Administración > Cuenta > Autorizaciones masivas).

Diseño de registro (planilla "UPLOAD DE CUENTAS" de Interbanking), ANSI, una línea por registro:
  1  cabecera   1 + código de cliente X(7) + "TERCEROS " X(9) + acción X(12) + fecha AAAAMMDD   → 200
  2  cuenta     2 + CBU 9(22) + CUIT 9(11) + denominación X(40) + referencia X(50, vacía)      → 200
  3  uso        3 + uso X(3) + 11 blancos                                                      →  15
  5  cierre     5 + código de cliente X(7) + cantidad de cuentas 9(6)                          → 200
(El registro 4, mail de la cuenta, es opcional y no lo usamos.)
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

USO_TERCEROS = "TER"     # desembolsos de créditos y premios: pagos a terceros
_ANCHO = 200
_PESOS_CUIT = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)


def _texto(valor: str, largo: int) -> str:
    """Mayúsculas sin acentos y sólo letras, números y espacios, como acepta Interbanking."""
    s = "".join(c for c in unicodedata.normalize("NFKD", valor or "") if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9 ]", " ", s)
    return re.sub(r" +", " ", s).strip().upper()[:largo]


def cuit_valido(cuit: str) -> bool:
    if not re.fullmatch(r"\d{11}", cuit or ""):
        return False
    resto = sum(int(d) * p for d, p in zip(cuit[:10], _PESOS_CUIT)) % 11
    verificador = 0 if resto == 0 else 9 if resto == 1 else 11 - resto
    return verificador == int(cuit[10])


def cuentas_de(pagos) -> tuple[list[dict], list[dict]]:
    """(cuentas, omitidas): una cuenta por CBU; sin CUIT/CUIL válido no se puede dar de alta."""
    cuentas, omitidas, vistos = [], [], set()
    for p in pagos:
        if p.cbu in vistos:
            continue
        vistos.add(p.cbu)
        cuit = "".join(ch for ch in (p.documento or "") if ch.isdigit())
        if not cuit_valido(cuit):
            omitidas.append({"beneficiario": p.beneficiario, "cbu": p.cbu, "documento": p.documento,
                             "motivo": "Sin CUIT/CUIL válido" if cuit else "Sin CUIT/CUIL"})
            continue
        cuentas.append({"cbu": p.cbu, "cuit": cuit, "denominacion": _texto(p.beneficiario, 40) or cuit})
    return cuentas, omitidas


def generar(cuentas: list[dict], codigo_cliente: str, fecha: date | None = None) -> str:
    """El TXT listo para subir (líneas con CRLF, como lo guarda el Bloc de notas)."""
    cliente = (codigo_cliente or "").strip()[:7]
    lineas = [("1" + cliente + "TERCEROS " + "ALTA".ljust(12) + (fecha or date.today()).strftime("%Y%m%d")).ljust(_ANCHO)]
    for c in cuentas:
        lineas.append(("2" + c["cbu"] + c["cuit"] + c["denominacion"].ljust(40)).ljust(_ANCHO))
        lineas.append("3" + USO_TERCEROS + " " * 11)
    lineas.append(("5" + cliente + str(len(cuentas)).zfill(6)).ljust(_ANCHO))
    return "\r\n".join(lineas) + "\r\n"
