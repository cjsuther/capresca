"""Catálogo de componentes (Property Classes) y su configuración por defecto.

Compartido por el seed y la API. Cada componente tiene atributos tipados que se guardan
como JSON en pp_producto_componente.config (equivalente a esquema_configuracion del modelo).
"""

# (codigo, nombre, categoria, permite_multiples, requerido, orden)
COMPONENTES = [
    ("TERM_AMOUNT", "Importe y plazo", "Límites", False, True, 1),
    ("INTEREST", "Intereses", "Pricing", True, True, 2),
    ("REPAYMENT_SCHEDULE", "Cronograma", "Amortización", False, True, 3),
    ("PAYMENT_RULES", "Reglas de pago", "Aplicación", False, False, 4),
    ("CHARGE", "Cargos", "Pricing", True, False, 5),
    ("TAX", "Impuestos", "Pricing", True, False, 6),
    ("OVERDUE", "Mora", "Riesgo", False, False, 7),
    ("PAYOFF", "Cancelación anticipada", "Servicing", False, False, 8),
    ("SETTLEMENT", "Liquidación", "Servicing", False, False, 9),
    ("ACCOUNTING", "Contabilidad", "Integración", False, False, 10),
    ("AVAILABILITY", "Disponibilidad", "Elegibilidad", False, False, 11),
    ("ACTIVITY_RESTRICTION", "Restricción de actividades", "Servicing", False, False, 12),
    ("PERIODIC", "Reglas periódicas", "Servicing", False, False, 13),
]

# Componentes activados por defecto al crear una versión nueva.
COMPONENTES_ON = ["TERM_AMOUNT", "INTEREST", "REPAYMENT_SCHEDULE", "PAYMENT_RULES",
                  "CHARGE", "TAX", "OVERDUE", "PAYOFF"]

# Configuración por defecto (atributos tipados) de cada componente.
DEFAULT_CONFIG: dict[str, dict] = {
    "TERM_AMOUNT": {},   # usa columnas core de la versión (montos/plazos/frecuencia)
    "INTEREST": {},      # usa calculador + tasa TNA
    "REPAYMENT_SCHEDULE": {"diaPago": 5, "primerVencimientoDias": 30,
                            "ajusteFinDeSemana": "SIGUIENTE_HABIL", "tipoCuota": "VENCIDA"},
    "PAYMENT_RULES": {"ordenImputacion": "MORA,INTERES,CAPITAL", "toleranciaDias": 3,
                       "permitePagoParcial": False, "permiteAdelanto": True},
    "CHARGE": {"momento": "DESEMBOLSO", "financiable": False,  # otorgamiento va en pp_producto_cargo
               "items": [{"etiqueta": "Cargo administrativo", "porcentaje": 1.5, "momento": "PRORRATEADO"}]},
    "TAX": {"items": [
        {"etiqueta": "IVA sobre interés", "base": "INTERES", "porcentaje": 21},
        {"etiqueta": "IVA sobre cargos", "base": "CARGOS", "porcentaje": 21},
        {"etiqueta": "Sellado", "base": "CUOTA", "porcentaje": 1.2}]},
    "OVERDUE": {"diasGracia": 5, "base": "CUOTA_VENCIDA", "capitaliza": False},  # TNA punitoria en tasa MORA
    "PAYOFF": {"permite": True, "penalidadPct": 0, "minCuotasPagadas": 3,
                "condonaInteresNoDevengado": True},
    "SETTLEMENT": {"generaLiquidacion": True, "remitirA": "TESORERIA"},
    "ACCOUNTING": {"cuentaCapital": "1.1.05.01", "cuentaInteres": "4.1.01",
                    "cuentaComision": "4.1.04", "cuentaIva": "2.1.07", "cuentaMora": "4.1.02",
                    "centroCosto": "CRED"},
    # `afectacionMaxPct`: cuánto del sueldo puede ocupar la cuota. Es el tope del crédito por línea
    # (antes estaba fijo en 30% en el código del portal).
    "AVAILABILITY": {"canales": ["SUCURSAL", "WEB"], "segmentos": ["AGENTE_PUBLICO"],
                      "edadMin": 18, "edadMax": 75, "antiguedadMinMeses": 0,
                      "afectacionMaxPct": 30,
                      "requiereGarante": False, "vigenteDesde": "", "vigenteHasta": ""},
    "ACTIVITY_RESTRICTION": {"permitePrepago": True, "permiteRenegociacion": True,
                              "permiteVacacionPago": False},
    "PERIODIC": {"repricingFrecuencia": "NINGUNA", "capitalizaInteres": False, "diaAplicacion": 1},
}
