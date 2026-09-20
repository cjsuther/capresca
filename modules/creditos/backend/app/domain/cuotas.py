"""Motor de cálculo de planes de cuotas.

Portado de `det_cuota` / `calcpres` (set_class.prg). Usa Decimal para
precisión al centavo (requisito de las pruebas de equivalencia contra VFP).

Composición de cuota (7 conceptos):
    total = amortizacion + interes + iva_interes
          + seguro + iva_seguro + gastos_adm + iva_gastos_adm

Sistemas de amortización (LineaCredito.tipo_calculo):
    1  Francés  (cuota constante)
    2  Alemán   (amortización de capital constante)
    3  Directo  (interés flat sobre capital original)
    4  Francés con período de gracia (misma cuota, gracia inicial)
    5  Cuota fija SIN interés (Res. 1903/2010): plazo = capital / cuota

NOTA: el mapeo exacto 1..4 -> sistema debe confirmarse con datasets reales
corridos en el VFP actual. La descomposición de conceptos y el tipo 5 están
tomados literalmente del código fuente.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Callable

CERO = Decimal("0.00")


def _q(x: Decimal) -> Decimal:
    """Redondeo monetario a 2 decimales (ROUND_HALF_UP, como VFP)."""
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def gomonth(d: date, meses: int) -> date:
    """Equivalente a GOMONTH de VFP: suma meses conservando el día si es posible."""
    m = d.month - 1 + meses
    y = d.year + m // 12
    m = m % 12 + 1
    # ajustar día al último del mes destino si hace falta
    import calendar

    ultimo = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, ultimo))


DIAS_MES = Decimal("30")
DIAS_ANIO = Decimal("365")


def tasa_mensual_desde_tna(tna: Decimal) -> Decimal:
    """Tasa mensual (%) según la convención CCyPP: TNA * 30 / 365.

    Verificado contra datos reales (tmpdev.DBF): TNA/tasa = 12.1667 = 365/30.
    """
    return Decimal(tna) * DIAS_MES / DIAS_ANIO


@dataclass
class ParametrosLinea:
    """Parámetros de la línea de crédito relevantes al cálculo."""
    tipo_calculo: int
    tna: Decimal                      # tasa nominal anual (%)
    tasa_mensual: Decimal | None = None  # tasa mensual (%) explícita; si None se deriva de tna
    iva: Decimal = Decimal("21")      # alícuota IVA (%)
    seguro_pct: Decimal = CERO        # seguro como % del saldo por cuota
    gastos_adm_pct: Decimal = CERO    # gastos administrativos % del saldo por cuota
    seguro_fijo: Decimal = CERO       # seguro monto fijo por cuota (alternativa)
    gastos_adm_fijo: Decimal = CERO   # gastos adm monto fijo por cuota
    por_afecta: Decimal = Decimal("30")  # % máximo de afectación del haber
    cartera: int = 1


@dataclass
class Cuota:
    numero: int
    vencimiento: date
    saldo_capital: Decimal
    amortizacion: Decimal
    interes: Decimal
    iva_interes: Decimal
    seguro: Decimal
    iva_seguro: Decimal
    gastos_adm: Decimal
    iva_gastos_adm: Decimal

    @property
    def total(self) -> Decimal:
        return _q(
            self.amortizacion + self.interes + self.iva_interes
            + self.seguro + self.iva_seguro + self.gastos_adm + self.iva_gastos_adm
        )

    def as_dict(self) -> dict:
        d = {
            "numero": self.numero,
            "vencimiento": self.vencimiento.isoformat(),
            "saldo_capital": str(self.saldo_capital),
            "amortizacion": str(self.amortizacion),
            "interes": str(self.interes),
            "iva_interes": str(self.iva_interes),
            "seguro": str(self.seguro),
            "iva_seguro": str(self.iva_seguro),
            "gastos_adm": str(self.gastos_adm),
            "iva_gastos_adm": str(self.iva_gastos_adm),
            "total": str(self.total),
        }
        return d


@dataclass
class PlanCuotas:
    cuotas: list[Cuota] = field(default_factory=list)

    @property
    def total_a_pagar(self) -> Decimal:
        return _q(sum((c.total for c in self.cuotas), CERO))

    @property
    def total_interes(self) -> Decimal:
        return _q(sum((c.interes for c in self.cuotas), CERO))

    @property
    def cuota_promedio(self) -> Decimal:
        if not self.cuotas:
            return CERO
        return _q(self.total_a_pagar / len(self.cuotas))


def _iva(monto: Decimal, alicuota: Decimal) -> Decimal:
    return _q(monto * alicuota * Decimal("0.01"))


def _cargos(saldo: Decimal, p: ParametrosLinea) -> tuple[Decimal, Decimal]:
    """Seguro y gastos administrativos de la cuota (fijo tiene prioridad)."""
    seguro = p.seguro_fijo if p.seguro_fijo > 0 else _q(saldo * p.seguro_pct * Decimal("0.01"))
    gastos = p.gastos_adm_fijo if p.gastos_adm_fijo > 0 else _q(saldo * p.gastos_adm_pct * Decimal("0.01"))
    return seguro, gastos


def generar_plan(
    capital: Decimal,
    plazo: int,
    linea: ParametrosLinea,
    fecha_primer_vto: date,
    cuota_fija: Decimal | None = None,
) -> PlanCuotas:
    """Genera el plan de cuotas según el tipo_calculo de la línea."""
    capital = Decimal(capital)
    # Tasa mensual (fracción): explícita o derivada de la TNA (convención 30/365).
    mensual_pct = linea.tasa_mensual if linea.tasa_mensual is not None else tasa_mensual_desde_tna(linea.tna)
    i = Decimal(mensual_pct) / Decimal("100")

    if linea.tipo_calculo == 5:
        return _plan_cuota_fija_sin_interes(capital, cuota_fija, linea, fecha_primer_vto)
    if linea.tipo_calculo == 2:
        return _plan_aleman(capital, plazo, i, linea, fecha_primer_vto)
    if linea.tipo_calculo == 3:
        return _plan_directo(capital, plazo, i, linea, fecha_primer_vto)
    # 1 y 4 (y default): sistema francés (calibrado con datos reales)
    return _plan_frances(capital, plazo, i, linea, fecha_primer_vto)


def _plan_frances(capital, plazo, i, linea, fvto) -> PlanCuotas:
    """Sistema francés CCyPP (calibrado contra tmpdev.DBF).

    La cuota constante es (capital + interés + IVA-interés), por lo que la
    anualidad usa la tasa efectiva  r = i * (1 + IVA).  El interés se calcula
    sobre el saldo a la tasa mensual `i`; el IVA, sobre el interés. Seguro y
    gastos administrativos se suman aparte (no entran en la anualidad).
    """
    plan = PlanCuotas()
    saldo = capital
    iva_frac = Decimal(1) + linea.iva / Decimal("100")
    if i == 0:
        cuota_const = _q(capital / plazo)
    else:
        r = i * iva_frac                       # tasa efectiva incluyendo IVA
        factor = (Decimal(1) + r) ** plazo
        cuota_const = _q(capital * (r * factor) / (factor - 1))
    for n in range(1, plazo + 1):
        interes = _q(saldo * i)
        iva_int = _iva(interes, linea.iva)
        amort = _q(cuota_const - interes - iva_int)
        if n == plazo:  # ajuste final para cerrar el saldo
            amort = saldo
        seguro, gastos = _cargos(saldo, linea)
        plan.cuotas.append(Cuota(
            numero=n, vencimiento=fvto, saldo_capital=saldo,
            amortizacion=amort, interes=interes, iva_interes=iva_int,
            seguro=seguro, iva_seguro=_iva(seguro, linea.iva),
            gastos_adm=gastos, iva_gastos_adm=_iva(gastos, linea.iva),
        ))
        saldo = _q(saldo - amort)
        fvto = gomonth(fvto, 1)
    return plan


def _plan_aleman(capital, plazo, i, linea, fvto) -> PlanCuotas:
    """Sistema alemán: amortización de capital constante."""
    plan = PlanCuotas()
    saldo = capital
    amort_const = _q(capital / plazo)
    for n in range(1, plazo + 1):
        interes = _q(saldo * i)
        amort = amort_const if n < plazo else saldo
        seguro, gastos = _cargos(saldo, linea)
        plan.cuotas.append(Cuota(
            numero=n, vencimiento=fvto, saldo_capital=saldo,
            amortizacion=amort, interes=interes, iva_interes=_iva(interes, linea.iva),
            seguro=seguro, iva_seguro=_iva(seguro, linea.iva),
            gastos_adm=gastos, iva_gastos_adm=_iva(gastos, linea.iva),
        ))
        saldo = _q(saldo - amort)
        fvto = gomonth(fvto, 1)
    return plan


def _plan_directo(capital, plazo, i, linea, fvto) -> PlanCuotas:
    """Sistema directo/flat: interés sobre capital original, amortización constante.

    Refleja  interes = capital * t1 / plazo  del código original.
    """
    plan = PlanCuotas()
    saldo = capital
    amort_const = _q(capital / plazo)
    interes_const = _q(capital * i)  # interés flat por cuota
    for n in range(1, plazo + 1):
        amort = amort_const if n < plazo else saldo
        seguro, gastos = _cargos(saldo, linea)
        plan.cuotas.append(Cuota(
            numero=n, vencimiento=fvto, saldo_capital=saldo,
            amortizacion=amort, interes=interes_const,
            iva_interes=_iva(interes_const, linea.iva),
            seguro=seguro, iva_seguro=_iva(seguro, linea.iva),
            gastos_adm=gastos, iva_gastos_adm=_iva(gastos, linea.iva),
        ))
        saldo = _q(saldo - amort)
        fvto = gomonth(fvto, 1)
    return plan


def _plan_cuota_fija_sin_interes(capital, cuota_fija, linea, fvto) -> PlanCuotas:
    """tipo_calculo = 5: plazo = capital / cuota, sin interés (Res. 1903/2010)."""
    if not cuota_fija or cuota_fija <= 0:
        raise ValueError("tipo_calculo=5 requiere cuota_fija > 0")
    cuota_fija = Decimal(cuota_fija)
    plazo = int((capital / cuota_fija).to_integral_value(rounding=ROUND_HALF_UP))
    plazo = max(plazo, 1)
    plan = PlanCuotas()
    saldo = capital
    for n in range(1, plazo + 1):
        amort = cuota_fija if n < plazo else saldo
        seguro, gastos = _cargos(saldo, linea)
        plan.cuotas.append(Cuota(
            numero=n, vencimiento=fvto, saldo_capital=saldo,
            amortizacion=amort, interes=CERO, iva_interes=CERO,
            seguro=seguro, iva_seguro=_iva(seguro, linea.iva),
            gastos_adm=gastos, iva_gastos_adm=_iva(gastos, linea.iva),
        ))
        saldo = _q(saldo - amort)
        fvto = gomonth(fvto, 1)
    return plan
