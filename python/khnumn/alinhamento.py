"""Alinhamento de fontes (F8.E2).

Alinha fontes heterogéneas com modelos geométricos adequados e restrições
explícitas. Nunca aplica transformações não rígidas por aparência: quando a
geometria é degenerada, o estado é declarado, não corrigido silenciosamente.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np


class ErroAlinhamento(Exception):
    """Falha no alinhamento de fontes, com causa legível."""


@dataclass
class ModeloGeometricoAlinhamento:
    """Modelo geométrico usado para alinhar uma fonte."""

    tipo: str
    """Tipo: `similaridade_7p`, `afim`, `rigida` ou `nenhuma`."""

    parametros: dict[str, Any]
    """Parâmetros do modelo (matriz, translação, escala, etc.)."""

    restricoes: list[str] = field(default_factory=list)
    """Restrições explícitas aplicadas (ex.: `sem_escala`, `sem_cisalhamento`)."""


@dataclass
class ResultadoAlinhamento:
    """Resultado do alinhamento de uma fonte."""

    fonte_origem: str
    fonte_destino: str
    modelo: ModeloGeometricoAlinhamento
    erro_residual_medio: float
    """Erro residual médio após o alinhamento, em metros."""

    pontos_usados: int
    """Número de pontos de correspondência usados."""

    estado: str = "SUCCEEDED"
    """Estado: `SUCCEEDED`, `DEGENERADO` ou `FAILED`."""

    motivo: str | None = None
    """Causa, quando o alinhamento não pôde ser concluído."""


def alinhar_fontes(
    pontos_origem: list[list[float]],
    pontos_destino: list[list[float]],
    modelo_tipo: str = "similaridade_7p",
    restricoes: list[str] | None = None,
    pesos: list[float] | None = None,
) -> ResultadoAlinhamento:
    """Alinha uma fonte de origem a uma fonte de destino.

    Usa o modelo geométrico especificado com as restrições declaradas.
    Quando os pontos são insuficientes ou a geometria é degenerada, o
    estado é `DEGENERADO` com a causa registada, nunca uma transformação
    não rígida aplicada por aparência.
    """
    origem = np.asarray(pontos_origem, dtype=float)
    destino = np.asarray(pontos_destino, dtype=float)

    if origem.shape != destino.shape:
        raise ErroAlinhamento(
            "pontos de origem e destino têm de ter a mesma forma"
        )
    if origem.ndim != 2 or origem.shape[1] != 3:
        raise ErroAlinhamento("os pontos têm de ser matrizes Nx3")

    n_pontos = origem.shape[0]
    restricoes = restricoes or []

    # Mínimo de pontos por tipo de modelo.
    minimos = {
        "similaridade_7p": 3,
        "rigida": 3,
        "afim": 4,
        "nenhuma": 1,
    }
    minimo = minimos.get(modelo_tipo, 3)
    if n_pontos < minimo:
        return ResultadoAlinhamento(
            fonte_origem="origem",
            fonte_destino="destino",
            modelo=ModeloGeometricoAlinhamento(
                tipo=modelo_tipo,
                parametros={},
                restricoes=list(restricoes),
            ),
            erro_residual_medio=float("nan"),
            pontos_usados=n_pontos,
            estado="DEGENERADO",
            motivo=(
                f"pontos insuficientes para {modelo_tipo}: "
                f"{n_pontos} < {minimo}"
            ),
        )

    # Ajuste por mínimos quadrados ponderados.
    if pesos is None:
        pesos_arr = np.ones(n_pontos)
    else:
        pesos_arr = np.asarray(pesos, dtype=float)
        if pesos_arr.shape[0] != n_pontos:
            raise ErroAlinhamento("os pesos têm de ter um valor por ponto")

    # Centroides ponderados.
    soma_pesos = float(np.sum(pesos_arr))
    if soma_pesos <= 0:
        return ResultadoAlinhamento(
            fonte_origem="origem",
            fonte_destino="destino",
            modelo=ModeloGeometricoAlinhamento(
                tipo=modelo_tipo,
                parametros={},
                restricoes=list(restricoes),
            ),
            erro_residual_medio=float("nan"),
            pontos_usados=n_pontos,
            estado="DEGENERADO",
            motivo="soma de pesos é zero ou negativa",
        )

    mu_o = np.sum(origem * pesos_arr[:, None], axis=0) / soma_pesos
    mu_d = np.sum(destino * pesos_arr[:, None], axis=0) / soma_pesos

    oc = origem - mu_o
    dc = destino - mu_d

    # Covariância cruzada ponderada.
    sigma = (oc * pesos_arr[:, None]).T @ dc / soma_pesos

    # SVD para rotação (algoritmo de Umeyama).
    try:
        U, S, Vt = np.linalg.svd(sigma)
    except np.linalg.LinAlgError as erro:
        return ResultadoAlinhamento(
            fonte_origem="origem",
            fonte_destino="destino",
            modelo=ModeloGeometricoAlinhamento(
                tipo=modelo_tipo,
                parametros={},
                restricoes=list(restricoes),
            ),
            erro_residual_medio=float("nan"),
            pontos_usados=n_pontos,
            estado="DEGENERADO",
            motivo=f"SVD falhou: {erro}",
        )

    D = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        D[2, 2] = -1.0

    R = Vt.T @ D @ U.T

    # Escala (apenas se não houver restrição sem_escala).
    escala = 1.0
    if "sem_escala" not in restricoes:
        var_o = float(np.sum(pesos_arr * np.sum(oc ** 2, axis=1)) / soma_pesos)
        if var_o > 0:
            num = float(
                np.sum(
                    pesos_arr
                    * np.sum(oc * (R @ oc.T).T, axis=1)
                )
            )
            escala = num / var_o

    # Translação.
    t = mu_d - escala * (R @ mu_o)

    # Erro residual médio.
    transformados = escala * (origem @ R.T) + t
    residuos = np.linalg.norm(transformados - destino, axis=1)
    erro_medio = float(np.mean(residuos))

    # Deteta degenerescência: erro residual muito grande indica que o
    # modelo não é adequado para os dados.
    if erro_medio > 10.0:
        estado = "DEGENERADO"
        motivo = (
            f"erro residual médio elevado ({erro_medio:.2f} m); "
            "geometria possivelmente degenerada"
        )
    else:
        estado = "SUCCEEDED"
        motivo = None

    return ResultadoAlinhamento(
        fonte_origem="origem",
        fonte_destino="destino",
        modelo=ModeloGeometricoAlinhamento(
            tipo=modelo_tipo,
            parametros={
                "rotacao": R.tolist(),
                "translacao": t.tolist(),
                "escala": escala,
            },
            restricoes=list(restricoes),
        ),
        erro_residual_medio=erro_medio,
        pontos_usados=n_pontos,
        estado=estado,
        motivo=motivo,
    )


def detetar_deformacao_nao_rigida(
    resultado: ResultadoAlinhamento,
    limiar_deformacao_m: float = 1.0,
) -> bool:
    """Deteta se há deformação não rígida entre as fontes.

    Quando o erro residual excede o limiar, indica deformação não rígida.
    Esta função apenas deteta: não aplica corretção silenciosa.
    """
    return resultado.erro_residual_medio > limiar_deformacao_m


def resultado_para_dict(
    resultado: ResultadoAlinhamento,
) -> dict[str, Any]:
    """Serializa o resultado de alinhamento para dicionário JSON."""
    return {
        "fonte_origem": resultado.fonte_origem,
        "fonte_destino": resultado.fonte_destino,
        "modelo": {
            "tipo": resultado.modelo.tipo,
            "parametros": resultado.modelo.parametros,
            "restricoes": resultado.modelo.restricoes,
        },
        "erro_residual_medio": resultado.erro_residual_medio,
        "pontos_usados": resultado.pontos_usados,
        "estado": resultado.estado,
        "motivo": resultado.motivo,
    }


__all__ = [
    "ErroAlinhamento",
    "ModeloGeometricoAlinhamento",
    "ResultadoAlinhamento",
    "alinhar_fontes",
    "detetar_deformacao_nao_rigida",
    "resultado_para_dict",
]
