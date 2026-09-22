"""API de Configurar Créditos — catálogo de líneas de producto (estilo Temenos AA).

Fase 3: persistencia del catálogo + versiones + pricing + componentes, con el ciclo de
vida de una línea (crear · modificar = nueva versión · revisar · publicar · retirar ·
reactivar). El cronograma se sigue calculando en el frontend (simulador en vivo).
"""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import configuraciones as config
from app.core.database import get_db
from app.core.numbering import crear_con_numero_unico
from app.core.idempotency import con_idempotencia
from sqlalchemy.exc import IntegrityError
from app.deps import get_current_user
from app import models, models_productos as m
from app.seed_productos import _componentes_default
from app.productos_componentes import COMPONENTES, DEFAULT_CONFIG
from app.services.productos_calc import cronograma, resumen

router = APIRouter(prefix="/api/creditos/productos", tags=["productos"],
                   dependencies=[Depends(get_current_user)])


# ---------------- permisos: SALEN de los ROLES efectivos (perfil + grupos), no de un perfil hardcodeado (H-150) ----------------
# Diseñar/editar/enviar = rol de operador de créditos; aprobar/publicar = rol aprobador (supervisor/admin).
# `caps_creditos` mira los roles efectivos (incluye los heredados de grupos): para habilitar a alguien se le
# asigna el rol/grupo en Seguridad, no un override puntual. Es la MISMA regla que usa el motor de workflow.
from app.core.permisos import caps_creditos


def _caps(db, user: models.Usuario) -> dict:
    return caps_creditos(db, user)


def _req_edita(db, user: models.Usuario):
    if not _caps(db, user)["edita"]:
        raise HTTPException(403, "No tenés permiso para diseñar/editar créditos (creditos:creditos:write). Se asigna en Seguridad de Portezuelo.")


def _req_aprueba(db, user: models.Usuario):
    if not _caps(db, user)["aprueba"]:
        raise HTTPException(403, "No tenés permiso de aprobación de créditos (creditos:aprobaciones:*). Se asigna en Seguridad de Portezuelo.")

DEFAULT_CFG = dict(sistema="FRANCES", modalidad="FIJA", tna=52, baseDias="ACT/365",
                   frecuencia="MENSUAL", montoMin=100000, montoMax=5000000,
                   plazoMin=6, plazoMax=60, graciaCapital=0, cargoOtorg=2, moraTNA=120)


class ComponenteIn(BaseModel):
    codigo: str
    activo: bool = True
    config: dict = {}
    heredado: bool = False


class ConfigIn(BaseModel):
    sistema: str; modalidad: str = "FIJA"; tna: float; baseDias: str = "ACT/365"
    frecuencia: str = "MENSUAL"; montoMin: float; montoMax: float
    plazoMin: int; plazoMax: int; graciaCapital: int = 0; cargoOtorg: float = 0; moraTNA: float = 0
    indice: str = ""; margen: float = 0
    tnaNegociable: bool = False; tnaMin: float = 0; tnaMax: float = 0
    vigenciaDesde: str = ""; vigenciaHasta: str = ""   # vigencia de ESTA versión (ISO date)
    cfgHeredada: bool = False
    componentes: list[ComponenteIn] | None = None


class AccionIn(BaseModel):
    accion: str  # revisar | publicar | retirar | reactivar


class CrearIn(BaseModel):
    nombre: str | None = None
    familia_id: str | None = None
    copiar_de: str | None = None   # clon independiente (snapshot)
    padre_id: str | None = None    # deriva heredando del padre (Fase D)


# ---------------- helpers ----------------
def _calc_codigo_por_version(db: Session) -> dict[str, str]:
    """calculador_version_id -> codigo del calculador (FRANCES, ALEMAN...)."""
    out = {}
    for cv, c in db.query(m.PPCalculadorVersion, m.PPCalculador).join(
            m.PPCalculador, m.PPCalculadorVersion.calculador_id == m.PPCalculador.id):
        out[cv.id] = c.codigo
    return out


def _calc_version_por_codigo(db: Session, codigo: str) -> m.PPCalculadorVersion:
    cv = (db.query(m.PPCalculadorVersion).join(m.PPCalculador)
          .filter(m.PPCalculador.codigo == codigo)
          .order_by(m.PPCalculadorVersion.numero_version.desc()).first())
    if not cv:
        raise HTTPException(422, f"Calculador desconocido: {codigo}")
    return cv


def _ultima(prod: m.PPProducto) -> m.PPVersion:
    return max(prod.versiones, key=lambda v: v.numero_version)


def _version_efectiva(prod: m.PPProducto) -> m.PPVersion:
    """Versión VIGENTE hoy: la PUBLICADA cuya vigencia (desde/hasta) incluye la fecha actual.

    Si hay varias, la de mayor número. Si ninguna publicada está vigente por fecha, la última
    publicada; si no hay ninguna publicada, la última existente. La usan la oferta, la
    originación y la herencia: una nueva versión aún no vigente (borrador o publicada a futuro)
    no reemplaza a la vigente."""
    hoy = date.today()
    vig = [v for v in prod.versiones if v.estado == "PUBLICADO"
           and (not v.vigente_desde or v.vigente_desde <= hoy)
           and (not v.vigente_hasta or v.vigente_hasta > hoy)]
    if vig:
        return max(vig, key=lambda v: v.numero_version)
    pubs = [v for v in prod.versiones if v.estado == "PUBLICADO"]
    return max(pubs, key=lambda v: v.numero_version) if pubs else _ultima(prod)


def _serial_efectivo(db: Session, prod: m.PPProducto, calc_map: dict[str, str]) -> dict:
    """Serializa la VERSIÓN VIGENTE del producto (para oferta/originación)."""
    return _serial_v(db, prod, _version_efectiva(prod), calc_map)


def _version_publicada_vigente(prod: m.PPProducto):
    """La versión ofrecible al ciudadano: sólo si está PUBLICADA y vigente HOY (sin el fallback
    de _version_efectiva). Fuente única para el portal y para marcar 'vigente en portal' en el
    catálogo del backoffice."""
    v = _version_efectiva(prod)
    hoy = date.today()
    ok = (v.estado == "PUBLICADO"
          and (not v.vigente_desde or v.vigente_desde <= hoy)
          and (not v.vigente_hasta or v.vigente_hasta > hoy))
    return v if ok else None


def _tasa(v: m.PPVersion, codigo: str) -> float:
    for t in v.tasas:
        if t.codigo == codigo:
            return float(t.tasa_default)
    return 0.0


def _tna_base(db: Session, v: m.PPVersion) -> float:
    """TNA efectiva base de la versión: `tasa_default` si es FIJA, `índice + margen` si es VARIABLE.

    Es la tasa ANTES de negociación/bonificación (que sólo aplica en la originación). Fuente única
    para que la simulación (prueba en vivo, portal) coincida con la originación en tasa variable."""
    tna_row = next((t for t in v.tasas if t.codigo == "TNA"), None)
    if tna_row and tna_row.modalidad == "VARIABLE":
        return (config.indice_valor(tna_row.indice_referencia) or 0.0) + float(tna_row.margen)
    return float(tna_row.tasa_default) if tna_row else _tasa(v, "TNA")


def _feriados_engine(db: Session, pais: str = "AR") -> set:
    """Feriados activos del país (módulo Configuraciones) para el ajuste a día hábil del cronograma."""
    from datetime import date as _d
    hoy = _d.today()
    return config.feriados(pais, _d(hoy.year - 1, 1, 1), _d(hoy.year + 15, 12, 31))


