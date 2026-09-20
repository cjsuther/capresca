"""Calculador de cronograma para Configurar Créditos — ÚNICA FUENTE DE VERDAD.

Lo usan por igual: la prueba en vivo (endpoint /productos/preview), la simulación
persistida y la originación de contratos. Sistemas: francés, alemán, americano, bullet,
con período de gracia, frecuencia (mensual/trimestral), cuota vencida/adelantada
(anualidad anticipada correcta), cargos (prorrateado/desembolso/financiable) e impuestos.
Usa float para el cálculo y redondea a 2 decimales al final; la última cuota absorbe el
redondeo para que el saldo cierre exacto en 0.
"""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP


def _r(x: float, dec: int = 2) -> Decimal:
    dec = max(0, min(6, int(dec)))
    return Decimal(str(x)).quantize(Decimal(1).scaleb(-dec), rounding=ROUND_HALF_UP)


# Feriados nacionales argentinos de fecha FIJA (inamovibles). Los trasladables/movibles
# (Carnaval, Viernes Santo, Malvinas cuando cae finde, puentes turísticos por decreto) NO están
# acá: requieren un maestro de feriados por año; se inyectan vía el parámetro `feriados`.
FERIADOS_FIJOS = {
    (1, 1),    # Año Nuevo
    (3, 24),   # Día de la Memoria
    (4, 2),    # Malvinas
    (5, 1),    # Día del Trabajador
    (5, 25),   # Revolución de Mayo
    (7, 9),    # Independencia
    (12, 8),   # Inmaculada Concepción
    (12, 25),  # Navidad
}


def _es_feriado(d: date, extra: set[date] | None) -> bool:
    return (d.month, d.day) in FERIADOS_FIJOS or (extra is not None and d in extra)


def _inhabil(d: date, extra: set[date] | None) -> bool:
    return d.weekday() >= 5 or _es_feriado(d, extra)  # 5 sábado, 6 domingo, o feriado


def _ajusta(d: date, modo: str, feriados: set[date] | None = None) -> date:
    if modo == "SIGUIENTE_HABIL":
        while _inhabil(d, feriados):
            d += timedelta(days=1)
    elif modo == "ANTERIOR_HABIL":
        while _inhabil(d, feriados):
            d -= timedelta(days=1)
    return d


def _venc(fecha_valor: date, k: int, per: int, dia_pago: int,
          primer_dias: int, ajuste: str, feriados: set[date] | None = None) -> date:
    """1er vencimiento = fecha valor + primer_dias; luego cada 'per' meses en dia_pago."""
    first = fecha_valor + timedelta(days=primer_dias)
    total_month = first.year * 12 + (first.month - 1) + (k - 1) * per
    y, mo = divmod(total_month, 12)
    day = min(max(1, int(dia_pago or 1)), 28)
    return _ajusta(date(y, mo + 1, day), ajuste, feriados)


