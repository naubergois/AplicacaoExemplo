from __future__ import annotations

from typing import Any

from app.graph import support_graph


def _resumo_resposta(texto: str, limite: int = 180) -> str:
    texto_limpo = " ".join(texto.split())
    if len(texto_limpo) <= limite:
        return texto_limpo
    return f"{texto_limpo[:limite]}..."


def executar_simulacoes() -> None:
    cenarios: list[dict[str, Any]] = [
        {
            "titulo": "Atendimento - duvida sobre bagagem",
            "payload": {
                "message": "Qual e a franquia de bagagem para voo internacional?",
                "customer_name": "Ana",
            },
        },
        {
            "titulo": "Atendimento - programa de milhas",
            "payload": {
                "message": "Como funciona o programa de milhas e acumulacao de pontos?",
                "customer_name": "Rafael",
            },
        },
        {
            "titulo": "Vendas - viagem nacional",
            "payload": {
                "message": "Quero comprar passagem de Recife para Sao Paulo no proximo feriado.",
                "customer_name": "Bruna",
            },
        },
        {
            "titulo": "Vendas - viagem internacional",
            "payload": {
                "message": "Preciso de voo para Lisboa em outubro para 2 adultos e 1 crianca.",
                "customer_name": "Marcelo",
            },
        },
        {
            "titulo": "Vendas - tarifa executiva",
            "payload": {
                "message": "Tem opcao de classe executiva com bagagem extra para Nova York?",
                "customer_name": "Carolina",
            },
        },
        {
            "titulo": "Cancelamento - com codigo de reserva",
            "payload": {
                "message": "Quero cancelar minha passagem por mudanca de planos.",
                "customer_name": "Paulo",
                "reservation_code": "ZXC123",
            },
        },
        {
            "titulo": "Cancelamento - sem codigo de reserva",
            "payload": {
                "message": "Preciso cancelar minha viagem urgente.",
                "customer_name": "Luciana",
            },
        },
        {
            "titulo": "Cancelamento - pedido de reembolso",
            "payload": {
                "message": "Solicito cancelamento e gostaria de saber o prazo de estorno.",
                "customer_name": "Diego",
                "reservation_code": "LMN456",
            },
        },
        {
            "titulo": "Atendimento - alteracao de assento",
            "payload": {
                "message": "Consigo alterar o assento depois de emitir a passagem?",
                "customer_name": "Fernanda",
            },
        },
    ]

    print("=" * 80)
    print("SIMULADOR DE FLUXOS - AGENTES DE PASSAGENS AEREAS")
    print("=" * 80)

    contagem_fluxos = {"atendimento": 0, "vendas": 0, "cancelamento": 0}

    for indice, caso in enumerate(cenarios, start=1):
        print("\n" + "-" * 80)
        print(f"Cenario {indice}: {caso['titulo']}")
        print(f"Entrada: {caso['payload']}")

        try:
            resultado = support_graph.invoke(caso["payload"])
        except Exception as exc:
            print(f"Erro na execucao do cenario: {exc}")
            continue

        fluxo = resultado.get("intent", "atendimento")
        resposta = resultado.get("response", "Sem resposta")

        if fluxo in contagem_fluxos:
            contagem_fluxos[fluxo] += 1

        print(f"Fluxo executado: {fluxo}")
        print(f"Resposta resumida: {_resumo_resposta(resposta)}")

    print("\n" + "=" * 80)
    print("RESUMO DE FLUXOS IDENTIFICADOS")
    print("=" * 80)
    print(f"Atendimento:  {contagem_fluxos['atendimento']}")
    print(f"Vendas:       {contagem_fluxos['vendas']}")
    print(f"Cancelamento: {contagem_fluxos['cancelamento']}")


if __name__ == "__main__":
    executar_simulacoes()
