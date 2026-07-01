from app.agents.base import get_llm


class OrchestratorAgent:
    def __init__(self) -> None:
        self.llm = get_llm()

    def evaluate_case(
        self,
        message: str,
        execution_trace: list[dict[str, str]] | None = None,
    ) -> dict[str, str]:
        def registrar(intent: str, agente: str, tarefa: str, avaliacao: str) -> dict[str, str]:
            if execution_trace is not None:
                execution_trace.append(
                    {
                        "etapa": "roteamento",
                        "agente": "Orquestrador",
                        "tool": "llm:deepseek",
                        "detalhe": f"Intent={intent}; Agente={agente}; Tarefa={tarefa}",
                    }
                )
            return {
                "intent": intent,
                "agente_responsavel": agente,
                "tarefa": tarefa,
                "avaliacao_orquestrador": avaliacao,
            }

        raw = self.llm.invoke(
            f"""
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

Retorne estritamente neste formato:
AGENTE: atendimento|vendas|cancelamento
TAREFA: texto curto descrevendo a tarefa principal
AVALIACAO: texto curto explicando por que esse agente foi escolhido

Mensagem do cliente: {message}
""".strip()
        ).content

        resposta = str(raw).strip()
        resposta_lower = resposta.lower()

        intent_map = {
            "atendimento": "Agente de Atendimento",
            "vendas": "Agente de Vendas",
            "cancelamento": "Agente de Cancelamento",
        }

        intent = "atendimento"
        agente_responsavel = intent_map[intent]

        for linha in resposta_lower.splitlines():
            if linha.strip().startswith("agente:"):
                candidato = linha.split(":", 1)[1].strip()
                if candidato in intent_map:
                    intent = candidato
                    agente_responsavel = intent_map[intent]
                break

        tarefa = "Atendimento geral e orientacao"
        avaliacao = "Caso direcionado pela decisao do LLM (DeepSeek) com fallback de triagem."

        for linha in resposta_lower.splitlines():
            if linha.strip().startswith("tarefa:"):
                tarefa = linha.split("tarefa:", 1)[1].strip().capitalize() or tarefa
            if linha.strip().startswith("avaliacao:"):
                avaliacao = linha.split("avaliacao:", 1)[1].strip().capitalize() or avaliacao

        return registrar(intent, agente_responsavel, tarefa, avaliacao)
