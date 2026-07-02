from app.agents.atendimento_agent import AtendimentoAgent
from app.agents.base import get_llm
from app.agents.cancelamento_agent import CancelamentoAgent
from app.agents.flight_info_agent import buscar_voos, melhores_ofertas_voos
from app.agents.orchestrator_agent import OrchestratorAgent
from app.agents.reducao_danos_agent import ReducaoDanosAgent
from app.agents.vendas_agent import VendasAgent

_orchestrator = OrchestratorAgent()
_atendimento = AtendimentoAgent()
_vendas = VendasAgent()
_reducao_danos = ReducaoDanosAgent()
_cancelamento = CancelamentoAgent()


def orchestrator_evaluate(
    message: str,
    execution_trace: list[dict[str, str]] | None = None,
) -> dict[str, str]:
    return _orchestrator.evaluate_case(message, execution_trace=execution_trace)


def orchestrator_stream_reasoning(message: str):
    """Faz streaming do raciocinio do orquestrador (DeepSeek) token a token.

    Retorna (via generator) fragmentos de texto do raciocinio e, ao final,
    entrega o texto bruto acumulado atraves de StopIteration.value.
    """
    prompt = _orchestrator.build_prompt(message)
    partes: list[str] = []
    for chunk in _orchestrator.llm.stream(prompt):
        token = getattr(chunk, "content", "") or ""
        if token:
            partes.append(token)
            yield token
    return "".join(partes)


def orchestrator_parse(raw: str) -> dict[str, str]:
    return _orchestrator.parse_decision(raw)


def orchestrator_register(
    decision: dict[str, str],
    execution_trace: list[dict[str, str]] | None = None,
) -> dict[str, str]:
    return _orchestrator.register(decision, execution_trace=execution_trace)


def atendimento_response(
    message: str,
    customer_name: str | None = None,
    execution_trace: list[dict[str, str]] | None = None,
) -> str:
    return _atendimento.respond(
        message=message,
        customer_name=customer_name,
        execution_trace=execution_trace,
    )


def vendas_response(
    message: str,
    customer_name: str | None = None,
    execution_trace: list[dict[str, str]] | None = None,
) -> str:
    return _vendas.respond(
        message=message,
        customer_name=customer_name,
        execution_trace=execution_trace,
    )


def reducao_danos_response(
    message: str,
    customer_name: str | None = None,
    execution_trace: list[dict[str, str]] | None = None,
) -> str:
    return _reducao_danos.respond(
        message=message,
        customer_name=customer_name,
        execution_trace=execution_trace,
    )


def cancelamento_response(
    message: str,
    reservation_code: str | None = None,
    customer_name: str | None = None,
    contexto_retencao: str | None = None,
    execution_trace: list[dict[str, str]] | None = None,
) -> str:
    return _cancelamento.respond(
        message=message,
        reservation_code=reservation_code,
        customer_name=customer_name,
        contexto_retencao=contexto_retencao,
        execution_trace=execution_trace,
    )


def buscar_voos_info(
    origem: str,
    destino: str,
    data_voo: str | None = None,
    max_resultados: int = 5,
) -> str:
    return buscar_voos.invoke(
        {
            "origem": origem,
            "destino": destino,
            "data_voo": data_voo,
            "max_resultados": max_resultados,
        }
    )


def melhores_ofertas_info(destino: str | None = None, max_resultados: int = 5) -> str:
    return melhores_ofertas_voos.invoke(
        {
            "destino": destino,
            "max_resultados": max_resultados,
        }
    )
