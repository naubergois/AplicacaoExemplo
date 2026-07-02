from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agents import (
    atendimento_response,
    cancelamento_response,
    orchestrator_evaluate,
    reducao_danos_response,
    vendas_response,
)


class ConversationState(TypedDict, total=False):
    message: str
    memory_context: str
    history_text: str
    is_initial_contact: bool
    customer_name: str | None
    reservation_code: str | None
    intent: str
    tarefa: str
    agente_responsavel: str
    avaliacao_orquestrador: str
    resposta_retencao: str
    response: str
    execution_trace: list[dict[str, str]]
    precomputed_decision: dict[str, str]


def orchestrator_node(state: ConversationState) -> ConversationState:
    trace = state.get("execution_trace") or []

    precomputed = state.get("precomputed_decision")
    if precomputed:
        return {
            "intent": precomputed.get("intent", "atendimento"),
            "agente_responsavel": precomputed.get("agente_responsavel", "Agente de Atendimento"),
            "tarefa": precomputed.get("tarefa", "Atendimento geral"),
            "avaliacao_orquestrador": precomputed.get("avaliacao_orquestrador", ""),
            "execution_trace": trace,
        }

    if state.get("is_initial_contact", False):
        trace.append(
            {
                "etapa": "roteamento",
                "agente": "Orquestrador",
                "tool": "-",
                "detalhe": "Primeiro contato do cliente: direcionado para triagem inicial no atendimento.",
            }
        )
        return {
            "intent": "atendimento",
            "agente_responsavel": "Agente de Atendimento",
            "tarefa": "Triagem inicial e entendimento da necessidade",
            "avaliacao_orquestrador": "Regra de negocio: todo primeiro atendimento inicia no agente de atendimento.",
            "execution_trace": trace,
        }

    return {
        **orchestrator_evaluate(state["message"], execution_trace=trace),
        "execution_trace": trace,
    }


def atendimento_node(state: ConversationState) -> ConversationState:
    trace = state.get("execution_trace") or []
    partes: list[str] = []
    if state.get("memory_context"):
        partes.append(f"[MEMORIA DE CLIENTE]\n{state['memory_context']}")
    if state.get("history_text"):
        partes.append(f"[HISTORICO RECENTE - LANGCHAIN]\n{state['history_text']}")
    partes.append(f"[PEDIDO ATUAL]\n{state['message']}")
    mensagem = "\n\n".join(partes)
    response = atendimento_response(
        message=mensagem,
        customer_name=state.get("customer_name"),
        execution_trace=trace,
    )
    return {"response": response, "execution_trace": trace}


def vendas_node(state: ConversationState) -> ConversationState:
    trace = state.get("execution_trace") or []
    partes: list[str] = []
    if state.get("memory_context"):
        partes.append(f"[MEMORIA DE CLIENTE]\n{state['memory_context']}")
    if state.get("history_text"):
        partes.append(f"[HISTORICO RECENTE - LANGCHAIN]\n{state['history_text']}")
    partes.append(f"[PEDIDO ATUAL]\n{state['message']}")
    mensagem = "\n\n".join(partes)
    response = vendas_response(
        message=mensagem,
        customer_name=state.get("customer_name"),
        execution_trace=trace,
    )
    return {"response": response, "execution_trace": trace}


def cancelamento_node(state: ConversationState) -> ConversationState:
    trace = state.get("execution_trace") or []
    partes: list[str] = []
    if state.get("memory_context"):
        partes.append(f"[MEMORIA DE CLIENTE]\n{state['memory_context']}")
    if state.get("history_text"):
        partes.append(f"[HISTORICO RECENTE - LANGCHAIN]\n{state['history_text']}")
    partes.append(f"[PEDIDO ATUAL]\n{state['message']}")
    mensagem = "\n\n".join(partes)
    response = cancelamento_response(
        message=mensagem,
        reservation_code=state.get("reservation_code"),
        customer_name=state.get("customer_name"),
        contexto_retencao=state.get("resposta_retencao"),
        execution_trace=trace,
    )
    resposta_retencao = state.get("resposta_retencao")
    if resposta_retencao:
        response_final = (
            "[ETAPA 1 - REDUCAO DE DANOS]\n"
            f"{resposta_retencao}\n\n"
            "[ETAPA 2 - CANCELAMENTO]\n"
            f"{response}"
        )
    else:
        response_final = response

    return {"response": response_final, "execution_trace": trace}


def reducao_danos_node(state: ConversationState) -> ConversationState:
    trace = state.get("execution_trace") or []
    partes: list[str] = []
    if state.get("memory_context"):
        partes.append(f"[MEMORIA DE CLIENTE]\n{state['memory_context']}")
    if state.get("history_text"):
        partes.append(f"[HISTORICO RECENTE - LANGCHAIN]\n{state['history_text']}")
    partes.append(f"[PEDIDO ATUAL]\n{state['message']}")
    mensagem = "\n\n".join(partes)
    response = reducao_danos_response(
        message=mensagem,
        customer_name=state.get("customer_name"),
        execution_trace=trace,
    )
    return {"resposta_retencao": response, "execution_trace": trace}


def route_intent(state: ConversationState) -> str:
    intent = state.get("intent", "atendimento")
    if intent not in {"atendimento", "vendas", "cancelamento"}:
        return "atendimento"
    return intent


builder = StateGraph(ConversationState)
builder.add_node("orquestrador", orchestrator_node)
builder.add_node("atendimento", atendimento_node)
builder.add_node("vendas", vendas_node)
builder.add_node("reducao_danos", reducao_danos_node)
builder.add_node("cancelamento", cancelamento_node)

builder.set_entry_point("orquestrador")
builder.add_conditional_edges(
    "orquestrador",
    route_intent,
    {
        "atendimento": "atendimento",
        "vendas": "vendas",
        "cancelamento": "reducao_danos",
    },
)

builder.add_edge("atendimento", END)
builder.add_edge("vendas", END)
builder.add_edge("reducao_danos", "cancelamento")
builder.add_edge("cancelamento", END)

support_graph = builder.compile()
