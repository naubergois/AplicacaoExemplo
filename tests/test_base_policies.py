"""Testes de politicas e utilitarios de tools em app/agents/base.py.

Aprendizado coberto:
- get_llm() deve exigir DEEPSEEK_API_KEY (falha explicita, nao silenciosa).
- Bloqueio por politica (milhas/bagagem) e case-insensitive.
- Execucao dinamica de tools por registro (montar_registro_tools + executar_tool_call)
  para evitar hardcode por nome; tool inexistente -> mensagem de indisponibilidade;
  tool que lanca excecao -> mensagem de fallback (nunca propaga o erro).
"""

import pytest
from langchain_core.tools import tool

from app.agents.base import (
    deve_bloquear_por_politica,
    executar_tool_call,
    get_llm,
    mensagem_politica_indisponivel,
    montar_registro_tools,
)


def test_get_llm_exige_api_key(monkeypatch):
    get_llm.cache_clear()
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        get_llm()
    get_llm.cache_clear()  # limpa para nao vazar estado sem chave para outros testes


@pytest.mark.parametrize(
    "texto",
    ["Quero saber sobre MILHAS", "posso levar bagagem extra?", "programa de milhas"],
)
def test_bloqueio_por_politica_positivo(texto):
    assert deve_bloquear_por_politica(texto) is True


@pytest.mark.parametrize(
    "texto",
    ["quero comprar passagem", "qual o status do voo?", "cancelar reserva"],
)
def test_bloqueio_por_politica_negativo(texto):
    assert deve_bloquear_por_politica(texto) is False


def test_mensagem_politica_menciona_equipe_humana():
    assert "humana" in mensagem_politica_indisponivel().lower()


@tool("tool_ok")
def _tool_ok(valor: str) -> str:
    """Retorna o valor recebido."""
    return f"ok:{valor}"


@tool("tool_quebra")
def _tool_quebra(valor: str) -> str:
    """Sempre lanca excecao para testar o fallback."""
    raise ValueError("falha proposital")


def test_montar_registro_tools_indexa_por_nome():
    registro = montar_registro_tools([_tool_ok, _tool_quebra])
    assert set(registro.keys()) == {"tool_ok", "tool_quebra"}


def test_executar_tool_call_sucesso():
    registro = montar_registro_tools([_tool_ok])
    resultado = executar_tool_call(
        registro, {"name": "tool_ok", "args": {"valor": "x"}}, "indisponivel"
    )
    assert resultado == "ok:x"


def test_executar_tool_call_tool_inexistente():
    registro = montar_registro_tools([_tool_ok])
    resultado = executar_tool_call(
        registro, {"name": "nao_existe", "args": {}}, "indisponivel"
    )
    assert resultado == "indisponivel"


def test_executar_tool_call_absorve_excecao():
    registro = montar_registro_tools([_tool_quebra])
    resultado = executar_tool_call(
        registro, {"name": "tool_quebra", "args": {"valor": "x"}}, "indisponivel"
    )
    assert "nao foi possivel" in resultado.lower()
