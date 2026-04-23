import httpx
from datetime import date
from sqlalchemy.orm import Session
from app.models.interactive_menu import InteractiveMenuConfig, InteractiveMenuOption
from app.models.conversation import Conversation
from app.services import whatsapp_service

GREETING_PATTERNS = [
    "hola", "buenas", "buen dia", "buenos dias", "buenas tardes",
    "buenas noches", "hi", "hello", "menu",
]


def is_greeting(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in GREETING_PATTERNS or normalized.startswith("hola")


def get_active_menu(db: Session) -> InteractiveMenuConfig | None:
    return (
        db.query(InteractiveMenuConfig)
        .filter(InteractiveMenuConfig.is_active == True)
        .first()
    )


def get_menu_option(db: Session, option_id: str) -> InteractiveMenuOption | None:
    return (
        db.query(InteractiveMenuOption)
        .filter(
            InteractiveMenuOption.option_id == option_id,
            InteractiveMenuOption.is_active == True,
        )
        .first()
    )


async def send_interactive_menu(db: Session, phone: str, conversation: Conversation = None) -> dict | None:
    """Envia el menu interactivo al contacto."""
    menu = get_active_menu(db)
    if not menu or not menu.options:
        return None

    has_client = conversation and conversation.client_id is not None
    active_options = [o for o in menu.options if o.is_active and (not o.requires_client or has_client)]
    if not active_options:
        return None

    rows = [
        {
            "id": o.option_id,
            "title": o.title[:24],  # WA limit for row title
            "description": (o.description or "")[:72],  # WA limit for row description
        }
        for o in active_options
    ]

    sections = [{"title": "Opciones", "rows": rows}]

    return await whatsapp_service.send_interactive_list(
        to=phone,
        header_text="Portezuelo",
        body_text=menu.greeting_text,
        sections=sections,
    )


async def process_menu_reply(db: Session, conversation: Conversation, reply_id: str) -> str | None:
    """Procesa la seleccion de una opcion del menu. Retorna el texto de respuesta."""
    option = get_menu_option(db, reply_id)
    if not option:
        return "Opcion no reconocida. Escriba 'hola' para ver el menu."

    # Check if the option requires a linked client
    if option.requires_client and conversation.client_id is None:
        return (
            "Para usar esta opcion necesitamos verificar su identidad. "
            "Un operador se comunicara con usted en breve."
        )

    if option.action_type == "REPLY_TEXT":
        return option.action_payload.get("text", "")

    elif option.action_type == "CALL_MODULE":
        payload = option.action_payload
        url_template = payload.get("url_template", "")
        url = url_template.format(
            client_id=conversation.client_id,
            today=date.today().isoformat(),
        )
        try:
            async with httpx.AsyncClient() as client:
                r = await client.request(
                    payload.get("method", "GET"), url, timeout=15.0,
                )
                if r.status_code == 200:
                    data = r.json()
                    response_template = payload.get("response_template", "{}")
                    return response_template.format(**data)
                else:
                    return "No se pudo obtener la informacion en este momento. Intente mas tarde."
        except Exception as e:
            print(f"[menu_service] Error calling module: {e}")
            return "Ocurrio un error al consultar la informacion. Intente mas tarde."

    return None
