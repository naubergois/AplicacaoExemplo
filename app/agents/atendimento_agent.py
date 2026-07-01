from urllib.parse import quote

import requests
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from app.agents.base import (
    deve_bloquear_por_politica,
    executar_tool_call,
    get_llm,
    mensagem_politica_indisponivel,
    montar_registro_tools,
)
from app.agents.flight_info_agent import delegar_execucao_tool_voos, ferramentas_voos


@tool("consultar_clima_cidade")
def consultar_clima_cidade(cidade: str) -> str:
    """Consulta temperatura e condicao do clima atual de uma cidade."""
    try:
        url = f"https://wttr.in/{quote(cidade)}?format=j1"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        atual = data.get("current_condition", [{}])[0]
        desc = atual.get("weatherDesc", [{"value": "Sem descricao"}])[0].get("value", "Sem descricao")
        temp = atual.get("temp_C", "N/A")
        umidade = atual.get("humidity", "N/A")
        vento = atual.get("windspeedKmph", "N/A")
        return (
            f"Clima em {cidade}: {desc}. Temperatura: {temp} C. "
            f"Umidade: {umidade}%. Vento: {vento} km/h."
        )
    except Exception:
        return f"Nao foi possivel consultar o clima em {cidade} neste momento."


class AtendimentoAgent:
    def __init__(self) -> None:
        self.llm = get_llm()

    def respond(
        self,
        message: str,
        customer_name: str | None = None,
        execution_trace: list[dict[str, str]] | None = None,
    ) -> str:
        if deve_bloquear_por_politica(message):
            return mensagem_politica_indisponivel()

        if execution_trace is not None:
            execution_trace.append(
                {
                    "etapa": "agente",
                    "agente": "Agente de Atendimento",
                    "tool": "-",
                    "detalhe": "Iniciou atendimento geral",
                }
            )

        own_tools = [consultar_clima_cidade]
        flight_tools = ferramentas_voos()
        own_tool_registry = montar_registro_tools(own_tools)
        llm_with_tools = self.llm.bind_tools(own_tools + flight_tools)
        messages = [
            SystemMessage(
                content=(
                    "Voce e um agente de atendimento de uma empresa de passagens aereas com foco "
                    "em marketing e experiencia do cliente. Responda em portugues brasileiro de "
                    "forma objetiva, cordial e util.\n\n"
                    "Diretrizes:\n"
                    "- Se a duvida for geral, esclareca politicas e proximos passos.\n"
                    "- Use a tool consultar_clima_cidade quando o cliente perguntar sobre clima, "
                    "temperatura, previsao ou tempo em uma cidade.\n"
                    "- Use as tools buscar_voos e melhores_ofertas_voos quando o cliente pedir "
                    "disponibilidade, horario, status, rota ou preco de voo.\n"
                    "- Se faltar cidade para consulta de clima, pergunte a cidade antes de responder.\n"
                    "- Se faltar origem, destino ou data para consulta de voos, pergunte os dados "
                    "minimos necessarios antes de responder.\n"
                    "- Quando a mensagem trouxer o bloco [MEMORIA DE CLIENTE], use essas "
                    "informacoes para personalizar a resposta e evitar perguntas repetidas.\n"
                    "- So fale sobre milhagem, bagagem, descontos e beneficios se houver politica "
                    "interna explicita para isso.\n"
                    "- Se o cliente perguntar sobre assunto sem ferramenta disponivel ou sem "
                    "politica estabelecida, informe que nao pode confirmar no momento e encaminhe "
                    "para equipe humana.\n"
                    "- Para perguntas sobre milhagem e bagagem sem politica definida, responda "
                    "que a informacao nao esta disponivel neste canal.\n"
                    "- Nao invente regras juridicas. Quando necessario, diga que vai validar com a equipe."
                )
            ),
            HumanMessage(content=f"Cliente: {customer_name or 'Nao informado'}\nMensagem: {message}"),
        ]

        for _ in range(4):
            ai_msg = llm_with_tools.invoke(messages)
            messages.append(ai_msg)

            tool_calls = getattr(ai_msg, "tool_calls", None) or []
            if not tool_calls:
                return str(ai_msg.content)

            for call in tool_calls:
                resultado = executar_tool_call(
                    tool_registry=own_tool_registry,
                    tool_call=call,
                    unavailable_message="",
                )
                if not resultado:
                    resultado = delegar_execucao_tool_voos(
                        call,
                        execution_trace=execution_trace,
                        solicitante="Agente de Atendimento",
                    )
                elif execution_trace is not None:
                    execution_trace.append(
                        {
                            "etapa": "tool",
                            "agente": "Agente de Atendimento",
                            "tool": str(call.get("name", "desconhecida")),
                            "detalhe": "Executou tool propria",
                        }
                    )

                messages.append(ToolMessage(content=resultado, tool_call_id=call.get("id", "")))

        return "Nao foi possivel concluir o atendimento neste momento. Tente novamente."
