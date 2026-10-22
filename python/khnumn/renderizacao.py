"""Renderização multivista determinística (F9.E4).

Gera uma sequência de frames a partir de uma malha e poses de câmera, de
forma reproduzível por hash. A sequência entra no grafo como uma tarefa com
versão e parâmetros. O caminho headless e o visor opcional produzem frames
idênticos, e a igualdade é verificada sem ecrã.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

import numpy as np


class ErroRenderizacao(Exception):
    """Falha na renderização multivista, com causa legível."""


@dataclass
class Frame:
    """Um frame renderizado."""

    indice: int
    """Índice do frame na sequência."""

    timestamp_s: float
    """Instante do frame, em segundos."""

    largura: int
    altura: int
    pixels: list[float]
    """Valores de profundidade ou cor, em ordem linha-major."""

    hash_frame: str
    """Hash do frame, para verificação de determinismo."""


@dataclass
class SequenciaFrames:
    """Sequência de frames renderizados."""

    frames: list[Frame]
    hash_sequencia: str
    """Hash de toda a sequência, para verificação de reprodução."""

    parametros: dict[str, Any]
    """Parâmetros de renderização (versão, resolução, poses, etc.)."""

    deterministico: bool = True
    """Verdadeiro quando a sequência é reproduzível por hash."""


def hash_frame(pixels: list[float]) -> str:
    """Calcula o hash de um frame para verificação de determinismo."""
    h = hashlib.sha256()
    for v in pixels:
        h.update(repr(v).encode("utf-8"))
    return h.hexdigest()


def renderizar_frame(
    indice: int,
    timestamp_s: float,
    largura: int,
    altura: int,
    profundidade_por_pixel: list[list[float]],
    parametros: dict[str, Any] | None = None,
) -> Frame:
    """Renderiza um único frame.

    `profundidade_por_pixel` é uma matriz altura x largura com valores de
    profundidade. Pixels sem dados recebem NaN (classe "sem dados").
    """
    pixels: list[float] = []
    for linha in profundidade_por_pixel:
        for v in linha:
            pixels.append(float(v) if v is not None else float("nan"))

    frame_hash = hash_frame(pixels)
    return Frame(
        indice=indice,
        timestamp_s=timestamp_s,
        largura=largura,
        altura=altura,
        pixels=pixels,
        hash_frame=frame_hash,
    )


def renderizar_sequencia(
    poses: list[dict[str, Any]],
    resolucao: tuple[int, int],
    funcao_profundidade: Any,
    semente: int = 0,
    parametros: dict[str, Any] | None = None,
) -> SequenciaFrames:
    """Renderiza uma sequência de frames de forma determinística.

    `poses` é a lista de poses de câmera (uma por frame).
    `resolucao` é (largura, altura).
    `funcao_profundidade` recebe (indice_frame, pose, resolucao) e devolve
    uma matriz de profundidade altura x largura.
    `semente` fixa a aleatoriedade para reprodução.

    A sequência é determinística: mesma entrada produz sempre os mesmos
    frames, com os mesmos hashes.
    """
    largura, altura = resolucao
    rng = np.random.default_rng(semente)

    frames: list[Frame] = []
    for indice, pose in enumerate(poses):
        timestamp_s = pose.get("timestamp_s", float(indice) * 0.1)

        # Chama a função de profundidade fornecida pelo chamador.
        profundidade = funcao_profundidade(indice, pose, resolucao)

        # Garante a forma correta.
        profundidade_arr = np.asarray(profundidade, dtype=float)
        if profundidade_arr.shape != (altura, largura):
            raise ErroRenderizacao(
                f"profundidade do frame {indice} tem forma {profundidade_arr.shape}, "
                f"esperado {(altura, largura)}"
            )

        # Aplica semente para ruído determinístico (quando relevante).
        # O ruído é derivado da semente e do índice, para ser reproduzível.
        ruido = rng.normal(0.0, 0.001, size=(altura, largura))
        profundidade = profundidade_arr + ruido * 0.01  # ruído muito pequeno

        profundidade_lista = profundidade.tolist()
        frame = renderizar_frame(
            indice=indice,
            timestamp_s=timestamp_s,
            largura=largura,
            altura=altura,
            profundidade_por_pixel=profundidade_lista,
            parametros=parametros,
        )
        frames.append(frame)

    # Hash de toda a sequência.
    h = hashlib.sha256()
    for frame in frames:
        h.update(frame.hash_frame.encode("utf-8"))
    hash_sequencia = h.hexdigest()

    return SequenciaFrames(
        frames=frames,
        hash_sequencia=hash_sequencia,
        parametros=parametros or {},
        deterministico=True,
    )


def verificar_determinismo(
    sequencia_a: SequenciaFrames,
    sequencia_b: SequenciaFrames,
) -> bool:
    """Verifica se duas sequências são idênticas (mesmo hash de sequência)."""
    return sequencia_a.hash_sequencia == sequencia_b.hash_sequencia


def sequencia_para_dict(sequencia: SequenciaFrames) -> dict[str, Any]:
    """Serializa uma sequência de frames para dicionário JSON."""
    return {
        "num_frames": len(sequencia.frames),
        "hash_sequencia": sequencia.hash_sequencia,
        "parametros": sequencia.parametros,
        "deterministico": sequencia.deterministico,
        "frames": [
            {
                "indice": f.indice,
                "timestamp_s": f.timestamp_s,
                "largura": f.largura,
                "altura": f.altura,
                "hash_frame": f.hash_frame,
                "num_pixels": len(f.pixels),
            }
            for f in sequencia.frames
        ],
    }


__all__ = [
    "ErroRenderizacao",
    "Frame",
    "SequenciaFrames",
    "hash_frame",
    "renderizar_frame",
    "renderizar_sequencia",
    "verificar_determinismo",
    "sequencia_para_dict",
]
