import json
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.agents import (
    orchestrator_parse,
    orchestrator_register,
    orchestrator_stream_reasoning,
)
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


def _sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/chat/stream")
def chat_stream(payload: ChatRequest) -> StreamingResponse:
    is_initial_contact = True
    if payload.customer_name:
        is_initial_contact = memory_service.get_profile(payload.customer_name) is None

    memory_context = memory_service.build_memory_context(payload.customer_name)
    history_messages = memory_service.build_langchain_history(payload.customer_name, limit=6)
    history_text = memory_service.format_langchain_history(history_messages, limit=6)

    def event_stream():
        execution_trace: list[dict[str, str]] = []
        memoria_step = {
            "etapa": "memoria",
            "agente": "MemoryService",
            "tool": "langchain_history",
            "detalhe": (
                f"Contexto estruturado={'sim' if bool(memory_context) else 'nao'}; "
                f"mensagens_historico={len(history_messages)}"
            ),
        }
        execution_trace.append(memoria_step)
        yield _sse("trace", memoria_step)

        try:
            # Fase 1: roteamento com raciocinio do modelo (streaming token a token)
            if is_initial_contact:
                yield _sse(
                    "reasoning",
                    {"token": "Primeiro contato do cliente: aplicando triagem inicial no atendimento."},
                )
                decision = {
                    "intent": "atendimento",
                    "agente_responsavel": "Agente de Atendimento",
                    "tarefa": "Triagem inicial e entendimento da necessidade",
                    "avaliacao_orquestrador": "Regra de negocio: todo primeiro atendimento inicia no agente de atendimento.",
                }
                routing_step = {
                    "etapa": "roteamento",
                    "agente": "Orquestrador",
                    "tool": "regra:triagem",
                    "detalhe": "Primeiro contato direcionado para triagem inicial no atendimento.",
                }
                execution_trace.append(routing_step)
                yield _sse("trace", routing_step)
            else:
                yield _sse("reasoning_start", {"agente": "Orquestrador"})
                raw_reasoning = ""
                for token in orchestrator_stream_reasoning(payload.message):
                    raw_reasoning += token
                    yield _sse("reasoning", {"token": token})
                decision = orchestrator_parse(raw_reasoning)
                before = len(execution_trace)
                orchestrator_register(decision, execution_trace=execution_trace)
                for step in execution_trace[before:]:
                    yield _sse("trace", step)

            yield _sse(
                "decision",
                {
                    "intent": decision["intent"],
                    "agente_responsavel": decision["agente_responsavel"],
                    "tarefa": decision["tarefa"],
                    "avaliacao": decision["avaliacao_orquestrador"],
                },
            )

            # Fase 2: executa o agente escolhido (grafo em thread) e transmite o trace ao vivo
            result_holder: dict[str, object] = {}
            error_holder: dict[str, object] = {}

            def run_graph():
                try:
                    result_holder["result"] = support_graph.invoke(
                        {
                            "message": payload.message,
                            "memory_context": memory_context,
                            "history_text": history_text,
                            "is_initial_contact": is_initial_contact,
                            "customer_name": payload.customer_name,
                            "reservation_code": payload.reservation_code,
                            "execution_trace": execution_trace,
                            "precomputed_decision": decision,
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    error_holder["error"] = str(exc)

            worker = threading.Thread(target=run_graph, daemon=True)
            worker.start()

            emitted = len(execution_trace)
            while worker.is_alive() or emitted < len(execution_trace):
                while emitted < len(execution_trace):
                    yield _sse("trace", execution_trace[emitted])
                    emitted += 1
                if not worker.is_alive():
                    break
                time.sleep(0.12)
            worker.join()

            if "error" in error_holder:
                yield _sse("error", {"detail": error_holder["error"]})
                return

            result = result_holder.get("result", {}) or {}
            response_text = result.get("response", "Nao foi possivel gerar resposta.")

            if payload.customer_name:
                interaction = ChatInteractionRecord(
                    customer_name=payload.customer_name,
                    message=payload.message,
                    response=response_text,
                    intent=result.get("intent", decision["intent"]),
                    agente_responsavel=result.get("agente_responsavel"),
                    reservation_code=payload.reservation_code,
                )
                memory_service.save_interaction(interaction)

            yield _sse(
                "done",
                {
                    "intent": result.get("intent", decision["intent"]),
                    "agente_responsavel": result.get("agente_responsavel"),
                    "tarefa": result.get("tarefa"),
                    "response": response_text,
                    "execucao": result.get("execution_trace", execution_trace),
                    "memoria": {
                        "customer_name": payload.customer_name,
                        "is_initial_contact": is_initial_contact,
                        "context_available": bool(memory_context),
                        "context_snapshot": memory_context,
                        "langchain_history_size": len(history_messages),
                        "langchain_history_snapshot": history_text,
                    },
                },
            )
        except Exception as exc:  # noqa: BLE001
            yield _sse("error", {"detail": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
