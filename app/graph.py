from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agents import atendimento_response, cancelamento_response, vendas_response, get_llm


class ConversationState(TypedDict, total=False):
    message: str
    customer_name: str | None
    reservation_code: str | None
    intent: str
    response: str


def classify_intent(state: ConversationState) -> ConversationState:
    llm = get_llm()
    raw = llm.invoke(
        f"""
Classifique a intencao do cliente para uma aplicacao de passagens aereas.
Retorne apenas uma intencao: atendimento, vendas ou cancelamento.
Nao adicione explicacoes.

Mensagem: {state['message']}
""".strip()
    ).content

    resposta = str(raw).strip().lower()
    if "cancel" in resposta:
        intent = "cancelamento"
    elif "vend" in resposta or "compr" in resposta:
        intent = "vendas"
    else:
        intent = "atendimento"

    return {"intent": intent}


def atendimento_node(state: ConversationState) -> ConversationState:
    response = atendimento_response(
        message=state["message"],
        customer_name=state.get("customer_name"),
    )
    return {"response": response}


def vendas_node(state: ConversationState) -> ConversationState:
    response = vendas_response(
        message=state["message"],
        customer_name=state.get("customer_name"),
    )
    return {"response": response}


def cancelamento_node(state: ConversationState) -> ConversationState:
    response = cancelamento_response(
        message=state["message"],
        reservation_code=state.get("reservation_code"),
        customer_name=state.get("customer_name"),
    )
    return {"response": response}


def route_intent(state: ConversationState) -> str:
    intent = state.get("intent", "atendimento")
    if intent not in {"atendimento", "vendas", "cancelamento"}:
        return "atendimento"
    return intent


builder = StateGraph(ConversationState)
builder.add_node("classify_intent", classify_intent)
builder.add_node("atendimento", atendimento_node)
builder.add_node("vendas", vendas_node)
builder.add_node("cancelamento", cancelamento_node)

builder.set_entry_point("classify_intent")
builder.add_conditional_edges(
    "classify_intent",
    route_intent,
    {
        "atendimento": "atendimento",
        "vendas": "vendas",
        "cancelamento": "cancelamento",
    },
)

builder.add_edge("atendimento", END)
builder.add_edge("vendas", END)
builder.add_edge("cancelamento", END)

support_graph = builder.compile()
