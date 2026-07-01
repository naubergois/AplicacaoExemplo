from typing import Literal, Optional

from pydantic import BaseModel, Field


Intent = Literal["atendimento", "vendas", "cancelamento"]


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=2)
    customer_name: Optional[str] = None
    reservation_code: Optional[str] = None


class ChatResponse(BaseModel):
    intent: Intent
    response: str


class IntentOutput(BaseModel):
    intent: Intent
