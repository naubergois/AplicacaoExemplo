import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

_TOPICOS_RESTRITOS = (
    "milha",
    "milhas",
    "milhagem",
    "pontos",
    "programa de milhas",
    "bagagem",
    "franquia",
    "mala",
)


@lru_cache
def get_llm() -> ChatOpenAI:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("A variavel DEEPSEEK_API_KEY nao foi definida.")

    return ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        api_key=api_key,
        base_url="https://api.deepseek.com",
        temperature=0.2,
    )


def _mensagem_politica_indisponivel() -> str:
    return (
        "No momento, este canal nao possui ferramenta ou politica oficial configurada para "
        "responder sobre milhagem e bagagem. Para evitar informacao imprecisa, vou encaminhar "
        "seu caso para a equipe humana de atendimento."
    )


def _deve_bloquear_por_politica(message: str) -> bool:
    texto = message.lower()
    return any(topico in texto for topico in _TOPICOS_RESTRITOS)


def atendimento_response(message: str, customer_name: str | None = None) -> str:
    if _deve_bloquear_por_politica(message):
        return _mensagem_politica_indisponivel()

    llm = get_llm()
    prompt = f"""
Voce e um agente de atendimento de uma empresa de passagens aereas com foco em marketing e experiencia do cliente.
Responda em portugues brasileiro de forma objetiva, cordial e util.

Cliente: {customer_name or 'Nao informado'}
Mensagem do cliente: {message}

Diretrizes:
- Se a duvida for geral, esclareca politicas e proximos passos.
- So fale sobre milhagem, bagagem, descontos e beneficios se houver politica interna explicita para isso.
- Se o cliente perguntar sobre assunto sem ferramenta disponivel ou sem politica estabelecida, informe que nao pode confirmar no momento e encaminhe para equipe humana.
- Para perguntas sobre milhagem e bagagem sem politica definida, responda que a informacao nao esta disponivel neste canal.
- Nao invente regras juridicas. Quando necessario, diga que vai validar com a equipe.
""".strip()
    return llm.invoke(prompt).content


def vendas_response(message: str, customer_name: str | None = None) -> str:
    if _deve_bloquear_por_politica(message):
        return _mensagem_politica_indisponivel()

    llm = get_llm()
    prompt = f"""
Voce e um agente de vendas de passagens aereas.
Responda em portugues brasileiro com foco comercial e consultivo.

Cliente: {customer_name or 'Nao informado'}
Pedido: {message}

Diretrizes:
- Pergunte dados que faltam (origem, destino, datas, bagagem, numero de passageiros).
- Sugira opcoes de tarifa (economica, flexivel, executiva) com linguagem clara.
- Nao ofereca milhagem, bagagem, descontos ou beneficios sem politica definida no contexto.
- Se faltar ferramenta ou politica para responder, informe a indisponibilidade e direcione para atendimento humano.
- Finalize com um CTA para fechar a compra.
""".strip()
    return llm.invoke(prompt).content


def cancelamento_response(
    message: str,
    reservation_code: str | None = None,
    customer_name: str | None = None,
) -> str:
    if _deve_bloquear_por_politica(message):
        return _mensagem_politica_indisponivel()

    llm = get_llm()
    prompt = f"""
Voce e um agente de cancelamento de passagens aereas.
Responda em portugues brasileiro de modo empatico e claro.

Cliente: {customer_name or 'Nao informado'}
Codigo da reserva: {reservation_code or 'Nao informado'}
Solicitacao: {message}

Diretrizes:
- Liste passos para cancelar com seguranca.
- Informe de forma neutra que multa/reembolso dependem da tarifa e prazo.
- Oriente como acompanhar status do estorno.
- Se faltar codigo da reserva, solicite.
- Se a solicitacao depender de ferramenta indisponivel ou politica nao estabelecida, nao invente resposta: informe limitacao e encaminhe para a equipe humana.
""".strip()
    return llm.invoke(prompt).content