def _params_cronograma(v: m.PPVersion, feriados: set | None = None, decimales: int = 2) -> dict:
    """Extrae de la versión los parámetros del cronograma (única fuente de verdad).

    Sale de las columnas core y de los componentes activos REPAYMENT_SCHEDULE / CHARGE / TAX.
    Si se pasa `feriados` (del maestro), el ajuste a día hábil los saltea también. `decimales` es la
    precisión de redondeo de las cuotas (Parámetro de créditos DECIMALES_CALCULO). H-197.
    """
    comps = {c.componente_codigo: c for c in v.componentes if c.activo}
    rs = (comps["REPAYMENT_SCHEDULE"].config or {}) if "REPAYMENT_SCHEDULE" in comps else {}
    ch = (comps["CHARGE"].config or {}) if "CHARGE" in comps else {}
    tx = (comps["TAX"].config or {}) if "TAX" in comps else {}
    return {
        "feriados": feriados,
        "gracia": v.gracia_capital or 0,
        "frecuencia": v.frecuencia_pago or "MENSUAL",
        "cargos": [{"porcentaje": it.get("porcentaje"), "momento": it.get("momento")}
                   for it in (ch.get("items") or [])],
        "impuestos": [{"base": it.get("base"), "porcentaje": it.get("porcentaje")}
                      for it in (tx.get("items") or [])],
        "dia_pago": rs.get("diaPago", 5),
        "primer_venc_dias": rs.get("primerVencimientoDias", 30),
        "ajuste_fin_semana": rs.get("ajusteFinDeSemana", "SIN_AJUSTE"),
        "tipo_cuota": rs.get("tipoCuota", "VENCIDA"),
        "financiable": bool(ch.get("financiable", False)),
        "cargo_momento": ch.get("momento", "PRORRATEADO"),
        "decimales": decimales,
    }


def _cargo(v: m.PPVersion, codigo: str) -> float:
    for c in v.cargos:
        if c.codigo == codigo:
            return float(c.porcentaje)
    return 0.0


# ---------------- disponibilidad / segmentación (Fase E) ----------------
SEGMENTOS_CATALOGO = ["AGENTE_PUBLICO", "JUBILADO", "PENSIONADO", "DOCENTE", "MUNICIPAL", "CONTRATADO", "LIBRE"]
# Catálogo de canales y códigos de canal por defecto. El catálogo REAL y qué código corresponde a cada
# contexto (portal / backoffice) son CONFIGURABLES en Parámetros (H-185): la API no hardcodea "WEB" ni
# "SUCURSAL", los lee de la tabla `parametros` (claves CANALES / CANAL_PORTAL / CANAL_BACKOFFICE), que se
# siembran al arrancar y se editan en Controles → Parámetros. Estas constantes son sólo el fallback.
CANALES_CATALOGO = ["SUCURSAL", "WEB", "APP", "CONVENIO"]
CANAL_PORTAL_DEFAULT = "WEB"
CANAL_BACKOFFICE_DEFAULT = "SUCURSAL"


def _param_obligatorio(db: Session, clave: str) -> str:
    """Lee un parámetro de configuración OBLIGATORIO. H-185: los parámetros de canal se siembran al
    arrancar; si faltan (alguien los borró) la API falla fuerte con un mensaje claro, en vez de asumir
    un default silencioso que podría abrir un canal por error."""
    p = db.query(models.Parametro).filter(models.Parametro.clave == clave).first()
    if not p or not (p.valor or "").strip():
        raise HTTPException(500, f"Falta el parámetro de configuración obligatorio '{clave}'. "
                                 f"Cargalo en Controles → Parámetros generales.")
    return p.valor.strip()


def canales_catalogo(db: Session) -> list[str]:
    """Catálogo de canales habilitados (Parámetro CANALES, coma-separado). Obligatorio."""
    return [c.strip().upper() for c in _param_obligatorio(db, "CANALES").split(",") if c.strip()]


def canal_portal(db: Session) -> str:
    """Código de canal que habilita el portal del ciudadano (Parámetro CANAL_PORTAL). Obligatorio."""
    return _param_obligatorio(db, "CANAL_PORTAL").upper()


def canal_backoffice(db: Session) -> str:
    """Canal por defecto al originar desde el backoffice sin canal explícito (CANAL_BACKOFFICE). Obligatorio."""
    return _param_obligatorio(db, "CANAL_BACKOFFICE").upper()


DECIMALES_CALCULO_DEFAULT = 2   # decimales de redondeo del cálculo de la cuota (0–6)
DECIMALES_MOSTRAR_DEFAULT = 2    # decimales con que se MUESTRAN los importes en pantalla (0–6)

# Parámetros del ámbito CRÉDITOS (H-197/H-198): canales + decimales de cálculo y de visualización.
CREDITOS_PARAMS_DEFAULT = [
    ("CANALES", ",".join(CANALES_CATALOGO), "Catálogo de canales de venta habilitados (coma-separado)."),
    ("CANAL_PORTAL", CANAL_PORTAL_DEFAULT, "Código de canal habilitado en el portal del ciudadano (solo web)."),
    ("CANAL_BACKOFFICE", CANAL_BACKOFFICE_DEFAULT, "Canal asumido al originar desde el backoffice sin canal explícito."),
    ("DECIMALES_CALCULO", str(DECIMALES_CALCULO_DEFAULT), "Decimales para el REDONDEO del cálculo de las cuotas (0–6)."),
    ("DECIMALES_MOSTRAR", str(DECIMALES_MOSTRAR_DEFAULT), "Decimales con que se MUESTRAN los importes de créditos en pantalla (0–6)."),
]


def _decimales_param(db: Session, clave: str, default: int) -> int:
    p = db.query(models.Parametro).filter(models.Parametro.clave == clave).first()
    try:
        return max(0, min(6, int((p.valor if p else str(default)) or default)))
    except (TypeError, ValueError):
        return default


def decimales_calculo(db: Session) -> int:
    """Decimales de redondeo para el CÁLCULO de préstamos (Parámetro DECIMALES_CALCULO). H-197."""
    return _decimales_param(db, "DECIMALES_CALCULO", DECIMALES_CALCULO_DEFAULT)


def decimales_mostrar(db: Session) -> int:
    """Decimales con que se MUESTRAN los importes de créditos en pantalla (Parámetro DECIMALES_MOSTRAR). H-198."""
    return _decimales_param(db, "DECIMALES_MOSTRAR", DECIMALES_MOSTRAR_DEFAULT)


def seed_canales_parametros(db: Session) -> None:
    """Siembra los parámetros del ámbito CRÉDITOS si faltan (idempotente): canales + decimales de cálculo.
    Se editan en Créditos → Parámetros de créditos."""
    for clave, valor, desc in CREDITOS_PARAMS_DEFAULT:
        if not db.query(models.Parametro).filter(models.Parametro.clave == clave).first():
            db.add(models.Parametro(clave=clave, valor=valor, descripcion=desc, ambito="creditos"))
    db.commit()

# ---------------- relationship pricing (Fase G) ----------------
# Bonificación de TNA (en puntos, negativa = descuento) según la relación integral del cliente.
RELACION_PRICING = {"ESTANDAR": 0.0, "PREFERENCIAL": -2.0, "PREMIUM": -4.0}


def _bonus_relacion(relacion: str | None) -> float:
    return RELACION_PRICING.get((relacion or "ESTANDAR").upper(), 0.0)