def cronograma(sistema: str, monto: float, plazo: int, tna: float,
               cargo_pct: float = 0.0, fecha_valor: date | None = None, *,
               gracia: int = 0, frecuencia: str = "MENSUAL",
               cargos: list[dict] | None = None, impuestos: list[dict] | None = None,
               dia_pago: int = 5, primer_venc_dias: int = 30,
               ajuste_fin_semana: str = "SIN_AJUSTE", tipo_cuota: str = "VENCIDA",
               financiable: bool = False, cargo_momento: str = "PRORRATEADO",
               feriados: set[date] | None = None, decimales: int = 2) -> list[dict]:
    fecha_valor = fecha_valor or date.today()
    cargos = cargos or []
    impuestos = impuestos or []
    per = 3 if str(frecuencia).upper() == "TRIMESTRAL" else 1
    n = max(1, int(plazo))
    i = float(tna) / 100 * per / 12
    g = min(max(0, int(gracia or 0)), n - 1)
    n_amort = max(1, n - g)
    adelantada = str(tipo_cuota).upper() == "ADELANTADA"
    disbursed = float(monto)

    # Cargos: prorrateado (% de cuota o fijo por cuota), desembolso (1ª cuota) o financiado (al capital).
    per_cuota_fijo = 0.0
    cuota_pct = 0.0
    cuota1_extra = 0.0
    financiado = 0.0
    otorg = disbursed * (float(cargo_pct) / 100)
    # 'financiable' tiene prioridad: si está marcado, el cargo se suma al capital y se
    # amortiza (nunca se ignora silenciosamente aunque el momento sea PRORRATEADO).
    if financiable:
        financiado += otorg
    elif str(cargo_momento).upper() == "PRORRATEADO":
        per_cuota_fijo += otorg / n
    else:
        cuota1_extra += otorg
    for c in cargos:
        pct = float(c.get("porcentaje") or 0) / 100
        if str(c.get("momento") or "PRORRATEADO").upper() == "PRORRATEADO":
            cuota_pct += pct                       # % de la base de cada cuota
        elif financiable:
            financiado += disbursed * pct          # % del capital, financiado
        else:
            cuota1_extra += disbursed * pct        # % del capital, cobrado al desembolso

    P = disbursed + financiado                     # capital que efectivamente se amortiza
    taxes = [(str(t.get("base") or "CUOTA").upper(), float(t.get("porcentaje") or 0) / 100)
             for t in impuestos]

    # Anualidad anticipada (cuota adelantada): la 1ª cuota amortizante no devenga interés
    # (se paga al inicio del período) y la cuota francesa se descuenta un período.
    factor = (1 / (1 + i)) if (adelantada and i > 0) else 1.0
    frances = (P / n_amort) if i == 0 else (P * i) / (1 - (1 + i) ** (-n_amort)) * factor
    amort = P / n_amort
    filas: list[dict] = []
    bal = P
    primer_amort = True
    for k in range(1, n + 1):
        en_gracia = k <= g
        if sistema == "AMERICANO":
            interes = P * i
            capital = P if k == n else 0.0
        elif sistema == "BULLET":
            interes = P * ((1 + i) ** n - 1) if k == n else 0.0
            capital = P if k == n else 0.0
        elif en_gracia:
            interes = bal * i
            capital = 0.0
        elif sistema == "ALEMAN":
            interes = 0.0 if (adelantada and primer_amort) else bal * i
            capital = amort
            primer_amort = False
        else:  # FRANCES
            if adelantada and primer_amort:
                interes = 0.0
                capital = frances
            else:
                interes = bal * i
                capital = frances - interes
            primer_amort = False
        if k == n:
            capital = bal  # la última cuota salda el saldo exacto (absorbe el redondeo)

        base_cuota = capital + interes
        cargos_base = per_cuota_fijo + base_cuota * cuota_pct + (cuota1_extra if k == 1 else 0.0)
        imp = 0.0
        for b, p in taxes:
            base = (interes if b == "INTERES" else capital if b == "CAPITAL"
                    else cargos_base if b == "CARGOS"
                    else (base_cuota + cargos_base) if b == "TOTAL" else base_cuota)
            imp += base * p
        cargos_cuota = cargos_base + imp

        closing = max(0.0, bal - capital)
        if k == n:
            closing = 0.0
        filas.append({
            "numero_cuota": k,
            "fecha_vencimiento": _venc(fecha_valor, k, per, int(dia_pago or 5),
                                       int(primer_venc_dias if primer_venc_dias is not None else 30),
                                       str(ajuste_fin_semana or "SIN_AJUSTE"), feriados),
            "saldo_inicial": _r(bal, decimales), "capital": _r(capital, decimales), "interes": _r(interes, decimales),
            "cargos": _r(cargos_cuota, decimales), "impuestos": _r(imp, decimales),
            "total": _r(capital + interes + cargos_cuota, decimales),
            "saldo_final": _r(closing, decimales),
        })
        bal = closing
    return filas


def _tir_periodica(disbursed: float, totales: list[float]) -> float:
    """TIR por período que iguala Σ cuota_k/(1+r)^k al monto desembolsado (bisección)."""
    def npv(r: float) -> float:
        return sum(c / (1 + r) ** (k + 1) for k, c in enumerate(totales)) - disbursed
    lo, hi = -0.9, 5.0
    f_lo = npv(lo)
    if f_lo == 0:
        return lo
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = npv(mid)
        if abs(f_mid) < 1e-7:
            return mid
        if (f_lo < 0) != (f_mid < 0):
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def resumen(filas: list[dict], monto: float, frecuencia: str = "MENSUAL", tna: float = 0.0) -> dict:
    """Totales, TNA, TEA (efectiva anual de la tasa) y CFT (TIR anual real, incluye cargos/impuestos)."""
    per = 3 if str(frecuencia).upper() == "TRIMESTRAL" else 1
    m = 12 / per                                    # períodos por año
    i = float(tna) / 100 * per / 12                 # tasa por período
    tea = ((1 + i) ** m - 1) * 100 if i > -1 else 0.0
    totales = [float(f["total"]) for f in filas]
    r = _tir_periodica(float(monto), totales) if totales and float(monto) > 0 else 0.0
    cft = ((1 + r) ** m - 1) * 100 if r > -1 else 0.0
    return {
        "totalCuotas": round(sum(totales), 2),
        "totalInteres": round(sum(float(f["interes"]) for f in filas), 2),
        "totalCargos": round(sum(float(f["cargos"]) for f in filas), 2),
        "primeraCuota": round(totales[0], 2) if totales else 0.0,
        "tna": round(float(tna), 4), "tea": round(tea, 2), "cft": round(cft, 2),
    }
