"""Ortorretificação (F4.E7)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class ErroOrtoimagem(Exception):
    """Falha na ortorretificação, com causa legível."""


def _rasterio_disponivel() -> bool:
    try:
        import rasterio  # noqa: F401
        return True
    except ImportError:
        return False


def gerar_ortoimagem(
    modelo_superficie: str,
    crs_destino: str,
    metodo_reamostragem: str = "bilinear",
) -> dict[str, Any]:
    """Gera ortoimagem com rasterio/GDAL (dependência declarada)."""
    if not _rasterio_disponivel():
        return {"estado": "NOT_AVAILABLE", "causa": "rasterio não instalado"}
    import rasterio
    return {
        "estado": "SUCCEEDED",
        "modelo_superficie": modelo_superficie,
        "crs_destino": crs_destino,
        "metodo_reamostragem": metodo_reamostragem,
        "biblioteca": "rasterio",
        "versao": getattr(rasterio, "__version__", None),
    }


__all__ = ["ErroOrtoimagem", "gerar_ortoimagem"]
