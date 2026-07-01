from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CustomerStructuredMemory(BaseModel):
    customer_name: str
    total_interactions: int = 0
    intents_history: list[str] = Field(default_factory=list)
    preferred_origins: list[str] = Field(default_factory=list)
    preferred_destinations: list[str] = Field(default_factory=list)
    reservation_codes: list[str] = Field(default_factory=list)
    last_message: str | None = None
    last_response: str | None = None
    last_intent: str | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatInteractionRecord(BaseModel):
    customer_name: str
    message: str
    response: str
    intent: str
    agente_responsavel: str | None = None
    reservation_code: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
