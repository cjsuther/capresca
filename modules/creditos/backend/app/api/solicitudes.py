"""Solicitudes de crédito (línea nueva / product builder).

Cliente registrado (maestro real) o no registrado (alta express, según permiso). Workflow con
cuatro-ojos: BORRADOR → EN_EVALUACION → APROBADA → ORIGINADA (o RECHAZADA / ANULADA). Una solicitud
APROBADA alimenta la originación (ver contratos.originar con solicitud_pp_id).
"""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.services import auditoria as audit
from app.services import documentos

from app.core import clientes_padron
from app.core.database import get_db
from app.core.personas import edad_de
from app.core.descargas import disposicion
from app.core.numbering import crear_con_numero_unico
from app.core.idempotency import con_idempotencia
from app.deps import get_current_user
from app import models, models_productos as m
from app.api.productos import (_version_efectiva, _disponibilidad, _elegibilidad,
                               _tna_base, _calc_codigo_por_version, _params_cronograma,
                               _cargo, _feriados_engine, decimales_calculo)
from app.core.permisos import caps_creditos
from app.api.contratos import _ctx
from app.services.productos_calc import cronograma, resumen

router = APIRouter(prefix="/api/creditos/solicitudes", tags=["solicitudes"],
                   dependencies=[Depends(get_current_user)])

ESTADOS = ["BORRADOR", "EN_EVALUACION", "APROBADA", "RECHAZADA", "ORIGINADA", "ANULADA"]

# Permisos por ROLES (H-150): la capacidad en el circuito de créditos sale de los roles efectivos del
# usuario (perfil + grupos) — misma regla para Solicitudes, Configurar y el motor de workflow.
def _caps(db, user: models.Usuario) -> dict:
    return caps_creditos(db, user)


def _req_edita(db, user: models.Usuario):
    if not _caps(db, user)["edita"]:
        raise HTTPException(403, "No tenés permiso para cargar/editar solicitudes de crédito (creditos:creditos:write). Se asigna en Seguridad de Portezuelo.")


def _req_aprueba(db, user: models.Usuario):
    if not _caps(db, user)["aprueba"]:
        raise HTTPException(403, "No tenés permiso de aprobación de solicitudes (creditos:aprobaciones:*). Se asigna en Seguridad de Portezuelo.")


class SolicitudIn(BaseModel):
    producto_id: str
    monto_solicitado: float = Field(gt=0)
    plazo_solicitado: int = Field(gt=0, le=240)
    solicitante_tipo: str = "REGISTRADO"          # REGISTRADO | NO_REGISTRADO
    cliente_id: int | None = None                 # si REGISTRADO
    cliente_datos: dict = {}                       # si NO_REGISTRADO: {cuil, apellido_nombre, dni, nacimiento}
    segmento: str = ""
    canal: str = "SUCURSAL"
    fecha_nacimiento: date | None = None      # la edad se calcula (H-219); no se carga a mano
    antiguedad_meses: int | None = Field(default=None, ge=0, le=1200)  # hasta 4 dígitos (0–1200 meses = 100 años)
    relacion: str = "ESTANDAR"
    datos_adicionales: dict = {}
    origen: str = "SUCURSAL"


class AccionIn(BaseModel):
    accion: str            # enviar | aprobar | rechazar | anular
    motivo: str = ""
    observacion: str = ""  # nota del asesor al resolver (queda en datos_adicionales.obs_revision)


def _cliente_nombre(db: Session, s: m.PPSolicitud) -> str:
    if s.solicitante_tipo == "REGISTRADO" and s.cliente_id:
        cli = db.get(models.Cliente, s.cliente_id)
        return cli.apellido_nombre if cli else f"Cliente {s.cliente_id}"
    return (s.cliente_datos or {}).get("apellido_nombre") or "Sin nombre"


