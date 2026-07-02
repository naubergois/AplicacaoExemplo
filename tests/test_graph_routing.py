"""Testes de roteamento do grafo (sem chamar LLM).

Aprendizado coberto:
- route_intent normaliza intents invalidos para atendimento.
- orchestrator_node prioriza precomputed_decision (nao re-roteia no /chat/stream).
- Regra de negocio: primeiro contato (is_initial_contact) sempre inicia no
  Agente de Atendimento, ANTES de acionar o LLM.
- Cancelamento passa por reducao_danos antes de cancelamento no grafo compilado.
"""

from app.graph import orchestrator_node, route_intent, support_graph


def test_route_intent_valido():
    assert route_intent({"intent": "vendas"}) == "vendas"
    assert route_intent({"intent": "cancelamento"}) == "cancelamento"


def test_route_intent_invalido_vira_atendimento():
    assert route_intent({"intent": "financeiro"}) == "atendimento"
    assert route_intent({}) == "atendimento"


def test_orchestrator_node_usa_precomputed_decision():
    state = {
        "message": "qualquer",
        "execution_trace": [],
        "precomputed_decision": {
            "intent": "vendas",
            "agente_responsavel": "Agente de Vendas",
            "tarefa": "cotar",
            "avaliacao_orquestrador": "compra",
        },
    }
    resultado = orchestrator_node(state)
    assert resultado["intent"] == "vendas"
    assert resultado["agente_responsavel"] == "Agente de Vendas"


def test_orchestrator_node_primeiro_contato_vai_para_atendimento():
    state = {"message": "quero comprar passagem", "is_initial_contact": True, "execution_trace": []}
    resultado = orchestrator_node(state)
    assert resultado["intent"] == "atendimento"
    assert resultado["agente_responsavel"] == "Agente de Atendimento"
    assert resultado["execution_trace"][-1]["etapa"] == "roteamento"


def test_grafo_cancelamento_passa_por_reducao_danos():
    edges = support_graph.get_graph().edges
    pares = {(edge.source, edge.target) for edge in edges}
    assert ("reducao_danos", "cancelamento") in pares
