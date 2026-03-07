from pydantic import BaseModel
from typing import Optional


class ModuleResponse(BaseModel):
    id: int
    code: str
    name: str
    description: Optional[str]
    icon: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}
