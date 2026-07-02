"""Configuracao compartilhada dos testes.

- Garante DEEPSEEK_API_KEY definido para permitir instanciar os agentes sem rede
  (a construcao do ChatOpenAI nao faz chamada de API; so o .invoke()/.stream() faria).
- Coloca a raiz do projeto no sys.path para os imports `app.*` funcionarem.
"""

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Chave dummy: nunca e usada em chamada real de rede nos testes.
os.environ.setdefault("DEEPSEEK_API_KEY", "test-key-dummy")
