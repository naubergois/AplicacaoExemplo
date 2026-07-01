from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.graph import support_graph
from app.models import ChatRequest, ChatResponse

app = FastAPI(title="Agentes de Passagens Aereas com DeepSeek + LangGraph")
BASE_DIR = Path(__file__).resolve().parent


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/simulador")
def simulador() -> FileResponse:
    return FileResponse(BASE_DIR / "app" / "static" / "simulador_fluxos.html")


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    try:
        result = support_graph.invoke(
            {
                "message": payload.message,
                "customer_name": payload.customer_name,
                "reservation_code": payload.reservation_code,
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ChatResponse(
        intent=result.get("intent", "atendimento"),
        response=result.get("response", "Nao foi possivel gerar resposta."),
    )
