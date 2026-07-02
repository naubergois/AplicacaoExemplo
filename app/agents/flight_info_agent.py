from __future__ import annotations

import random
import sqlite3
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

from app.agents.base import executar_tool_call, montar_registro_tools


class FlightInfoAgent:
    def __init__(self, db_path: Path | None = None) -> None:
        root_dir = Path(__file__).resolve().parents[2]
        self.db_path = db_path or (root_dir / "data" / "flights.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_database()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_database(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS flights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flight_code TEXT NOT NULL UNIQUE,
                    airline TEXT NOT NULL,
                    origin_city TEXT NOT NULL,
                    origin_iata TEXT NOT NULL,
                    destination_city TEXT NOT NULL,
                    destination_iata TEXT NOT NULL,
                    departure_time TEXT NOT NULL,
                    arrival_time TEXT NOT NULL,
                    cabin_class TEXT NOT NULL,
                    price_brl REAL NOT NULL,
                    seats_available INTEGER NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            total = conn.execute("SELECT COUNT(*) AS total FROM flights").fetchone()["total"]
            if total == 0:
                self._seed_next_two_months(conn)

    def _seed_next_two_months(self, conn: sqlite3.Connection) -> None:
        random.seed(42)
        start = date.today()
        end = start + timedelta(days=60)

        routes = [
            ("Recife", "REC", "Sao Paulo", "GRU", 3.0, 420.0),
            ("Sao Paulo", "GRU", "Recife", "REC", 3.0, 430.0),
            ("Rio de Janeiro", "GIG", "Sao Paulo", "CGH", 1.0, 260.0),
            ("Sao Paulo", "CGH", "Rio de Janeiro", "GIG", 1.0, 250.0),
            ("Brasilia", "BSB", "Salvador", "SSA", 1.8, 310.0),
            ("Salvador", "SSA", "Brasilia", "BSB", 1.8, 300.0),
            ("Curitiba", "CWB", "Fortaleza", "FOR", 3.3, 450.0),
            ("Fortaleza", "FOR", "Curitiba", "CWB", 3.3, 460.0),
            ("Belo Horizonte", "CNF", "Porto Alegre", "POA", 2.0, 340.0),
            ("Porto Alegre", "POA", "Belo Horizonte", "CNF", 2.0, 350.0),
            ("Sao Paulo", "GRU", "Lisboa", "LIS", 9.5, 1800.0),
            ("Lisboa", "LIS", "Sao Paulo", "GRU", 10.0, 1750.0),
        ]

        flight_slots = [time(6, 30), time(14, 15), time(20, 40)]
        airlines = ["Azul", "Gol", "LATAM"]
        cabin_options = ["Economica", "Executiva"]
        status_options = ["On Time", "On Time", "On Time", "Delayed"]

        batch = []
        seq = 1000
        day = start
        while day <= end:
            for route in routes:
                origem, origem_iata, destino, destino_iata, duracao_horas, base_price = route
                for slot in flight_slots:
                    departure_dt = datetime.combine(day, slot)
                    arrival_dt = departure_dt + timedelta(hours=duracao_horas)
                    airline = random.choice(airlines)
                    cabin = random.choice(cabin_options)
                    seats = random.randint(12, 180)
                    status = random.choice(status_options)

                    variation = random.uniform(-0.18, 0.25)
                    peak = 0.16 if departure_dt.weekday() in (4, 5, 6) else 0.0
                    cabin_extra = 0.55 if cabin == "Executiva" else 0.0
                    price = round(base_price * (1 + variation + peak + cabin_extra), 2)

                    seq += 1
                    code = f"NA{seq}"
                    batch.append(
                        (
                            code,
                            airline,
                            origem,
                            origem_iata,
                            destino,
                            destino_iata,
                            departure_dt.isoformat(timespec="minutes"),
                            arrival_dt.isoformat(timespec="minutes"),
                            cabin,
                            price,
                            seats,
                            status,
                        )
                    )
            day += timedelta(days=1)

        conn.executemany(
            """
            INSERT INTO flights (
                flight_code,
                airline,
                origin_city,
                origin_iata,
                destination_city,
                destination_iata,
                departure_time,
                arrival_time,
                cabin_class,
                price_brl,
                seats_available,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            batch,
        )

    def search_flights(
        self,
        origem: str,
        destino: str,
        data_voo: str | None = None,
        max_resultados: int = 5,
    ) -> list[sqlite3.Row]:
        query = (
            "SELECT * FROM flights "
            "WHERE lower(origin_city) LIKE ? AND lower(destination_city) LIKE ? "
            "AND seats_available > 0 "
        )
        params: list[object] = [f"%{origem.lower()}%", f"%{destino.lower()}%"]

        if data_voo:
            query += "AND date(departure_time) = date(?) "
            params.append(data_voo)

        query += "ORDER BY departure_time ASC, price_brl ASC LIMIT ?"
        params.append(max_resultados)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return rows

    def cheapest_deals(self, destino: str | None = None, max_resultados: int = 5) -> list[sqlite3.Row]:
        query = "SELECT * FROM flights WHERE seats_available > 0 "
        params: list[object] = []

        if destino:
            query += "AND lower(destination_city) LIKE ? "
            params.append(f"%{destino.lower()}%")

        query += "ORDER BY price_brl ASC, departure_time ASC LIMIT ?"
        params.append(max_resultados)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return rows

    def available_routes(self, max_rotas: int = 40) -> list[sqlite3.Row]:
        query = (
            "SELECT origin_city, origin_iata, destination_city, destination_iata, "
            "COUNT(*) AS total_voos, MIN(price_brl) AS menor_preco, "
            "MAX(price_brl) AS maior_preco, MIN(departure_time) AS proxima_saida "
            "FROM flights WHERE seats_available > 0 "
            "GROUP BY origin_city, origin_iata, destination_city, destination_iata "
            "ORDER BY origin_city ASC, destination_city ASC LIMIT ?"
        )
        with self._connect() as conn:
            rows = conn.execute(query, [max_rotas]).fetchall()
        return rows


flight_info_agent = FlightInfoAgent()


def _format_rows(rows: list[sqlite3.Row]) -> str:
    if not rows:
        return "Nenhum voo encontrado para os filtros informados."

    lines = []
    for row in rows:
        lines.append(
            (
                f"{row['flight_code']} | {row['airline']} | "
                f"{row['origin_city']}({row['origin_iata']}) -> "
                f"{row['destination_city']}({row['destination_iata']}) | "
                f"Saida: {row['departure_time']} | Chegada: {row['arrival_time']} | "
                f"Classe: {row['cabin_class']} | Preco: R$ {row['price_brl']:.2f} | "
                f"Assentos: {row['seats_available']} | Status: {row['status']}"
            )
        )
    return "\n".join(lines)


@tool("buscar_voos")
def buscar_voos(
    origem: str,
    destino: str,
    data_voo: str | None = None,
    max_resultados: int = 5,
) -> str:
    """Busca voos por origem, destino e opcionalmente data (AAAA-MM-DD)."""
    rows = flight_info_agent.search_flights(
        origem=origem,
        destino=destino,
        data_voo=data_voo,
        max_resultados=max_resultados,
    )
    return _format_rows(rows)


@tool("melhores_ofertas_voos")
def melhores_ofertas_voos(destino: str | None = None, max_resultados: int = 5) -> str:
    """Lista voos mais baratos, opcionalmente filtrando por destino."""
    rows = flight_info_agent.cheapest_deals(destino=destino, max_resultados=max_resultados)
    return _format_rows(rows)


@tool("listar_todos_os_voos")
def listar_todos_os_voos(max_rotas: int = 40) -> str:
    """Lista todas as rotas/voos disponiveis (todos os destinos) com contagem, faixa de
    preco e proxima saida. Use quando o cliente perguntar por qualquer destino, todos os
    voos, quais destinos existem ou nao especificar origem/destino."""
    rows = flight_info_agent.available_routes(max_rotas=max_rotas)
    if not rows:
        return "Nenhuma rota disponivel no momento."

    linhas = ["Rotas disponiveis (todos os destinos):"]
    for row in rows:
        linhas.append(
            (
                f"{row['origin_city']}({row['origin_iata']}) -> "
                f"{row['destination_city']}({row['destination_iata']}) | "
                f"Voos: {row['total_voos']} | "
                f"Preco: R$ {row['menor_preco']:.2f} a R$ {row['maior_preco']:.2f} | "
                f"Proxima saida: {row['proxima_saida']}"
            )
        )
    return "\n".join(linhas)


def ferramentas_voos():
    """Retorna as tools oficialmente pertencentes ao agente de informacao de voos."""
    return [buscar_voos, melhores_ofertas_voos, listar_todos_os_voos]


def delegar_execucao_tool_voos(
    tool_call: dict[str, Any],
    execution_trace: list[dict[str, str]] | None = None,
    solicitante: str = "Agente consumidor",
) -> str:
    """Executa uma tool de voos no proprio agente responsavel por essas tools."""
    nome_tool = str(tool_call.get("name", "desconhecida"))
    if execution_trace is not None:
        execution_trace.append(
            {
                "etapa": "delegacao",
                "agente": solicitante,
                "tool": nome_tool,
                "detalhe": "Delegou execucao para Agente de Informacao de Voos",
            }
        )

    return executar_tool_call(
        tool_registry=montar_registro_tools(ferramentas_voos()),
        tool_call=tool_call,
        unavailable_message="Tool solicitada nao esta disponivel no agente de informacao de voos.",
    )
