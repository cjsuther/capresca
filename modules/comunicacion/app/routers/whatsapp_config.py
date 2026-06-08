from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.dependencies.auth import get_current_user_id
from app.models.whatsapp_config import WhatsappConfig
from app.schemas.whatsapp import WhatsappConfigResponse, WhatsappConfigUpdate

router = APIRouter(tags=["whatsapp-config"])


@router.get("/whatsapp-config", response_model=WhatsappConfigResponse)
def get_config(db: Session = Depends(get_db)):
    config = db.query(WhatsappConfig).filter(WhatsappConfig.is_active == True).first()
    if not config:
        raise HTTPException(404, "Configuracion de WhatsApp no encontrada")
    return _mask_config(config)


@router.put("/whatsapp-config", response_model=WhatsappConfigResponse)
def update_config(
    data: WhatsappConfigUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    config = db.query(WhatsappConfig).filter(WhatsappConfig.is_active == True).first()

    if not config:
        # Alta inicial: access_token es obligatorio
        if not data.access_token:
            raise HTTPException(400, "access_token es requerido para la configuración inicial")
        config = WhatsappConfig(
            phone_number_id=data.phone_number_id,
            business_account_id=data.business_account_id,
            access_token=data.access_token,
            webhook_verify_token=data.webhook_verify_token,
            app_secret=data.app_secret or None,
            display_phone_number=data.display_phone_number,
            is_active=True,
            updated_by_user_id=user_id,
        )
        db.add(config)
    else:
        config.phone_number_id = data.phone_number_id
        config.business_account_id = data.business_account_id
        config.webhook_verify_token = data.webhook_verify_token
        config.display_phone_number = data.display_phone_number
        # Token y app_secret: si vienen vacíos en el form, preservar lo guardado
        if data.access_token:
            config.access_token = data.access_token
        if data.app_secret is not None and data.app_secret != "":
            config.app_secret = data.app_secret
        config.updated_by_user_id = user_id

    db.commit()
    db.refresh(config)
    return _mask_config(config)


def _mask_config(config: WhatsappConfig) -> dict:
    token = config.access_token or ""
    masked = token[:8] + "..." + token[-4:] if len(token) > 12 else "***"
    return {
        "id": config.id,
        "phone_number_id": config.phone_number_id,
        "business_account_id": config.business_account_id,
        "access_token_masked": masked,
        "webhook_verify_token": config.webhook_verify_token,
        "has_app_secret": bool(config.app_secret),
        "display_phone_number": config.display_phone_number,
        "is_active": config.is_active,
    }
