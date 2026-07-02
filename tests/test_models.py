"""Testes dos modelos Pydantic da API."""

import pytest
from pydantic import ValidationError

from app.models import ChatRequest, ChatResponse


def test_chat_request_exige_mensagem_minima():
    with pytest.raises(ValidationError):
        ChatRequest(message="a")  # min_length=2


def test_chat_request_campos_opcionais():
    req = ChatRequest(message="ola")
    assert req.customer_name is None
    assert req.reservation_code is None


def test_chat_response_defaults():
    resp = ChatResponse(intent="atendimento", response="ok")
    assert resp.execucao == []
    assert resp.memoria is None
    assert resp.agente_responsavel is None


def test_chat_response_intent_invalido():
    with pytest.raises(ValidationError):
        ChatResponse(intent="financeiro", response="ok")
