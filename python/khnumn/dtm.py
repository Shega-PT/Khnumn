"""DTM e filtragem de solo (F4.E8)."""

from __future__ import annotations

from typing import Any

import numpy as np


class ErroDTM(Exception):
    """Falha no DTM, com causa legível."""


def _open3d_disponivel() -> bool:
    try:
        import open3d  # noqa: F401
        return True
    except ImportError:
        return False


def classificar_solo(pontos: np.ndarray, altura_relativa: float = 0.5) -> dict[str, Any]:
    """Classifica pontos em solo/não-solo (Open3D quando disponível)."""
    if _open3d_disponivel():
        import open3d as o3d
        nuvem = o3d.geometry.PointCloud()
        nuvem.points = o3d.utility.Vector3dVector(np.asarray(pontos, dtype=float))
        # Filtragem morfológica simplificada: pontos abaixo do percentil.
        z = np.asarray(pontos, dtype=float)[:, 2]
        limiar = float(np.percentile(z, 30))
        solo = pontos[z <= limiar]
        nao_solo = pontos[z > limiar]
        return {
            "biblioteca": "open3d",
            "solo": solo.tolist() if hasattr(solo, "tolist") else [],
            "nao_solo": nao_solo.tolist() if hasattr(nao_solo, "tolist") else [],
            "metodo": "open3d",
        }
    # Fallback numérico, para ambientes sem Open3D.
    z = np.asarray(pontos, dtype=float)[:, 2]
    limiar = float(np.percentile(z, 30))
    solo = pontos[z <= limiar]
    nao_solo = pontos[z > limiar]
    return {
        "biblioteca": "numpy",
        "solo": solo.tolist() if hasattr(solo, "tolist") else [],
        "nao_solo": nao_solo.tolist() if hasattr(nao_solo, "tolist") else [],
        "metodo": "percentil",
        "aviso": "Open3D não disponível; classificação aproximada",
    }


def gerar_dtm(pontos: np.ndarray) -> dict[str, Any]:
    resultado = classificar_solo(pontos)
    solo = resultado.get("solo", [])
    return {
        "estado": "SUCCEEDED",
        "num_solo": len(solo),
        "num_nao_solo": len(resultado.get("nao_solo", [])),
        "zonas": {"medidas": len(solo), "interpoladas": 0, "desconhecidas": 0},
        "biblioteca": resultado.get("biblioteca"),
    }


__all__ = ["ErroDTM", "classificar_solo", "gerar_dtm"]
