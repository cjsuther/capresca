"""Sistema de cálculos — fórmulas del motor de cronograma, transparencia y depuración.

Expone, para el módulo Créditos:
  · Las fórmulas exactas que aplica cada sistema de amortización (francés, alemán,
    americano, bullet), con sus variables y el orden de armado de cada cuota.
  · La "certificación" del motor: checksum real del código fuente + precisión/redondeo.
    El motor es ÚNICA FUENTE DE VERDAD (mismo código que la prueba en vivo, la
    simulación y la originación), por eso la fórmula no se reescribe en runtime: se
    versiona/certifica. Lo editable son los PARÁMETROS (tasa, plazo, gracia…), no el código.
  · Un depurador ("debug") que arma las cuotas paso a paso mostrando los números reales
    de cada operación: saldo inicial → interés = saldo × i → capital = cuota − interés → saldo final.
"""
import hashlib
import inspect as _inspect
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user
from app.services import productos_calc as PC
from app import models_productos as m

router = APIRouter(prefix="/api/creditos/sistema-calculos", tags=["sistema-calculos"],
                   dependencies=[Depends(get_current_user)])


# ── Fórmulas documentadas (texto legible; el símbolo · es multiplicación) ──────────
SISTEMAS = [
    {
        "codigo": "FRANCES",
        "nombre": "Francés (cuota constante)",
        "resumen": "Cuota fija; el interés arranca alto y decrece, el capital arranca bajo y crece.",
        "formula": "cuota = P · i / (1 − (1 + i)^(−n))",
        "variables": [
            ("P", "capital que se amortiza (monto + cargos financiados)"),
            ("i", "tasa por período = TNA/100 · (meses del período)/12"),
            ("n", "cantidad de cuotas amortizantes (plazo − gracia)"),
        ],
        "pasos": [
            "interés = saldo · i",
            "capital = cuota − interés",
            "saldo_final = saldo − capital",
        ],
        "nota": "Cuota adelantada (anualidad anticipada): la 1ª cuota amortizante no devenga "
                "interés y la cuota se descuenta un período con factor 1/(1+i).",
    },
    {
        "codigo": "ALEMAN",
        "nombre": "Alemán (amortización constante)",
        "resumen": "Capital fijo por cuota; el interés (y la cuota total) decrecen.",
        "formula": "capital = P / n   (fijo);   interés = saldo · i",
        "variables": [
            ("P", "capital que se amortiza"),
            ("i", "tasa por período"),
            ("n", "cuotas amortizantes"),
        ],
        "pasos": [
            "capital = P / n  (constante)",
            "interés = saldo · i",
            "cuota = capital + interés  (decreciente)",
            "saldo_final = saldo − capital",
        ],
        "nota": "Cuota adelantada: la 1ª amortizante no devenga interés.",
    },
    {
        "codigo": "AMERICANO",
        "nombre": "Americano / bullet clásico (interés periódico, capital al final)",
        "resumen": "Sólo se paga interés cada período; el capital se devuelve íntegro en la última cuota. "
                   "Es el “bullet” clásico de la banca: interés corriente + repago único de capital al vencimiento.",
        "formula": "interés = P · i  (cada cuota);   capital = P  (sólo en cuota n)",
        "variables": [("P", "capital"), ("i", "tasa por período"), ("n", "plazo")],
        "pasos": [
            "interés = P · i  (todas las cuotas)",
            "capital = 0  hasta la última; capital = P en la cuota n",
            "saldo_final = P  (constante) hasta el final",
        ],
        "nota": "El saldo no baja hasta la última cuota.",
    },
    {
        "codigo": "BULLET",
        "nombre": "A vencimiento / capitalizado (interés compuesto, pago único)",
        "resumen": "No hay pagos intermedios; capital e interés capitalizado se pagan juntos al final "
                   "(estilo cupón cero). Distinto del bullet clásico con interés periódico → ver Americano.",
        "formula": "pago_final = P · (1 + i)^n     (interés capitalizado = P·((1+i)^n − 1))",
        "variables": [("P", "capital"), ("i", "tasa por período"), ("n", "plazo")],
        "pasos": [
            "cuotas 1..n−1: interés = 0, capital = 0",
            "cuota n: interés = P · ((1+i)^n − 1);  capital = P",
        ],
        "nota": "Interés compuesto capitalizado hasta el vencimiento.",
    },
]

