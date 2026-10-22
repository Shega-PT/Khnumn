"""Rasterizador de software como instrumento de validacao (F9.E2).

Implementa em Python o mesmo algoritmo do rasterizador Rust
(`crates/khnumn-core/src/rasterizador.rs`), expondo-o atraves do contrato
`khnumn-tarefa-v1` para que o nucleo Rust possa despachar tarefas de
rasterizacao.

Produz campos quantificados, nunca imagens. A classe "sem dados" e
representada por NaN e nunca apresentada como um valor. A projecao coincide
com a do motor de SfM para todos os modelos de camara que o motor usa.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import numpy as np


class ErroRasterizador(Exception):
    """Falha na rasterizacao, com causa legivel."""


#: Valor sentinela para a classe "sem dados".
SEM_DADOS = float("nan")


@dataclass
class ParametrosCamara:
    """Parametros intrinsecos de uma camara."""

    modelo: str
    """Modelo: `SIMPLE_PINHOLE`, `PINHOLE`, `SIMPLE_RADIAL` ou `RADIAL`."""

    largura: int
    altura: int
    params: list[float]


@dataclass
class PoseCamara:
    """Pose de uma camara (R | t)."""

    rotacao: list[list[float]]  # 3x3
    translacao: list[float]  # 3


@dataclass
class Ponto3D:
    """Ponto 3D no referencial do mundo."""

    x: float
    y: float
    z: float


@dataclass
class Observacao:
    """Observacao de um ponto numa imagem."""

    ponto_id: int
    u: float
    v: float


@dataclass
class Raster:
    """Raster de saida: grelha 2D de valores float64."""

    largura: int
    altura: int
    valores: list[float]  # ordem linha-major, NaN = sem dados
    transformacao: list[float]  # [origem_x, res_x, rot_x, origem_y, rot_y, res_y]
    crs: str | None = None
    nodata: float | None = None


def _extrair_intrinsecos(
    camara: ParametrosCamara,
) -> tuple[float, float, float, float, tuple[float, float] | None]:
    """Extrai parametros intrinsecos e distorcao dos parametros da camara."""
    p = camara.params
    modelo = camara.modelo.upper()

    if modelo == "SIMPLE_PINHOLE":
        if len(p) < 3:
            raise ErroRasterizador(
                "SIMPLE_PINHOLE requer pelo menos 3 parametros (fx, cx, cy)"
            )
        return (p[0], p[0], p[1], p[2], None)

    if modelo == "PINHOLE":
        if len(p) < 4:
            raise ErroRasterizador(
                "PINHOLE requer pelo menos 4 parametros (fx, fy, cx, cy)"
            )
        return (p[0], p[1], p[2], p[3], None)

    if modelo == "SIMPLE_RADIAL":
        if len(p) < 4:
            raise ErroRasterizador(
                "SIMPLE_RADIAL requer pelo menos 4 parametros (f, cx, cy, k1)"
            )
        return (p[0], p[0], p[1], p[2], (p[3], 0.0))

    if modelo == "RADIAL":
        if len(p) < 5:
            raise ErroRasterizador(
                "RADIAL requer pelo menos 5 parametros (fx, fy, cx, cy, k1)"
            )
        k2 = p[5] if len(p) > 5 else 0.0
        return (p[0], p[1], p[2], p[3], (p[4], k2))

    raise ErroRasterizador(f"modelo de camara nao suportado: {camara.modelo}")


def projetar_ponto(
    ponto: Ponto3D,
    pose: PoseCamara,
    camara: ParametrosCamara,
) -> tuple[float, float]:
    """Projecta um ponto 3D para o plano da imagem (modelo pinhole).

    A projecao e a mesma funcao que o motor de SfM usa
    (docs/Khnumn.md §10.1), e tem de coincidir com ela para que o
    rasterizador produza campos quantificados consistentes com a
    geometria de entrada.
    """
    # Transforma o ponto para coordenadas da camara: Xc = R * Xw + t.
    r = pose.rotacao
    t = pose.translacao
    xc = (
        r[0][0] * ponto.x
        + r[0][1] * ponto.y
        + r[0][2] * ponto.z
        + t[0]
    )
    yc = (
        r[1][0] * ponto.x
        + r[1][1] * ponto.y
        + r[1][2] * ponto.z
        + t[1]
    )
    zc = (
        r[2][0] * ponto.x
        + r[2][1] * ponto.y
        + r[2][2] * ponto.z
        + t[2]
    )

    # Ponto atras da camara: nao projecta.
    if zc <= 0.0:
        raise ErroRasterizador("ponto atras da camara: profundidade nao positiva")

    # Coordenadas normalizadas.
    x = xc / zc
    y = yc / zc

    fx, fy, cx, cy, distorcao = _extrair_intrinsecos(camara)

    # Aplica distorcao radial (k1, k2) quando fornecida.
    if distorcao is not None:
        k1, k2 = distorcao
        r2 = x * x + y * y
        fator = 1.0 + k1 * r2 + k2 * r2 * r2
        x *= fator
        y *= fator

    # Coordenadas de pixel.
    u = fx * x + cx
    v = fy * y + cy
    return (u, v)


def rasterizar_pontos_observados(
    pontos: list[Ponto3D],
    observacoes: list[Observacao],
    camara: ParametrosCamara,
    pose: PoseCamara,
    largura: int,
    altura: int,
    valor_por_ponto: list[float],
    agregacao: str = "media",
) -> Raster:
    """Rasteriza pontos 3D observados por uma camara sobre uma grelha 2D.

    Para cada observacao, projecta o ponto 3D para o plano da imagem e
    atribui o valor associado ao pixel correspondente. Quando varios pontos
    caem no mesmo pixel, a agregacao e definida por `agregacao`
    (`media`, `max` ou `min`). Pixels sem qualquer observacao recebem a
    classe "sem dados" (NaN).
    """
    if len(pontos) != len(valor_por_ponto):
        raise ErroRasterizador(
            "pontos e valor_por_ponto devem ter o mesmo comprimento"
        )

    valores = np.full((altura, largura), SEM_DADOS, dtype=np.float64)
    acumuladores: dict[tuple[int, int], list[float]] = {}

    for obs in observacoes:
        if obs.ponto_id >= len(pontos):
            continue
        ponto = pontos[obs.ponto_id]
        try:
            u, v = projetar_ponto(ponto, pose, camara)
        except ErroRasterizador:
            continue

        ui = int(round(u))
        vi = int(round(v))

        # Descarta pixels fora da grelha.
        if ui < 0 or vi < 0 or ui >= largura or vi >= altura:
            continue

        chave = (vi, ui)
        acumuladores.setdefault(chave, []).append(valor_por_ponto[obs.ponto_id])

    for (yi, xi), vals in acumuladores.items():
        arr = np.asarray(vals, dtype=float)
        if agregacao == "media":
            valores[yi, xi] = float(np.mean(arr))
        elif agregacao == "max":
            valores[yi, xi] = float(np.max(arr))
        elif agregacao == "min":
            valores[yi, xi] = float(np.min(arr))
        else:
            raise ErroRasterizador(f"agregacao desconhecida: {agregacao}")

    return Raster(
        largura=largura,
        altura=altura,
        valores=valores.flatten().tolist(),
        transformacao=[0.0, 1.0, 0.0, 0.0, 0.0, -1.0],
        crs=None,
        nodata=None,
    )


def filtro_plano_near(
    pontos: list[Ponto3D],
    pose: PoseCamara,
    limiar_profundidade: float,
) -> list[Ponto3D]:
    """Remove pontos cuja profundidade e menor que o limiar do plano near."""
    resultado: list[Ponto3D] = []
    r = pose.rotacao
    t = pose.translacao
    for ponto in pontos:
        zc = r[2][0] * ponto.x + r[2][1] * ponto.y + r[2][2] * ponto.z + t[2]
        if zc > limiar_profundidade:
            resultado.append(ponto)
    return resultado


def hash_raster(raster: Raster) -> str:
    """Calcula o hash de um raster para verificacao de determinismo."""
    h = hashlib.sha256()
    h.update(str(raster.largura).encode("utf-8"))
    h.update(str(raster.altura).encode("utf-8"))
    for v in raster.valores:
        h.update(repr(v).encode("utf-8"))
    return h.hexdigest()


def raster_para_dict(raster: Raster) -> dict[str, Any]:
    """Serializa um raster para dicionario JSON."""
    return {
        "largura": raster.largura,
        "altura": raster.altura,
        "valores": raster.valores,
        "transformacao": raster.transformacao,
        "crs": raster.crs,
        "nodata": raster.nodata,
    }


def dict_para_raster(dados: dict[str, Any]) -> Raster:
    """Constrói um Raster a partir de um dicionario JSON."""
    return Raster(
        largura=int(dados["largura"]),
        altura=int(dados["altura"]),
        valores=[float(v) for v in dados["valores"]],
        transformacao=[float(v) for v in dados["transformacao"]],
        crs=dados.get("crs"),
        nodata=dados.get("nodata"),
    )


__all__ = [
    "ErroRasterizador",
    "SEM_DADOS",
    "ParametrosCamara",
    "PoseCamara",
    "Ponto3D",
    "Observacao",
    "Raster",
    "projetar_ponto",
    "rasterizar_pontos_observados",
    "filtro_plano_near",
    "hash_raster",
    "raster_para_dict",
    "dict_para_raster",
]