def _evaluar(db: Session, s: m.PPSolicitud) -> dict:
    """Elegibilidad (Fase E) + cuota/TNA estimada (cronograma, única fuente de verdad)."""
    prod = db.get(m.PPProducto, s.producto_id)
    if not prod:
        return {"elegible": False, "motivos": ["Producto inexistente."]}
    v = _version_efectiva(prod)
    monto, plazo = float(s.monto_solicitado), int(s.plazo_solicitado)
    motivos: list[str] = []
    if not (float(v.monto_minimo) <= monto <= float(v.monto_maximo)):
        motivos.append(f"Monto fuera de rango ({float(v.monto_minimo):.0f}–{float(v.monto_maximo):.0f}).")
    if not (v.plazo_minimo <= plazo <= v.plazo_maximo):
        motivos.append(f"Plazo fuera de rango ({v.plazo_minimo}–{v.plazo_maximo}).")
    # TNA base efectiva: fija = tasa_default; VARIABLE = índice + margen (H-200). Antes usaba `_tasa` (sólo
    # tasa_default → 0 en productos de tasa variable), así la cuota estimada de la solicitud ignoraba el
    # interés y no coincidía con la simulación ni con la originación (que usan `_tna_base`). Motor único.
    tna = _tna_base(db, v)
    cuota_est = tna_ef = 0.0
    if not motivos:
        calc_map = _calc_codigo_por_version(db)
        sistema = calc_map.get(v.calculador_version_id, "FRANCES")
        filas = cronograma(sistema, monto, plazo, tna, _cargo(v, "OTORGAMIENTO"), date.today(),
                           **_params_cronograma(v, _feriados_engine(db), decimales_calculo(db)))
        res = resumen(filas, monto, v.frecuencia_pago or "MENSUAL", tna)
        cuota_est, tna_ef = res["primeraCuota"], res["tna"]
    # La afectación (cuota sobre el sueldo declarado) se evalúa con el resto: el tope lo fija la línea.
    sueldo = float((s.datos_adicionales or {}).get("sueldo_declarado") or 0)
    ctx = _ctx(s.segmento or None, s.canal or None,
               edad_de(s.fecha_nacimiento) or s.edad, s.antiguedad_meses)
    ctx["afectacion"] = round(cuota_est / sueldo * 100, 1) if (sueldo > 0 and cuota_est) else None
    elig = _elegibilidad(_disponibilidad(v), ctx)
    if not elig.get("elegible", True):
        motivos += elig.get("motivos", [])
    return {"elegible": not motivos, "motivos": motivos,
            "tna_ofrecida": round(tna_ef or tna, 4), "cuota_estimada": round(cuota_est, 2)}


def _datos_liquidacion(db: Session, s: m.PPSolicitud) -> dict:
    """Checklist de 'listo para liquidar' de una solicitud (H-134).

    Sólo APLICA al canal web (origen PORTAL / canal WEB): esas solicitudes entran express y hay que
    verificar que llegue todo lo necesario para aprobar la liquidación ANTES de originar el contrato.
    Obligatorios: apellido/nombre + DNI (identidad) y CBU de 22 dígitos (acreditación). CUIL y sueldo
    son deseables (se completan al dar de alta en el maestro) y no bloquean.
    """
    aplica = s.origen == "PORTAL" or s.canal == "WEB"
    cd = s.cliente_datos or {}
    da = s.datos_adicionales or {}
    cli = db.get(models.Cliente, s.cliente_id) if (s.solicitante_tipo == "REGISTRADO" and s.cliente_id) else None
    nombre = ((cli.apellido_nombre if cli else cd.get("apellido_nombre")) or "").strip()
    dni = ((cli.dni if cli else cd.get("dni")) or "").strip()
    cuil = ((cli.cuil if cli else cd.get("cuil")) or "").strip()
    cbu = "".join(ch for ch in str(da.get("cbu") or "") if ch.isdigit())
    items = [
        {"campo": "nombre", "label": "Apellido y nombre", "requerido": True, "ok": bool(nombre), "valor": nombre},
        {"campo": "dni", "label": "DNI", "requerido": True, "ok": bool(dni), "valor": dni},
        {"campo": "cbu", "label": "CBU de acreditación", "requerido": True, "ok": len(cbu) == 22, "valor": cbu},
        {"campo": "cuil", "label": "CUIL", "requerido": False, "ok": bool(cuil), "valor": cuil},
        {"campo": "sueldo", "label": "Sueldo declarado", "requerido": False, "ok": bool(da.get("sueldo_declarado")),
         "valor": da.get("sueldo_declarado")},
    ]
    faltantes = [it["label"] for it in items if it["requerido"] and not it["ok"]]
    return {"aplica": aplica, "lista": not faltantes, "faltantes": faltantes, "items": items}


