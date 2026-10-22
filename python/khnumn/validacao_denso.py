"""Validação da via densa contra a referência de acelerador (F4.E10)."""

from __future__ import annotations

from typing import Any

import numpy as np


class ErroValidacaoDenso(Exception):
    """Falha na validação densa, com causa legível."""


def comparar_com_referencia(
    densa_cpu: np.ndarray,
    densa_gpu: np.ndarray,
    limiar_densidade: float = 0.9,
    limiar_distancia: float = 0.05,
) -> dict[str, Any]:
    """Compara densidade, completude, distância ponto-superfície e outliers."""
    a = np.asarray(densa_cpu, dtype=float)
    b = np.asarray(densa_gpu, dtype=float)
    densidade_ratio = float(a.shape[0] / max(1, b.shape[0]))
    # Distância média entre conjuntos (aproximação por vizinho mais próximo).
    if a.shape[0] == 0 or b.shape[0] == 0:
        return {"estado": "FAIL", "causa": "conjunto vazio"}
    # Implementação sem scipy: amostragem.
    amostra = a[: min(1000, a.shape[0])]
    dists = []
    for p in amostra:
        d = np.min(np.linalg.norm(b - p, axis=1))
        dists.append(float(d))
    distancia_media = float(np.mean(dists)) if dists else float("nan")
    outliers = int(sum(1 for d in dists if d > limiar_distancia))
    taxa_outliers = outliers / max(1, len(dists))
    aprovado = densidade_ratio >= limiar_densidade and distancia_media <= limiar_distancia
    return {
        "densidade_ratio": densidade_ratio,
        "distancia_media": distancia_media,
        "taxa_outliers": taxa_outliers,
        "num_outliers": outliers,
        "estado": "PASS" if aprovado else "FAIL",
    }


__all__ = ["ErroValidacaoDenso", "comparar_com_referencia"]
