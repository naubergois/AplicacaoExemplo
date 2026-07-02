# AGENTS.md

Guia para agentes de IA (e humanos) que trabalham neste repositório. Consolida as
convenções, regras de negócio e as **correções de erros** aprendidas durante o
desenvolvimento. Leia antes de alterar código.

## Visão geral

Aplicação FastAPI de atendimento de passagens aéreas com orquestração multi-agente
via **LangGraph** e LLM **DeepSeek** (acessado pela interface `ChatOpenAI` do
`langchain-openai`, pois a API do DeepSeek é compatível com a da OpenAI).

Agentes: `orchestrator`, `atendimento`, `vendas`, `cancelamento`, `reducao_danos`
e `flight_info` (agente de tools de voos). Fluxo compilado em [app/graph.py](app/graph.py).

## Comandos

```bash
# Ambiente (macOS: Python é externally-managed; sempre usar venv)
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# Rodar a API (auto-reload; HTML é servido fresco, não precisa reiniciar para mudar UI)
.venv/bin/python -m uvicorn main:app --reload --port 8000

# Testes
.venv/bin/python -m pytest
```

Requer `DEEPSEEK_API_KEY` no `.env` (opcional `DEEPSEEK_MODEL`, padrão `deepseek-chat`).

## Arquitetura e convenções

- **Roteamento 100% via LLM**: o orquestrador não usa heurística por palavra-chave.
  O parse é **estrito na linha `AGENTE:`** (ver `parse_decision`). Fallback → `atendimento`.
- **Regra de primeiro contato**: cliente sem perfil (`is_initial_contact`) sempre inicia
  no **Agente de Atendimento**, com prioridade sobre o LLM. `main.py` envia a flag no
  state; `graph.py` a respeita no `orchestrator_node`.
- **Tools por registro dinâmico**: agentes com tools montam `montar_registro_tools` +
  `executar_tool_call` — nunca fazer hardcode por nome de tool.
- **Separação de responsabilidades de tools de voos**: `vendas` e `atendimento` **não**
  executam tools de voos diretamente; obtêm schemas via `ferramentas_voos()` e delegam a
  execução via `delegar_execucao_tool_voos()` no `FlightInfoAgent`.
- **Streaming SSE**: `POST /chat/stream` transmite eventos `reasoning` (tokens do
  orquestrador), `trace` (cada chamada DeepSeek/tool ao vivo), `decision` e `done`. Roda o
  grafo em thread com polling do `execution_trace` compartilhado e injeta
  `precomputed_decision` no state para não re-rotear.
- **UI** ([app/static/chat_ui.html](app/static/chat_ui.html)): layout de 3 colunas
  (chat + memória + "Chamadas ao DeepSeek"), alimentado pelo SSE de `/chat/stream`
  (fetch + ReadableStream, parse manual de blocos SSE separados por `\n\n`).

## Correções de erros aprendidas (evitar regressão)

- **"Não foi possível concluir a cotação"**: agentes com loop de tools (`vendas`,
  `atendimento`) devem, após esgotar as iterações, fazer um `invoke` final **sem tools**
  para sintetizar a resposta. Cada `invoke` registra trace etapa `llm` com a(s) tool(s).
- **Falso positivo de cancelamento**: não usar substring global (ex.: `"cancel"` em
  qualquer linha da resposta do LLM). Fazer parse estrito da linha `AGENTE:` — uma
  saudação que mencione "cancelar" não deve rotear para cancelamento.
- **Pergunta por "qualquer destino"**: existe a tool `listar_todos_os_voos` /
  `available_routes` que lista todas as rotas; os prompts de `vendas`/`atendimento`
  orientam o modelo a usá-la para consultas genéricas.
- **UI perdida em commit**: a lógica JS de streaming já foi perdida uma vez (só o CSS
  sobreviveu). Após editar `chat_ui.html`, valide com `grep`/no navegador que
  `enviarMensagem`, a bolha de reasoning e a coluna de chamadas continuam presentes.
- **macOS / ambiente**: `pip install` global falha (`externally-managed-environment`);
  sempre usar a `.venv`. `rg` pode não estar instalado — usar busca do editor.
- **DeepSeek/GPT-5 params**: em GPT-5 usar `max_completion_tokens` (não `max_tokens`).
- **`data/` é gitignored**: os bancos SQLite (`data/flights.db`, `data/customer_memory.db`)
  são criados/semeados em runtime; não versionar.

## Testes

Suíte em [tests/](tests) com pytest ([pytest.ini](pytest.ini)). Cobrem **funções puras
e determinísticas sem chamada de rede** (o LLM não é invocado; `.invoke()/.stream()`
nunca são chamados nos testes):

- `tests/conftest.py`: define `DEEPSEEK_API_KEY` dummy (permite instanciar os agentes —
  a construção do `ChatOpenAI` não faz chamada de rede) e ajusta o `sys.path`.
- `tests/test_orchestrator.py`: parsing estrito de `AGENTE:`, fallback, sem falso
  positivo de cancelamento, registro de trace.
- `tests/test_base_policies.py`: `get_llm` exige a API key, bloqueio por política
  (milhas/bagagem), execução dinâmica de tools (sucesso, inexistente, exceção absorvida).
- `tests/test_flight_info.py`: seed/queries do SQLite em DB temporário, `available_routes`,
  tool `listar_todos_os_voos`, `ferramentas_voos` (3 tools), delegação com trace.
- `tests/test_graph_routing.py`: `route_intent`, `precomputed_decision`, regra de primeiro
  contato, aresta `reducao_danos → cancelamento`.
- `tests/test_models.py`: validação dos modelos Pydantic (`ChatRequest`/`ChatResponse`).

Diretrizes ao adicionar testes:

- Não faça testes que dependam de rede/LLM. Para lógica que precisa de LLM, teste apenas
  as partes puras (`build_prompt`, `parse_decision`, `register`).
- Para tools de voos, instancie `FlightInfoAgent(db_path=tmp_path/...)` para isolar o DB.
- Atenção: `orchestrator_node` faz `trace = state.get("execution_trace") or []`; uma lista
  **vazia** é falsy e é substituída por uma nova — verifique o trace no retorno do node,
  não na referência passada.
