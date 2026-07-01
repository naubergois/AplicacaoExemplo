import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

load_dotenv()

_TOPICOS_RESTRITOS = (
    "milha",
    "milhas",
    "milhagem",
    "pontos",
    "programa de milhas",
    "bagagem",
    "franquia",
    "mala",
)


@lru_cache
def get_llm() -> ChatOpenAI:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("A variavel DEEPSEEK_API_KEY nao foi definida.")

    return ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        api_key=api_key,
        base_url="https://api.deepseek.com",
        temperature=0.2,
    )


def mensagem_politica_indisponivel() -> str:
    return (
        "No momento, este canal nao possui ferramenta ou politica oficial configurada para "
        "responder sobre milhagem e bagagem. Para evitar informacao imprecisa, vou encaminhar "
        "seu caso para a equipe humana de atendimento."
    )


def deve_bloquear_por_politica(message: str) -> bool:
    texto = message.lower()
    return any(topico in texto for topico in _TOPICOS_RESTRITOS)


def montar_registro_tools(tools: list[BaseTool]) -> dict[str, BaseTool]:
    return {tool.name: tool for tool in tools}


def executar_tool_call(
    tool_registry: dict[str, BaseTool],
    tool_call: dict[str, Any],
    unavailable_message: str,
) -> str:
    nome = str(tool_call.get("name", ""))
    args = tool_call.get("args", {})
    tool = tool_registry.get(nome)
    if tool is None:
        return unavailable_message

    try:
        return str(tool.invoke(args))
    except Exception:
        return "Nao foi possivel executar a consulta solicitada neste momento."