def _contab_cfg(v: m.PPVersion) -> dict:
    """Config contable (componente ACCOUNTING) resuelta sobre los valores por defecto."""
    row = next((c for c in v.componentes if c.componente_codigo == "ACCOUNTING"), None)
    base = dict(DEFAULT_CONFIG.get("ACCOUNTING", {}))
    if row and row.config:
        base.update(row.config)
    return base


def _lista(v) -> list[str]:
    """Normaliza segmentos/canales: acepta lista o string separado por comas."""
    if isinstance(v, list):
        return [str(x).strip().upper() for x in v if str(x).strip()]
    if isinstance(v, str):
        return [x.strip().upper() for x in v.split(",") if x.strip()]
    return []


def _disponibilidad(v: m.PPVersion) -> dict | None:
    """Config de disponibilidad (AVAILABILITY) normalizada, o None si el componente está inactivo."""
    row = next((c for c in v.componentes if c.componente_codigo == "AVAILABILITY"), None)
    if not row or not row.activo:
        return None
    cfg = row.config or {}
    return {
        "segmentos": _lista(cfg.get("segmentos")),
        "canales": _lista(cfg.get("canales")),
        "edadMin": cfg.get("edadMin") or None,
        "edadMax": cfg.get("edadMax") or None,
        "antiguedadMinMeses": cfg.get("antiguedadMinMeses") or None,
        "requiereGarante": bool(cfg.get("requiereGarante", False)),
        "vigenteDesde": cfg.get("vigenteDesde") or "",
        "vigenteHasta": cfg.get("vigenteHasta") or "",
    }


def _elegibilidad(disp: dict | None, ctx: dict) -> dict:
    """Evalúa si un solicitante (ctx) es elegible según la disponibilidad del producto.

    Las reglas por atributo del solicitante (segmento/canal/edad/antigüedad) sólo se
    aplican si ese dato viene en ctx; la vigencia se evalúa siempre.
    """
    if not disp:
        return {"elegible": True, "motivos": []}
    motivos: list[str] = []
    hoy = ctx.get("fecha") or date.today().isoformat()
    if disp["vigenteDesde"] and hoy < disp["vigenteDesde"]:
        motivos.append(f"Aún no vigente (desde {disp['vigenteDesde']}).")
    if disp["vigenteHasta"] and hoy > disp["vigenteHasta"]:
        motivos.append(f"Vigencia expirada ({disp['vigenteHasta']}).")
    seg = ctx.get("segmento")
    if disp["segmentos"] and seg and seg.upper() not in disp["segmentos"]:
        motivos.append(f"Segmento {seg} no habilitado (permitidos: {', '.join(disp['segmentos'])}).")
    can = ctx.get("canal")
    if disp["canales"] and can and can.upper() not in disp["canales"]:
        motivos.append(f"Canal {can} no habilitado (permitidos: {', '.join(disp['canales'])}).")
    edad = ctx.get("edad")
    if edad is not None:
        if disp["edadMin"] and edad < disp["edadMin"]:
            motivos.append(f"Edad mínima {disp['edadMin']} (solicitante {edad}).")
        if disp["edadMax"] and edad > disp["edadMax"]:
            motivos.append(f"Edad máxima {disp['edadMax']} (solicitante {edad}).")
    ant = ctx.get("antiguedad_meses")
    if ant is not None and disp["antiguedadMinMeses"] and ant < disp["antiguedadMinMeses"]:
        motivos.append(f"Antigüedad mínima {disp['antiguedadMinMeses']} meses (solicitante {ant}).")
    return {"elegible": not motivos, "motivos": motivos}


def _componentes_serial(v: m.PPVersion) -> list[dict]:
    """Todos los componentes del catálogo, marcando cuáles están activos en la versión."""
    rows = {c.componente_codigo: c for c in v.componentes}
    out = []
    for cod, nom, cat, multi, req, orden in COMPONENTES:
        r = rows.get(cod)
        out.append({
            "codigo": cod, "nombre": nom, "categoria": cat, "multiple": multi,
            "requerido": req, "orden": orden,
            "activo": bool(r) and r.activo,
            "config": (r.config if r and r.config else dict(DEFAULT_CONFIG.get(cod, {}))),
            "heredado": bool(r) and r.heredado,
        })
    return out


def _serial_v(db: Session, prod: m.PPProducto, v: m.PPVersion, calc_map: dict[str, str]) -> dict:
    fam = db.get(m.PPFamilia, prod.familia_id)
    grp = db.get(m.PPGrupo, fam.grupo_id) if fam else None
    tna_mod = next((t.modalidad for t in v.tasas if t.codigo == "TNA"), "FIJA")
    tna_def = _tasa(v, "TNA")
    _ind_cod = next((t.indice_referencia for t in v.tasas if t.codigo == "TNA"), "")
    _margen = next((float(t.margen) for t in v.tasas if t.codigo == "TNA"), 0.0)
    if tna_mod == "VARIABLE" and _ind_cod:
        tna_vigente = round((config.indice_valor(_ind_cod) or 0.0) + _margen, 4)
    else:
        tna_vigente = tna_def
    publicadas = sorted({x.numero_version for x in prod.versiones if x.estado == "PUBLICADO"})
    base = {
        "componentes": _componentes_serial(v),
        "id": prod.id, "nombre": prod.nombre, "codigo": prod.codigo,
        "grupo": grp.nombre if grp else "", "familia": fam.nombre if fam else "",
        "version": v.numero_version, "estado": v.estado,
        "derivadaDe": v.derivada_de, "publicadas": publicadas,
        "enviadoPor": v.enviado_por, "aprobadoPor": v.aprobado_por, "publicadoPor": v.publicado_por,
        "cfg": {
            "sistema": calc_map.get(v.calculador_version_id, "FRANCES"),
            "modalidad": tna_mod, "tna": tna_def, "tnaVigente": tna_vigente, "baseDias": v.base_dias,
            "frecuencia": v.frecuencia_pago, "montoMin": float(v.monto_minimo),
            "montoMax": float(v.monto_maximo), "plazoMin": v.plazo_minimo,
            "plazoMax": v.plazo_maximo, "graciaCapital": v.gracia_capital,
            "cargoOtorg": _cargo(v, "OTORGAMIENTO"), "moraTNA": _tasa(v, "MORA"),
            "indice": next((t.indice_referencia for t in v.tasas if t.codigo == "TNA"), ""),
            "margen": next((float(t.margen) for t in v.tasas if t.codigo == "TNA"), 0.0),
            "tnaNegociable": next((t.negociable for t in v.tasas if t.codigo == "TNA"), False),
            "tnaMin": next((float(t.tasa_minima) for t in v.tasas if t.codigo == "TNA"), 0.0),
            "tnaMax": next((float(t.tasa_maxima) for t in v.tasas if t.codigo == "TNA"), 0.0),
            "vigenciaDesde": str(v.vigente_desde) if v.vigente_desde else "",
            "vigenciaHasta": str(v.vigente_hasta) if v.vigente_hasta else "",
        },
        "cfgHeredada": v.cfg_heredada, "padre": None,
        "disponibilidad": _disponibilidad(v),
    }
    # Herencia (Fase D): resolver condiciones heredadas desde el padre (recursivo, 1..n niveles).
    # Se hereda de la versión EFECTIVA del padre (la publicada), no de un borrador en curso.
    if prod.padre_id:
        padre = db.get(m.PPProducto, prod.padre_id)
        if padre:
            base["padre"] = {"id": padre.id, "codigo": padre.codigo, "nombre": padre.nombre}
            pres = _serial_v(db, padre, _version_efectiva(padre), calc_map)  # padre resuelto (versión efectiva)
            if v.cfg_heredada:
                base["cfg"] = pres["cfg"]
            pcomp = {c["codigo"]: c for c in pres["componentes"]}
            for c in base["componentes"]:
                if c["heredado"] and c["codigo"] in pcomp:
                    c["activo"] = pcomp[c["codigo"]]["activo"]
                    c["config"] = pcomp[c["codigo"]]["config"]
    return base


