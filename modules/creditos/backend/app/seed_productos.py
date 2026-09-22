"""Semilla de la plataforma de productos de préstamo (Configurar Créditos).

Referencia (monedas, calculadores certificados, componentes, catálogo línea/grupo/familia)
+ 4 líneas de ejemplo con su versión. Re-ejecutable: no hace nada si ya está sembrado.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app import models_productos as m
from app.productos_componentes import COMPONENTES, COMPONENTES_ON, DEFAULT_CONFIG

CALCULADORES = [
    ("FRANCES", "Sistema francés"), ("ALEMAN", "Sistema alemán"),
    ("AMERICANO", "Sistema americano"), ("BULLET", "Pago único al vencimiento"),
]


def _componentes_default(defs: dict[str, m.PPComponenteDefinicion]) -> list[m.PPComponente]:
    out = []
    for cod in COMPONENTES_ON:
        d = defs[cod]
        out.append(m.PPComponente(componente_codigo=cod, orden=d.orden,
                                  requerido=d.requerido, activo=True,
                                  config=dict(DEFAULT_CONFIG.get(cod, {}))))
    return out


def seed_productos(db: Session) -> None:
    if db.query(m.PPLinea).first():
        return

    ars = m.PPMoneda(codigo_iso="ARS", nombre="Peso argentino", simbolo="$")
    usd = m.PPMoneda(codigo_iso="USD", nombre="Dólar estadounidense", simbolo="US$")
    db.add_all([ars, usd])

    calc_ver: dict[str, m.PPCalculadorVersion] = {}
    for cod, nom in CALCULADORES:
        c = m.PPCalculador(codigo=cod, nombre=nom)
        db.add(c); db.flush()
        cv = m.PPCalculadorVersion(calculador_id=c.id, numero_version=2,
                                   estado="PUBLICADO", checksum=f"cert-{cod.lower()}-v2")
        db.add(cv); db.flush()
        calc_ver[cod] = cv

    defs: dict[str, m.PPComponenteDefinicion] = {}
    for cod, nom, cat, multi, req, orden in COMPONENTES:
        d = m.PPComponenteDefinicion(codigo=cod, nombre=nom, categoria=cat,
                                     permite_multiples=multi, requerido=req, orden=orden)
        db.add(d); defs[cod] = d
    db.flush()

    linea = m.PPLinea(codigo="LENDING", nombre="Préstamos")
    db.add(linea); db.flush()
    grupos = {}
    for cod, nom in [("PERS", "Personales"), ("ESP", "Especiales"), ("HIP", "Hipotecarios")]:
        g = m.PPGrupo(linea_id=linea.id, codigo=cod, nombre=nom)
        db.add(g); grupos[nom] = g
    db.flush()
    familias = {}
    for grupo_nom, cod, nom in [
        ("Personales", "AGP", "Agente público"), ("Especiales", "JUB", "Jubilados"),
        ("Hipotecarios", "AGP-H", "Agente público"),
    ]:
        f = m.PPFamilia(grupo_id=grupos[grupo_nom].id, codigo=cod, nombre=nom)
        db.add(f); familias[(grupo_nom, nom)] = f
    db.flush()

    def crear(familia, codigo, nombre, numero, estado, sistema, tna, mora, cargo,
              monto_min, monto_max, plazo_min, plazo_max, base="ACT/365", modalidad="FIJA",
              enviado_por=None, publicado_por=None, disp=None, indice=None, margen=0):
        p = m.PPProducto(familia_id=familia.id, codigo=codigo, nombre=nombre)
        db.add(p); db.flush()
        v = m.PPVersion(
            producto_id=p.id, numero_version=numero, estado=estado, moneda_id=ars.id,
            calculador_version_id=calc_ver[sistema].id,
            monto_minimo=Decimal(str(monto_min)), monto_maximo=Decimal(str(monto_max)),
            plazo_minimo=plazo_min, plazo_maximo=plazo_max, base_dias=base,
            # una versión que estuvo/está publicada conserva su vigencia
            vigente_desde=date(2026, 1, 1) if estado in ("PUBLICADO", "RETIRADO") else None,
            vigente_hasta=date(2026, 6, 30) if estado == "RETIRADO" else None,
            enviado_por=enviado_por,
            publicado_por=publicado_por or ("admin" if estado in ("PUBLICADO", "RETIRADO") else None),
        )
        db.add(v); db.flush()
        db.add_all([
            m.PPTasa(producto_version_id=v.id, codigo="TNA", modalidad=modalidad, tasa_default=Decimal(str(tna)),
                     indice_referencia=(indice or ""), margen=Decimal(str(margen))),
            m.PPTasa(producto_version_id=v.id, codigo="MORA", modalidad="FIJA", tasa_default=Decimal(str(mora))),
            m.PPCargo(producto_version_id=v.id, codigo="OTORGAMIENTO", nombre="Cargo de otorgamiento", porcentaje=Decimal(str(cargo))),
        ])
        for comp in _componentes_default(defs):
            comp.producto_version_id = v.id
            db.add(comp)
        if disp is not None:  # Disponibilidad (Fase E): activa AVAILABILITY con reglas de segmentación
            d = defs["AVAILABILITY"]
            db.add(m.PPComponente(producto_version_id=v.id, componente_codigo="AVAILABILITY",
                                  orden=d.orden, requerido=d.requerido, activo=True,
                                  config={**DEFAULT_CONFIG["AVAILABILITY"], **disp}))
        return p

    pers = crear(familias[("Personales", "Agente público")], "LP-PERS-01", "Préstamo Personal Flexible",
          3, "PUBLICADO", "FRANCES", 52, 120, 2, 100000, 5000000, 6, 60,
          disp={"segmentos": ["AGENTE_PUBLICO", "DOCENTE", "MUNICIPAL"], "canales": ["SUCURSAL", "WEB", "APP"],
                "edadMin": 18, "edadMax": 65})
    crear(familias[("Personales", "Agente público")], "LP-ADEL-01", "Adelanto de Haberes",
          1, "EN_REVISION", "ALEMAN", 78, 120, 2, 100000, 800000, 6, 12, enviado_por="creditos")
    jub = crear(familias[("Especiales", "Jubilados")], "LP-JUB-01", "Crédito Jubilados Ley 5094",
          2, "PUBLICADO", "FRANCES", 41, 90, 2, 100000, 3000000, 6, 60,
          disp={"segmentos": ["JUBILADO", "PENSIONADO"], "canales": ["SUCURSAL", "CONVENIO"],
                "edadMin": 60, "edadMax": 90})
    crear(familias[("Hipotecarios", "Agente público")], "LP-VIV-01", "Vivienda Techo Propio (piloto)",
          1, "RETIRADO", "FRANCES", 33, 60, 2, 100000, 20000000, 12, 120)
    # Línea de tasa VARIABLE (BADLAR + margen) para demostrar repricing periódico (Fase G)
    crear(familias[("Personales", "Agente público")], "LP-VAR-01", "Crédito Tasa Variable (BADLAR)",
          1, "PUBLICADO", "FRANCES", 0, 90, 2, 100000, 4000000, 6, 48,
          modalidad="VARIABLE", indice="BADLAR", margen=10)

    # Bundle (Fase G): paquete que ofrece dos líneas juntas.
    b = m.PPBundle(codigo="BND-CAP-01", nombre="Paquete Créditos CaPreSCa",
                   descripcion="Préstamo personal + crédito para jubilados de la familia, ofrecidos juntos.")
    db.add(b); db.flush()
    db.add_all([
        m.PPBundleItem(bundle_id=b.id, producto_id=pers.id, rol="PRINCIPAL", obligatorio=True, orden=1),
        m.PPBundleItem(bundle_id=b.id, producto_id=jub.id, rol="COMPLEMENTO", obligatorio=False, orden=2),
    ])

    db.commit()
