"""Planeador de pipeline (Fase 5)."""

from __future__ import annotations

from typing import Any

from . import cenario as _cenario


class ErroPlaneador(Exception):
    """Falha no planeamento, com causa legível."""


def pipelines_compativeis(cenario: str) -> list[str]:
    if cenario in ("aerial_nadir", "aerial_oblique"):
        return ["sfm_incremental", "sfm_global"]
    if cenario == "satellite_optical":
        return ["satelite_rpc"]
    return ["sfm_incremental"]


def escolher_caminho_denso(hardware_gpu: bool, requisito_densidade: str) -> str:
    if hardware_gpu:
        return "denso_acelerador"
    if requisito_densidade == "alta":
        return "denso_cpu"
    return "esparsa_delaunay"


def estimar_custo(pipeline: str, dense_path: str, ensemble_samples: int, iteracoes: int) -> dict[str, Any]:
    base = 1.0
    if dense_path == "denso_cpu":
        base *= 3.0
    if dense_path == "denso_acelerador":
        base *= 1.5
    custo = base * (1 + 0.1 * ensemble_samples + 0.2 * iteracoes)
    return {"pipeline": pipeline, "custo_relativo": float(custo)}


def planear(
    cenario: str,
    hardware_gpu: bool,
    requisito_densidade: str = "media",
    ensemble_samples: int = 10,
    iteracoes_refino: int = 3,
    manual_override: str | None = None,
) -> dict[str, Any]:
    if manual_override:
        cenario = manual_override
    candidatos = pipelines_compativeis(cenario)
    dense_path = escolher_caminho_denso(hardware_gpu, requisito_densidade)
    planos = []
    for p in candidatos:
        custo = estimar_custo(p, dense_path, ensemble_samples, iteracoes_refino)
        planos.append({
            "pipeline": p,
            "dense_path": dense_path,
            "custo": custo,
            "ensemble_samples": ensemble_samples,
            "iteracoes_refino": iteracoes_refino,
        })
    # Escolha: menor custo.
    escolhido = min(planos, key=lambda x: x["custo"]["custo_relativo"]) if planos else None
    decisoes = [
        {"decisao": "cenario", "valor": cenario},
        {"decisao": "caminho_denso", "valor": dense_path},
        {"decisao": "pipeline", "valor": escolhido["pipeline"] if escolhido else None},
    ]
    return {
        "cenario": cenario,
        "candidatos": candidatos,
        "dense_path": dense_path,
        "escolhido": escolhido,
        "decisoes": decisoes,
        "fallback": "esparsa_delaunay" if dense_path != "esparsa_delaunay" else None,
    }


def funcao_multiobjetivo(custos: dict[str, float], pesos: dict[str, float]) -> float:
    total = 0.0
    for chave, valor in custos.items():
        peso = pesos.get(chave, 1.0)
        total += peso * valor
    return float(total)


__all__ = [
    "ErroPlaneador",
    "estimar_custo",
    "escolher_caminho_denso",
    "funcao_multiobjetivo",
    "pipelines_compativeis",
    "planear",
]
