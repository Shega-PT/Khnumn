"""Extração adaptativa de fotogramas (F6.E2).

Seleciona fotogramas de uma sequência de vídeo com base em deslocamento,
nitidez, paralaxe, sobreposição e mudança de perspectiva, respeitando uma
política de memória limitada. A seleção nunca é silenciosa: cada fotograma
excluído ou incluído fica com a sua justificação registada.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from . import qualidade


class ErroVideo(Exception):
    """Falha na extração de fotogramas, com causa legível."""


@dataclass
class FotogramaSelecionado:
    """Fotograma selecionado com a justificação da escolha."""

    indice: int
    """Índice do fotograma na sequência original."""

    caminho: str
    """Caminho do ficheiro de origem."""

    motivo_inclusao: str
    """Razão pela qual o fotograma foi incluído (deslocamento, nitidez,
    paralaxe, sobreposição, mudança de perspetiva)."""

    pontuacao: float
    """Pontuação de qualidade do fotograma (0.0 a 1.0)."""

    hash_perceptual: int
    """Hash perceptual dHash para deteção de quase-duplicados."""


@dataclass
class PoliticaMemoria:
    """Política de memória para seleção de fotogramas."""

    max_fotogramas: int = 200
    """Número máximo de fotogramas a selecionar."""

    max_memoria_mb: int = 500
    """Orçamento de memória, em megabytes, para processamento."""

    tamanho_lado_max_px: int = 1024
    """Tamanho máximo do lado maior da imagem analisada, em píxeis."""


def _carregar_cinza_reduzida(caminho: Path, tamanho_lado_max: int) -> Any:
    """Carrega a imagem em tons de cinza, reduzida ao limite de memória."""
    import numpy as np

    try:
        with Image.open(caminho) as imagem:
            imagem = imagem.convert("L")
            largura, altura = imagem.size
            escala = min(1.0, tamanho_lado_max / max(largura, altura))
            if escala < 1.0:
                novo = (
                    max(1, int(largura * escala)),
                    max(1, int(altura * escala)),
                )
                imagem = imagem.resize(novo, Image.Resampling.BILINEAR)
            return np.asarray(imagem, dtype=np.uint8)
    except (OSError, ValueError) as erro:
        raise ErroVideo(
            f"não foi possível ler a imagem {caminho}: {erro}"
        ) from erro


def _deslocamento(fotograma_a: np.ndarray, fotograma_b: np.ndarray) -> float:
    """Mede o deslocamento médio entre dois fotogramas (diferença absoluta)."""
    if fotograma_a.shape != fotograma_b.shape:
        return float("inf")
    return float(
        np.mean(np.abs(fotograma_a.astype(float) - fotograma_b.astype(float)))
    )


def selecionar_fotogramas(
    caminhos: list[str | Path],
    politica: PoliticaMemoria | None = None,
    nitidez_minima: float = 20.0,
) -> dict[str, Any]:
    """Seleciona fotogramas adaptativamente de uma sequência de vídeo.

    Os critérios são: deslocamento entre fotogramas consecutivos, nitidez
    (variância do Laplaciano), paralaxe, sobreposição e mudança de perspetiva.
    A política de memória limita o número de fotogramas e o tamanho das
    imagens analisadas. Cada decisão de inclusão/exclusão fica registada com
    a sua razão.
    """
    politica = politica or PoliticaMemoria()
    caminhos = [Path(c) for c in caminhos]

    if not caminhos:
        return {
            "fotogramas_selecionados": [],
            "num_originais": 0,
            "num_selecionados": 0,
            "politica": {
                "max_fotogramas": politica.max_fotogramas,
                "max_memoria_mb": politica.max_memoria_mb,
                "tamanho_lado_max_px": politica.tamanho_lado_max_px,
            },
            "motivos_exclusao": [],
        }

    fotogramas: list[FotogramaSelecionado] = []
    motivos_exclusao: list[dict[str, Any]] = []
    imagem_anterior: Any = None
    indice_anterior: int | None = None

    for indice, caminho in enumerate(caminhos):
        # Limite de número de fotogramas.
        if len(fotogramas) >= politica.max_fotogramas:
            motivos_exclusao.append(
                {
                    "indice": indice,
                    "caminho": str(caminho),
                    "motivo": "limite de número de fotogramas atingido",
                }
            )
            continue

        try:
            imagem = _carregar_cinza_reduzida(
                caminho, politica.tamanho_lado_max_px
            )
        except ErroVideo as erro:
            motivos_exclusao.append(
                {
                    "indice": indice,
                    "caminho": str(caminho),
                    "motivo": str(erro),
                }
            )
            continue

        # Nitidez.
        laplaciano = float(np.var(cv2.Laplacian(imagem, cv2.CV_64F)))
        if laplaciano < nitidez_minima:
            motivos_exclusao.append(
                {
                    "indice": indice,
                    "caminho": str(caminho),
                    "motivo": (
                        f"nitidez abaixo do limiar ({laplaciano:.2f} < {nitidez_minima})"
                    ),
                }
            )
            continue

        # Deslocamento relativo ao fotograma anterior selecionado.
        desloc = 0.0
        if imagem_anterior is not None and indice_anterior is not None:
            desloc = _deslocamento(imagem_anterior, imagem)
            if desloc < 1.0:
                motivos_exclusao.append(
                    {
                        "indice": indice,
                        "caminho": str(caminho),
                        "motivo": (
                            f"deslocamento insuficiente face ao fotograma "
                            f"{indice_anterior} ({desloc:.4f} < 1.0)"
                        ),
                    }
                )
                continue

        # Paralaxe e sobreposição: aproximadas pelo deslocamento; valores
        # elevados indicam mudança de perspetiva útil para reconstrução.
        mudanca_perspetiva = desloc > 5.0

        motivo_inclusao = []
        if desloc >= 1.0:
            motivo_inclusao.append("deslocamento")
        if laplaciano >= nitidez_minima:
            motivo_inclusao.append("nitidez")
        if mudanca_perspetiva:
            motivo_inclusao.append("mudanca_perspetiva")

        hash_perc = qualidade.hash_perceptual(caminho)

        fotogramas.append(
            FotogramaSelecionado(
                indice=indice,
                caminho=str(caminho),
                motivo_inclusao="; ".join(motivo_inclusao) or "primeiro_fotograma",
                pontuacao=float(min(1.0, laplaciano / 100.0)),
                hash_perceptual=hash_perc,
            )
        )
        imagem_anterior = imagem
        indice_anterior = indice

    return {
        "fotogramas_selecionados": [
            {
                "indice": f.indice,
                "caminho": f.caminho,
                "motivo_inclusao": f.motivo_inclusao,
                "pontuacao": f.pontuacao,
                "hash_perceptual": f.hash_perceptual,
            }
            for f in fotogramas
        ],
        "num_originais": len(caminhos),
        "num_selecionados": len(fotogramas),
        "politica": {
            "max_fotogramas": politica.max_fotogramas,
            "max_memoria_mb": politica.max_memoria_mb,
            "tamanho_lado_max_px": politica.tamanho_lado_max_px,
        },
        "motivos_exclusao": motivos_exclusao,
    }


def resultado_para_dict(
    resultado: dict[str, Any],
) -> dict[str, Any]:
    """Devolve o resultado já em forma de dicionário (identidade para JSON)."""
    return resultado


__all__ = [
    "ErroVideo",
    "FotogramaSelecionado",
    "PoliticaMemoria",
    "resultado_para_dict",
    "selecionar_fotogramas",
]
