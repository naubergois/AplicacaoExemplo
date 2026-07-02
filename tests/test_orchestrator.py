"""Testes do parsing/roteamento do Orquestrador.

Aprendizado coberto (regressao):
- Roteamento e 100% via LLM, mas o PARSE deve ser estrito na linha "AGENTE:".
- Nao pode haver falso positivo de cancelamento so porque a palavra "cancelar"
  aparece no raciocinio/saudacao (bug historico de substring global).
- Fallback para atendimento quando o intent nao e reconhecido.
"""

from app.agents.orchestrator_agent import OrchestratorAgent


def _agent() -> OrchestratorAgent:
    return OrchestratorAgent()


def test_parse_decision_vendas():
    raw = (
        "Penso que o cliente quer comprar.\n"
        "AGENTE: vendas\n"
        "TAREFA: cotar passagem\n"
        "AVALIACAO: intencao clara de compra"
    )
    decisao = _agent().parse_decision(raw)
    assert decisao["intent"] == "vendas"
    assert decisao["agente_responsavel"] == "Agente de Vendas"
    assert decisao["tarefa"].lower().startswith("cotar")


def test_parse_decision_cancelamento():
    raw = "AGENTE: cancelamento\nTAREFA: cancelar reserva\nAVALIACAO: pediu estorno"
    decisao = _agent().parse_decision(raw)
    assert decisao["intent"] == "cancelamento"
    assert decisao["agente_responsavel"] == "Agente de Cancelamento"


def test_parse_decision_atendimento():
    raw = "AGENTE: atendimento\nTAREFA: tirar duvida\nAVALIACAO: caso ambiguo"
    decisao = _agent().parse_decision(raw)
    assert decisao["intent"] == "atendimento"
    assert decisao["agente_responsavel"] == "Agente de Atendimento"


def test_parse_nao_confunde_cancelar_no_raciocinio():
    # A palavra "cancelar" aparece no raciocinio, mas AGENTE e atendimento.
    raw = (
        "O cliente perguntou como funciona cancelar no futuro, mas so quer saber horarios.\n"
        "AGENTE: atendimento\n"
        "TAREFA: informar horarios\n"
        "AVALIACAO: duvida informativa, sem intencao de cancelar"
    )
    decisao = _agent().parse_decision(raw)
    assert decisao["intent"] == "atendimento"


def test_parse_intent_desconhecido_faz_fallback_atendimento():
    raw = "AGENTE: financeiro\nTAREFA: algo\nAVALIACAO: intent invalido"
    decisao = _agent().parse_decision(raw)
    assert decisao["intent"] == "atendimento"


def test_register_anexa_trace_de_roteamento():
    trace: list[dict[str, str]] = []
    decisao = {
        "intent": "vendas",
        "agente_responsavel": "Agente de Vendas",
        "tarefa": "cotar",
        "avaliacao_orquestrador": "compra",
    }
    resultado = _agent().register(decisao, execution_trace=trace)
    assert resultado["intent"] == "vendas"
    assert len(trace) == 1
    assert trace[0]["etapa"] == "roteamento"
    assert trace[0]["tool"] == "llm:deepseek"
    assert trace[0]["agente"] == "Orquestrador"
