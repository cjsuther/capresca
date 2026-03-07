from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.transfers import Transfer
from app.services import interbanking_client


def list_transfers(db: Session, page: int = 1, per_page: int = 20):
    q = db.query(Transfer).order_by(Transfer.initiated_at.desc())
    total = q.count()
    data = q.offset((page - 1) * per_page).limit(per_page).all()
    return data, total


def validar_cbu(db: Session, user_id: int, cbu_or_alias: str, username: str = None, ip: str = None):
    return interbanking_client.call(
        db=db,
        user_id=user_id,
        operation="VALIDAR_CBU",
        method="POST",
        path="/transferencias/validar",
        payload={"cbu_or_alias": cbu_or_alias},
        username=username,
        ip_address=ip,
    )


def iniciar_transferencia(
    db: Session,
    user_id: int,
    cuenta_origen: str,
    cbu_destino: str,
    monto,
    concepto: str,
    username: str = None,
    ip: str = None,
):
    result = interbanking_client.call(
        db=db,
        user_id=user_id,
        operation="INICIAR_TRANSFERENCIA",
        method="POST",
        path="/transferencias/iniciar",
        payload={
            "cuenta_origen": cuenta_origen,
            "cbu_destino": cbu_destino,
            "monto": str(monto),
            "concepto": concepto,
        },
        username=username,
        ip_address=ip,
    )
    transfer = Transfer(
        cuenta_origen=cuenta_origen,
        cbu_destino=cbu_destino,
        monto=monto,
        concepto=concepto,
        id_operacion_ib=result.get("id_operacion"),
        status=result.get("status", "INICIADA"),
        initiated_by=user_id,
    )
    db.add(transfer)
    db.commit()
    db.refresh(transfer)
    return transfer


def get_estado_transferencia(db: Session, user_id: int, transfer_id: str, username: str = None, ip: str = None):
    result = interbanking_client.call(
        db=db,
        user_id=user_id,
        operation="ESTADO_TRANSFERENCIA",
        method="GET",
        path=f"/transferencias/{transfer_id}/estado",
        username=username,
        ip_address=ip,
    )
    # Actualizar registro local si existe
    transfer = db.query(Transfer).filter(Transfer.id_operacion_ib == transfer_id).first()
    if transfer:
        transfer.status = result.get("status", transfer.status)
        transfer.last_status_check = datetime.now(timezone.utc)
        transfer.last_status_payload = result
        db.commit()
    return result