def _serial(db: Session, prod: m.PPProducto, calc_map: dict[str, str]) -> dict:
    # La tarjeta del catálogo muestra la ÚLTIMA versión; además marca qué versión está
    # vigente HOY en el portal (puede ser una anterior, si la última está en revisión).
    base = _serial_v(db, prod, _ultima(prod), calc_map)
    vig = _version_publicada_vigente(prod)
    base["vigentePortal"] = vig.numero_version if vig else None
    # H-190: origen de la copia (para el prompt "¿retirar el original?" al publicar y trazabilidad).
    base["copiadoDe"] = None
    if getattr(prod, "copiado_de", None):
        src = db.get(m.PPProducto, prod.copiado_de)
        if src:
            base["copiadoDe"] = {"id": src.id, "codigo": src.codigo, "nombre": src.nombre,
                                 "publicado": any(x.estado == "PUBLICADO" for x in src.versiones)}
    return base


def _aplicar_cfg(db: Session, v: m.PPVersion, cfg: dict) -> None:
    v.calculador_version_id = _calc_version_por_codigo(db, cfg["sistema"]).id
    v.base_dias = cfg["baseDias"]; v.frecuencia_pago = cfg["frecuencia"]
    v.monto_minimo = Decimal(str(cfg["montoMin"])); v.monto_maximo = Decimal(str(cfg["montoMax"]))
    v.plazo_minimo = int(cfg["plazoMin"]); v.plazo_maximo = int(cfg["plazoMax"])
    v.gracia_capital = int(cfg["graciaCapital"])
    vd, vh = cfg.get("vigenciaDesde") or "", cfg.get("vigenciaHasta") or ""
    v.vigente_desde = date.fromisoformat(vd) if vd else v.vigente_desde
    v.vigente_hasta = date.fromisoformat(vh) if vh else None
    for t in v.tasas:
        if t.codigo == "TNA":
            t.tasa_default = Decimal(str(cfg["tna"])); t.modalidad = cfg["modalidad"]
            t.indice_referencia = cfg.get("indice", ""); t.margen = Decimal(str(cfg.get("margen", 0)))
            t.negociable = bool(cfg.get("tnaNegociable", False))
            t.tasa_minima = Decimal(str(cfg.get("tnaMin", 0))); t.tasa_maxima = Decimal(str(cfg.get("tnaMax", 0)))
        elif t.codigo == "MORA":
            t.tasa_default = Decimal(str(cfg["moraTNA"]))
    for c in v.cargos:
        if c.codigo == "OTORGAMIENTO":
            c.porcentaje = Decimal(str(cfg["cargoOtorg"]))


_REQUERIDOS = {cod for cod, _, _, _, req, _ in COMPONENTES if req}
_ORDEN = {cod: orden for cod, _, _, _, _, orden in COMPONENTES}


def _aplicar_componentes(db: Session, v: m.PPVersion, comps: list[dict]) -> None:
    rows = {c.componente_codigo: c for c in v.componentes}
    for comp in comps:
        cod = comp["codigo"]
        activo = comp.get("activo", True) or cod in _REQUERIDOS
        cfg = comp.get("config") or {}
        hered = bool(comp.get("heredado", False))
        r = rows.get(cod)
        if activo:
            if r:
                r.activo = True; r.config = cfg; r.heredado = hered
            else:
                db.add(m.PPComponente(producto_version_id=v.id, componente_codigo=cod,
                                      orden=_ORDEN.get(cod, 99), requerido=cod in _REQUERIDOS,
                                      activo=True, config=cfg, heredado=hered))
        elif r:
            db.delete(r)


