"""Mapa de cobertura e contagem de furos (F4.E11/F4.E12)."""

from __future__ import annotations

from typing import Any

import numpy as np

from . import raster


def gerar_mapa_cobertura(
    coords: list[tuple[float, float]],
    largura: int,
    altura: int,
) -> dict[str, Any]:
    """Gera raster de cobertura com métricas declaradas."""
    valores = [1.0 for _ in coords]
    r = raster.rasterizar_pontos(coords, valores, largura, altura)
    metricas = raster.metricas_raster(r)
    # Contagem de furos: componentes conexas de NaN.
    mascara = raster.classe_sem_observacao(r)
    furos = _contar_componentes(mascara)
    area_furos = int(mascara.sum())
    cobertura = 100.0 * (1.0 - mascara.mean())
    return {
        "raster": r,
        "cobertura_percent": float(cobertura),
        "furos_contagem": int(furos),
        "furos_area_px": area_furos,
        "metricas": metricas,
    }


def _contar_componentes(mascara: np.ndarray) -> int:
    """Conta componentes conexas de True (4-vizinhança)."""
    visitado = np.zeros_like(mascara, dtype=bool)
    contagem = 0
    h, w = mascara.shape
    for y in range(h):
        for x in range(w):
            if mascara[y, x] and not visitado[y, x]:
                contagem += 1
                pilha = [(y, x)]
                while pilha:
                    cy, cx = pilha.pop()
                    if cy < 0 or cx < 0 or cy >= h or cx >= w:
                        continue
                    if visitado[cy, cx] or not mascara[cy, cx]:
                        continue
                    visitado[cy, cx] = True
                    pilha.extend([(cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)])
    return contagem


def gerar_mapa_incerteza(
    coords: list[tuple[float, float]],
    valores: list[float],
    largura: int,
    altura: int,
    legenda: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Gera raster de incerteza com legenda."""
    r = raster.rasterizar_pontos(coords, valores, largura, altura)
    metricas = raster.metricas_raster(r)
    return {
        "raster": r,
        "metricas": metricas,
        "legenda": legenda or [],
    }


__all__ = ["gerar_mapa_cobertura", "gerar_mapa_incerteza"]
