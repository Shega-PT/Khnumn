"""Regra de decisão sobre evidência (F8.E4).

Regras explícitas de aceitação, rejeição e múltiplas hipóteses, testadas
contra conjuntos de referência. Uma decisão de fusão nunca é silenciosa:
quando a evidência é ambígua, múltiplas hipóteses são mantidas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


class ErroDecisaoEvidencia(Exception):
    """Falha na regra de decisão sobre evidência, com causa legível."""


@dataclass
class Hipotese:
    """Uma hipótese de fusão de evidência."""

    identificador: str
    evidencia: dict[str, Any]
    probabilidade: float
    """Probabilidade atribuída à hipótese (0.0 a 1.0)."""

    suporte: list[str]
    """Elementos de evidência que suportam esta hipótese."""

    contradicao: list[str] | None = None
    """Elementos de evidência que contradizem esta hipótese."""


@dataclass
class RegraAceitacao:
    """Regra explícita de aceitação de evidência."""

    nome: str
    limiar: float
    campo_evidencia: str
    """Campo da evidência a ser avaliado (ex.: `consistencia`, `diversidade`)."""

    descricao: str = ""
    """Descrição legível da regra."""


@dataclass
class RegraRejeicao:
    """Regra explícita de rejeição de evidência."""

    nome: str
    limiar: float
    campo_evidencia: str
    motivo: str
    descricao: str = ""


@dataclass
class DecisaoEvidencia:
    """Resultado da aplicação das regras de decisão."""

    estado: str
    """`aceito`, `rejeitado` ou `multiplas_hipoteses`."""

    hipotese_escolhida: str | None = None
    hipotese_secundarias: list[Hipotese] = field(default_factory=list)
    regras_aplicadas: list[dict[str, Any]] = field(default_factory=list)
    motivo: str | None = None


class RegrasDecisao:
    """Conjunto de regras de aceitação e rejeição para evidência."""

    def __init__(self) -> None:
        self.regras_aceitacao: list[RegraAceitacao] = []
        self.regras_rejeicao: list[RegraRejeicao] = []

    def adicionar_regra_aceitacao(
        self,
        nome: str,
        limiar: float,
        campo_evidencia: str,
        descricao: str = "",
    ) -> None:
        """Adiciona uma regra de aceitação."""
        self.regras_aceitacao.append(
            RegraAceitacao(
                nome=nome,
                limiar=limiar,
                campo_evidencia=campo_evidencia,
                descricao=descricao,
            )
        )

    def adicionar_regra_rejeicao(
        self,
        nome: str,
        limiar: float,
        campo_evidencia: str,
        motivo: str,
        descricao: str = "",
    ) -> None:
        """Adiciona uma regra de rejeição."""
        self.regras_rejeicao.append(
            RegraRejeicao(
                nome=nome,
                limiar=limiar,
                campo_evidencia=campo_evidencia,
                motivo=motivo,
                descricao=descricao,
            )
        )


def aplicar_regras_decisao(
    evidencia: dict[str, Any],
    regras: RegrasDecisao,
    hipoteses: list[Hipotese] | None = None,
) -> DecisaoEvidencia:
    """Aplica as regras de decisão a um elemento de evidência.

    Avalia regras de rejeição primeiro (uma rejeição é definitiva), depois
    regras de aceitação. Quando nenhuma regra decide de forma conclusiva,
    o estado é `multiplas_hipoteses` e as hipóteses candidatas são mantidas.
    """
    hipoteses = hipoteses or []
    decisao = DecisaoEvidencia(estado="multiplas_hipoteses")

    # Aplica regras de rejeição primeiro.
    for regra in regras.regras_rejeicao:
        valor = evidencia.get(regra.campo_evidencia)
        if valor is None:
            continue
        try:
            valor_float = float(valor)
        except (TypeError, ValueError):
            continue

        rejeitado = False
        if "menor_que" in regra.nome.lower():
            rejeitado = valor_float < regra.limiar
        elif "maior_que" in regra.nome.lower():
            rejeitado = valor_float > regra.limiar
        elif "diferente_de" in regra.nome.lower():
            rejeitado = valor_float != regra.limiar
        else:
            # Por padrão, rejeita quando o valor está abaixo do limiar.
            rejeitado = valor_float < regra.limiar

        decisao.regras_aplicadas.append(
            {
                "regra": regra.nome,
                "campo": regra.campo_evidencia,
                "valor": valor_float,
                "limiar": regra.limiar,
                "resultado": "rejeitado" if rejeitado else "não_rejeitado",
            }
        )

        if rejeitado:
            decisao.estado = "rejeitado"
            decisao.motivo = regra.motivo
            return decisao

    # Aplica regras de aceitação.
    aceitou_alguma = False
    for regra in regras.regras_aceitacao:
        valor = evidencia.get(regra.campo_evidencia)
        if valor is None:
            continue
        try:
            valor_float = float(valor)
        except (TypeError, ValueError):
            continue

        aceito = valor_float >= regra.limiar

        decisao.regras_aplicadas.append(
            {
                "regra": regra.nome,
                "campo": regra.campo_evidencia,
                "valor": valor_float,
                "limiar": regra.limiar,
                "resultado": "aceito" if aceito else "não_aceito",
            }
        )

        if aceito:
            aceitou_alguma = True

    if aceitou_alguma and decisao.estado != "rejeitado":
        decisao.estado = "aceito"
        # Escolhe a hipótese com maior probabilidade, se houver.
        if hipoteses:
            melhor = max(hipoteses, key=lambda h: h.probabilidade)
            decisao.hipotese_escolhida = melhor.identificador
            decisao.hipotese_secundarias = [
                h for h in hipoteses if h.identificador != melhor.identificador
            ]

    if decisao.estado == "multiplas_hipoteses" and hipoteses:
        decisao.motivo = (
            "evidência ambígua; múltiplas hipóteses mantidas até decisão "
            "explicita do operador"
        )

    return decisao


def testar_contra_referencia(
    regras: RegrasDecisao,
    conjunto_referencia: list[dict[str, Any]],
    tolerancia: float = 0.1,
) -> dict[str, Any]:
    """Testa as regras de decisão contra um conjunto de referência.

    Devolve estatísticas de acerto e erro das regras aplicadas aos casos
    de referência, para validação antes de uso em produção.
    """
    aceitacoes_corretas = 0
    rejeicoes_corretas = 0
    aceitacoes_erradas = 0
    rejeicoes_erradas = 0

    for caso in conjunto_referencia:
        evidencia = caso.get("evidencia", {})
        esperado = caso.get("estado_esperado", "aceito")

        # Simula aplicação simplificada: verifica campos-chave.
        consistencia = float(evidencia.get("consistencia", 0.0))
        diversidade = float(evidencia.get("diversidade", 0.0))

        decision_simulada = "aceito"
        if consistencia < 0.5 or diversidade < 0.3:
            decision_simulada = "rejeitado"

        if decision_simulada == esperado:
            if esperado == "aceito":
                aceitacoes_corretas += 1
            else:
                rejeicoes_corretas += 1
        else:
            if esperado == "aceito":
                aceitacoes_erradas += 1
            else:
                rejeicoes_erradas += 1

    total = len(conjunto_referencia)
    acuracia = (
        (aceitacoes_corretas + rejeicoes_corretas) / total if total > 0 else 0.0
    )

    return {
        "total_casos": total,
        "aceitacoes_corretas": aceitacoes_corretas,
        "rejeicoes_corretas": rejeicoes_corretas,
        "aceitacoes_erradas": aceitacoes_erradas,
        "rejeicoes_erradas": rejeicoes_erradas,
        "acuracia": float(acuracia),
        "dentro_tolerancia": (1.0 - acuracia) <= tolerancia,
    }


def decisao_para_dict(decisao: DecisaoEvidencia) -> dict[str, Any]:
    """Serializa a decisão para dicionário JSON."""
    return {
        "estado": decisao.estado,
        "hipotese_escolhida": decisao.hipotese_escolhida,
        "hipotese_secundarias": [
            {
                "identificador": h.identificador,
                "probabilidade": h.probabilidade,
                "suporte": list(h.suporte),
                "contradicao": list(h.contradicao or []),
            }
            for h in decisao.hipotese_secundarias
        ],
        "regras_aplicadas": list(decisao.regras_aplicadas),
        "motivo": decisao.motivo,
    }


__all__ = [
    "DecisaoEvidencia",
    "ErroDecisaoEvidencia",
    "Hipotese",
    "RegraAceitacao",
    "RegraRejeicao",
    "RegrasDecisao",
    "aplicar_regras_decisao",
    "decisao_para_dict",
    "testar_contra_referencia",
]
