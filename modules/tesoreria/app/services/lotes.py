"""Reglas de negocio de los lotes de pagos.

Garantías de dinero:
- Un lote se crea una sola vez por (origen, referencia): reenviarlo devuelve el mismo.
- Un mismo pago (referencia externa del origen) no puede estar vivo en dos lotes a la vez.
- Enviar es una transición atómica (UPDATE … WHERE estado = …): un doble clic o dos tesoreros a la vez
  no envían dos veces. Cada pago pasa a ENVIANDO (guardado) antes de llamar al banco.
- Si la llamada al banco se corta, el pago queda INCIERTO y sólo una persona lo resuelve.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.dependencies.auth import Usuario
from app.services import avisos, interbanking, workflow

# Estados de un pago que lo mantienen "vivo" (no se puede cargar de nuevo en otro lote).
VIVOS = ("PENDIENTE", "ENVIANDO", "ENVIADO", "CONFIRMADO", "INCIERTO")
ETIQUETA_ORIGEN = {"CREDITOS": "Créditos", "CONCILIACION": "Conciliación", "MANUAL": "Carga manual"}


def _ahora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def evento(db: Session, lote: models.Lote, usuario: str, accion: str, detalle: str = "") -> None:
    db.add(models.Evento(lote_id=lote.id, usuario=usuario, accion=accion, detalle=detalle[:2000]))


# ── Serialización ────────────────────────────────────────────────────────────────────────────────
def _pago(p: models.Pago) -> dict:
    return {"id": p.id, "referencia_externa": p.referencia_externa, "beneficiario": p.beneficiario,
            "documento": p.documento, "cbu": p.cbu, "monto": float(p.monto), "concepto": p.concepto,
            "estado": p.estado, "motivo": p.motivo, "id_operacion_ib": p.id_operacion_ib,
            "estado_banco": p.estado_banco,
            "enviado_en": p.enviado_en.isoformat() if p.enviado_en else None,
            "confirmado_en": p.confirmado_en.isoformat() if p.confirmado_en else None}


def resumen(lote: models.Lote) -> dict:
    activos = [p for p in lote.pagos if p.estado not in ("EXCLUIDO", "RECHAZADO")]
    por_estado: dict[str, int] = {}
    for p in lote.pagos:
        por_estado[p.estado] = por_estado.get(p.estado, 0) + 1
    return {
        "id": lote.id, "codigo": lote.codigo, "origen": lote.origen,
        "origen_nombre": ETIQUETA_ORIGEN.get(lote.origen, lote.origen),
        "referencia_origen": lote.referencia_origen, "descripcion": lote.descripcion, "estado": lote.estado,
        "motivo_rechazo": lote.motivo_rechazo, "simulado": lote.simulado,
        "cantidad": len(activos), "total": float(sum((p.monto for p in activos), Decimal(0))),
        "excluidos": sum(1 for p in lote.pagos if p.estado == "EXCLUIDO"), "por_estado": por_estado,
        "cuenta_origen": ({"account_number": lote.cuenta_origen, "account_type": lote.cuenta_origen_tipo,
                           "bank_number": lote.cuenta_origen_banco, "nombre": lote.cuenta_origen_nombre}
                          if lote.cuenta_origen else None),
        "creado_por": lote.creado_por, "creado_en": lote.creado_en.isoformat() if lote.creado_en else None,
        "enviado_por": lote.enviado_por, "enviado_en": lote.enviado_en.isoformat() if lote.enviado_en else None,
    }


def detalle(db: Session, lote: models.Lote, user: Usuario) -> dict:
    ok, _st, motivo, nivel = puede_aprobar(lote, user, estricto=False)
    eventos = (db.query(models.Evento).filter_by(lote_id=lote.id).order_by(models.Evento.fecha, models.Evento.id).all())
    r = workflow.regla()
    total_niveles = len(r.niveles) if (r and r.activo) else 1
    return {**resumen(lote), "pagos": [_pago(p) for p in lote.pagos],
            "aprobaciones": [{"nivel": a.nivel_orden, "aprobado_por": a.aprobado_por,
                              "fecha": a.fecha.isoformat() if a.fecha else None} for a in lote.aprobaciones],
            "niveles": total_niveles, "nivel_actual": nivel,
            "puede_aprobar": ok, "motivo_no_aprueba": "" if ok else motivo,
            "puede_enviar": user.puede("lotes:enviar"), "puede_editar": user.puede("lotes:write"),
            "envio_simulado": settings.envio_simulado,
            "eventos": [{"fecha": e.fecha.isoformat() if e.fecha else None, "usuario": e.usuario,
                         "accion": e.accion, "detalle": e.detalle} for e in eventos]}


# ── Alta ─────────────────────────────────────────────────────────────────────────────────────────
def _proximo_codigo(db: Session) -> str:
    anio = date.today().year
    prefijo = f"LOT-{anio}-"
    ultimo = db.query(func.max(models.Lote.codigo)).filter(models.Lote.codigo.like(f"{prefijo}%")).scalar()
    n = int(ultimo.rsplit("-", 1)[1]) + 1 if ultimo else 1
    return f"{prefijo}{n:05d}"


def _validar_pago(p: dict) -> tuple[dict | None, str]:
    cbu = "".join(ch for ch in str(p.get("cbu") or "") if ch.isdigit())
    if len(cbu) != 22:
        return None, "El CBU debe tener 22 dígitos."
    try:
        monto = Decimal(str(p.get("monto"))).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        return None, "Monto inválido."
    if monto <= 0:
        return None, "El monto debe ser mayor a cero."
    beneficiario = str(p.get("beneficiario") or "").strip()
    if not beneficiario:
        return None, "Falta el beneficiario."
    ref = str(p.get("referencia_externa") or "").strip()
    if not ref:
        return None, "Falta la referencia del pago."
    return {"referencia_externa": ref[:80], "beneficiario": beneficiario[:160],
            "documento": "".join(ch for ch in str(p.get("documento") or "") if ch.isalnum())[:20],
            "cbu": cbu, "monto": monto, "concepto": str(p.get("concepto") or "")[:120]}, ""


def crear_lote(db: Session, *, origen: str, referencia_origen: str, descripcion: str, pagos: list[dict],
               usuario: str, callback_url: str | None = None) -> tuple[models.Lote, list[dict], bool]:
    """Crea el lote con los pagos válidos. Devuelve (lote, rechazados, ya_existia)."""
    if origen not in models.ORIGENES:
        raise HTTPException(422, f"Origen inválido: {origen}.")
    referencia_origen = (referencia_origen or "").strip()[:80]
    if not referencia_origen:
        raise HTTPException(422, "Falta la referencia del lote.")
    ya = db.query(models.Lote).filter_by(origen=origen, referencia_origen=referencia_origen).first()
    if ya:
        return ya, [], True

    validos, rechazados, vistos = [], [], set()
    for p in pagos:
        v, motivo = _validar_pago(p)
        ref = str(p.get("referencia_externa") or "")
        if v and v["referencia_externa"] in vistos:
            v, motivo = None, "Referencia repetida dentro del lote."
        if v:
            vivo = (db.query(models.Pago).join(models.Lote)
                    .filter(models.Lote.origen == origen, models.Pago.referencia_externa == v["referencia_externa"],
                            models.Pago.estado.in_(VIVOS)).first())
            if vivo:
                v, motivo = None, f"Ya está en el lote {vivo.lote.codigo} ({vivo.estado})."
        if v:
            vistos.add(v["referencia_externa"]); validos.append(v)
        else:
            rechazados.append({"referencia_externa": ref, "motivo": motivo})
    if not validos:
        raise HTTPException(422, {"mensaje": "El lote no tiene pagos válidos.", "rechazados": rechazados})

    for intento in range(5):
        lote = models.Lote(codigo=_proximo_codigo(db), origen=origen, referencia_origen=referencia_origen,
                           descripcion=(descripcion or "")[:200], callback_url=callback_url, creado_por=usuario)
        lote.pagos = [models.Pago(**v) for v in validos]
        db.add(lote)
        try:
            db.flush()
            break
        except IntegrityError:
            db.rollback()
            ya = db.query(models.Lote).filter_by(origen=origen, referencia_origen=referencia_origen).first()
            if ya:                                   # otro proceso lo creó en paralelo
                return ya, [], True
    else:  # pragma: no cover - cinco colisiones seguidas de código
        raise HTTPException(409, "No se pudo numerar el lote; reintentá.")
    total = sum((v["monto"] for v in validos), Decimal(0))
    evento(db, lote, usuario, "ALTA", f"{len(validos)} pago(s) por ${total:,.2f}"
           + (f"; {len(rechazados)} rechazado(s) al cargar" if rechazados else ""))
    db.commit(); db.refresh(lote)
    return lote, rechazados, False


# ── Revisión ─────────────────────────────────────────────────────────────────────────────────────
def _pago_del_lote(lote: models.Lote, pago_id: int) -> models.Pago:
    p = next((x for x in lote.pagos if x.id == pago_id), None)
    if not p:
        raise HTTPException(404, "Pago no encontrado en el lote.")
    return p


def _reiniciar_aprobaciones(db: Session, lote: models.Lote, usuario: str) -> None:
    if lote.aprobaciones:
        lote.aprobaciones.clear()
        evento(db, lote, usuario, "APROBACIONES_REINICIADAS", "El lote cambió: vuelve a empezar la aprobación.")


def excluir(db: Session, lote: models.Lote, pago_id: int, motivo: str, user: Usuario) -> None:
    if lote.estado != "PENDIENTE_APROBACION":
        raise HTTPException(409, "Sólo se excluyen pagos de un lote pendiente de aprobación.")
    p = _pago_del_lote(lote, pago_id)
    if p.estado != "PENDIENTE":
        raise HTTPException(409, "El pago ya no está pendiente.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise HTTPException(422, "Indicá el motivo de la exclusión.")
    if sum(1 for x in lote.pagos if x.estado == "PENDIENTE") == 1:
        raise HTTPException(409, "Es el último pago del lote: para no enviar nada, rechazá el lote.")
    p.estado, p.motivo = "EXCLUIDO", motivo[:300]
    _reiniciar_aprobaciones(db, lote, user.username)
    evento(db, lote, user.username, "EXCLUSION", f"{p.beneficiario} (${p.monto:,.2f}): {motivo}")
    db.commit()


def incluir(db: Session, lote: models.Lote, pago_id: int, user: Usuario) -> None:
    if lote.estado != "PENDIENTE_APROBACION":
        raise HTTPException(409, "Sólo se modifican lotes pendientes de aprobación.")
    p = _pago_del_lote(lote, pago_id)
    if p.estado != "EXCLUIDO":
        raise HTTPException(409, "El pago no está excluido.")
    p.estado, p.motivo = "PENDIENTE", ""
    _reiniciar_aprobaciones(db, lote, user.username)
    evento(db, lote, user.username, "INCLUSION", f"{p.beneficiario} vuelve al lote")
    db.commit()


# ── Aprobación (workflow) ────────────────────────────────────────────────────────────────────────
def puede_aprobar(lote: models.Lote, user: Usuario, estricto: bool = True) -> tuple[bool, int, str, int]:
    """(ok, status_http, motivo, nivel_actual). Regla inactiva o inexistente: un paso, con el permiso
    de aprobar. Activa: cada nivel lo aprueba su rol (con excepciones por usuario) y, con cuatro-ojos,
    no puede aprobar quien armó el lote ni quien ya aprobó un nivel anterior."""
    nivel_actual = len(lote.aprobaciones) + 1
    if lote.estado != "PENDIENTE_APROBACION":
        return False, 409, "El lote no está pendiente de aprobación.", nivel_actual
    try:
        r = workflow.regla()
    except HTTPException:
        if estricto:
            raise
        return False, 503, "No se pudo leer el workflow de aprobación.", nivel_actual
    if r is None or not r.activo or not r.niveles:
        if not user.puede("aprobaciones:aprobar"):
            return False, 403, "Falta el permiso tesoreria:aprobaciones:aprobar (Seguridad).", nivel_actual
        return True, 200, "", nivel_actual
    nivel = next((n for n in r.niveles if n.orden == nivel_actual), None)
    if nivel is None:
        return False, 409, "La aprobación ya está completa.", nivel_actual
    if not workflow.habilitado(nivel, user.username, user.permisos):
        return False, 403, f"No te corresponde aprobar el nivel {nivel.orden} ({nivel.nombre}).", nivel_actual
    actores = {lote.creado_por} | {a.aprobado_por for a in lote.aprobaciones}
    if nivel.cuatro_ojos and user.username in actores:
        return False, 409, "Cuatro-ojos: no podés aprobar un lote que armaste o que ya aprobaste.", nivel_actual
    return True, 200, "", nivel_actual


def aprobar(db: Session, lote: models.Lote, user: Usuario) -> None:
    ok, status, motivo, nivel = puede_aprobar(lote, user)
    if not ok:
        raise HTTPException(status, motivo)
    if not any(p.estado == "PENDIENTE" for p in lote.pagos):
        raise HTTPException(409, "El lote no tiene pagos para aprobar.")
    db.add(models.LoteAprobacion(lote_id=lote.id, nivel_orden=nivel, aprobado_por=user.username))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Otro aprobador acaba de resolver este nivel. Refrescá el lote.")
    db.refresh(lote)
    r = workflow.regla()
    total = len(r.niveles) if (r and r.activo and r.niveles) else 1
    evento(db, lote, user.username, "APROBACION", f"Nivel {nivel} de {total}")
    if len(lote.aprobaciones) >= total:
        lote.estado, lote.aprobado_en = "APROBADO", _ahora()
        evento(db, lote, user.username, "LOTE_APROBADO", "Listo para enviar por Interbanking")
    db.commit()
    if lote.estado == "APROBADO":
        avisos.avisar(db, lote)            # los excluidos vuelven a su origen


def rechazar(db: Session, lote: models.Lote, motivo: str, user: Usuario) -> None:
    ok, status, msg, _ = puede_aprobar(lote, user)
    if not ok and status != 409:            # rechazar no exige cuatro-ojos, sí el rol del nivel
        raise HTTPException(status, msg)
    if lote.estado != "PENDIENTE_APROBACION":
        raise HTTPException(409, "Sólo se rechaza un lote pendiente de aprobación.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise HTTPException(422, "Indicá el motivo del rechazo.")
    lote.estado, lote.motivo_rechazo = "RECHAZADO", motivo[:300]
    for p in lote.pagos:
        if p.estado == "PENDIENTE":
            p.estado, p.motivo = "RECHAZADO", motivo[:300]
    evento(db, lote, user.username, "LOTE_RECHAZADO", motivo)
    db.commit()
    avisos.avisar(db, lote)


# ── Envío por Interbanking ───────────────────────────────────────────────────────────────────────
def _enviar_pago(db: Session, lote: models.Lote, p: models.Pago, desde: str) -> None:
    """Toma el pago (transición atómica desde `desde`), lo guarda ENVIANDO y recién ahí llama al banco."""
    tomado = (db.query(models.Pago).filter(models.Pago.id == p.id, models.Pago.estado == desde)
              .update({"estado": "ENVIANDO", "motivo": ""}, synchronize_session=False))
    db.commit()
    if not tomado:
        return
    db.refresh(p)
    p.enviado_en = _ahora()
    if settings.envio_simulado:
        p.estado, p.id_operacion_ib, p.estado_banco = "ENVIADO", f"SIM-{p.id}", "SIMULADO"
        db.commit()
        return
    concepto = f"{lote.codigo} {p.concepto}".strip()[:120]
    try:
        cuenta = {"account_number": lote.cuenta_origen, "account_type": lote.cuenta_origen_tipo,
                  "bank_number": lote.cuenta_origen_banco} if lote.cuenta_origen else None
        r = interbanking.enviar(p.cbu, float(p.monto), concepto, cuenta)
        p.transfer_id, p.id_operacion_ib = r.get("id"), str(r.get("id_operacion_ib") or "")
        p.estado_banco = str(r.get("status") or "")
        p.estado = interbanking.clasificar(p.estado_banco)
        if p.estado == "CONFIRMADO":
            p.confirmado_en = _ahora()
    except interbanking.EnvioRechazado as e:
        p.estado, p.motivo = "FALLIDO", f"Interbanking rechazó la transferencia: {e}"[:300]
    except interbanking.EnvioIncierto as e:
        p.estado, p.motivo = "INCIERTO", (f"{e}. Verificá en el banco si salió antes de resolverlo; "
                                          "no se reintenta solo.")[:300]
    db.commit()


def recalcular(lote: models.Lote) -> None:
    if lote.estado not in ("ENVIADO", "CON_ERRORES", "CONFIRMADO"):
        return
    activos = [p for p in lote.pagos if p.estado not in ("EXCLUIDO", "RECHAZADO")]
    if activos and all(p.estado == "CONFIRMADO" for p in activos):
        lote.estado = "CONFIRMADO"
    elif any(p.estado in ("FALLIDO", "INCIERTO") for p in activos) and not any(
            p.estado in ("ENVIANDO", "ENVIADO", "PENDIENTE") for p in activos):
        lote.estado = "CON_ERRORES"
    else:
        lote.estado = "ENVIADO"


def cuentas_para_pagar() -> dict:
    """Cuentas disponibles como origen del pago (las de Interbanking)."""
    return interbanking.cuentas()


def _elegir_cuenta(elegida: str | None) -> dict:
    """Valida la cuenta elegida contra las que ofrece Interbanking. Sin elección, la predeterminada.
    Con dinero de por medio no se envía a ciegas: sin cuenta, no sale. En simulación sí, para poder
    probar el circuito aunque Interbanking todavía no tenga cuentas configuradas."""
    disponibles = interbanking.cuentas().get("items") or []
    if elegida:
        cuenta = next((c for c in disponibles if str(c["account_number"]) == str(elegida)), None)
        if cuenta is None:
            raise HTTPException(422, "La cuenta de origen elegida no está entre las cuentas disponibles.")
        return cuenta
    cuenta = next((c for c in disponibles if c.get("predeterminada")), None)
    if cuenta is None:
        if settings.envio_simulado:
            return {}
        raise HTTPException(422, "Elegí desde qué cuenta sale el pago (no hay cuenta de pagos configurada "
                                 "en Interbanking).")
    return cuenta


def enviar(db: Session, lote: models.Lote, user: Usuario, cuenta_origen: str | None = None) -> None:
    if not user.puede("lotes:enviar"):
        raise HTTPException(403, "Falta el permiso tesoreria:lotes:enviar (Seguridad).")
    if lote.estado != "APROBADO":
        raise HTTPException(409, "El lote no está aprobado para enviar (o ya se está enviando).")
    cuenta = _elegir_cuenta(cuenta_origen)      # antes de tomar el lote: si falla, queda APROBADO
    tomado = (db.query(models.Lote).filter(models.Lote.id == lote.id, models.Lote.estado == "APROBADO")
              .update({"estado": "ENVIADO", "enviado_por": user.username, "enviado_en": _ahora(),
                       "simulado": settings.envio_simulado,
                       "cuenta_origen": str(cuenta.get("account_number") or "")[:50],
                       "cuenta_origen_tipo": (cuenta.get("account_type") or "CC")[:5],
                       "cuenta_origen_banco": (cuenta.get("bank_number") or "011")[:5],
                       "cuenta_origen_nombre": (cuenta.get("nombre") or "")[:120]}, synchronize_session=False))
    db.commit()
    if not tomado:
        raise HTTPException(409, "El lote no está aprobado para enviar (o ya se está enviando).")
    db.refresh(lote)
    desde = (f"desde la cuenta {lote.cuenta_origen_banco}/{lote.cuenta_origen}/{lote.cuenta_origen_tipo}"
             if lote.cuenta_origen else "sin cuenta de origen configurada")
    evento(db, lote, user.username, "ENVIO", f"Modo simulación: no se movió dinero ({desde})" if settings.envio_simulado
           else f"Enviado por Interbanking {desde}")
    db.commit()
    for p in list(lote.pagos):
        if p.estado == "PENDIENTE":
            _enviar_pago(db, lote, p, desde="PENDIENTE")
    db.refresh(lote)
    recalcular(lote)
    db.commit()
    avisos.avisar(db, lote)


def actualizar(db: Session, lote: models.Lote, usuario: str = "sistema") -> int:
    """Consulta en Interbanking los pagos en curso y reintenta los avisos pendientes. Devuelve cuántos
    pagos cambiaron de estado."""
    cambios = 0
    for p in lote.pagos:
        if p.estado != "ENVIADO":
            continue
        if lote.simulado or p.estado_banco == "SIMULADO":
            p.estado, p.estado_banco, p.confirmado_en = "CONFIRMADO", "SIMULADO", _ahora()
            cambios += 1
            continue
        if not p.transfer_id:
            continue
        try:
            eb = interbanking.estado(p.transfer_id)
        except Exception:
            continue                                    # se reintenta en la próxima actualización
        nuevo = interbanking.clasificar(eb)
        if eb != p.estado_banco or nuevo != p.estado:
            p.estado_banco, p.estado = eb, nuevo
            if nuevo == "CONFIRMADO":
                p.confirmado_en = _ahora()
            if nuevo == "FALLIDO":
                p.motivo = f"El banco informó {eb}."
            cambios += 1
    if cambios:
        evento(db, lote, usuario, "ESTADOS_ACTUALIZADOS", f"{cambios} pago(s) cambiaron de estado")
    recalcular(lote)
    db.commit()
    avisos.avisar(db, lote)
    return cambios


def reintentar(db: Session, lote: models.Lote, pago_id: int, user: Usuario) -> None:
    if not user.puede("lotes:enviar"):
        raise HTTPException(403, "Falta el permiso tesoreria:lotes:enviar (Seguridad).")
    p = _pago_del_lote(lote, pago_id)
    if p.estado != "FALLIDO":
        raise HTTPException(409, "Sólo se reintentan pagos fallidos (un pago incierto se resuelve a mano).")
    if lote.estado not in ("ENVIADO", "CON_ERRORES"):
        raise HTTPException(409, "El lote no está en envío.")
    # Un pago vivo por referencia: si el origen ya lo volvió a mandar en otro lote, reintentarlo acá lo
    # pagaría dos veces.
    otro = (db.query(models.Pago).join(models.Lote)
            .filter(models.Lote.origen == lote.origen, models.Pago.referencia_externa == p.referencia_externa,
                    models.Pago.id != p.id, models.Pago.estado.in_(VIVOS)).first())
    if otro:
        raise HTTPException(409, f"Ese pago ya se volvió a cargar en el lote {otro.lote.codigo} ({otro.estado}).")
    evento(db, lote, user.username, "REINTENTO", f"{p.beneficiario} (${p.monto:,.2f})")
    db.commit()
    _enviar_pago(db, lote, p, desde="FALLIDO")
    db.refresh(lote)
    recalcular(lote)
    db.commit()
    avisos.avisar(db, lote)


def resolver_incierto(db: Session, lote: models.Lote, pago_id: int, resultado: str, observacion: str,
                      user: Usuario) -> None:
    """El tesorero verificó en el banco qué pasó con un pago incierto y lo registra."""
    if not user.puede("lotes:enviar"):
        raise HTTPException(403, "Falta el permiso tesoreria:lotes:enviar (Seguridad).")
    p = _pago_del_lote(lote, pago_id)
    if p.estado != "INCIERTO":
        raise HTTPException(409, "El pago no está incierto.")
    if resultado not in ("CONFIRMADO", "FALLIDO"):
        raise HTTPException(422, "Resultado inválido (CONFIRMADO | FALLIDO).")
    observacion = (observacion or "").strip()
    if not observacion:
        raise HTTPException(422, "Indicá qué verificaste en el banco.")
    p.estado, p.motivo = resultado, f"Resuelto a mano: {observacion}"[:300]
    if resultado == "CONFIRMADO":
        p.confirmado_en = _ahora()
    evento(db, lote, user.username, "INCIERTO_RESUELTO", f"{p.beneficiario}: {resultado} — {observacion}")
    recalcular(lote)
    db.commit()
    avisos.avisar(db, lote)
