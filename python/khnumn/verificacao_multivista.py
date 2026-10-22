"""Verificação multivista por acumulação de profundidade (F8.E6).

Calcula `inconsistencia_multivista_m` por sub-região, com o número de
vistas observadoras declarado, e compara com a referência de varrimento laser
dentro dos limiares declarados. Depende de F9.E4 (renderização multivista
determinística) para os rasters de profundidade.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


class ErroVerificacaoMultivista(Exception):
    """Falha na verificação multivista, com causa legível."""


@dataclass
class SubRegiao:
    """Uma sub-região de uma cena para verificação multivista."""

    identificador: str
    coordenadas: list[float]
    """[x_min, y_min, x_max, y_max] da sub-região."""

    inconsistencia_m: float | None = None
    """Inconsistência multivista medida, em metros."""

    num_vistas_observadoras: int = 0
    """Número de vistas que observam esta sub-região."""

    profundidade_media_m: float | None = None
    """Profundidade média estimada na sub-região, em metros."""

    estado: str = "sem_dados"
    """Estado: `valido`, `inconsistente`, `sem_dados`."""


@dataclass
class ReferenciaLaser:
    """Referência de varrimento laser para comparação."""

    profundidade_por_regiao: dict[str, float]
    """Profundidade de referência por identificador de sub-região, em metros."""

    limiar_inconsistencia_m: float = 0.05
    """Limiar de inconsistência aceitável, em metros."""


@dataclass
class ResultadoVerificacaoMultivista:
    """Resultado da verificação multivista."""

    sub_regioes: list[SubRegiao]
    referencia_laser: ReferenciaLaser | None
    num_regioes_inconsistentes: int
    num_regioes_validas: int
    num_regioes_sem_dados: int
    inconsistencia_media_m: float
    estado: str = "SUCCEEDED"
    motivo: str | None = None


def acumular_profundidade_por_subregiao(
    rasters_profundidade: list[dict[str, Any]],
    sub_regioes: list[SubRegiao],
) -> list[SubRegiao]:
    """Acumula mapas de profundidade de múltiplas vistas por sub-região.

    Para cada sub-região, calcula a inconsistência multivista como o desvio
    padrão das profundidades estimadas por cada vista observadora. O número
    de vistas observadoras é declarado para cada sub-região.
    """
    for sub_regiao in sub_regioes:
        x_min, y_min, x_max, y_max = sub_regiao.coordenadas

        profundidades_vistas: list[float] = []
        num_vistas = 0

        for raster in rasters_profundidade:
            dados = raster.get("dados")
            transformacao = raster.get("transformacao")
            if dados is None or transformacao is None:
                continue

            # Converte coordenadas do mundo para índices do raster (simplificado).
            # Em produção, usaria a transformação geoespacial completa.
            try:
                import numpy as np

                matriz = np.asarray(dados, dtype=float)
                h, w = matriz.shape

                # Mapeia coordenadas do mundo para índices de pixel (aproximado).
                ix_min = int(max(0, x_min * w / 1000.0))
                iy_min = int(max(0, y_min * h / 1000.0))
                ix_max = int(min(w, x_max * w / 1000.0))
                iy_max = int(min(h, y_max * h / 1000.0))

                if ix_max > ix_min and iy_max > iy_min:
                    regiao = matriz[iy_min:iy_max, ix_min:ix_max]
                    dados_finitos = regiao[np.isfinite(regiao)]
                    if dados_finitos.size > 0:
                        profundidades_vistas.append(
                            float(np.mean(dados_finitos))
                        )
                        num_vistas += 1
            except Exception:
                continue

        if num_vistas == 0:
            sub_regiao.num_vistas_observadoras = 0
            sub_regiao.profundidade_media_m = None
            sub_regiao.inconsistencia_m = None
            sub_regiao.estado = "sem_dados"
            continue

        sub_regiao.num_vistas_observadoras = num_vistas
        sub_regiao.profundidade_media_m = float(np.mean(profundidades_vistas))

        if num_vistas >= 2:
            desvio = float(np.std(profundidades_vistas))
            sub_regiao.inconsistencia_m = desvio
            sub_regiao.estado = "valido"
        else:
            sub_regiao.inconsistencia_m = 0.0
            sub_regiao.estado = "valido"

    return sub_regioes


def comparar_referencia_laser(
    sub_regioes: list[SubRegiao],
    referencia: ReferenciaLaser,
) -> ResultadoVerificacaoMultivista:
    """Compara a inconsistência multivista com a referência de varrimento laser.

    Uma sub-região é inconsistente quando o seu `inconsistencia_m` excede o
    limiar da referência laser. O número de vistas observadoras é declarado
    para cada sub-região.
    """
    inconsistencias: list[float] = []
    num_inconsistentes = 0
    num_validas = 0
    num_sem_dados = 0

    for sub_regiao in sub_regioes:
        if sub_regiao.estado == "sem_dados":
            num_sem_dados += 1
            continue

        if sub_regiao.inconsistencia_m is None:
            num_sem_dados += 1
            continue

        inconsistencias.append(sub_regiao.inconsistencia_m)

        ref_profundidade = referencia.profundidade_por_regiao.get(
            sub_regiao.identificador
        )
        if ref_profundidade is not None:
            # Compara a profundidade média com a referência laser.
            if sub_regiao.profundidade_media_m is not None:
                desvio_laser = abs(
                    sub_regiao.profundidade_media_m - ref_profundidade
                )
                if (
                    desvio_laser > referencia.limiar_inconsistencia_m
                    or sub_regiao.inconsistencia_m
                    > referencia.limiar_inconsistencia_m
                ):
                    num_inconsistentes += 1
                    sub_regiao.estado = "inconsistente"
                else:
                    num_validas += 1
                    sub_regiao.estado = "valido"
            else:
                num_sem_dados += 1
        else:
            # Sem referência para esta sub-região, avalia apenas a
            # inconsistência intrínseca.
            if sub_regiao.inconsistencia_m > referencia.limiar_inconsistencia_m:
                num_inconsistentes += 1
                sub_regiao.estado = "inconsistente"
            else:
                num_validas += 1
                sub_regiao.estado = "valido"

    inconsistencia_media = (
        float(np.mean(inconsistencias)) if inconsistencias else 0.0
    )

    estado = "SUCCEEDED" if num_inconsistentes == 0 else "SUCCEEDED_WITH_WARNINGS"
    motivo: str | None = None
    if num_inconsistentes > 0:
        motivo = (
            f"{num_inconsistentes} sub-região(ões) inconsistente(s) com a "
            f"referência laser (limiar {referencia.limiar_inconsistencia_m} m)"
        )

    return ResultadoVerificacaoMultivista(
        sub_regioes=list(sub_regioes),
        referencia_laser=referencia,
        num_regioes_inconsistentes=num_inconsistentes,
        num_regioes_validas=num_validas,
        num_regioes_sem_dados=num_sem_dados,
        inconsistencia_media_m=inconsistencia_media,
        estado=estado,
        motivo=motivo,
    )


def sub_regiao_para_dict(sub: SubRegiao) -> dict[str, Any]:
    """Serializa uma sub-região para dicionário JSON."""
    return {
        "identificador": sub.identificador,
        "coordenadas": list(sub.coordenadas),
        "inconsistencia_m": sub.inconsistencia_m,
        "num_vistas_observadoras": sub.num_vistas_observadoras,
        "profundidade_media_m": sub.profundidade_media_m,
        "estado": sub.estado,
    }


def resultado_para_dict(
    resultado: ResultadoVerificacaoMultivista,
) -> dict[str, Any]:
    """Serializa o resultado de verificação para dicionário JSON."""
    return {
        "sub_regioes": [sub_regiao_para_dict(s) for s in resultado.sub_regioes],
        "num_regioes_inconsistentes": resultado.num_regioes_inconsistentes,
        "num_regioes_validas": resultado.num_regioes_validas,
        "num_regioes_sem_dados": resultado.num_regioes_sem_dados,
        "inconsistencia_media_m": resultado.inconsistencia_media_m,
        "estado": resultado.estado,
        "motivo": resultado.motivo,
    }


__all__ = [
    "ErroVerificacaoMultivista",
    "ReferenciaLaser",
    "ResultadoVerificacaoMultivista",
    "SubRegiao",
    "acumular_profundidade_por_subregiao",
    "comparar_referencia_laser",
    "resultado_para_dict",
    "sub_regiao_para_dict",
]