# ---------------- endpoints ----------------
@router.get("")
def catalogo(db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    calc_map = _calc_codigo_por_version(db)
    prods = db.query(m.PPProducto).all()
    items = sorted((_serial(db, p, calc_map) for p in prods), key=lambda x: x["nombre"])
    return {"items": items, "total": len(items), "permisos": _caps(db, user), "usuario": user.username}


@router.get("/_familias")
def familias(db: Session = Depends(get_db)):
    out = []
    for f in db.query(m.PPFamilia).all():
        g = db.get(m.PPGrupo, f.grupo_id)
        out.append({"id": f.id, "nombre": f.nombre, "grupo": g.nombre if g else ""})
    return {"items": out}


@router.get("/_modelo")
def modelo():
    """Modelo de datos de la plataforma (tablas pp_* y sus columnas) — inspector."""
    tablas = []
    for t in sorted(m.Base.metadata.sorted_tables, key=lambda x: x.name):
        if not t.name.startswith("pp_"):
            continue
        cols = []
        for c in t.columns:
            fk = next(iter(c.foreign_keys), None)
            cols.append({"nombre": c.name, "tipo": str(c.type),
                         "pk": c.primary_key, "nullable": c.nullable,
                         "fk": str(fk.column) if fk else None})
        tablas.append({"tabla": t.name, "columnas": cols})
    return {"tablas": tablas, "total": len(tablas)}


@router.get("/{producto_id}")
def obtener(producto_id: str, db: Session = Depends(get_db)):
    prod = db.get(m.PPProducto, producto_id)
    if not prod:
        raise HTTPException(404, "Producto no encontrado")
    return _serial(db, prod, _calc_codigo_por_version(db))


@router.get("/{producto_id}/versiones")
def versiones(producto_id: str, db: Session = Depends(get_db)):
    """Todas las versiones de la línea (para historial y comparación)."""
    prod = db.get(m.PPProducto, producto_id)
    if not prod:
        raise HTTPException(404, "Producto no encontrado")
    calc_map = _calc_codigo_por_version(db)
    items = [_serial_v(db, prod, v, calc_map) for v in sorted(prod.versiones, key=lambda x: x.numero_version)]
    return {"items": items, "total": len(items)}


@router.get("/{producto_id}/raw")
def raw(producto_id: str, db: Session = Depends(get_db)):
    """Filas crudas persistidas del producto (inspector de datos)."""
    prod = db.get(m.PPProducto, producto_id)
    if not prod:
        raise HTTPException(404, "Producto no encontrado")

    def row(o, cols):
        return {c: (str(getattr(o, c)) if not isinstance(getattr(o, c), (int, float, bool, dict, type(None))) else getattr(o, c)) for c in cols}

    versiones = []
    for v in sorted(prod.versiones, key=lambda x: x.numero_version):
        versiones.append({
            "pp_producto_version": row(v, ["id", "numero_version", "estado", "derivada_de",
                "monto_minimo", "monto_maximo", "plazo_minimo", "plazo_maximo", "frecuencia_pago",
                "base_dias", "gracia_capital", "vigente_desde", "vigente_hasta",
                "enviado_por", "aprobado_por", "publicado_por"]),
            "pp_producto_tasa": [row(t, ["codigo", "modalidad", "tasa_default"]) for t in v.tasas],
            "pp_producto_cargo": [row(c, ["codigo", "porcentaje", "momento_aplicacion"]) for c in v.cargos],
            "pp_producto_componente": [row(c, ["componente_codigo", "activo", "orden", "config"])
                                        for c in sorted(v.componentes, key=lambda x: x.orden)],
        })
    return {"pp_producto": row(prod, ["id", "codigo", "nombre", "familia_id"]),
            "versiones": versiones}


class PreviewIn(BaseModel):
    sistema: str = "FRANCES"
    monto: float
    plazo: int
    tna: float
    cargoOtorg: float = 0
    gracia: int = 0
    frecuencia: str = "MENSUAL"
    cargos: list[dict] = []
    impuestos: list[dict] = []
    diaPago: int = 5
    primerVencimientoDias: int = 30
    ajusteFinDeSemana: str = "SIN_AJUSTE"
    tipoCuota: str = "VENCIDA"
    financiable: bool = False
    cargoMomento: str = "PRORRATEADO"


def _cronograma_serial(filas: list[dict]) -> list[dict]:
    return [{
        "numero_cuota": f["numero_cuota"], "fecha_vencimiento": str(f["fecha_vencimiento"]),
        "saldo_inicial": float(f["saldo_inicial"]), "capital": float(f["capital"]),
        "interes": float(f["interes"]), "cargos": float(f["cargos"]),
        "impuestos": float(f.get("impuestos", 0)), "total": float(f["total"]),
        "saldo_final": float(f["saldo_final"]),
    } for f in filas]


@router.post("/preview")
def preview(data: PreviewIn, db: Session = Depends(get_db)):
    """Cronograma + resumen de un escenario (única fuente de verdad, sin persistir).

    Lo consume la prueba en vivo de Configurar Créditos; usa el MISMO `cronograma` que la
    originación y la simulación persistida, así el preview coincide con el contrato real.
    """
    filas = cronograma(
        data.sistema, data.monto, data.plazo, data.tna, data.cargoOtorg, date.today(),
        gracia=data.gracia, frecuencia=data.frecuencia, cargos=data.cargos, impuestos=data.impuestos,
        dia_pago=data.diaPago, primer_venc_dias=data.primerVencimientoDias,
        ajuste_fin_semana=data.ajusteFinDeSemana, tipo_cuota=data.tipoCuota,
        financiable=data.financiable, cargo_momento=data.cargoMomento,
        feriados=_feriados_engine(db))
    return {"rows": _cronograma_serial(filas), "resumen": resumen(filas, data.monto, data.frecuencia, data.tna)}


class SimularIn(BaseModel):
    monto: float
    plazo: int
    tna: float | None = None       # override opcional (escenario negociado)
    etiqueta: str = ""


def _serial_sim(s: m.PPSimulacion, prod: m.PPProducto | None = None) -> dict:
    return {
        "id": s.id, "producto_id": s.producto_id, "version": s.producto_version_numero,
        "etiqueta": s.etiqueta, "sistema": s.sistema, "monto": float(s.monto), "plazo": s.plazo,
        "tna": float(s.tna), "cargoPct": float(s.cargo_pct),
        "totalCuotas": float(s.total_cuotas), "totalInteres": float(s.total_interes),
        "primeraCuota": float(s.primera_cuota), "creadoPor": s.creado_por,
        "creadoEn": s.creado_en.isoformat() if s.creado_en else None,
        "producto": (prod.nombre if prod else None), "codigo": (prod.codigo if prod else None),
        "cuotas": [{
            "numero_cuota": q.numero_cuota, "fecha_vencimiento": str(q.fecha_vencimiento),
            "saldo_inicial": float(q.saldo_inicial), "capital": float(q.capital),
            "interes": float(q.interes), "cargos": float(q.cargos), "total": float(q.total),
            "saldo_final": float(q.saldo_final),
        } for q in sorted(s.cuotas, key=lambda x: x.numero_cuota)],
    }


class SimPreviewIn(BaseModel):
    monto: float
    plazo: int
    segmento: str | None = None
    canal: str | None = None
    edad: int | None = None
    antiguedad_meses: int | None = None


@router.post("/{producto_id}/simular-preview")
def simular_preview(producto_id: str, data: SimPreviewIn, db: Session = Depends(get_db),
                    user: models.Usuario = Depends(get_current_user)):
    """Cronograma + cuota + elegibilidad de un escenario SIN persistir (para el alta guiada de
    solicitudes en el backoffice, H-136). Mismo motor que la simulación persistida y la originación."""
    prod = db.get(m.PPProducto, producto_id)
    if not prod:
        raise HTTPException(404, "Producto no encontrado")
    v = _ultima(prod)
    if not (float(v.monto_minimo) <= data.monto <= float(v.monto_maximo)):
        raise HTTPException(422, f"Monto fuera de rango ({float(v.monto_minimo):.0f}–{float(v.monto_maximo):.0f}).")
    if not (v.plazo_minimo <= data.plazo <= v.plazo_maximo):
        raise HTTPException(422, f"Plazo fuera de rango ({v.plazo_minimo}–{v.plazo_maximo}).")
    sistema = _calc_codigo_por_version(db).get(v.calculador_version_id, "FRANCES")
    tna = _tna_base(db, v)
    cargo = _cargo(v, "OTORGAMIENTO")
    filas = cronograma(sistema, data.monto, data.plazo, tna, cargo, date.today(),
                       **_params_cronograma(v, _feriados_engine(db), decimales_calculo(db)))
    total = sum(float(f["total"]) for f in filas)
    ctx = {"segmento": data.segmento, "canal": data.canal, "edad": data.edad, "antiguedad_meses": data.antiguedad_meses}
    elig = _elegibilidad(_disponibilidad(v), ctx)
    return {
        "sistema": sistema, "tna": tna, "monto": data.monto, "plazo": data.plazo,
        "cantidadCuotas": len(filas), "totalCuotas": round(total, 2),
        "totalInteres": round(sum(float(f["interes"]) for f in filas), 2),
        "primeraCuota": round(float(filas[0]["total"]), 2),
        "cuotaPromedio": round(total / len(filas), 2) if filas else 0.0,
        "elegible": elig["elegible"], "motivos": elig["motivos"],
        "cuotas": [{"numero_cuota": f["numero_cuota"], "fecha_vencimiento": str(f["fecha_vencimiento"]),
                    "capital": round(float(f["capital"]), 2), "interes": round(float(f["interes"]), 2),
                    "total": round(float(f["total"]), 2)} for f in filas],
    }


@router.post("/{producto_id}/simulaciones", status_code=201)
def crear_simulacion(producto_id: str, data: SimularIn, db: Session = Depends(get_db),
                     user: models.Usuario = Depends(get_current_user)):
    """Calcula el cronograma de un escenario y lo persiste (trazabilidad de simulaciones)."""
    prod = db.get(m.PPProducto, producto_id)
    if not prod:
        raise HTTPException(404, "Producto no encontrado")
    v = _ultima(prod)
    if not (float(v.monto_minimo) <= data.monto <= float(v.monto_maximo)):
        raise HTTPException(422, f"Monto fuera de rango ({float(v.monto_minimo):.0f}–{float(v.monto_maximo):.0f}).")
    if not (v.plazo_minimo <= data.plazo <= v.plazo_maximo):
        raise HTTPException(422, f"Plazo fuera de rango ({v.plazo_minimo}–{v.plazo_maximo}).")
    calc_map = _calc_codigo_por_version(db)
    sistema = calc_map.get(v.calculador_version_id, "FRANCES")
    tna = data.tna if data.tna is not None else _tna_base(db, v)   # variable = índice + margen
    cargo = _cargo(v, "OTORGAMIENTO")
    filas = cronograma(sistema, data.monto, data.plazo, tna, cargo, date.today(),
                       **_params_cronograma(v, _feriados_engine(db), decimales_calculo(db)))
    total_cuotas = sum(f["total"] for f in filas)
    total_interes = sum(f["interes"] for f in filas)
    s = m.PPSimulacion(
        producto_id=prod.id, producto_version_numero=v.numero_version,
        etiqueta=(data.etiqueta or "").strip(), sistema=sistema,
        monto=Decimal(str(data.monto)), plazo=data.plazo, tna=Decimal(str(tna)),
        cargo_pct=Decimal(str(cargo)), total_cuotas=Decimal(str(total_cuotas)),
        total_interes=Decimal(str(total_interes)), primera_cuota=Decimal(str(filas[0]["total"])),
        creado_por=user.username)
    db.add(s); db.flush()
    for f in filas:
        db.add(m.PPCuotaSimulada(
            simulacion_id=s.id, numero_cuota=f["numero_cuota"], fecha_vencimiento=f["fecha_vencimiento"],
            saldo_inicial=f["saldo_inicial"], capital=f["capital"], interes=f["interes"],
            cargos=f["cargos"], total=f["total"], saldo_final=f["saldo_final"]))
    db.commit()
    return _serial_sim(s, prod)


@router.get("/{producto_id}/simulaciones")
def listar_simulaciones(producto_id: str, db: Session = Depends(get_db)):
    prod = db.get(m.PPProducto, producto_id)
    if not prod:
        raise HTTPException(404, "Producto no encontrado")
    sims = db.query(m.PPSimulacion).filter_by(producto_id=producto_id).order_by(
        m.PPSimulacion.creado_en.desc()).all()
    return {"items": [_serial_sim(s, prod) for s in sims], "total": len(sims)}


@router.delete("/{producto_id}/simulaciones/{sim_id}")
def borrar_simulacion(producto_id: str, sim_id: str, db: Session = Depends(get_db),
                      user: models.Usuario = Depends(get_current_user)):
    s = db.get(m.PPSimulacion, sim_id)
    if not s or s.producto_id != producto_id:
        raise HTTPException(404, "Simulación no encontrada")
    db.delete(s); db.commit()
    return {"ok": True}


@router.post("", status_code=201)
def crear(data: CrearIn, db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user),
          idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    _req_edita(db, user)
    # Idempotencia: un reintento con la misma clave no crea dos líneas.
    return con_idempotencia(db, idempotency_key, "POST /api/productos",
                            lambda: _crear_impl(db, data, user), user.username)


def _crear_impl(db: Session, data: CrearIn, user) -> dict:
    padre = db.get(m.PPProducto, data.padre_id) if data.padre_id else None
    fuente = padre or (db.get(m.PPProducto, data.copiar_de) if data.copiar_de else None)
    if data.familia_id:
        fam = db.get(m.PPFamilia, data.familia_id)
    elif fuente:
        fam = db.get(m.PPFamilia, fuente.familia_id)
    else:
        fam = (db.query(m.PPFamilia).filter(m.PPFamilia.nombre == "Agente público").first()
               or db.query(m.PPFamilia).first())
    if not fam:
        raise HTTPException(500, "Catálogo no sembrado")
    # Código único: primer LP-NUEVA-NN libre. Usar el total de productos como sufijo colisiona
    # cuando se crearon/borraron líneas antes (la constraint pp_producto_codigo_key es única).
    def _codigo_libre() -> str:
        usados = {c for (c,) in db.query(m.PPProducto.codigo)
                  .filter(m.PPProducto.codigo.like("LP-NUEVA-%")).all()}
        n = 1
        while f"LP-NUEVA-{n:02d}" in usados:
            n += 1
        return f"LP-NUEVA-{n:02d}"

    def _mk_prod(codigo: str) -> m.PPProducto:
        p = m.PPProducto(familia_id=fam.id, padre_id=(padre.id if padre else None), codigo=codigo,
                         # H-190/H-201: si es una copia (Duplicar), recordá de qué producto salió sólo para
                         # TRAZABILIDAD/linaje. Una copia es un préstamo independiente: publicarla NO retira el
                         # original (ambos coexisten). La derivación (padre) es otra cosa.
                         copiado_de=(data.copiar_de if data.copiar_de else None),
                         nombre=data.nombre or (f"{fuente.nombre} ({'derivado' if padre else 'copia'})" if fuente else "Nueva línea de crédito"))
        db.add(p)
        return p
    # Código único aun con dos usuarios creando líneas a la vez (reintenta ante colisión).
    prod = crear_con_numero_unico(db, _codigo_libre, _mk_prod)
    ars = db.query(m.PPMoneda).filter(m.PPMoneda.codigo_iso == "ARS").first()

    if fuente:  # clonar la última versión de la fuente (plantilla o padre)
        src = _ultima(fuente)
        v = m.PPVersion(
            producto_id=prod.id, numero_version=1, estado="BORRADOR", moneda_id=src.moneda_id,
            calculador_version_id=src.calculador_version_id,
            monto_minimo=src.monto_minimo, monto_maximo=src.monto_maximo,
            plazo_minimo=src.plazo_minimo, plazo_maximo=src.plazo_maximo,
            unidad_plazo=src.unidad_plazo, frecuencia_pago=src.frecuencia_pago,
            base_dias=src.base_dias, regla_feriados=src.regla_feriados,
            gracia_capital=src.gracia_capital, gracia_interes=src.gracia_interes,
            permite_prepago=src.permite_prepago, cfg_heredada=bool(padre))
        db.add(v); db.flush()
        for t in src.tasas:
            db.add(m.PPTasa(producto_version_id=v.id, codigo=t.codigo, modalidad=t.modalidad,
                            tasa_default=t.tasa_default, indice_referencia=t.indice_referencia, margen=t.margen,
                            tasa_minima=t.tasa_minima, tasa_maxima=t.tasa_maxima, negociable=t.negociable))
        for c in src.cargos:
            db.add(m.PPCargo(producto_version_id=v.id, codigo=c.codigo, nombre=c.nombre, porcentaje=c.porcentaje, momento_aplicacion=c.momento_aplicacion))
        for comp in src.componentes:
            db.add(m.PPComponente(producto_version_id=v.id, componente_codigo=comp.componente_codigo,
                                  orden=comp.orden, requerido=comp.requerido, activo=comp.activo,
                                  config=dict(comp.config or {}), heredado=bool(padre)))
    else:  # línea en blanco con valores por defecto
        cv = _calc_version_por_codigo(db, DEFAULT_CFG["sistema"])
        v = m.PPVersion(producto_id=prod.id, numero_version=1, estado="BORRADOR",
                        moneda_id=ars.id, calculador_version_id=cv.id,
                        monto_minimo=Decimal(str(DEFAULT_CFG["montoMin"])),
                        monto_maximo=Decimal(str(DEFAULT_CFG["montoMax"])),
                        plazo_minimo=DEFAULT_CFG["plazoMin"], plazo_maximo=DEFAULT_CFG["plazoMax"])
        db.add(v); db.flush()
        db.add_all([
            m.PPTasa(producto_version_id=v.id, codigo="TNA", tasa_default=Decimal(str(DEFAULT_CFG["tna"]))),
            m.PPTasa(producto_version_id=v.id, codigo="MORA", tasa_default=Decimal(str(DEFAULT_CFG["moraTNA"]))),
            m.PPCargo(producto_version_id=v.id, codigo="OTORGAMIENTO", nombre="Cargo de otorgamiento",
                      porcentaje=Decimal(str(DEFAULT_CFG["cargoOtorg"]))),
        ])
        defs = {d.codigo: d for d in db.query(m.PPComponenteDefinicion).all()}
        for comp in _componentes_default(defs):
            comp.producto_version_id = v.id
            db.add(comp)
    db.commit()
    return _serial(db, prod, _calc_codigo_por_version(db))


def _validar_cfg(data: dict) -> None:
    """Rechaza configuraciones inválidas al guardar (fail-fast). Tolera borradores incompletos
    (valores en 0), pero no contradicciones ni negativos: antes esto se guardaba con 200 y sólo
    se detectaba —parcialmente— al publicar (H-099)."""
    tna, mora = data.get("tna", 0), data.get("moraTNA", 0)
    mn, mx = data.get("montoMin", 0), data.get("montoMax", 0)
    pmn, pmx = data.get("plazoMin", 0), data.get("plazoMax", 0)
    errs = []
    if tna < 0: errs.append("la TNA no puede ser negativa")
    if mora < 0: errs.append("la TNA de mora no puede ser negativa")
    if data.get("cargoOtorg", 0) < 0: errs.append("el cargo de otorgamiento no puede ser negativo")
    if data.get("graciaCapital", 0) < 0: errs.append("la gracia no puede ser negativa")
    if mn < 0 or mx < 0: errs.append("los montos no pueden ser negativos")
    if mn > 0 and mx > 0 and mn > mx: errs.append("el monto mínimo no puede superar al máximo")
    if pmn < 0 or pmx < 0: errs.append("los plazos no pueden ser negativos")
    if pmn > 0 and pmx > 0 and pmn > pmx: errs.append("el plazo mínimo no puede superar al máximo")
    if data.get("tnaNegociable"):
        tmn, tmx = data.get("tnaMin", 0), data.get("tnaMax", 0)
        if tmn < 0 or tmx < 0: errs.append("la banda de tasa no puede ser negativa")
        if tmn > 0 and tmx > 0 and tmn > tmx: errs.append("la TNA mínima no puede superar a la máxima")
    if errs:
        raise HTTPException(422, "Configuración inválida: " + "; ".join(errs) + ".")


@router.put("/{producto_id}/config")
def guardar_config(producto_id: str, cfg: ConfigIn, db: Session = Depends(get_db),
                   user: models.Usuario = Depends(get_current_user)):
    _req_edita(db, user)
    prod = db.get(m.PPProducto, producto_id)
    if not prod:
        raise HTTPException(404, "Producto no encontrado")
    v = _ultima(prod)
    if v.estado in ("APROBADO", "PUBLICADO", "RETIRADO"):
        raise HTTPException(409, "La versión ya no es editable (aprobada/publicada); creá una versión nueva.")
    data = cfg.model_dump()
    _validar_cfg(data)
    v.cfg_heredada = bool(data.get("cfgHeredada", False))
    _aplicar_cfg(db, v, data)
    if data.get("componentes") is not None:
        _aplicar_componentes(db, v, data["componentes"])
    db.commit()
    return _serial(db, prod, _calc_codigo_por_version(db))


class DisponibilidadIn(BaseModel):
    activo: bool = True
    canales: list[str] = []
    segmentos: list[str] = []
    edadMin: int | None = None
    edadMax: int | None = None
    antiguedadMinMeses: int | None = None
    requiereGarante: bool = False
    vigenteDesde: str = ""
    vigenteHasta: str = ""


@router.put("/{producto_id}/disponibilidad")
def editar_disponibilidad(producto_id: str, data: DisponibilidadIn, db: Session = Depends(get_db),
                          user: models.Usuario = Depends(get_current_user)):
    """H-189: edita la DISPONIBILIDAD (canales/segmentos/reglas) de la versión VIGENTE, INCLUSO publicada.
    Los canales/segmentos son metadata de DISTRIBUCIÓN (a quién y por qué canal se ofrece), no términos
    financieros congelados del producto: cambiarlos no altera contratos ya originados (snapshot) ni el
    cronograma. Por eso se pueden modificar sin crear una versión nueva. No toca condiciones ni pricing."""
    _req_edita(db, user)
    prod = db.get(m.PPProducto, producto_id)
    if not prod:
        raise HTTPException(404, "Producto no encontrado")
    v = _version_efectiva(prod)
    cfg = {
        "canales": [str(c).strip().upper() for c in (data.canales or []) if str(c).strip()],
        "segmentos": [str(s).strip() for s in (data.segmentos or []) if str(s).strip()],
        "edadMin": data.edadMin, "edadMax": data.edadMax,
        "antiguedadMinMeses": data.antiguedadMinMeses, "requiereGarante": bool(data.requiereGarante),
        "vigenteDesde": data.vigenteDesde or "", "vigenteHasta": data.vigenteHasta or "",
    }
    row = next((c for c in v.componentes if c.componente_codigo == "AVAILABILITY"), None)
    if row:
        row.activo = data.activo
        row.config = cfg
    else:
        db.add(m.PPComponente(producto_version_id=v.id, componente_codigo="AVAILABILITY",
                              orden=_ORDEN.get("AVAILABILITY", 99), requerido=False,
                              activo=data.activo, config=cfg))
    db.commit()
    return _serial(db, prod, _calc_codigo_por_version(db))


@router.post("/{producto_id}/nueva-version")
def nueva_version(producto_id: str, db: Session = Depends(get_db),
                  user: models.Usuario = Depends(get_current_user)):
    _req_edita(db, user)
    prod = db.get(m.PPProducto, producto_id)
    if not prod:
        raise HTTPException(404, "Producto no encontrado")
    prev = _ultima(prod)
    from app.core.numbering import crear_con_numero_unico
    from sqlalchemy import func as _func

    def _gen():   # re-lee el máximo por producto para reintentar ante la carrera (H-108)
        ult = db.query(_func.max(m.PPVersion.numero_version)).filter_by(producto_id=prod.id).scalar() or 0
        return ult + 1

    def _construir(n):
        v = m.PPVersion(
            producto_id=prod.id, numero_version=n, estado="BORRADOR",
            derivada_de=prev.numero_version, moneda_id=prev.moneda_id,
            calculador_version_id=prev.calculador_version_id,
            monto_minimo=prev.monto_minimo, monto_maximo=prev.monto_maximo,
            plazo_minimo=prev.plazo_minimo, plazo_maximo=prev.plazo_maximo,
            unidad_plazo=prev.unidad_plazo, frecuencia_pago=prev.frecuencia_pago,
            base_dias=prev.base_dias, regla_feriados=prev.regla_feriados,
            gracia_capital=prev.gracia_capital, gracia_interes=prev.gracia_interes,
            permite_prepago=prev.permite_prepago, cfg_heredada=prev.cfg_heredada)
        db.add(v)
        return v
    nv = crear_con_numero_unico(db, _gen, _construir)
    for t in prev.tasas:
        db.add(m.PPTasa(producto_version_id=nv.id, codigo=t.codigo, modalidad=t.modalidad,
                        tasa_default=t.tasa_default, indice_referencia=t.indice_referencia, margen=t.margen,
                        tasa_minima=t.tasa_minima, tasa_maxima=t.tasa_maxima, negociable=t.negociable))
    for c in prev.cargos:
        db.add(m.PPCargo(producto_version_id=nv.id, codigo=c.codigo, nombre=c.nombre, porcentaje=c.porcentaje, momento_aplicacion=c.momento_aplicacion))
    for comp in prev.componentes:
        db.add(m.PPComponente(producto_version_id=nv.id, componente_codigo=comp.componente_codigo,
                              orden=comp.orden, requerido=comp.requerido, activo=comp.activo,
                              config=dict(comp.config or {}), heredado=comp.heredado))
    db.commit()
    return _serial(db, prod, _calc_codigo_por_version(db))


@router.delete("/{producto_id}")
def borrar(producto_id: str, db: Session = Depends(get_db),
           user: models.Usuario = Depends(get_current_user)):
    _req_edita(db, user)
    prod = db.get(m.PPProducto, producto_id)
    if not prod:
        raise HTTPException(404, "Producto no encontrado")
    v = _ultima(prod)
    if v.estado not in ("BORRADOR", "EN_REVISION"):
        raise HTTPException(409, "Sólo se pueden borrar líneas en borrador o en revisión.")
    if len(prod.versiones) == 1:
        # Borra la línea completa: antes chequear referencias (evita un 500 crudo por FK, H-099).
        hijos = db.query(m.PPProducto).filter_by(padre_id=prod.id).count()
        if hijos:
            raise HTTPException(409, f"No se puede borrar: tiene {hijos} línea(s) derivada(s) que heredan de ésta.")
        contratos = db.query(m.PPContrato).filter_by(producto_id=prod.id).count()
        if contratos:
            raise HTTPException(409, f"No se puede borrar: tiene {contratos} contrato(s) originado(s) con esta línea.")
        db.delete(prod); alcance = "producto"
    else:
        db.delete(v); alcance = "version"          # borra sólo esta versión (deja las anteriores)
    try:
        db.commit()
    except IntegrityError:                          # red de seguridad ante cualquier otra referencia
        db.rollback()
        raise HTTPException(409, "No se puede borrar: la línea está referenciada por otros registros.")
    return {"ok": True, "borro": alcance}


@router.post("/{producto_id}/estado")
def cambiar_estado(producto_id: str, data: AccionIn, db: Session = Depends(get_db),
                   user: models.Usuario = Depends(get_current_user)):
    prod = db.get(m.PPProducto, producto_id)
    if not prod:
        raise HTTPException(404, "Producto no encontrado")
    v = _ultima(prod)
    acc = data.accion
    from app.services import workflow as wf
    if acc == "revisar":
        _req_edita(db, user)
        if v.estado != "BORRADOR":
            raise HTTPException(409, "Sólo un borrador se envía a revisión.")
        v.estado = "EN_REVISION"; v.enviado_por = user.username; v.aprobado_por = None
        wf.limpiar_aprobaciones(db, "LINEA", v.id)     # arranca la cadena limpia
    elif acc == "rechazar":
        _req_aprueba(db, user)
        if v.estado != "EN_REVISION":
            raise HTTPException(409, "Sólo una versión en revisión se rechaza.")
        v.estado = "BORRADOR"; v.aprobado_por = None
        wf.limpiar_aprobaciones(db, "LINEA", v.id)     # reinicia la cadena
    elif acc == "aprobar":
        if v.estado != "EN_REVISION":
            raise HTTPException(409, "Sólo una versión en revisión se aprueba.")
        # H-153: si el workflow está INACTIVO/ausente, aprobar_paso auto-aprueba sin mirar permisos; ahí el
        # gate es el rol aprobador de la pantalla (_req_aprueba). Con el workflow ACTIVO gatea el motor por
        # rol de cada nivel (permite niveles intermedios con roles no-aprobadores) + cuatro-ojos.
        _regla = wf.regla(db, "LINEA")
        if _regla is None or not _regla.activo:
            _req_aprueba(db, user)
        # Cadena de N niveles en serie (motor de workflow configurable).
        paso = wf.aprobar_paso(db, "LINEA", v.id, user, v.enviado_por)
        if not paso["ok"]:
            raise HTTPException(paso["status"], paso["motivo"])
        if paso["completo"]:
            v.estado = "APROBADO"; v.aprobado_por = user.username
        # si faltan niveles, sigue EN_REVISION esperando la próxima aprobación
    elif acc == "publicar":
        _req_aprueba(db, user)
        if v.estado != "APROBADO":
            raise HTTPException(409, "Sólo una versión APROBADA se publica.")
        if v.monto_minimo > v.monto_maximo or v.plazo_minimo > v.plazo_maximo:
            raise HTTPException(422, "Validación de integridad: montos/plazos fuera de rango.")
        if v.plazo_minimo < 1 or v.monto_minimo <= 0:
            raise HTTPException(422, "Validación de integridad: monto/plazo mínimo debe ser positivo.")
        if _tasa(v, "TNA") < 0 or _tasa(v, "MORA") < 0:
            raise HTTPException(422, "Validación de integridad: la TNA/mora no puede ser negativa.")
        v.estado = "PUBLICADO"; v.publicado_por = user.username
        if not v.vigente_desde:
            v.vigente_desde = date.today()   # si no se fijó fecha, entra en vigencia hoy
        # La versión publicada anterior deja de estar vigente cuando arranca esta.
        for prev in prod.versiones:
            if prev.id != v.id and prev.estado == "PUBLICADO" and (not prev.vigente_hasta or prev.vigente_hasta > v.vigente_desde):
                prev.vigente_hasta = v.vigente_desde
    elif acc == "retirar":
        _req_aprueba(db, user)
        if v.estado != "PUBLICADO":
            raise HTTPException(409, "Sólo una versión publicada se retira.")
        v.estado = "RETIRADO"; v.vigente_hasta = date.today()
    elif acc == "reactivar":
        _req_aprueba(db, user)
        if v.estado != "RETIRADO":
            raise HTTPException(409, "Sólo una versión retirada se reactiva.")
        v.estado = "PUBLICADO" if v.vigente_desde else "BORRADOR"
        v.vigente_hasta = None
    else:
        raise HTTPException(422, f"Acción desconocida: {acc}")
    db.commit()
    return _serial(db, prod, _calc_codigo_por_version(db))


@router.post("/{producto_id}/publicar-directo")
def publicar_directo(producto_id: str, db: Session = Depends(get_db),
                     user: models.Usuario = Depends(get_current_user)):
    """H-190: publica el préstamo en UN paso (revisar→aprobar→publicar) cuando el cuatro-ojos (regla LINEA)
    está INACTIVO. Si está ACTIVO, sólo lo manda a revisión y devuelve needs_approval=True (otra persona
    aprueba, respetando la separación de funciones). Simplifica el flujo del builder."""
    prod = db.get(m.PPProducto, producto_id)
    if not prod:
        raise HTTPException(404, "Producto no encontrado")
    from app.services import workflow as wf
    regla = wf.regla(db, "LINEA")
    activo_wf = bool(regla and regla.activo)
    if _ultima(prod).estado == "BORRADOR":
        cambiar_estado(producto_id, AccionIn(accion="revisar"), db, user)
    if activo_wf:   # cuatro-ojos activo → queda EN_REVISION para aprobación de un tercero
        return {"needs_approval": True, "producto": _serial(db, prod, _calc_codigo_por_version(db))}
    if _ultima(prod).estado == "EN_REVISION":
        cambiar_estado(producto_id, AccionIn(accion="aprobar"), db, user)
    if _ultima(prod).estado == "APROBADO":
        cambiar_estado(producto_id, AccionIn(accion="publicar"), db, user)
    return {"needs_approval": False, "producto": _serial(db, prod, _calc_codigo_por_version(db))}
