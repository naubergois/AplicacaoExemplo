from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from app.agents.base import (
    deve_bloquear_por_politica,
    get_llm,
    mensagem_politica_indisponivel,
)
from app.agents.flight_info_agent import delegar_execucao_tool_voos, ferramentas_voos


class VendasAgent:
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
                    "agente": "Agente de Vendas",
                    "tool": "-",
                    "detalhe": "Iniciou atendimento comercial",
                }
            )

        tools = ferramentas_voos()
        llm_with_tools = self.llm.bind_tools(tools)
        messages = [
            SystemMessage(
                content=(
                    "Voce e um agente de vendas de passagens aereas. Responda em portugues "
                    "brasileiro com foco comercial e consultivo.\n\n"
                    "Diretrizes:\n"
                    "- Use as tools de voos para consultar disponibilidade e preco quando o cliente "
                    "pedir cotacao ou opcoes de voo.\n"
                    "- Quando faltar origem, destino, data ou quantidade de passageiros, pergunte "
                    "de forma objetiva antes de fechar recomendacao.\n"
                    "- Sugira opcoes de tarifa (economica, flexivel, executiva) com linguagem clara.\n"
                    "- Nao ofereca milhagem, bagagem, descontos ou beneficios sem politica definida.\n"
                    "- Finalize com CTA para avancar na compra."
                )
            ),
            HumanMessage(content=f"Cliente: {customer_name or 'Nao informado'}\nPedido: {message}"),
        ]

        for _ in range(4):
            ai_msg = llm_with_tools.invoke(messages)
            messages.append(ai_msg)

            tool_calls = getattr(ai_msg, "tool_calls", None) or []
            if not tool_calls:
                return str(ai_msg.content)

            for call in tool_calls:
                resultado = delegar_execucao_tool_voos(
                    call,
                    execution_trace=execution_trace,
                    solicitante="Agente de Vendas",
                )

                messages.append(ToolMessage(content=resultado, tool_call_id=call.get("id", "")))

        return "Nao foi possivel concluir a cotacao neste momento. Tente novamente."
