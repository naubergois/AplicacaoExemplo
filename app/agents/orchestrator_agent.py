from app.agents.base import get_llm

_INTENT_MAP = {
    "atendimento": "Agente de Atendimento",
    "vendas": "Agente de Vendas",
    "cancelamento": "Agente de Cancelamento",
}


class OrchestratorAgent:
    def __init__(self) -> None:
        self.llm = get_llm()

    def build_prompt(self, message: str) -> str:
        return f"""
Voce e o agente ORQUESTRADOR de uma aplicacao de passagens aereas.
Analise a mensagem do cliente e decida, com julgamento proprio, qual agente deve
atende-lo. Nao use apenas palavras-chave: interprete a intencao real do cliente.

Agentes disponiveis:
- atendimento: duvidas gerais, suporte, orientacoes, informacoes de voos, clima e
  qualquer caso ambiguo ou sem contexto suficiente (triagem inicial).
- vendas: intencao real de comprar, cotar, comparar tarifas ou fechar uma compra.
- cancelamento: intencao clara de cancelar viagem, pedir estorno ou encerrar reserva.

Diretrizes de decisao:
- Se a intencao nao estiver clara, escolha atendimento para coletar mais informacoes.
- So escolha cancelamento quando houver intencao real de cancelar, nao apenas mencao ao tema.
- So escolha vendas quando houver intencao real de comprar ou cotar.

Explique brevemente seu raciocinio antes de decidir e, ao final,
retorne estritamente neste formato:
AGENTE: atendimento|vendas|cancelamento
TAREFA: texto curto descrevendo a tarefa principal
AVALIACAO: texto curto explicando por que esse agente foi escolhido

Mensagem do cliente: {message}
""".strip()

    def parse_decision(self, raw: str) -> dict[str, str]:
        resposta = str(raw).strip()
        resposta_lower = resposta.lower()

        intent = "atendimento"
        for linha in resposta_lower.splitlines():
            if linha.strip().startswith("agente:"):
                candidato = linha.split(":", 1)[1].strip()
                if candidato in _INTENT_MAP:
                    intent = candidato
                break

        tarefa = "Atendimento geral e orientacao"
        avaliacao = "Caso direcionado pela decisao do LLM (DeepSeek) com fallback de triagem."
        for linha in resposta_lower.splitlines():
            if linha.strip().startswith("tarefa:"):
                tarefa = linha.split("tarefa:", 1)[1].strip().capitalize() or tarefa
            if linha.strip().startswith("avaliacao:"):
                avaliacao = linha.split("avaliacao:", 1)[1].strip().capitalize() or avaliacao

        return {
            "intent": intent,
            "agente_responsavel": _INTENT_MAP[intent],
            "tarefa": tarefa,
            "avaliacao_orquestrador": avaliacao,
        }

    def register(
        self,
        decision: dict[str, str],
        execution_trace: list[dict[str, str]] | None = None,
    ) -> dict[str, str]:
        if execution_trace is not None:
            execution_trace.append(
                {
                    "etapa": "roteamento",
                    "agente": "Orquestrador",
                    "tool": "llm:deepseek",
                    "detalhe": (
                        f"Intent={decision['intent']}; "
                        f"Agente={decision['agente_responsavel']}; "
                        f"Tarefa={decision['tarefa']}; "
                        f"Avaliacao={decision['avaliacao_orquestrador']}"
                    ),
                }
            )
        return {
            "intent": decision["intent"],
            "agente_responsavel": decision["agente_responsavel"],
            "tarefa": decision["tarefa"],
            "avaliacao_orquestrador": decision["avaliacao_orquestrador"],
        }

    def evaluate_case(
        self,
        message: str,
        execution_trace: list[dict[str, str]] | None = None,
    ) -> dict[str, str]:
        raw = self.llm.invoke(self.build_prompt(message)).content
        decision = self.parse_decision(str(raw))
        return self.register(decision, execution_trace=execution_trace)