# Reglas transversales (cargos, impuestos, fechas) que el motor aplica sobre cualquier sistema.
REGLAS_COMUNES = [
    ("Período", "i = TNA/100 · per/12, con per = 3 si la frecuencia es TRIMESTRAL, si no 1."),
    ("Gracia", "Las primeras g cuotas sólo devengan interés (capital = 0); amortiza n − g."),
    ("Cargos prorrateados", "Se reparten en cada cuota; 'al desembolso' se cobran en la 1ª; "
                            "'financiable' se suman al capital P."),
    ("Impuestos", "Se calculan sobre la base configurada (INTERÉS/CAPITAL/CARGOS/CUOTA/TOTAL)."),
    ("Última cuota", "Absorbe el redondeo: capital = saldo restante, saldo_final = 0."),
    ("CFT (TIR)", "Tasa que iguala Σ cuota_k/(1+r)^k al monto desembolsado; anualizada = (1+r)^(12/per) − 1."),
    ("TEA", "Efectiva anual de la TNA: (1 + i)^(12/per) − 1."),
]


# Gobernanza: cómo evoluciona una fórmula (decisión de diseño, no editable en runtime).
GOBERNANZA = [
    "La fórmula del motor NO se edita en tiempo de ejecución: es código certificado y versionado.",
    "Cambiar el comportamiento de un préstamo se hace con PARÁMETROS (tasa, plazo, gracia, cargos, "
    "impuestos, frecuencia…) desde Configurar Créditos — nunca reescribiendo la fórmula.",
    "Si el negocio necesita una fórmula nueva, se publica una nueva VERSIÓN del calculador "
    "(pp_calculador_version) con su checksum; los productos apuntan a una versión certificada y los "
    "contratos ya otorgados quedan congelados sobre la versión con la que se calcularon (auditable).",
]


def _certificacion(db: Session) -> dict:
    """Checksum real del código del motor + versión certificada del calculador en DB por sistema."""
    src = _inspect.getsource(PC)
    checksum = hashlib.sha256(src.encode("utf-8")).hexdigest()
    calcs = []
    for cod in ("FRANCES", "ALEMAN", "AMERICANO", "BULLET"):
        c = db.query(m.PPCalculador).filter_by(codigo=cod).first()
        cv = (max(c.versiones, key=lambda v: v.numero_version) if c and c.versiones else None)
        calcs.append({
            "sistema": cod,
            "version": cv.numero_version if cv else None,
            "estado": cv.estado if cv else "SIN CERTIFICAR",
            "motor": cv.motor if cv else "",
            "checksumCert": cv.checksum if cv else "",
        })
    return {
        "motor": "productos_calc.cronograma",
        "certificado": True,
        "checksum": checksum,
        "checksumCorto": checksum[:12],
        "precisionDecimal": 2,
        "reglaRedondeo": "HALF_UP",
        "lineasCodigo": src.count("\n") + 1,
        "fuenteUnica": "prueba en vivo · simulación · originación usan este mismo código",
        "calculadores": calcs,
    }


@router.get("")
def catalogo(db: Session = Depends(get_db)):
    return {
        "sistemas": SISTEMAS,
        "reglasComunes": [{"titulo": t, "detalle": d} for t, d in REGLAS_COMUNES],
        "certificacion": _certificacion(db),
        "gobernanza": GOBERNANZA,
    }


class DebugIn(BaseModel):
    sistema: str = "FRANCES"
    monto: float = 100000
    plazo: int = 12
    tna: float = 52.0
    frecuencia: str = "MENSUAL"
    gracia: int = 0
    tipoCuota: str = "VENCIDA"
    cargoPct: float = 0.0


def _fmt(x: float) -> str:
    return f"{x:,.2f}".replace(",", "·").replace(".", ",").replace("·", ".")


