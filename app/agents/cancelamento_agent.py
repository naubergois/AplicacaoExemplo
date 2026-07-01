from app.agents.base import deve_bloquear_por_politica, get_llm, mensagem_politica_indisponivel


class CancelamentoAgent:
    def __init__(self) -> None:
        self.llm = get_llm()

    def respond(
        self,
        message: str,
        reservation_code: str | None = None,
        customer_name: str | None = None,
        contexto_retencao: str | None = None,
        execution_trace: list[dict[str, str]] | None = None,
    ) -> str:
        if deve_bloquear_por_politica(message):
            return mensagem_politica_indisponivel()

        if execution_trace is not None:
            execution_trace.append(
                {
                    "etapa": "agente",
                    "agente": "Agente de Cancelamento",
                    "tool": "-",
                    "detalhe": "Procedimento de cancelamento iniciado",
                }
            )

        prompt = f"""
Voce e um agente de cancelamento de passagens aereas.
Responda em portugues brasileiro de modo empatico e claro.

Cliente: {customer_name or 'Nao informado'}
Codigo da reserva: {reservation_code or 'Nao informado'}
Solicitacao: {message}
Contexto previo de retencao: {contexto_retencao or 'Nao houve tentativa de retencao'}

Diretrizes:
- Nao repita o texto da etapa de retencao; foque apenas no procedimento de cancelamento.
- Liste passos para cancelar com seguranca.
- Informe de forma neutra que multa/reembolso dependem da tarifa e prazo.
- Oriente como acompanhar status do estorno.
- Se faltar codigo da reserva, solicite.
- Se a solicitacao depender de ferramenta indisponivel ou politica nao estabelecida, nao invente resposta: informe limitacao e encaminhe para a equipe humana.
""".strip()
        return self.llm.invoke(prompt).content
