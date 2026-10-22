"""Rasterização de superfície como instrumento de validação (§13.6).

Produz campos quantificados, nunca imagens. A classe "sem observação" é
explícita, e nunca é apresentada como um valor.
"""

from __future__ import annotations

from typing import Any

import numpy as np


#: Valor sentinela para a classe "sem observação".
SEM_OBSERVACAO = float("nan")


class ErroRaster(Exception):
    """Falha na rasterização, com causa legível."""


def rasterizar_pontos(
    coords: list[tuple[float, float]],
    valores: list[float],
    largura: int,
    altura: int,
    agregacao: str = "media",
) -> np.ndarray:
    """Rasteriza uma lista de pontos (u, v, valor) numa grelha.

    A classe "sem observação" é NaN. A agregação pode ser 'media', 'max'
    ou 'min' quando vários pontos caem no mesmo píxel.
    """
    if len(coords) != len(valores):
        raise ErroRaster("coords e valores têm de ter o mesmo comprimento")
    raster = np.full((altura, largura), SEM_OBSERVACAO, dtype=float)
    acumulador: dict[tuple[int, int], list[float]] = {}
    for (u, v), valor in zip(coords, valores):
        xi, yi = int(round(u)), int(round(v))
        if 0 <= xi < largura and 0 <= yi < altura:
            acumulador.setdefault((yi, xi), []).append(float(valor))

    for (yi, xi), vals in acumulador.items():
        arr = np.asarray(vals, dtype=float)
        if agregacao == "media":
            raster[yi, xi] = float(np.mean(arr))
        elif agregacao == "max":
            raster[yi, xi] = float(np.max(arr))
        elif agregacao == "min":
            raster[yi, xi] = float(np.min(arr))
        else:
            raise ErroRaster(f"agregação desconhecida: {agregacao}")
    return raster


def metricas_raster(raster: np.ndarray) -> dict[str, Any]:
    """Calcula média, p95 e máximo, ignorando a classe sem observação."""
    dados = raster[np.isfinite(raster)]
    if dados.size == 0:
        return {"n": 0, "media": None, "p95": None, "maximo": None,
                "sem_observacao_px": int(raster.size)}
    return {
        "n": int(dados.size),
        "media": float(np.mean(dados)),
        "p95": float(np.percentile(dados, 95)),
        "maximo": float(np.max(dados)),
        "sem_observacao_px": int(raster.size - dados.size),
    }


def classe_sem_observacao(raster: np.ndarray) -> np.ndarray:
    """Devolve uma máscara booleana da classe sem observação."""
    return ~np.isfinite(raster)


__all__ = [
    "ErroRaster",
    "SEM_OBSERVACAO",
    "classe_sem_observacao",
    "metricas_raster",
    "rasterizar_pontos",
]
