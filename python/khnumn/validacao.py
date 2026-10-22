"""Métricas de exatidão e relatório de incerteza (F3.E11, F3.E12)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np


class ErroValidacao(Exception):
    """Falha na validação, com causa legível."""


def rmse(vetor: np.ndarray) -> float:
    """RMSE de um vetor de erros."""
    vetor = np.asarray(vetor, dtype=float).ravel()
    if vetor.size == 0:
        return float("nan")
    return float(np.sqrt(np.mean(vetor ** 2)))


def metricas_exatidao(
    estimado: np.ndarray,
    referencia: np.ndarray,
    tolerancia_h_m: float | None = None,
    tolerancia_v_m: float | None = None,
    blunder_factor: float = 3.0,
) -> dict[str, Any]:
    """Calcula RMSE H/V/3D, erro médio, percentis e blunders.

    `estimado` e `referencia` são matrizes Nx3 (ou Nx2). A regra do
    blunder marca como blunder todo o ponto cujo erro excede
    `blunder_factor` vezes o RMSE-alvo.
    """
    estimado = np.asarray(estimado, dtype=float)
    referencia = np.asarray(referencia, dtype=float)
    if estimado.shape != referencia.shape:
        raise ErroValidacao("estimado e referencia têm de ter a mesma forma")
    if estimado.ndim != 2 or estimado.shape[1] not in (2, 3):
        raise ErroValidacao("as coordenadas têm de ser Nx2 ou Nx3")

    erros = estimado - referencia
    erros_h = np.linalg.norm(erros[:, :2], axis=1)
    if erros.shape[1] == 3:
        erros_v = np.abs(erros[:, 2])
        erros_3d = np.linalg.norm(erros, axis=1)
    else:
        erros_v = np.zeros(len(erros))
        erros_3d = erros_h.copy()

    rmse_h = rmse(erros_h)
    rmse_v = rmse(erros_v)
    rmse_3d = rmse(erros_3d)
    erro_medio_h = float(np.mean(erros_h)) if len(erros_h) else float("nan")
    erro_medio_v = float(np.mean(erros_v)) if len(erros_v) else float("nan")

    percentis = {
        "p50_h": float(np.percentile(erros_h, 50)) if len(erros_h) else float("nan"),
        "p90_h": float(np.percentile(erros_h, 90)) if len(erros_h) else float("nan"),
        "p95_h": float(np.percentile(erros_h, 95)) if len(erros_h) else float("nan"),
        "p99_h": float(np.percentile(erros_h, 99)) if len(erros_h) else float("nan"),
    }

    # Blunders: erro horizontal acima do limiar.
    limiar_blunder = (tolerancia_h_m if tolerancia_h_m is not None else rmse_h) * blunder_factor
    blunders = [int(i) for i in range(len(erros_h)) if erros_h[i] > limiar_blunder]

    return {
        "n": int(len(erros_h)),
        "rmse_horizontal_m": rmse_h,
        "rmse_vertical_m": rmse_v,
        "rmse_3d_m": rmse_3d,
        "erro_medio_horizontal_m": erro_medio_h,
        "erro_medio_vertical_m": erro_medio_v,
        "percentis": percentis,
        "blunders": blunders,
        "num_blunders": len(blunders),
        "limiar_blunder_m": float(limiar_blunder),
    }


def estado_aceitacao(
    metricas: dict[str, Any],
    tolerancia_h_m: float | None,
    tolerancia_v_m: float | None,
    max_mean_error_ratio: float = 0.25,
    blunder_factor: float = 3.0,
) -> dict[str, Any]:
    """Emite o estado de aceitação com a causa.

    Estados: PASS, PASS_WITH_WARNINGS, FAIL, NOT_VALIDATED.
    """
    causas: list[str] = []
    if tolerancia_h_m is None and tolerancia_v_m is None:
        return {"estado": "NOT_VALIDATED", "causa": "tolerâncias não declaradas"}

    rmse_h = metricas["rmse_horizontal_m"]
    rmse_v = metricas["rmse_vertical_m"]

    if tolerancia_h_m is not None and rmse_h > tolerancia_h_m:
        causas.append(f"RMSE horizontal {rmse_h:.4f} m excede a tolerância {tolerancia_h_m:.4f} m")
    if tolerancia_v_m is not None and rmse_v > tolerancia_v_m:
        causas.append(f"RMSE vertical {rmse_v:.4f} m excede a tolerância {tolerancia_v_m:.4f} m")

    # Razão erro médio / RMSE.
    if rmse_h and not math.isnan(rmse_h) and rmse_h > 0:
        razao = abs(metricas["erro_medio_horizontal_m"]) / rmse_h
        if razao > max_mean_error_ratio:
            causas.append(f"razão erro médio/RMSE {razao:.3f} excede {max_mean_error_ratio}")

    if metricas["num_blunders"] > 0:
        causas.append(f"{metricas['num_blunders']} blunder(s) detectado(s)")

    if not causas:
        return {"estado": "PASS", "causa": None}
    if len(causas) == 1 and "blunder" not in causas[0]:
        return {"estado": "PASS_WITH_WARNINGS", "causa": "; ".join(causas)}
    return {"estado": "FAIL", "causa": "; ".join(causas)}


def decompor_incerteza(
    incerteza_controlo: float,
    incerteza_cena: float,
) -> dict[str, Any]:
    """Decompõe a incerteza total em parcela de controlo e de cena."""
    total = math.sqrt(incerteza_controlo ** 2 + incerteza_cena ** 2)
    fracao_controlo = (incerteza_controlo / total) if total > 0 else 0.0
    return {
        "incerteza_controlo": float(incerteza_controlo),
        "incerteza_cena": float(incerteza_cena),
        "incerteza_total": float(total),
        "fracao_controlo": float(fracao_controlo),
        "fracao_cena": float(1.0 - fracao_controlo),
    }


__all__ = [
    "ErroValidacao",
    "decompor_incerteza",
    "estado_aceitacao",
    "metricas_exatidao",
    "rmse",
]
