"""Testes do agente de informacao de voos (acesso a SQLite, sem LLM).

Aprendizado coberto:
- available_routes/listar_todos_os_voos: nova tool que lista TODOS os destinos
  (usada quando o cliente pergunta por "qualquer destino").
- ferramentas_voos() deve expor exatamente as 3 tools de voos.
- Delegacao registra trace "delegacao" (agentes de vendas/atendimento nao executam
  tools de voos diretamente).
- _format_rows lida com resultado vazio sem quebrar.
"""

from pathlib import Path

from app.agents.flight_info_agent import (
    FlightInfoAgent,
    _format_rows,
    delegar_execucao_tool_voos,
    ferramentas_voos,
    listar_todos_os_voos,
)


def _agent_temp(tmp_path: Path) -> FlightInfoAgent:
    return FlightInfoAgent(db_path=tmp_path / "flights_test.db")


def test_seed_e_search_flights(tmp_path):
    agent = _agent_temp(tmp_path)
    rows = agent.search_flights("Recife", "Sao Paulo", max_resultados=3)
    assert len(rows) >= 1
    assert rows[0]["origin_city"] == "Recife"
    assert rows[0]["destination_city"] == "Sao Paulo"


def test_cheapest_deals_ordena_por_preco(tmp_path):
    agent = _agent_temp(tmp_path)
    rows = agent.cheapest_deals(max_resultados=5)
    precos = [row["price_brl"] for row in rows]
    assert precos == sorted(precos)


def test_available_routes_lista_todas_as_rotas(tmp_path):
    agent = _agent_temp(tmp_path)
    rows = agent.available_routes(max_rotas=40)
    # O seed define 12 rotas distintas.
    assert len(rows) >= 10
    destinos = {row["destination_city"] for row in rows}
    assert "Sao Paulo" in destinos
    for row in rows:
        assert row["menor_preco"] <= row["maior_preco"]


def test_listar_todos_os_voos_tool_formata_saida():
    saida = listar_todos_os_voos.invoke({})
    assert "Rotas disponiveis" in saida
    assert "->" in saida


def test_ferramentas_voos_expoe_tres_tools():
    nomes = {tool.name for tool in ferramentas_voos()}
    assert nomes == {"buscar_voos", "melhores_ofertas_voos", "listar_todos_os_voos"}


def test_delegar_execucao_registra_trace():
    trace: list[dict[str, str]] = []
    resultado = delegar_execucao_tool_voos(
        {"name": "listar_todos_os_voos", "args": {}},
        execution_trace=trace,
        solicitante="Agente de Vendas",
    )
    assert "Rotas disponiveis" in resultado
    assert len(trace) == 1
    assert trace[0]["etapa"] == "delegacao"
    assert trace[0]["agente"] == "Agente de Vendas"
    assert trace[0]["tool"] == "listar_todos_os_voos"


def test_format_rows_vazio():
    assert "Nenhum voo" in _format_rows([])