def _serial(db: Session, s: m.PPSolicitud) -> dict:
    return {
        "id": s.id, "numero": s.numero, "estado": s.estado, "solicitanteTipo": s.solicitante_tipo,
        "clienteId": s.cliente_id, "clienteDatos": s.cliente_datos or {},
        "clienteNombre": _cliente_nombre(db, s),
        "productoId": s.producto_id, "monto": float(s.monto_solicitado), "plazo": s.plazo_solicitado,
        "segmento": s.segmento, "canal": s.canal, "antiguedadMeses": s.antiguedad_meses,
        "fechaNacimiento": str(s.fecha_nacimiento) if s.fecha_nacimiento else None,
        "edad": edad_de(s.fecha_nacimiento) if s.fecha_nacimiento else s.edad,   # calculada; el dato viejo si no hay fecha
        "relacion": s.relacion, "datosAdicionales": s.datos_adicionales or {}, "origen": s.origen,
        "evaluacion": s.evaluacion or {}, "contratoId": s.contrato_id, "motivoRechazo": s.motivo_rechazo,
        "datosLiquidacion": _datos_liquidacion(db, s),
        "creadoPor": s.creado_por, "creadoEn": str(s.creado_en) if s.creado_en else None,
        "enviadaPor": s.enviada_por, "resueltaPor": s.resuelta_por,
    }


def _numero(db: Session) -> str:
    """Primer SOL-{anio}-NNNNN libre. count()+1 colisiona con la constraint única al borrar
    solicitudes (mismo bug que H-097 en las líneas de crédito)."""
    anio = date.today().year
    pref = f"SOL-{anio}-"
    usados = {x for (x,) in db.query(m.PPSolicitud.numero).filter(m.PPSolicitud.numero.like(f"{pref}%")).all()}
    n = 1
    while f"{pref}{n:05d}" in usados:
        n += 1
    return f"{pref}{n:05d}"


