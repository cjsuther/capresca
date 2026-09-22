"""Configuraciones en memoria para los tests: responde como `GET /internal/configuraciones/*`.

Arranca como una base recién sembrada del módulo Configuraciones (impuestos e índices por defecto,
feriados AR del año actual y los dos siguientes, las cuatro reglas de Créditos INACTIVAS con un nivel
APROBAR). Los tests la ajustan con los helpers (`activar`, `agregar_nivel`, `override`…).
"""
from __future__ import annotations

import copy
import re
from datetime import date, timedelta

from app.core import configuraciones

IMPUESTOS = [
    {"id": 1, "codigo": "IIBB-CAT", "nombre": "Ingresos Brutos Catamarca", "tipo": "IIBB", "alicuota": 4.0,
     "base": "TOTAL", "cuenta_contable": "2.1.08", "jurisdiccion": "Catamarca", "vigente_desde": None,
     "vigente_hasta": None, "activo": True},
    {"id": 2, "codigo": "IVA105", "nombre": "IVA 10,5%", "tipo": "IVA", "alicuota": 10.5, "base": "INTERES",
     "cuenta_contable": "2.1.07.02", "jurisdiccion": "", "vigente_desde": None, "vigente_hasta": None, "activo": True},
    {"id": 3, "codigo": "IVA21", "nombre": "IVA 21%", "tipo": "IVA", "alicuota": 21.0, "base": "INTERES",
     "cuenta_contable": "2.1.07.01", "jurisdiccion": "", "vigente_desde": None, "vigente_hasta": None, "activo": True},
    {"id": 4, "codigo": "SELLOS", "nombre": "Sellado provincial", "tipo": "SELLADO", "alicuota": 1.2, "base": "CUOTA",
     "cuenta_contable": "2.1.09", "jurisdiccion": "", "vigente_desde": None, "vigente_hasta": None, "activo": True},
]
INDICES = [
    {"id": 1, "codigo": "BADLAR", "nombre": "BADLAR bancos privados", "valor": 45.0, "fuente": "BCRA",
     "fecha_valor": None, "activo": True},
    {"id": 2, "codigo": "TPM", "nombre": "Tasa de política monetaria", "valor": 40.0, "fuente": "BCRA",
     "fecha_valor": None, "activo": True},
    {"id": 3, "codigo": "UVA", "nombre": "Unidad de Valor Adquisitivo (equiv. anual)", "valor": 30.0,
     "fuente": "INDEC", "fecha_valor": None, "activo": True},
]
OBJETOS = ("LINEA", "SOLICITUD", "DESEMBOLSO", "REFINANCIACION")
_AR_FIJOS = [(1, 1), (3, 24), (4, 2), (5, 1), (5, 25), (7, 9), (12, 8), (12, 25)]


def _pascua(anio: int) -> date:
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    mm = (a + 11 * h + 22 * l) // 451
    return date(anio, (h + l - 7 * mm + 114) // 31, ((h + l - 7 * mm + 114) % 31) + 1)


def feriados_ar(anio: int) -> set[date]:
    p = _pascua(anio)
    return {date(anio, m, d) for m, d in _AR_FIJOS} | {p - timedelta(days=2), p - timedelta(days=48),
                                                        p - timedelta(days=47)}


class ConfigFalsa:
    def __init__(self):
        self.impuestos = copy.deepcopy(IMPUESTOS)
        self.indices = copy.deepcopy(INDICES)
        hoy = date.today()
        self.feriados = {("AR", f) for a in (hoy.year, hoy.year + 1, hoy.year + 2) for f in feriados_ar(a)}
        self.reglas = {o: {"id": n, "modulo": "creditos", "objeto": o, "nombre": o, "descripcion": "",
                           "activo": False,
                           "niveles": [{"id": n * 10 + 1, "orden": 1, "nombre": "Aprobación", "rol": "APROBAR",
                                        "cuatroOjos": True, "usuarios": []}]}
                       for n, o in enumerate(OBJETOS, start=1)}
        self.caida = False
        self.pedidos: list[str] = []

    # ── la "API interna" ────────────────────────────────────────────────────────────────────
    def get(self, path: str, params: dict | None = None):
        self.pedidos.append(path)
        if self.caida:
            raise ConnectionError("Configuraciones caído (simulado)")
        params = params or {}
        activos = lambda xs: [x for x in xs if x["activo"] or params.get("estado") == "todos"]
        if path == "/impuestos":
            return {"items": copy.deepcopy(activos(self.impuestos))}
        if path == "/indices":
            return {"items": copy.deepcopy(activos(self.indices))}
        if m := re.fullmatch(r"/indices/(\w+)", path):
            return copy.deepcopy(next((i for i in self.indices if i["codigo"] == m.group(1)), None))
        if path == "/feriados":
            desde, hasta = date.fromisoformat(params["desde"]), date.fromisoformat(params["hasta"])
            fechas = sorted(f for p, f in self.feriados if p == params["pais"] and desde <= f <= hasta)
            return {"pais": params["pais"], "fechas": [f.isoformat() for f in fechas]}
        if m := re.fullmatch(r"/workflow/creditos/(\w+)", path):
            return copy.deepcopy(self.reglas.get(m.group(1)))
        raise AssertionError(f"ruta no simulada: {path}")

    # ── helpers de los tests (cada cambio invalida la caché, como pasaría a los segundos) ──
    def _cambio(self):
        configuraciones.limpiar_cache()

    def activar(self, objeto: str, activo: bool = True) -> None:
        self.reglas[objeto]["activo"] = activo
        self._cambio()

    def niveles(self, objeto: str) -> list[dict]:
        return self.reglas[objeto]["niveles"]

    def agregar_nivel(self, objeto: str, nombre: str = "Aprobación", rol: str = "APROBAR",
                      cuatro_ojos: bool = True) -> None:
        niveles = self.reglas[objeto]["niveles"]
        niveles.append({"id": len(niveles) + 100, "orden": len(niveles) + 1, "nombre": nombre, "rol": rol,
                        "cuatroOjos": cuatro_ojos, "usuarios": []})
        self._cambio()

    def editar_nivel(self, objeto: str, orden: int, **cambios) -> None:
        nivel = next(n for n in self.reglas[objeto]["niveles"] if n["orden"] == orden)
        nivel.update(cambios)
        self._cambio()

    def override(self, objeto: str, orden: int, username: str, modo: str) -> None:
        nivel = next(n for n in self.reglas[objeto]["niveles"] if n["orden"] == orden)
        nivel["usuarios"] = [u for u in nivel["usuarios"] if u["username"] != username]
        nivel["usuarios"].append({"id": len(nivel["usuarios"]) + 1, "username": username, "modo": modo})
        self._cambio()

    def set_indice(self, codigo: str, valor: float, activo: bool = True) -> None:
        ind = next(i for i in self.indices if i["codigo"] == codigo)
        ind["valor"], ind["activo"] = valor, activo
        self._cambio()

    def agregar_feriado(self, fecha: date, pais: str = "AR") -> None:
        self.feriados.add((pais, fecha))
        self._cambio()


CONFIG = ConfigFalsa()


def reiniciar() -> ConfigFalsa:
    """Vuelve al estado recién sembrado (lo llama el fixture autouse de conftest)."""
    CONFIG.__init__()
    configuraciones.usar_fuente(CONFIG)
    return CONFIG
