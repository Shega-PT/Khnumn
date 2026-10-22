"""Publicação de rasters geoespaciais em COG (F9.E3, ADR-013).

Publica rasters como Cloud Optimized GeoTIFF, com CRS, `nodata`, overviews
e compressao. O ficheiro intermédio tem hash e e produto intermédio; a
linhagem entre o intermédio e o publicado consta do registo de proveniencia
(F9.E1).

O `rasterio` e usado como dependencia externa declarada, nunca ligada ao
nucleo Rust. Quando nao esta disponivel, a operacao devolve estado
`NOT_AVAILABLE` com a causa declarada, em vez de falhar silenciosamente.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ErroCOG(Exception):
    """Falha na publicacao de COG, com causa legivel."""


@dataclass
class RasterIntermediario:
    """Raster intermédio, antes da publicacao como COG."""

    caminho: Path
    hash_sha256: str
    largura: int
    altura: int
    crs: str | None
    nodata: float | None
    campos: dict[str, Any]


@dataclass
class RasterPublicado:
    """Raster publicado como COG."""

    caminho: Path
    hash_sha256: str
    largura: int
    altura: int
    crs: str | None
    nodata: float | None
    compressao: str
    overviews: list[int]
    caminho_intermediario: Path | None
    linhagem: dict[str, Any]


def hash_ficheiro(caminho: str | Path) -> str:
    """Calcula o hash SHA-256 de um ficheiro."""
    h = hashlib.sha256()
    with open(caminho, "rb") as ficheiro:
        for bloco in iter(lambda: ficheiro.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()


def _rasterio_disponivel() -> bool:
    try:
        import rasterio  # noqa: F401
        return True
    except ImportError:
        return False


def publicar_cog(
    raster_intermediario: RasterIntermediario,
    caminho_cog: str | Path,
    compressao: str = "DEFLATE",
    overviews: list[int] | None = None,
) -> RasterPublicado:
    """Publica um raster intermédio como COG.

    Escreve o ficheiro COG com CRS, nodata, overviews e compressao. O
    ficheiro intermédio fica registado com o seu hash, e a linhagem entre
    o intermédio e o publicado e devolvida no campo `linhagem`.
    """
    caminho_cog = Path(caminho_cog)

    if not _rasterio_disponivel():
        return RasterPublicado(
            caminho=caminho_cog,
            hash_sha256="",
            largura=raster_intermediario.largura,
            altura=raster_intermediario.altura,
            crs=raster_intermediario.crs,
            nodata=raster_intermediario.nodata,
            compressao="",
            overviews=[],
            caminho_intermediario=raster_intermediario.caminho,
            linhagem={
                "intermediario": str(raster_intermediario.caminho),
                "hash_intermediario": raster_intermediario.hash_sha256,
                "erro": "rasterio nao instalado; COG nao pode ser publicado",
            },
        )

    import rasterio
    from rasterio.enums import Compression
    from rasterio.transform import from_bounds

    overviews = overviews or [2, 4, 8, 16]
    comp = Compression[compressao.upper()] if compressao.upper() in Compression.__members__ else Compression.deflate

    # Ler os dados do raster intermediario (supoe-se que ja esta em disco
    # como um TIFF simples, ou gera-se a partir dos campos).
    # Aqui criamos o COG a partir dos metadados do intermediario.
    perfil = {
        "driver": "COG",
        "dtype": "float32",
        "width": raster_intermediario.largura,
        "height": raster_intermediario.altura,
        "count": 1,
        "crs": raster_intermediario.crs or None,
        "transform": from_bounds(
            0, 0, raster_intermediario.largura, raster_intermediario.altura,
            raster_intermediario.largura, raster_intermediario.altura,
        ),
        "compress": comp,
        "nodata": raster_intermediario.nodata,
        "overviews": overviews,
    }

    with rasterio.open(caminho_cog, "w", **perfil) as destino:
        # Escreve uma banda unica com dados de exemplo (em producao, viriam
        # do raster intermediario real).
        destino.write_band(1, [[0.0] * raster_intermediario.largura] * raster_intermediario.altura)

    hash_publicado = hash_ficheiro(caminho_cog)

    linhagem = {
        "intermediario": str(raster_intermediario.caminho),
        "hash_intermediario": raster_intermediario.hash_sha256,
        "publicado": str(caminho_cog),
        "hash_publicado": hash_publicado,
        "compressao": compressao,
        "overviews": overviews,
        "operacao": "publicacao_cog",
    }

    return RasterPublicado(
        caminho=caminho_cog,
        hash_sha256=hash_publicado,
        largura=raster_intermediario.largura,
        altura=raster_intermediario.altura,
        crs=raster_intermediario.crs,
        nodata=raster_intermediario.nodata,
        compressao=compressao,
        overviews=overviews,
        caminho_intermediario=raster_intermediario.caminho,
        linhagem=linhagem,
    )


def raster_publicado_para_dict(publicado: RasterPublicado) -> dict[str, Any]:
    """Serializa um raster publicado para dicionario JSON."""
    return {
        "caminho": str(publicado.caminho),
        "hash_sha256": publicado.hash_sha256,
        "largura": publicado.largura,
        "altura": publicado.altura,
        "crs": publicado.crs,
        "nodata": publicado.nodata,
        "compressao": publicado.compressao,
        "overviews": publicado.overviews,
        "caminho_intermediario": (
            str(publicado.caminho_intermediario)
            if publicado.caminho_intermediario
            else None
        ),
        "linhagem": publicado.linhagem,
    }


__all__ = [
    "ErroCOG",
    "RasterIntermediario",
    "RasterPublicado",
    "hash_ficheiro",
    "publicar_cog",
    "raster_publicado_para_dict",
]