@router.get("")
def listar(estado: str = Query(""), q: str = Query(""), producto_id: str = Query(""),
           db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    qry = db.query(m.PPSolicitud)
    if estado:
        qry = qry.filter(m.PPSolicitud.estado == estado)
    if producto_id:
        qry = qry.filter(m.PPSolicitud.producto_id == producto_id)
    items = [_serial(db, s) for s in qry.order_by(m.PPSolicitud.creado_en.desc()).all()]
    if q:
        ql = q.lower()
        items = [i for i in items if ql in (i["clienteNombre"] or "").lower() or ql in i["numero"].lower()]
    return {"items": items, "estados": ESTADOS, "permisos": _caps(db, user)}


@router.post("", status_code=201)
def crear(data: SolicitudIn, db: Session = Depends(get_db),
          user: models.Usuario = Depends(get_current_user),
          idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    _req_edita(db, user)
    if not db.get(m.PPProducto, data.producto_id):
        raise HTTPException(404, "Producto no encontrado.")
    tipo = data.solicitante_tipo.upper()
    if tipo == "REGISTRADO":
        if not data.cliente_id or not db.get(models.Cliente, data.cliente_id):
            raise HTTPException(422, "Cliente registrado inexistente.")
    else:  # NO_REGISTRADO — alta express (según permiso; hoy: mismo que edita)
        cd = data.cliente_datos or {}
        if not (cd.get("apellido_nombre") and cd.get("cuil")):
            raise HTTPException(422, "El alta express requiere al menos nombre y CUIL.")

    # H-202: bloqueo duro por elegibilidad. Si lo declarado NO cumple las condiciones de la línea
    # (segmento/canal/edad/antigüedad/monto/plazo), no se puede pedir la solicitud — misma regla que el
    # portal. La evaluación usa la misma fuente que la simulación. (Un dato NO declarado no bloquea:
    # `_elegibilidad` sólo aplica la regla del atributo cuando ese dato viene.)
    _tmp = m.PPSolicitud(producto_id=data.producto_id, monto_solicitado=Decimal(str(data.monto_solicitado)),
                         plazo_solicitado=data.plazo_solicitado, segmento=data.segmento, canal=data.canal,
                         edad=edad_de(data.fecha_nacimiento), fecha_nacimiento=data.fecha_nacimiento,
                         antiguedad_meses=data.antiguedad_meses)
    _ev = _evaluar(db, _tmp)
    if not _ev.get("elegible"):
        raise HTTPException(422, "No cumple las condiciones para esta línea: " + "; ".join(_ev.get("motivos", [])))

    def _do() -> dict:
        return _crear_solicitud(db, data, tipo, user)
    # Idempotencia de operación: un reintento con la misma Idempotency-Key no crea otra solicitud.
    return con_idempotencia(db, idempotency_key, "POST /api/solicitudes", _do, user.username)


def _crear_solicitud(db: Session, data, tipo: str, user) -> dict:
    def _construir(numero: str) -> m.PPSolicitud:
        s = m.PPSolicitud(
            numero=numero, estado="BORRADOR", solicitante_tipo=tipo,
            cliente_id=data.cliente_id if tipo == "REGISTRADO" else None,
            cliente_datos={} if tipo == "REGISTRADO" else data.cliente_datos,
            producto_id=data.producto_id, monto_solicitado=Decimal(str(data.monto_solicitado)),
            plazo_solicitado=data.plazo_solicitado, segmento=data.segmento, canal=data.canal,
            edad=edad_de(data.fecha_nacimiento), fecha_nacimiento=data.fecha_nacimiento,
            antiguedad_meses=data.antiguedad_meses, relacion=data.relacion.upper(),
            datos_adicionales=data.datos_adicionales, origen=data.origen, creado_por=user.username)
        s.evaluacion = _evaluar(db, s)
        db.add(s)
        return s
    # Número único tolerante a concurrencia (reintenta ante colisión, la constraint es el árbitro).
    s = crear_con_numero_unico(db, lambda: _numero(db), _construir)
    db.commit(); db.refresh(s)
    return _serial(db, s)


@router.get("/{sid}")
def obtener(sid: str, db: Session = Depends(get_db)):
    s = db.get(m.PPSolicitud, sid)
    if not s:
        raise HTTPException(404, "Solicitud no encontrada.")
    return _serial(db, s)


@router.put("/{sid}")
def editar(sid: str, data: SolicitudIn, db: Session = Depends(get_db),
           user: models.Usuario = Depends(get_current_user)):
    _req_edita(db, user)
    s = db.get(m.PPSolicitud, sid)
    if not s:
        raise HTTPException(404, "Solicitud no encontrada.")
    if s.estado != "BORRADOR":
        raise HTTPException(409, "Sólo se puede editar una solicitud en BORRADOR.")
    s.producto_id = data.producto_id
    s.monto_solicitado = Decimal(str(data.monto_solicitado)); s.plazo_solicitado = data.plazo_solicitado
    s.segmento = data.segmento; s.canal = data.canal
    s.fecha_nacimiento = data.fecha_nacimiento; s.edad = edad_de(data.fecha_nacimiento)
    s.antiguedad_meses = data.antiguedad_meses; s.relacion = data.relacion.upper()
    s.datos_adicionales = data.datos_adicionales; s.origen = data.origen
    s.solicitante_tipo = data.solicitante_tipo.upper()
    s.cliente_id = data.cliente_id if s.solicitante_tipo == "REGISTRADO" else None
    s.cliente_datos = {} if s.solicitante_tipo == "REGISTRADO" else data.cliente_datos
    s.evaluacion = _evaluar(db, s)
    db.commit(); db.refresh(s)
    return _serial(db, s)


@router.post("/{sid}/estado")
def cambiar_estado(sid: str, data: AccionIn, db: Session = Depends(get_db),
                   user: models.Usuario = Depends(get_current_user)):
    s = db.get(m.PPSolicitud, sid)
    if not s:
        raise HTTPException(404, "Solicitud no encontrada.")
    acc = data.accion.lower()
    if data.observacion.strip():   # nota del asesor al resolver (aprobar/rechazar/anular/originar)
        s.datos_adicionales = {**(s.datos_adicionales or {}), "obs_revision": data.observacion.strip()[:500]}
    from app.services import workflow as wf
    if acc == "enviar":
        _req_edita(db, user)
        if s.estado != "BORRADOR":
            raise HTTPException(409, "Sólo se envía a evaluación desde BORRADOR.")
        s.estado = "EN_EVALUACION"; s.enviada_por = user.username
        s.evaluacion = _evaluar(db, s)
        wf.limpiar_aprobaciones(db, "SOLICITUD", s.id)
    elif acc in ("aprobar", "rechazar"):
        if s.estado != "EN_EVALUACION":
            raise HTTPException(409, "Sólo se resuelve una solicitud EN_EVALUACION.")
        # H-153: con la regla SOLICITUD sembrada INACTIVA (app single-admin, H-141) el motor auto-aprobaba
        # sin mirar permisos → cualquier usuario autenticado resolvía. Si no hay workflow activo, el gate es
        # el rol aprobador de la pantalla (_req_aprueba); con el workflow activo gatea el motor por nivel.
        _regla = wf.regla(db, "SOLICITUD")
        if _regla is None or not _regla.activo:
            _req_aprueba(db, user)
        if acc == "rechazar":
            ok, status, motivo = wf.puede_aprobar(db, "SOLICITUD", user, actores={s.enviada_por} if s.enviada_por else set())
            if not ok:
                raise HTTPException(status, motivo)
            s.estado = "RECHAZADA"; s.motivo_rechazo = data.motivo or "Sin motivo"; s.resuelta_por = user.username
            wf.limpiar_aprobaciones(db, "SOLICITUD", s.id)
        else:
            # H-203: no se puede aprobar la solicitud de un cliente NO registrado en el maestro (alta express
            # o solicitud del portal aún sin promover). El asesor debe darlo de alta —o vincular un cliente
            # existente— con "promover-cliente" antes de aprobar.
            if s.solicitante_tipo == "NO_REGISTRADO":
                raise HTTPException(409, "El cliente no está registrado en el maestro. Dalo de alta "
                                         "(o vinculá un cliente existente) antes de aprobar la solicitud.")
            # Cadena de N niveles: cada aprobación avanza; sólo la última pasa a APROBADA.
            paso = wf.aprobar_paso(db, "SOLICITUD", s.id, user, s.enviada_por)
            if not paso["ok"]:
                raise HTTPException(paso["status"], paso["motivo"])
            if paso["completo"]:
                ev = _evaluar(db, s)
                if not ev.get("elegible"):
                    raise HTTPException(422, "No se puede aprobar: " + "; ".join(ev.get("motivos", [])))
                s.estado = "APROBADA"; s.evaluacion = ev; s.resuelta_por = user.username
    elif acc == "anular":
        _req_edita(db, user)
        if s.estado == "ORIGINADA":
            raise HTTPException(409, "No se puede anular una solicitud ya originada.")
        s.estado = "ANULADA"; s.motivo_rechazo = data.motivo or s.motivo_rechazo
    else:
        raise HTTPException(422, f"Acción inválida: {data.accion}.")
    db.commit(); db.refresh(s)
    return _serial(db, s)


class PromoverIn(BaseModel):
    cliente_id: int = 0           # vincular un cliente YA existente del maestro (alta hecha en Clientes → Maestro)
    id_cliente: str = ""          # código a asignar en el maestro (opcional; si vacío se genera)
    # Datos completados/confirmados por el asesor en la revisión del alta (H-137). Vacío = usar lo declarado.
    cuil: str = ""                # una web/express llega sin CUIL: el asesor lo completa acá
    dni: str = ""
    apellido_nombre: str = ""
    email: str = ""
    telefono: str = ""
    domicilio: str = ""
    localidad: str = ""
    copiar_documentos: bool = True   # guardar los adjuntos de la solicitud en la ficha del cliente


def _copiar_documentos(db: Session, s: m.PPSolicitud, cliente_id: int, usuario: str) -> dict:
    """Pasa los adjuntos de la solicitud a la ficha del cliente en el módulo Clientes (idempotente).
    Si Clientes no responde, no se deshace el alta/vínculo: se informa y se puede reintentar."""
    import base64
    docs = db.query(m.PPSolicitudDocumento).filter_by(solicitud_id=s.id).order_by(m.PPSolicitudDocumento.subido_en).all()
    if not docs:
        return {"guardados": 0, "repetidos": 0}
    lote = [{"nombre": d.nombre, "content_type": d.content_type, "tipo": d.tipo,
             "origen": f"Solicitud {s.numero}", "contenido_base64": base64.b64encode(d.contenido).decode()}
            for d in docs]
    try:
        r = clientes_padron.copiar_documentos(cliente_id, lote)
    except clientes_padron.PadronNoDisponible as e:
        return {"guardados": 0, "repetidos": 0, "error": f"No se pudieron copiar los documentos al cliente: {e}"}
    audit.registrar_cambio(db, usuario=usuario, entidad="Solicitud", entidad_id=s.numero, operacion="DOCUMENTOS_A_CLIENTE",
                           resultado="OK", despues={"cliente_id": cliente_id, **{k: r.get(k) for k in ("guardados", "repetidos")}},
                           detalle=f"Documentos de {s.numero} guardados en el cliente {cliente_id}")
    return {"guardados": r.get("guardados", 0), "repetidos": r.get("repetidos", 0)}


@router.post("/{sid}/promover-cliente")
def promover_cliente(sid: str, data: PromoverIn, db: Session = Depends(get_db),
                     user: models.Usuario = Depends(get_current_user)):
    """Alta express → maestro real de clientes. El asesor confirma/completa los datos (incl. el CUIL,
    que la web no trae) en la revisión del alta. Requiere permiso de edición."""
    _req_edita(db, user)
    s = db.get(m.PPSolicitud, sid)
    if not s:
        raise HTTPException(404, "Solicitud no encontrada.")
    if s.solicitante_tipo != "NO_REGISTRADO":
        raise HTTPException(409, "La solicitud ya es de un cliente registrado.")
    # Vincular un cliente YA existente (lo dieron de alta en Clientes → Maestro y vuelven a vincular).
    if data.cliente_id:
        cli = db.get(models.Cliente, data.cliente_id)
        if not cli:
            raise HTTPException(404, "Cliente del maestro no encontrado.")
        s.solicitante_tipo = "REGISTRADO"; s.cliente_id = cli.id; s.cliente_datos = {}
        db.commit(); db.refresh(s)
        documentos = _copiar_documentos(db, s, cli.id, user.username) if data.copiar_documentos else None
        return {"solicitud": _serial(db, s), "clienteId": cli.id, "yaExistia": True, "documentos": documentos}
    cd = s.cliente_datos or {}
    nombre = (data.apellido_nombre or cd.get("apellido_nombre") or "").strip()
    if not nombre:
        raise HTTPException(422, "El apellido y nombre es obligatorio para el alta en el maestro.")
    dni = "".join(ch for ch in (data.dni or cd.get("dni") or "") if ch.isdigit())
    cuil = "".join(ch for ch in (data.cuil or cd.get("cuil") or "") if ch.isdigit())
    if cuil and len(cuil) != 11:
        raise HTTPException(422, "El CUIL debe tener 11 dígitos.")
    # El padrón es del módulo Clientes: la persona se da de alta ALLÁ (idempotente por documento) y
    # acá queda sólo el espejo. Así no hay dos maestros de clientes en el sistema.
    documento = cuil or dni
    if not documento:
        raise HTTPException(422, "Hace falta el DNI o el CUIL para darlo de alta en el padrón de clientes.")
    apellido, _, nombres = nombre.partition(",")
    try:
        r = clientes_padron.importar([{
            "documento": documento,
            "tipo_documento": "CUIL" if cuil else "DNI",
            "apellido": apellido.strip() or nombre,
            "nombres": nombres.strip(),
            "email": (data.email or cd.get("email") or "").strip(),
            "telefono": (data.telefono or cd.get("telefono") or "").strip(),
            "domicilio": (data.domicilio or cd.get("domicilio") or "").strip(),
            "localidad": (data.localidad or cd.get("localidad") or "").strip(),
        }])
    except Exception as e:                                   # el padrón no respondió
        raise HTTPException(503, f"No se pudo dar de alta en el padrón de clientes: {e}")
    ya_existia = documento in (r.get("existentes") or {})
    cliente_id = (r.get("creados") or {}).get(documento) or (r.get("existentes") or {}).get(documento)
    if not cliente_id:
        raise HTTPException(502, "El padrón de clientes no devolvió el id de la persona.")
    cli = clientes_padron.sincronizar(db, int(cliente_id))
    s.solicitante_tipo = "REGISTRADO"; s.cliente_id = cli.id; s.cliente_datos = {}
    db.commit(); db.refresh(s)
    documentos = _copiar_documentos(db, s, cli.id, user.username) if data.copiar_documentos else None
    return {"solicitud": _serial(db, s), "clienteId": cli.id, "yaExistia": ya_existia, "documentos": documentos}


@router.post("/{sid}/documentos/copiar-al-cliente")
def copiar_documentos_al_cliente(sid: str, db: Session = Depends(get_db),
                                 user: models.Usuario = Depends(get_current_user)):
    """Guarda (o vuelve a guardar) los adjuntos de una solicitud con cliente en la ficha del cliente.
    Idempotente: lo que el cliente ya tiene no se duplica."""
    _req_edita(db, user)
    s = db.get(m.PPSolicitud, sid)
    if not s:
        raise HTTPException(404, "Solicitud no encontrada.")
    if s.solicitante_tipo != "REGISTRADO" or not s.cliente_id:
        raise HTTPException(409, "Primero creá o vinculá el cliente de la solicitud.")
    r = _copiar_documentos(db, s, s.cliente_id, user.username)
    if r.get("error"):
        raise HTTPException(503, r["error"])
    return {"clienteId": s.cliente_id, **r}


# ---------------- Documentación adjunta (la sube el ciudadano; la ve el asesor) ----------------
@router.get("/{sid}/documentos")
def documentos_solicitud(sid: str, db: Session = Depends(get_db),
                         user: models.Usuario = Depends(get_current_user)):
    s = db.get(m.PPSolicitud, sid)
    if not s:
        raise HTTPException(404, "Solicitud no encontrada.")
    docs = db.query(m.PPSolicitudDocumento).filter_by(solicitud_id=s.id).order_by(m.PPSolicitudDocumento.subido_en).all()
    return {"items": [documentos.serial(d) for d in docs]}


@router.get("/{sid}/documentos/{doc_id}")
def descargar_documento_solicitud(sid: str, doc_id: str, db: Session = Depends(get_db),
                                  user: models.Usuario = Depends(get_current_user)):
    doc = db.query(m.PPSolicitudDocumento).filter_by(id=doc_id, solicitud_id=sid).first()
    if not doc:
        raise HTTPException(404, "Documento no encontrado.")
    return Response(content=doc.contenido, media_type=doc.content_type,
                    headers={"Content-Disposition": disposicion(doc.nombre)})
