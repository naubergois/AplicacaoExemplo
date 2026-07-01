from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.memory.models import ChatInteractionRecord, CustomerStructuredMemory


CITY_ROUTE_PATTERN = re.compile(
    r"\bde\s+([a-zA-Z\s]+?)\s+para\s+([a-zA-Z\s]+?)(?:\s|$)",
    flags=re.IGNORECASE,
)


class MemoryService:
    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or Path(__file__).resolve().parents[2]
        self.data_dir = self.root_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.sqlite_path = self.data_dir / "customer_memory.db"
        self._init_sqlite()

        self._text_memory_enabled = False
        self._collection = None
        self._init_chromadb()

    def _init_sqlite(self) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS customer_profiles (
                    customer_name TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS customer_interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_name TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    agente_responsavel TEXT,
                    reservation_code TEXT,
                    message TEXT NOT NULL,
                    response TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def _init_chromadb(self) -> None:
        try:
            import chromadb

            chroma_dir = self.data_dir / "chroma_memory"
            chroma_dir.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=str(chroma_dir))
            self._collection = client.get_or_create_collection("textual_customer_memory")
            self._text_memory_enabled = True
        except Exception:
            self._text_memory_enabled = False
            self._collection = None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_profile(self, customer_name: str) -> CustomerStructuredMemory | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM customer_profiles WHERE customer_name = ?",
                (customer_name,),
            ).fetchone()

        if not row:
            return None

        payload = json.loads(row["payload_json"])
        return CustomerStructuredMemory(**payload)

    def upsert_profile(self, profile: CustomerStructuredMemory) -> None:
        payload = profile.model_dump(mode="json")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO customer_profiles (customer_name, payload_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(customer_name)
                DO UPDATE SET payload_json = excluded.payload_json, updated_at = excluded.updated_at
                """,
                (
                    profile.customer_name,
                    json.dumps(payload, ensure_ascii=True),
                    profile.updated_at.isoformat(),
                ),
            )

    def save_interaction_sqlite(self, interaction: ChatInteractionRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO customer_interactions (
                    customer_name,
                    intent,
                    agente_responsavel,
                    reservation_code,
                    message,
                    response,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    interaction.customer_name,
                    interaction.intent,
                    interaction.agente_responsavel,
                    interaction.reservation_code,
                    interaction.message,
                    interaction.response,
                    interaction.created_at.isoformat(),
                ),
            )

    def save_interaction_chroma(self, interaction: ChatInteractionRecord) -> None:
        if not self._text_memory_enabled or self._collection is None:
            return

        doc = (
            f"Cliente: {interaction.customer_name}\n"
            f"Intent: {interaction.intent}\n"
            f"Agente: {interaction.agente_responsavel or 'Nao informado'}\n"
            f"Mensagem: {interaction.message}\n"
            f"Resposta: {interaction.response}"
        )
        self._collection.add(
            ids=[str(uuid.uuid4())],
            documents=[doc],
            metadatas=[
                {
                    "customer_name": interaction.customer_name,
                    "intent": interaction.intent,
                    "agente": interaction.agente_responsavel or "Nao informado",
                    "created_at": interaction.created_at.isoformat(),
                }
            ],
        )

    def _extract_route(self, message: str) -> tuple[str | None, str | None]:
        match = CITY_ROUTE_PATTERN.search(message)
        if not match:
            return None, None
        origem = match.group(1).strip().title()
        destino = match.group(2).strip().title()
        return origem, destino

    def _merge_unique(self, current: list[str], value: str | None, limit: int = 10) -> list[str]:
        if not value:
            return current
        updated = [item for item in current if item.lower() != value.lower()]
        updated.append(value)
        return updated[-limit:]

    def update_structured_memory(self, interaction: ChatInteractionRecord) -> CustomerStructuredMemory:
        existing = self.get_profile(interaction.customer_name)
        if existing is None:
            existing = CustomerStructuredMemory(customer_name=interaction.customer_name)

        origem, destino = self._extract_route(interaction.message)
        existing.total_interactions += 1
        existing.intents_history = self._merge_unique(existing.intents_history, interaction.intent, limit=20)
        existing.preferred_origins = self._merge_unique(existing.preferred_origins, origem)
        existing.preferred_destinations = self._merge_unique(existing.preferred_destinations, destino)
        existing.reservation_codes = self._merge_unique(existing.reservation_codes, interaction.reservation_code)
        existing.last_message = interaction.message
        existing.last_response = interaction.response
        existing.last_intent = interaction.intent
        existing.updated_at = datetime.utcnow()

        # Validacao estruturada via Pydantic antes de persistir.
        validated = CustomerStructuredMemory(**existing.model_dump())
        self.upsert_profile(validated)
        return validated

    def save_interaction(self, interaction: ChatInteractionRecord) -> CustomerStructuredMemory:
        self.save_interaction_sqlite(interaction)
        self.save_interaction_chroma(interaction)
        return self.update_structured_memory(interaction)

    def get_recent_interactions(self, customer_name: str, limit: int = 6) -> list[dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT message, response, intent, created_at
                FROM customer_interactions
                WHERE customer_name = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (customer_name, limit),
            ).fetchall()

        ordered = list(reversed(rows))
        return [
            {
                "message": str(row["message"]),
                "response": str(row["response"]),
                "intent": str(row["intent"]),
                "created_at": str(row["created_at"]),
            }
            for row in ordered
        ]

    def build_langchain_history(self, customer_name: str | None, limit: int = 6) -> list[BaseMessage]:
        if not customer_name:
            return []

        interactions = self.get_recent_interactions(customer_name, limit=limit)
        history: list[BaseMessage] = []
        for item in interactions:
            history.append(HumanMessage(content=item["message"]))
            history.append(AIMessage(content=item["response"]))
        return history

    def format_langchain_history(self, history_messages: list[BaseMessage], limit: int = 6) -> str:
        if not history_messages:
            return ""

        snippets: list[str] = []
        recent = history_messages[-(limit * 2) :]
        for msg in recent:
            role = "Cliente" if isinstance(msg, HumanMessage) else "Assistente"
            conteudo = str(msg.content).replace("\n", " ").strip()
            snippets.append(f"- {role}: {conteudo[:220]}")
        return "\n".join(snippets)

    def get_recent_text_memory(self, customer_name: str, limit: int = 3) -> list[str]:
        if not self._text_memory_enabled or self._collection is None:
            return []

        payload = self._collection.get(
            where={"customer_name": customer_name},
            include=["documents", "metadatas"],
        )
        docs = payload.get("documents", []) or []
        if not docs:
            return []
        # Chroma retorna em ordem de insercao para get simples.
        return [doc for doc in docs[-limit:] if isinstance(doc, str)]

    def build_memory_context(self, customer_name: str | None) -> str:
        if not customer_name:
            return ""

        profile = self.get_profile(customer_name)
        if profile is None:
            return ""

        snippets = [
            f"Cliente: {profile.customer_name}",
            f"Total de interacoes: {profile.total_interactions}",
            f"Ultimo intent: {profile.last_intent or 'Nao informado'}",
        ]
        if profile.preferred_origins:
            snippets.append(f"Origens recorrentes: {', '.join(profile.preferred_origins)}")
        if profile.preferred_destinations:
            snippets.append(f"Destinos recorrentes: {', '.join(profile.preferred_destinations)}")
        if profile.reservation_codes:
            snippets.append(f"Codigos de reserva conhecidos: {', '.join(profile.reservation_codes)}")

        recent_text = self.get_recent_text_memory(customer_name)
        if recent_text:
            snippets.append("Memorias textuais recentes:")
            for doc in recent_text:
                compact = doc.replace("\n", " | ")
                snippets.append(f"- {compact[:260]}")

        return "\n".join(snippets)
