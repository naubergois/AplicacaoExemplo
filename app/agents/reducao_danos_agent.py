from app.agents.base import deve_bloquear_por_politica, get_llm, mensagem_politica_indisponivel


class ReducaoDanosAgent:
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
                    "agente": "Agente de Reducao de Danos",
                    "tool": "-",
                    "detalhe": "Tentativa de retencao iniciada",
                }
            )

        prompt = f"""
Voce e um agente de reducao de danos (retencao) de uma empresa de passagens aereas.
Sua funcao e tentar reter o cliente antes do cancelamento, sem prometer algo sem politica definida.
Responda em portugues brasileiro de forma empatica e objetiva.

Cliente: {customer_name or 'Nao informado'}
Solicitacao inicial: {message}

Diretrizes:
- Reconheca o motivo do cliente e demonstre empatia.
- Tente reter com alternativas validas: remarcacao, credito em carteira, ajuste de datas, suporte prioritario.
- Nao ofereca milhagem, bagagem ou beneficios sem politica definida.
- Se nao houver alternativa segura no contexto, diga que vai encaminhar para cancelamento.
- Finalize perguntando se o cliente deseja seguir com uma alternativa ou confirmar o cancelamento.
""".strip()
        if execution_trace is not None:
            execution_trace.append(
                {
                    "etapa": "llm",
                    "agente": "Agente de Reducao de Danos",
                    "tool": "llm:deepseek",
                    "detalhe": "Chamada ao modelo para tentativa de retencao",
                }
            )
        return self.llm.invoke(prompt).content
