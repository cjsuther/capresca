from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.dependencies.auth import get_current_user_id
from app.models.interactive_menu import InteractiveMenuConfig, InteractiveMenuOption
from app.schemas.menu import MenuConfigResponse, MenuConfigUpdate, MenuOptionSchema

router = APIRouter(tags=["menu"])


@router.get("/menu", response_model=MenuConfigResponse)
def get_menu(db: Session = Depends(get_db)):
    menu = db.query(InteractiveMenuConfig).filter(InteractiveMenuConfig.is_active == True).first()
    if not menu:
        # Return default empty menu
        menu = InteractiveMenuConfig(
            id=0,
            greeting_text="Hola! Bienvenido a Portezuelo. Seleccione una opcion:",
            is_active=True,
        )
        menu.options = []
    return _menu_to_response(menu)


@router.put("/menu", response_model=MenuConfigResponse)
def update_menu(
    data: MenuConfigUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    menu = db.query(InteractiveMenuConfig).filter(InteractiveMenuConfig.is_active == True).first()

    if not menu:
        menu = InteractiveMenuConfig(
            greeting_text=data.greeting_text,
            is_active=True,
            updated_by=user_id,
        )
        db.add(menu)
        db.flush()
    else:
        menu.greeting_text = data.greeting_text
        menu.updated_by = user_id

    # Replace all options
    db.query(InteractiveMenuOption).filter(InteractiveMenuOption.menu_id == menu.id).delete()
    db.flush()

    for opt in data.options:
        option = InteractiveMenuOption(
            menu_id=menu.id,
            option_id=opt.option_id,
            title=opt.title,
            description=opt.description,
            sort_order=opt.sort_order,
            action_type=opt.action_type,
            action_payload=opt.action_payload,
            requires_client=opt.requires_client,
            is_active=opt.is_active,
        )
        db.add(option)

    db.commit()
    db.refresh(menu)
    return _menu_to_response(menu)


def _menu_to_response(menu: InteractiveMenuConfig) -> dict:
    return {
        "id": menu.id,
        "greeting_text": menu.greeting_text,
        "is_active": menu.is_active,
        "options": [
            {
                "option_id": o.option_id,
                "title": o.title,
                "description": o.description,
                "sort_order": o.sort_order,
                "action_type": o.action_type,
                "action_payload": o.action_payload,
                "requires_client": o.requires_client,
                "is_active": o.is_active,
            }
            for o in (menu.options or [])
        ],
    }
