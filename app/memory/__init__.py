from pathlib import Path

from app.memory.store import MemoryService

memory_service = MemoryService(root_dir=Path(__file__).resolve().parents[2])
