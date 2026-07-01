from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.graph import support_graph
from app.memory import memory_service
from app.memory.models import ChatInteractionRecord
from app.models import ChatRequest, ChatResponse

app = FastAPI(title="Agentes de Passagens Aereas com DeepSeek + LangGraph")
BASE_DIR = Path(__file__).resolve().parent


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/simulador")
def simulador() -> FileResponse:
    return FileResponse(BASE_DIR / "app" / "static" / "simulador_fluxos.html")


@app.get("/chat-ui")
def chat_ui() -> FileResponse:
    return FileResponse(BASE_DIR / "app" / "static" / "chat_ui.html")


@app.get("/memory/{customer_name}")
def customer_memory(customer_name: str) -> dict[str, object]:
    profile = memory_service.get_profile(customer_name)
    interactions = memory_service.get_recent_interactions(customer_name, limit=6)
    history_messages = memory_service.build_langchain_history(customer_name, limit=6)

    if profile is None:
        return {
            "customer_name": customer_name,
            "has_memory": False,
            "summary": "Sem memoria registrada para este cliente.",
            "recent_interactions": [],
            "langchain_history_size": len(history_messages),
        }

    return {
        "customer_name": customer_name,
        "has_memory": True,
        "summary": memory_service.build_memory_context(customer_name),
        "total_interactions": profile.total_interactions,
        "last_intent": profile.last_intent,
        "preferred_origins": profile.preferred_origins,
        "preferred_destinations": profile.preferred_destinations,
        "reservation_codes": profile.reservation_codes,
        "recent_interactions": interactions,
        "langchain_history_size": len(history_messages),
    }


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    is_initial_contact = True
    if payload.customer_name:
        is_initial_contact = memory_service.get_profile(payload.customer_name) is None

    memory_context = memory_service.build_memory_context(payload.customer_name)
    history_messages = memory_service.build_langchain_history(payload.customer_name, limit=6)
    history_text = memory_service.format_langchain_history(history_messages, limit=6)

    try:
        execution_trace: list[dict[str, str]] = []
        execution_trace.append(
            {
                "etapa": "memoria",
                "agente": "MemoryService",
                "tool": "langchain_history",
                "detalhe": (
                    f"Contexto estruturado={'sim' if bool(memory_context) else 'nao'}; "
                    f"mensagens_historico={len(history_messages)}"
                ),
            }
        )
        result = support_graph.invoke(
            {
                "message": payload.message,
                "memory_context": memory_context,
                "history_text": history_text,
                "is_initial_contact": is_initial_contact,
                "customer_name": payload.customer_name,
                "reservation_code": payload.reservation_code,
                "execution_trace": execution_trace,
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if payload.customer_name:
        interaction = ChatInteractionRecord(
            customer_name=payload.customer_name,
            message=payload.message,
            response=result.get("response", "Nao foi possivel gerar resposta."),
            intent=result.get("intent", "atendimento"),
            agente_responsavel=result.get("agente_responsavel"),
            reservation_code=payload.reservation_code,
        )
        memory_service.save_interaction(interaction)

    return ChatResponse(
        intent=result.get("intent", "atendimento"),
        agente_responsavel=result.get("agente_responsavel"),
        tarefa=result.get("tarefa"),
        response=result.get("response", "Nao foi possivel gerar resposta."),
        execucao=result.get("execution_trace", []),
        memoria={
            "customer_name": payload.customer_name,
            "is_initial_contact": is_initial_contact,
            "context_available": bool(memory_context),
            "context_snapshot": memory_context,
            "langchain_history_size": len(history_messages),
            "langchain_history_snapshot": history_text,
        },
    )