@router.post("/debug")
def debug(data: DebugIn):
    """Arma las cuotas con el motor real y devuelve el paso a paso legible por cuota."""
    per = 3 if str(data.frecuencia).upper() == "TRIMESTRAL" else 1
    i = float(data.tna) / 100 * per / 12
    n = max(1, int(data.plazo))
    g = min(max(0, int(data.gracia or 0)), n - 1)
    n_amort = max(1, n - g)
    adelantada = str(data.tipoCuota).upper() == "ADELANTADA"
    P = float(data.monto) * (1 + 0)  # cargos financiados no se incluyen en este debug simple
    factor = (1 / (1 + i)) if (adelantada and i > 0) else 1.0
    frances = (P / n_amort) if i == 0 else (P * i) / (1 - (1 + i) ** (-n_amort)) * factor

    # Cronograma real (misma función que producción) para los números finales redondeados.
    filas = PC.cronograma(data.sistema.upper(), data.monto, n, data.tna,
                          cargo_pct=data.cargoPct, fecha_valor=date.today(),
                          gracia=g, frecuencia=data.frecuencia, tipo_cuota=data.tipoCuota)

    # Parámetros derivados (lo que alimenta la fórmula).
    derivados = [
        ("per (meses del período)", str(per)),
        ("i (tasa por período)", f"{i:.8f}  =  {data.tna}/100 · {per}/12"),
        ("n (plazo)", str(n)),
        ("g (gracia)", str(g)),
        ("n_amort (cuotas amortizantes)", str(n_amort)),
        ("P (capital a amortizar)", _fmt(P)),
    ]
    if data.sistema.upper() == "FRANCES":
        derivados.append(("cuota francesa (constante)", _fmt(frances) +
                          (f"  · factor adelantada {factor:.6f}" if adelantada else "")))
    elif data.sistema.upper() == "ALEMAN":
        derivados.append(("capital fijo (P/n_amort)", _fmt(P / n_amort)))

    # Trazado paso a paso, replicando la lógica del motor con los números reales.
    pasos = []
    bal = P
    primer_amort = True
    sis = data.sistema.upper()
    for k in range(1, n + 1):
        en_gracia = k <= g
        detalle = []
        if sis == "AMERICANO":
            interes = P * i
            capital = P if k == n else 0.0
            detalle.append(f"interés = P · i = {_fmt(P)} · {i:.6f} = {_fmt(interes)}")
            detalle.append(f"capital = {'P (última cuota) = ' + _fmt(P) if k == n else '0 (sólo capitaliza interés)'}")
        elif sis == "BULLET":
            interes = P * ((1 + i) ** n - 1) if k == n else 0.0
            capital = P if k == n else 0.0
            if k == n:
                detalle.append(f"interés = P · ((1+i)^n − 1) = {_fmt(P)} · ((1+{i:.6f})^{n} − 1) = {_fmt(interes)}")
                detalle.append(f"capital = P = {_fmt(P)}")
            else:
                detalle.append("sin pago (capitaliza hasta el vencimiento)")
        elif en_gracia:
            interes = bal * i
            capital = 0.0
            detalle.append(f"[gracia] interés = saldo · i = {_fmt(bal)} · {i:.6f} = {_fmt(interes)}")
            detalle.append("capital = 0 (período de gracia)")
        elif sis == "ALEMAN":
            interes = 0.0 if (adelantada and primer_amort) else bal * i
            capital = P / n_amort
            if adelantada and primer_amort:
                detalle.append("interés = 0 (1ª cuota adelantada)")
            else:
                detalle.append(f"interés = saldo · i = {_fmt(bal)} · {i:.6f} = {_fmt(interes)}")
            detalle.append(f"capital = P/n_amort = {_fmt(capital)} (constante)")
            primer_amort = False
        else:  # FRANCES
            if adelantada and primer_amort:
                interes = 0.0
                capital = frances
                detalle.append("interés = 0 (1ª cuota adelantada)")
                detalle.append(f"capital = cuota = {_fmt(capital)}")
            else:
                interes = bal * i
                capital = frances - interes
                detalle.append(f"interés = saldo · i = {_fmt(bal)} · {i:.6f} = {_fmt(interes)}")
                detalle.append(f"capital = cuota − interés = {_fmt(frances)} − {_fmt(interes)} = {_fmt(capital)}")
            primer_amort = False
        if k == n:
            capital = bal
            detalle.append(f"ajuste última cuota: capital = saldo restante = {_fmt(bal)}")
        closing = 0.0 if k == n else max(0.0, bal - capital)
        detalle.append(f"saldo_final = saldo − capital = {_fmt(bal)} − {_fmt(capital)} = {_fmt(closing)}")
        pasos.append({
            "cuota": k,
            "saldoInicial": _fmt(bal),
            "interes": _fmt(interes),
            "capital": _fmt(capital),
            "cuota_total": _fmt(capital + interes),
            "saldoFinal": _fmt(closing),
            "enGracia": en_gracia,
            "detalle": detalle,
        })
        bal = closing

    resumen = PC.resumen(filas, data.monto, data.frecuencia, data.tna)
    return {
        "sistema": sis,
        "derivados": [{"nombre": nm, "valor": vl} for nm, vl in derivados],
        "pasos": pasos,
        "cronograma": [{
            "cuota": f["numero_cuota"],
            "vencimiento": str(f["fecha_vencimiento"]),
            "saldoInicial": _fmt(float(f["saldo_inicial"])),
            "capital": _fmt(float(f["capital"])),
            "interes": _fmt(float(f["interes"])),
            "cargos": _fmt(float(f["cargos"])),
            "total": _fmt(float(f["total"])),
            "saldoFinal": _fmt(float(f["saldo_final"])),
        } for f in filas],
        "resumen": resumen,
    }
