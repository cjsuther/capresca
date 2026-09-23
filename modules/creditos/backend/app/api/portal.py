"""Portal del ciudadano: SSO Mi Catamarca + simulador (Fase 1) + envío de solicitud (Fase 2).

Superficie PÚBLICA y separada del backoffice:
  - realm propio: token con scope 'portal' (dep get_ciudadano); nunca abre endpoints internos.
  - reutiliza el MOTOR ÚNICO de cálculo (product builder: cronograma): la cuota que ve el ciudadano
    es idéntica a la que se contrata en el backoffice (principio simulado == contratado).
  - Fase 1: simula sobre productos publicados+vigentes (read-only).
  - Fase 2: el ciudadano envía su solicitud → PPSolicitud EN_EVALUACION en el Inbox del backoffice
    (mismo pipeline cuatro-ojos: evaluar → aprobar → originar), y consulta el estado de las suyas.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Header, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse, Response
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.descargas import disposicion
from app.core.personas import edad_de
from app.core.idempotency import con_idempotencia
from app.core.numbering import crear_con_numero_unico
from app.core.security import create_portal_token, create_state_token, decode_token
from app.deps import Ciudadano, get_ciudadano
from app.services import auditoria as audit
from app.services import documentos
from app.services import haberes as haberes_svc
from app.services.mi_catamarca import get_provider
from app.services.productos_calc import cronograma, resumen
# Motor y helpers del PRODUCT BUILDER (lo nuevo): la simulación del portal usa exactamente
# el mismo cronograma que la originación del contrato (pp_contrato) → simulado == contratado.
from app.api.productos import (_calc_codigo_por_version, _tna_base, _cargo,
                               _params_cronograma, _feriados_engine, _version_publicada_vigente,
                               _disponibilidad, _elegibilidad, canal_portal, decimales_calculo)
from app.api.contratos import _ctx
from app.api.solicitudes import _numero as _numero_solicitud, _evaluar as _evaluar_solicitud
from app import models_productos as m, schemas

router = APIRouter(prefix="/api/creditos/portal", tags=["portal"])

# Tope de la cuota sobre el sueldo cuando la línea no configuró el suyo (componente Disponibilidad).
AFECTACION_MAX_DEFECTO = 30

# Destinos del crédito. El portal ya NO los pregunta (se sacó del formulario); se dejan porque las
# solicitudes viejas lo tienen guardado y el backoffice sigue mostrándolo.
DESTINOS: dict[str, str] = {
    "VIVIENDA": "Vivienda / refacción",
    "VEHICULO": "Vehículo",
    "CONSUMO": "Consumo / gastos personales",
    "EDUCACION": "Educación",
    "SALUD": "Salud",
    "REFINANCIACION": "Refinanciación de deudas",
    "EMPRENDIMIENTO": "Emprendimiento / negocio",
    "OTRO": "Otro",
}


def _destino_norm(v: str) -> str:
    """Normaliza el destino declarado; vacío o desconocido → '' (opcional)."""
    return (v or "").strip().upper() if (v or "").strip().upper() in DESTINOS else ""


# ----------------------------- Autenticación (SSO Mi Catamarca) -----------------------------
# H-158: anti-replay del state OIDC. El state va firmado (CSRF stateless) pero además el `nonce` se guarda
# al emitirlo y se CONSUME (borra) en el callback: un state válido no expirado no puede reusarse (one-time).
# Se usa el store genérico de claves vistas (pp_idempotencia), cuya PK es árbitro de la unicidad.
def _reservar_nonce(db: Session, nonce: str) -> None:
    from app import models_productos as mp
    try:
        db.add(mp.PPIdempotencia(clave=f"oidc-state:{nonce}", endpoint="oidc-state", usuario="portal"))
        db.commit()
    except Exception:
        db.rollback()   # colisión de nonce (imposible en la práctica): que el callback lo rechace


def _consumir_nonce(db: Session, nonce: str) -> bool:
    """True si el nonce estaba pendiente (se consume); False si ya fue usado o es desconocido (replay)."""
    from app import models_productos as mp
    rec = db.get(mp.PPIdempotencia, f"oidc-state:{nonce}")
    if rec is None:
        return False
    db.delete(rec); db.commit()
    return True


@router.get("/auth/login")
def login(db: Session = Depends(get_db)):
    """Devuelve la URL de autorización de Mi Catamarca (el SPA redirige ahí)."""
    prov = get_provider()
    nonce = uuid.uuid4().hex
    _reservar_nonce(db, nonce)
    state = create_state_token(nonce)
    return {"authorize_url": prov.authorize_url(state), "mock": prov.mock}


@router.get("/auth/mock-authorize")
def mock_authorize(state: str):
    """Sólo activo con el proveedor MOCK: simula que Mi Catamarca redirige al callback con un code."""
    prov = get_provider()
    if not prov.mock:
        raise HTTPException(404, "No disponible")
    s = get_settings()
    return RedirectResponse(f"{s.micatamarca_redirect_uri}?code=mock-code&state={state}")


@router.get("/auth/callback")
def callback(code: str, state: str, request: Request, db: Session = Depends(get_db)):
    """Callback OIDC: valida el state, intercambia el code y emite el token de sesión del portal."""
    try:
        st = decode_token(state)
    except InvalidTokenError:
        raise HTTPException(400, "state inválido o expirado")
    if st.get("scope") != "oidc-state":
        raise HTTPException(400, "state inválido")
    # H-158: one-time. Consumir el nonce; si ya se usó (o es desconocido), es un replay → rechazar.
    if not _consumir_nonce(db, st.get("nonce") or ""):
        raise HTTPException(400, "state ya utilizado o desconocido")

    try:
        ident = get_provider().identidad_desde_code(code)
    except Exception:
        # No filtramos el detalle del proveedor al navegador.
        audit.registrar_cambio(db, usuario="ciudadano", ip=audit.ip_de(request),
                               entidad="Ciudadano", operacion="LOGIN", resultado="ERROR",
                               detalle="Fallo el intercambio de code con Mi Catamarca")
        raise HTTPException(502, "No se pudo completar el ingreso con Mi Catamarca")

    token = create_portal_token(ident.sub, ident.email, ident.nombre, ident.documento)
    audit.registrar_cambio(db, usuario=ident.email or ident.sub, ip=audit.ip_de(request),
                           entidad="Ciudadano", entidad_id=ident.sub, operacion="LOGIN", resultado="OK",
                           despues={"email": ident.email, "nombre": ident.nombre},
                           detalle="Ingreso al portal vía Mi Catamarca")
    # Token en el fragmento (#): no viaja al servidor ni queda en logs de query.
    s = get_settings()
    return RedirectResponse(f"{s.portal_web_url}/ingreso#token={token}")


def videos_obligatorios() -> list[dict]:
    """Videos que hay que ver completos antes de confirmar (config `portal_videos`, "id:Título,…")."""
    out = []
    for item in (get_settings().portal_videos or "").split(","):
        vid, _, titulo = item.strip().partition(":")
        if vid:
            out.append({"id": vid, "titulo": titulo.strip() or vid,
                        "url": f"/portal-creditos/videos/{vid}.mp4"})
    return out


@router.get("/videos", response_model=list[schemas.PortalVideoOut])
def videos(c: Ciudadano = Depends(get_ciudadano)):
    """Videos del paso 4: el ciudadano los ve completos (sin adelantar) antes de confirmar."""
    return videos_obligatorios()


@router.get("/me", response_model=schemas.CiudadanoOut)
def me(c: Ciudadano = Depends(get_ciudadano)):
    return schemas.CiudadanoOut(sub=c.sub, email=c.email, nombre=c.nombre)


@router.get("/haberes", response_model=schemas.PortalHaberesOut)
def haberes(c: Ciudadano = Depends(get_ciudadano)):
    """Trae los haberes del ciudadano (sueldo/antigüedad/relación) de la fuente oficial (Mi Catamarca)
    o del mock, para autocompletar. Si aún no hay API real, es el mock (datos demo, editables)."""
    h = haberes_svc.get_provider().por_documento(c.documento, c.sub)
    return schemas.PortalHaberesOut(
        disponible=h.disponible, sueldo=h.sueldo, antiguedad_meses=h.antiguedad_meses,
        segmento=h.segmento, empleador=h.empleador, fuente=h.fuente)


# --------------------- Simulador sobre el PRODUCT BUILDER (lo nuevo, motor único) ---------------------
def _ofrecible_web(db: Session, v: m.PPVersion) -> bool:
    """El producto se ofrece por el canal del portal. H-185/H-189: el código de canal del portal es
    CONFIGURABLE (Parámetro CANAL_PORTAL, por defecto WEB). Regla OPT-IN para el canal público: un producto
    aparece en el portal SÓLO si tiene la Disponibilidad CONFIGURADA (componente activo). Si la
    Disponibilidad no está activada (sin canal definido), NO se ofrece por el portal — evita exponer al
    público productos que nadie habilitó explícitamente para la web (H-189). Con Disponibilidad activa:
    canales vacío = todos los canales (incluye el portal); o el canal del portal explícito."""
    disp = _disponibilidad(v)
    if disp is None:   # Disponibilidad NO configurada (componente inactivo) → no se ofrece públicamente
        return False
    canales = [str(x).upper() for x in (disp.get("canales") or [])]
    return (not canales) or (canal_portal(db) in canales)


@router.get("/productos", response_model=list[schemas.PortalProductoOut])
def productos_publicos(db: Session = Depends(get_db), _c: Ciudadano = Depends(get_ciudadano)):
    """Sólo productos PUBLICADOS y VIGENTES hoy, y habilitados en el canal del portal (H-185)."""
    calc = _calc_codigo_por_version(db)
    out = []
    for p in db.query(m.PPProducto).all():
        v = _version_publicada_vigente(p)
        if v is None or not _ofrecible_web(db, v):
            continue
        out.append(schemas.PortalProductoOut(
            id=p.id, nombre=p.nombre, codigo=p.codigo,
            sistema=calc.get(v.calculador_version_id, "FRANCES"), tna=round(_tna_base(db, v), 4),
            monto_min=float(v.monto_minimo), monto_max=float(v.monto_maximo),
            plazo_min=v.plazo_minimo, plazo_max=v.plazo_maximo))
    return sorted(out, key=lambda x: x.nombre)


@router.post("/simular", response_model=schemas.PortalSimulacionOut)
def simular(req: schemas.PortalSimularIn, db: Session = Depends(get_db),
            _c: Ciudadano = Depends(get_ciudadano)):
    """Simula sobre un producto PUBLICADO con el MISMO `cronograma` que la originación (no persiste)."""
    prod = db.get(m.PPProducto, req.producto_id)
    if not prod:
        raise HTTPException(404, "Producto no encontrado")
    v = _version_publicada_vigente(prod)
    if v is None:
        raise HTTPException(409, "El producto no está publicado ni vigente para simular.")
    if not (float(v.monto_minimo) <= req.monto <= float(v.monto_maximo)):
        raise HTTPException(422, f"Monto fuera de rango ({float(v.monto_minimo):.0f}–{float(v.monto_maximo):.0f}).")
    if not (v.plazo_minimo <= req.plazo <= v.plazo_maximo):
        raise HTTPException(422, f"Plazo fuera de rango ({v.plazo_minimo}–{v.plazo_maximo} cuotas).")

    sistema = _calc_codigo_por_version(db).get(v.calculador_version_id, "FRANCES")
    tna = _tna_base(db, v)   # variable = índice + margen (igual que la originación → simulado == contratado)
    cargo = _cargo(v, "OTORGAMIENTO")
    filas = cronograma(sistema, req.monto, req.plazo, tna, cargo, date.today(),
                       **_params_cronograma(v, _feriados_engine(db), decimales_calculo(db)))
    r = resumen(filas, req.monto, v.frecuencia_pago or "MENSUAL", tna)
    cuotas = [schemas.PortalCuotaOut(
        numero=f["numero_cuota"], vencimiento=str(f["fecha_vencimiento"]),
        capital=round(float(f["capital"]), 2), interes=round(float(f["interes"]), 2),
        cargos=round(float(f["cargos"]), 2), impuestos=round(float(f.get("impuestos", 0)), 2),
        total=round(float(f["total"]), 2)) for f in filas]
    cuota_prom = round(r["totalCuotas"] / len(filas), 2) if filas else 0.0
    elegible, motivos, afectacion = _evaluar_ciudadano(db, v, req, cuota_prom)
    return schemas.PortalSimulacionOut(
        producto=prod.nombre, sistema=sistema, tna=round(tna, 4), monto=req.monto,
        cantidad_cuotas=len(filas), total_a_pagar=r["totalCuotas"], total_interes=r["totalInteres"],
        cuota_promedio=cuota_prom, tea=r["tea"], cft=r["cft"],
        elegible=elegible, motivos=motivos, afectacion=afectacion, cuotas=cuotas)


@router.post("/pre-aprobado", response_model=schemas.PortalPreAprobadoOut)
def pre_aprobado(req: schemas.PortalPreAprobadoIn, db: Session = Depends(get_db),
                 _c: Ciudadano = Depends(get_ciudadano)):
    """'¿Cuánto puedo pedir?': el mayor monto cuya cuota no supera la afectación (cuota ≤ %·sueldo).

    Busca por bisección sobre el motor único (la cuota crece monótona con el monto). El resultado
    se redondea hacia abajo a $1.000; monto_maximo=0 si ni el monto mínimo entra en el margen."""
    prod = db.get(m.PPProducto, req.producto_id)
    if not prod:
        raise HTTPException(404, "Producto no encontrado")
    v = _version_publicada_vigente(prod)
    if v is None:
        raise HTTPException(409, "El producto no está disponible.")
    if not (v.plazo_minimo <= req.plazo <= v.plazo_maximo):
        raise HTTPException(422, f"Plazo fuera de rango ({v.plazo_minimo}–{v.plazo_maximo}).")
    # El tope lo fija la línea de crédito (componente Disponibilidad, "Tope del crédito"). El portal ya
    # no lo manda; si igual viene un valor, vale el más estricto de los dos.
    tope = (_disponibilidad(v) or {}).get("afectacionMaxPct")
    afectacion_max = min([x for x in (tope, req.afectacion_max) if x] or [AFECTACION_MAX_DEFECTO])
    target = req.sueldo * afectacion_max / 100
    lo, hi = float(v.monto_minimo), float(v.monto_maximo)
    cuota_de = lambda monto: _cuota_estimada(db, v, monto, req.plazo)[0]
    if cuota_de(lo) > target:                       # ni el mínimo entra en el margen
        return schemas.PortalPreAprobadoOut(monto_maximo=0, monto_min=lo, cuota=cuota_de(lo),
                                            afectacion=round(cuota_de(lo) / req.sueldo * 100, 1), plazo=req.plazo,
                                            afectacion_max=afectacion_max)
    if cuota_de(hi) <= target:                       # entra hasta el máximo de la línea
        best = hi
    else:
        best = lo
        for _ in range(28):
            mid = (lo + hi) / 2
            if cuota_de(mid) <= target:
                best, lo = mid, mid
            else:
                hi = mid
    best = float(int(best // 1000) * 1000)           # redondeo hacia abajo a $1.000
    cuota = cuota_de(best)
    return schemas.PortalPreAprobadoOut(
        monto_maximo=best, monto_min=float(v.monto_minimo), cuota=round(cuota, 2),
        afectacion=round(cuota / req.sueldo * 100, 1), plazo=req.plazo,
        afectacion_max=afectacion_max)


def _evaluar_ciudadano(db: Session, v, datos: schemas.DatosSolicitante, cuota: float):
    """Elegibilidad (según los datos declarados, canal WEB) + afectación estimada (cuota/sueldo).
    Devuelve (elegible|None, motivos, afectacion%|None). elegible=None si no declaró datos."""
    edad = edad_de(datos.fecha_nacimiento)
    declaro = bool(datos.segmento or edad is not None or datos.antiguedad_meses is not None)
    afectacion = round(cuota / datos.sueldo * 100, 1) if (datos.sueldo and datos.sueldo > 0) else None
    elegible, motivos = None, []
    if declaro or afectacion is not None:
        ctx = _ctx(datos.segmento or None, "WEB", edad, datos.antiguedad_meses)
        ctx["afectacion"] = afectacion          # el tope de la línea también decide la elegibilidad
        ev = _elegibilidad(_disponibilidad(v), ctx)
        elegible, motivos = ev["elegible"], ev["motivos"]
    return elegible, motivos, afectacion


# ----------------------- Solicitud de crédito (Fase 2) -----------------------
# El ciudadano envía su solicitud desde el portal: se crea una PPSolicitud NO_REGISTRADO (alta
# express con la identidad de Mi Catamarca) directamente EN_EVALUACION, para que aparezca en el
# Inbox del backoffice (cuatro-ojos) y siga el pipeline normal (evaluar → aprobar → originar).
# Marca de dueño: creado_por/enviada_por = "portal:<sub>" → filtra "mis solicitudes".

def _marca(c: Ciudadano) -> str:
    return f"portal:{c.sub}"


def _cuota_estimada(db: Session, v, monto: float, plazo: int) -> tuple[float, float]:
    """(cuota promedio, TNA) con el MISMO cronograma del simulador (independiente de la elegibilidad)."""
    sistema = _calc_codigo_por_version(db).get(v.calculador_version_id, "FRANCES")
    tna = _tna_base(db, v)
    filas = cronograma(sistema, monto, plazo, tna, _cargo(v, "OTORGAMIENTO"), date.today(),
                       **_params_cronograma(v, _feriados_engine(db), decimales_calculo(db)))
    r = resumen(filas, monto, v.frecuencia_pago or "MENSUAL", tna)
    return (round(r["totalCuotas"] / len(filas), 2) if filas else 0.0, round(tna, 4))


def _serial_portal_solicitud(db: Session, s: m.PPSolicitud) -> dict:
    prod = db.get(m.PPProducto, s.producto_id)
    da = s.datos_adicionales or {}
    ev = s.evaluacion or {}
    # Cuota que el ciudadano vio al simular (guardada al enviar); si falta, cae a la de la evaluación.
    cuota = da.get("cuota_estimada", ev.get("cuota_estimada") or 0)
    tna = da.get("tna", ev.get("tna_ofrecida") or 0)
    return schemas.PortalSolicitudOut(
        numero=s.numero, estado=s.estado, producto=(prod.nombre if prod else ""),
        monto=float(s.monto_solicitado), plazo=s.plazo_solicitado,
        cuota_estimada=float(cuota), tna=float(tna),
        fecha=str(s.creado_en) if s.creado_en else "", motivo_rechazo=s.motivo_rechazo or "",
    ).model_dump()


@router.post("/solicitudes", response_model=schemas.PortalSolicitudOut, status_code=201)
def enviar_solicitud(req: schemas.PortalSolicitudIn, request: Request,
                     db: Session = Depends(get_db), c: Ciudadano = Depends(get_ciudadano),
                     idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    """El ciudadano envía su solicitud → EN_EVALUACION en el Inbox del backoffice."""
    prod = db.get(m.PPProducto, req.producto_id)
    if not prod:
        raise HTTPException(404, "Producto no encontrado")
    v = _version_publicada_vigente(prod)
    if v is None:
        raise HTTPException(409, "El producto no está disponible para solicitar.")
    # H-185: guarda dura de canal — un producto no habilitado en el canal del portal no se puede solicitar
    # desde la web, aunque se conozca su id (no basta con ocultarlo del listado).
    if not _ofrecible_web(db, v):
        raise HTTPException(422, "El producto no está disponible por el canal web.")
    if not (float(v.monto_minimo) <= req.monto <= float(v.monto_maximo)):
        raise HTTPException(422, f"Monto fuera de rango ({float(v.monto_minimo):.0f}–{float(v.monto_maximo):.0f}).")
    if not (v.plazo_minimo <= req.plazo <= v.plazo_maximo):
        raise HTTPException(422, f"Plazo fuera de rango ({v.plazo_minimo}–{v.plazo_maximo} cuotas).")
    # Consentimientos obligatorios y CBU válido (acreditación).
    if not (req.acepta_terminos and req.acepta_datos):
        raise HTTPException(422, "Tenés que aceptar los términos y el tratamiento de datos para enviar.")
    cbu = "".join(ch for ch in (req.cbu or "") if ch.isdigit())
    if len(cbu) != 22:
        raise HTTPException(422, "El CBU debe tener 22 dígitos.")
    # Paso 4: los videos obligatorios tienen que estar vistos completos. El portal no deja avanzar sin
    # verlos; acá se exige igual para que no se pueda saltear llamando a la API directo.
    requeridos = [v["id"] for v in videos_obligatorios()]
    faltan = [v for v in requeridos if v not in set(req.videos_vistos)]
    if faltan:
        raise HTTPException(422, "Tenés que ver los videos completos antes de enviar la solicitud.")
    # H-162: el ciudadano declara su identidad (Mi Catamarca sólo confirma que existe). Apellido, nombre y
    # DNI son obligatorios para poder liquidar; el DNI debe tener 7 u 8 dígitos.
    apellido, nombre = (req.apellido or "").strip(), (req.nombre or "").strip()
    dni = "".join(ch for ch in (req.dni or "") if ch.isdigit())
    if not apellido or not nombre:
        raise HTTPException(422, "Cargá tu apellido y nombre.")
    if len(dni) not in (7, 8):
        raise HTTPException(422, "El DNI debe tener 7 u 8 dígitos.")
    apellido_nombre = f"{apellido}, {nombre}"
    # Fecha de nacimiento (en vez de la edad: no envejece sola) y contacto, obligatorios para evaluar
    # y para poder avisarle al ciudadano cómo siguió su trámite.
    edad = edad_de(req.fecha_nacimiento)
    if edad is None:
        raise HTTPException(422, "Cargá tu fecha de nacimiento.")
    if not (18 <= edad <= 99):
        raise HTTPException(422, "La fecha de nacimiento no es válida (la edad debe estar entre 18 y 99 años).")
    email = (req.email or "").strip() or (c.email or "")
    telefono = "".join(ch for ch in (req.telefono or "") if ch.isdigit() or ch in "+")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(422, "Cargá un email válido.")
    if len(telefono.lstrip("+")) < 8:
        raise HTTPException(422, "Cargá un teléfono de contacto (al menos 8 dígitos).")
    # H-202: bloqueo duro por elegibilidad. Si lo declarado por el ciudadano (segmento/edad/antigüedad) NO
    # cumple las condiciones de la línea, no puede enviar la solicitud. Misma fuente que el simulador; un
    # dato no declarado no bloquea (queda para la revisión del backoffice).
    _tmp = m.PPSolicitud(producto_id=prod.id, monto_solicitado=Decimal(str(req.monto)), plazo_solicitado=req.plazo,
                         segmento=req.segmento or "", canal="WEB", edad=edad,
                         fecha_nacimiento=req.fecha_nacimiento, antiguedad_meses=req.antiguedad_meses,
                         datos_adicionales={"sueldo_declarado": req.sueldo})
    _ev = _evaluar_solicitud(db, _tmp)
    if not _ev.get("elegible"):
        raise HTTPException(422, "No cumplís las condiciones para esta línea: " + "; ".join(_ev.get("motivos", [])))
    destino = _destino_norm(req.destino)
    marca = _marca(c)
    ip = audit.ip_de(request)
    cuota_est, tna_est = _cuota_estimada(db, v, req.monto, req.plazo)   # la que el ciudadano vio al simular

    def _construir(numero: str) -> m.PPSolicitud:
        s = m.PPSolicitud(
            numero=numero, estado="EN_EVALUACION", solicitante_tipo="NO_REGISTRADO", cliente_id=None,
            # Identidad DECLARADA por el ciudadano (H-162): Mi Catamarca sólo confirma que existe, no da su
            # perfil. El CUIL no lo entrega el OIDC: queda para completar en el alta del backoffice.
            cliente_datos={"apellido_nombre": apellido_nombre, "email": email, "telefono": telefono,
                           "nacimiento": str(req.fecha_nacimiento), "cuil": "", "dni": dni},
            producto_id=prod.id, monto_solicitado=Decimal(str(req.monto)), plazo_solicitado=req.plazo,
            # Datos declarados por el ciudadano (Fase 3): alimentan la evaluación del backoffice.
            segmento=req.segmento or "", canal="WEB", edad=edad, fecha_nacimiento=req.fecha_nacimiento,
            antiguedad_meses=req.antiguedad_meses,
            origen="PORTAL", relacion="ESTANDAR",
            datos_adicionales={"portal_sub": c.sub, "portal_email": c.email,
                               "email": email, "telefono": telefono,
                               "cuota_estimada": cuota_est, "tna": tna_est,
                               "sueldo_declarado": req.sueldo, "haberes_fuente": req.haberes_fuente,
                               "destino": destino,
                               "cbu": cbu, "consentimiento": {"terminos": True, "datos": True,
                                                              "fecha": str(date.today())},
                               "videos_vistos": {"videos": requeridos, "fecha": str(date.today())},
                               "afectacion": (round(cuota_est / req.sueldo * 100, 1)
                                              if (req.sueldo and req.sueldo > 0) else None)},
            creado_por=marca, enviada_por=marca)
        s.evaluacion = _evaluar_solicitud(db, s)
        db.add(s)
        return s

    def _do() -> dict:
        # Nº único tolerante a concurrencia (la constraint de la DB es el árbitro).
        s = crear_con_numero_unico(db, lambda: _numero_solicitud(db), _construir)
        db.commit(); db.refresh(s)
        audit.registrar_cambio(db, usuario=c.email or c.sub, ip=ip, entidad="Solicitud",
                               entidad_id=s.numero, operacion="ALTA", resultado="OK",
                               despues={"producto": prod.nombre, "monto": float(s.monto_solicitado),
                                        "plazo": s.plazo_solicitado, "estado": s.estado, "canal": "PORTAL"},
                               detalle=f"Solicitud {s.numero} enviada desde el portal por el ciudadano")
        return _serial_portal_solicitud(db, s)

    # Idempotencia: un doble-clic en "Enviar" no crea dos solicitudes.
    return con_idempotencia(db, idempotency_key, "POST /api/portal/solicitudes", _do, marca)


@router.get("/solicitudes", response_model=list[schemas.PortalSolicitudOut])
def mis_solicitudes(db: Session = Depends(get_db), c: Ciudadano = Depends(get_ciudadano)):
    """Las solicitudes del PROPIO ciudadano (por su marca portal:<sub>), más recientes primero."""
    rows = (db.query(m.PPSolicitud).filter(m.PPSolicitud.creado_por == _marca(c))
            .order_by(m.PPSolicitud.creado_en.desc()).all())
    return [_serial_portal_solicitud(db, s) for s in rows]


@router.get("/solicitudes/{numero}", response_model=schemas.PortalSolicitudDetalle)
def detalle_solicitud(numero: str, db: Session = Depends(get_db), c: Ciudadano = Depends(get_ciudadano)):
    """Detalle/seguimiento de UNA solicitud del propio ciudadano: datos, estado y cronograma estimado."""
    s = db.query(m.PPSolicitud).filter_by(numero=numero, creado_por=_marca(c)).first()
    if not s:
        raise HTTPException(404, "Solicitud no encontrada")
    base = _serial_portal_solicitud(db, s)
    da = s.datos_adicionales or {}
    prod = db.get(m.PPProducto, s.producto_id)
    v = _version_publicada_vigente(prod) if prod else None
    cuotas, total, sistema = [], 0.0, ""
    if v is not None:
        sistema = _calc_codigo_por_version(db).get(v.calculador_version_id, "FRANCES")
        tna = _tna_base(db, v)
        filas = cronograma(sistema, float(s.monto_solicitado), s.plazo_solicitado, tna,
                           _cargo(v, "OTORGAMIENTO"), date.today(),
                           **_params_cronograma(v, _feriados_engine(db), decimales_calculo(db)))
        total = round(sum(float(f["total"]) for f in filas), 2)
        cuotas = [schemas.PortalCuotaOut(
            numero=f["numero_cuota"], vencimiento=str(f["fecha_vencimiento"]),
            capital=round(float(f["capital"]), 2), interes=round(float(f["interes"]), 2),
            cargos=round(float(f["cargos"]), 2), impuestos=round(float(f.get("impuestos", 0)), 2),
            total=round(float(f["total"]), 2)) for f in filas]
    return schemas.PortalSolicitudDetalle(
        **base, sistema=sistema, destino=DESTINOS.get(da.get("destino", ""), ""),
        segmento=s.segmento or "", edad=s.edad,
        fecha_nacimiento=str(s.fecha_nacimiento) if s.fecha_nacimiento else None,
        antiguedad_meses=s.antiguedad_meses, sueldo=da.get("sueldo_declarado"),
        afectacion=da.get("afectacion"), total_a_pagar=total, cuotas=cuotas)


# ----------------------- Documentación adjunta (Fase 3+) -----------------------
# El ciudadano adjunta su documentación (DNI, recibo) a UNA solicitud propia mientras está
# EN_EVALUACION; el asesor la ve/descarga en el backoffice.

def _solicitud_propia(db: Session, numero: str, c: Ciudadano) -> m.PPSolicitud:
    s = db.query(m.PPSolicitud).filter_by(numero=numero, creado_por=_marca(c)).first()
    if not s:
        raise HTTPException(404, "Solicitud no encontrada")
    return s


@router.get("/solicitudes/{numero}/documentos")
def listar_documentos(numero: str, db: Session = Depends(get_db), c: Ciudadano = Depends(get_ciudadano)):
    s = _solicitud_propia(db, numero, c)
    docs = db.query(m.PPSolicitudDocumento).filter_by(solicitud_id=s.id).order_by(m.PPSolicitudDocumento.subido_en).all()
    return {"items": [documentos.serial(d) for d in docs], "puede_subir": s.estado in ("EN_EVALUACION", "BORRADOR")}


@router.post("/solicitudes/{numero}/documentos", status_code=201)
async def subir_documento(numero: str, request: Request, tipo: str = Form("OTRO"),
                          archivo: UploadFile = File(...), db: Session = Depends(get_db),
                          c: Ciudadano = Depends(get_ciudadano)):
    s = _solicitud_propia(db, numero, c)
    if s.estado not in ("EN_EVALUACION", "BORRADOR"):
        raise HTTPException(409, "No se pueden adjuntar documentos a una solicitud ya resuelta.")
    # El ciudadano adjunta exactamente un archivo de cada documento pedido (DNI frente, DNI dorso y recibo
    # de sueldo): ni otros tipos, ni un segundo del mismo. Para cambiarlo, el asesor lo gestiona.
    tipo = (tipo or "").upper()
    if tipo not in documentos.TIPOS_PORTAL:
        raise HTTPException(422, "Sólo se adjuntan el DNI (frente y dorso) y el recibo de sueldo.")
    if db.query(m.PPSolicitudDocumento).filter_by(solicitud_id=s.id, tipo=tipo).first():
        raise HTTPException(409, f"Ya adjuntaste {documentos.ETIQUETAS[tipo]} en esta solicitud.")
    contenido = await archivo.read()
    try:
        documentos.validar(archivo.content_type, len(contenido))
    except ValueError as e:
        raise HTTPException(422, str(e))
    doc = m.PPSolicitudDocumento(
        solicitud_id=s.id, tipo=tipo, nombre=(archivo.filename or "documento")[:200],
        content_type=archivo.content_type, tamano=len(contenido), contenido=contenido, subido_por=_marca(c))
    db.add(doc); db.commit(); db.refresh(doc)
    audit.registrar_cambio(db, usuario=c.email or c.sub, ip=audit.ip_de(request), entidad="Documento",
                           entidad_id=doc.id, operacion="ALTA", resultado="OK",
                           despues={"solicitud": s.numero, "tipo": doc.tipo, "nombre": doc.nombre},
                           detalle=f"Documento '{doc.nombre}' adjuntado a {s.numero} desde el portal")
    return documentos.serial(doc)


@router.get("/solicitudes/{numero}/documentos/{doc_id}")
def descargar_documento(numero: str, doc_id: str, db: Session = Depends(get_db),
                        c: Ciudadano = Depends(get_ciudadano)):
    s = _solicitud_propia(db, numero, c)
    doc = db.query(m.PPSolicitudDocumento).filter_by(id=doc_id, solicitud_id=s.id).first()
    if not doc:
        raise HTTPException(404, "Documento no encontrado")
    return Response(content=doc.contenido, media_type=doc.content_type,
                    headers={"Content-Disposition": disposicion(doc.nombre)})


@router.delete("/solicitudes/{numero}/documentos/{doc_id}")
def borrar_documento(numero: str, doc_id: str, db: Session = Depends(get_db),
                     c: Ciudadano = Depends(get_ciudadano)):
    s = _solicitud_propia(db, numero, c)
    if s.estado not in ("EN_EVALUACION", "BORRADOR"):
        raise HTTPException(409, "No se pueden quitar documentos de una solicitud ya resuelta.")
    doc = db.query(m.PPSolicitudDocumento).filter_by(id=doc_id, solicitud_id=s.id).first()
    if not doc:
        raise HTTPException(404, "Documento no encontrado")
    db.delete(doc); db.commit()
    return {"ok": True}


# ----------------------- Mis créditos (préstamo otorgado + cuotas + notificaciones) -----------------------
# El ciudadano ve los créditos que le originaron a partir de sus solicitudes (PPSolicitud.contrato_id),
# cómo vienen las cuotas (pagadas/pendientes/vencidas) y un feed de notificaciones derivado del estado.

def _contratos_del_ciudadano(db: Session, c: Ciudadano) -> list[m.PPContrato]:
    ids = [s.contrato_id for s in db.query(m.PPSolicitud)
           .filter(m.PPSolicitud.creado_por == _marca(c), m.PPSolicitud.contrato_id.isnot(None)).all()]
    if not ids:
        return []
    return db.query(m.PPContrato).filter(m.PPContrato.id.in_(ids)).order_by(m.PPContrato.creado_en.desc()).all()


def _resumen_credito(ct: m.PPContrato) -> schemas.PortalCreditoOut:
    hoy = date.today()
    cuotas = sorted(ct.cuotas, key=lambda x: x.numero_cuota)
    pend = [q for q in cuotas if q.estado == "PENDIENTE"]
    prox = next((q for q in pend if (q.total or 0) > 0), None)
    pagadas = len([q for q in cuotas if q.estado == "PAGADA"])
    en_mora = any(q.fecha_vencimiento and q.fecha_vencimiento < hoy for q in pend)
    proxima = None
    if prox:
        proxima = schemas.PortalProximaCuota(
            numero=prox.numero_cuota, vencimiento=str(prox.fecha_vencimiento), total=float(prox.total or 0),
            vencida=bool(prox.fecha_vencimiento and prox.fecha_vencimiento < hoy))
    return schemas.PortalCreditoOut(
        contrato=ct.numero_contrato, producto=(ct.snapshot_producto or {}).get("producto", ""),
        monto=float(ct.monto_original or 0), saldo=float(ct.saldo_capital or 0), estado=ct.estado,
        tna=float(ct.tasa_contratada or 0), plazo=ct.plazo, cuotas_pagadas=pagadas, cuotas_total=len(cuotas),
        progreso=round(pagadas / len(cuotas) * 100, 1) if cuotas else 0.0, en_mora=en_mora, proxima=proxima)


@router.get("/creditos", response_model=list[schemas.PortalCreditoOut])
def mis_creditos(db: Session = Depends(get_db), c: Ciudadano = Depends(get_ciudadano)):
    """Los créditos otorgados al ciudadano (originados desde sus solicitudes)."""
    return [_resumen_credito(ct) for ct in _contratos_del_ciudadano(db, c)]


@router.get("/creditos/{contrato}", response_model=schemas.PortalCreditoDetalle)
def detalle_credito(contrato: str, db: Session = Depends(get_db), c: Ciudadano = Depends(get_ciudadano)):
    """Detalle del crédito: cronograma con el estado de cada cuota (pagada/pendiente/vencida)."""
    ct = next((x for x in _contratos_del_ciudadano(db, c) if x.numero_contrato == contrato), None)
    if ct is None:
        raise HTTPException(404, "Crédito no encontrado")
    hoy = date.today()
    base = _resumen_credito(ct).model_dump()
    cuotas = [schemas.PortalCuotaEstadoOut(
        numero=q.numero_cuota, vencimiento=str(q.fecha_vencimiento), total=float(q.total or 0),
        pagado=float(q.pagado or 0), estado=q.estado,
        vencida=bool(q.estado == "PENDIENTE" and q.fecha_vencimiento and q.fecha_vencimiento < hoy))
        for q in sorted(ct.cuotas, key=lambda x: x.numero_cuota)]
    return schemas.PortalCreditoDetalle(**base, fecha_alta=str(ct.fecha_valor), cuotas=cuotas)


@router.get("/notificaciones", response_model=list[schemas.PortalNotificacionOut])
def notificaciones(db: Session = Depends(get_db), c: Ciudadano = Depends(get_ciudadano)):
    """Feed derivado del estado de los créditos del ciudadano: otorgamiento, próximos vencimientos, mora."""
    hoy = date.today()
    notis: list[schemas.PortalNotificacionOut] = []
    for ct in _contratos_del_ciudadano(db, c):
        # Otorgamiento reciente (últimos 21 días).
        if ct.creado_en and (hoy - ct.creado_en.date()).days <= 21:
            notis.append(schemas.PortalNotificacionOut(
                tipo="otorgado", titulo="Crédito otorgado", contrato=ct.numero_contrato,
                detalle=f"Tu crédito {ct.numero_contrato} por {float(ct.monto_original or 0):.0f} fue otorgado.",
                fecha=str(ct.creado_en.date())))
        pend = [q for q in sorted(ct.cuotas, key=lambda x: x.numero_cuota) if q.estado == "PENDIENTE" and (q.total or 0) > 0]
        prox = pend[0] if pend else None
        if prox and prox.fecha_vencimiento:
            dias = (prox.fecha_vencimiento - hoy).days
            if dias < 0:
                notis.append(schemas.PortalNotificacionOut(
                    tipo="mora", titulo="Cuota vencida", contrato=ct.numero_contrato,
                    detalle=f"La cuota {prox.numero_cuota} venció hace {-dias} día(s). Regularizá para evitar intereses.",
                    fecha=str(prox.fecha_vencimiento)))
            elif dias <= 7:
                notis.append(schemas.PortalNotificacionOut(
                    tipo="vencimiento", titulo="Próximo vencimiento", contrato=ct.numero_contrato,
                    detalle=f"Tu cuota {prox.numero_cuota} de {float(prox.total or 0):.0f} vence en {dias} día(s).",
                    fecha=str(prox.fecha_vencimiento)))
    notis.sort(key=lambda n: n.fecha, reverse=True)
    return notis
