"""Campo de resíduos de reprojeção por câmara (F3.E13).

Produz um raster de resíduos por câmara, com a classe "sem observação"
explícita (NaN). Métricas média, p95 e máximo por câmara. O resíduo apurado
é a mesma grandeza que o motor de SfM reporta, em píxeis.

Depende de F9.E2 (rasterizador de software) para a projeção da geometria
medida sobre a grelha 2D sob o modelo de câmara explícito.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from . import rasterizador


class ErroResiduos(Exception):
    """Falha no cálculo de resíduos de reprojeção, com causa legível."""


@dataclass
class ResiduoCamera:
    """Resíduos de reprojeção de uma câmara."""

    camera_id: str
    """Identificador da câmara."""

    largura: int
    altura: int
    valores: list[float]  # ordem linha-major, NaN = sem observação
    media_px: float
    p95_px: float
    maximo_px: float
    num_observacoes: int
    num_sem_observacao_px: int


@dataclass
class CampoResiduos:
    """Campo de resíduos de reprojeção por câmara."""

    residuos_por_camera: dict[str, ResiduoCamera]
    """Resíduos de cada câmara, indexados pelo identificador da câmara."""

    versao_rasterizador: str = "1.0.0"
    """Versão do rasterizador usado."""


def calcular_residuos_reprojecao(
    pontos_3d: list[list[float]],
    observacoes_por_camera: dict[str, list[list[float]]],
    cameras_por_camera: dict[str, dict[str, Any]],
    poses_por_camera: dict[str, dict[str, Any]],
    largura: int,
    altura: int,
) -> CampoResiduos:
    """Calcula o campo de resíduos de reprojeção por câmara.

    Para cada câmara:
    1. Projeta cada ponto 3D observado nessa câmara usando o modelo de
       câmara e a pose (mesma função do motor de SfM).
    2. Calcula o resíduo = distância entre o ponto projetado e a
       observação medida, em píxeis.
    3. Rasteriza os resíduos sobre a grelha 2D da câmara.
    4. Calcula métricas: média, p95, máximo.

    Pixels sem qualquer observação recebem a classe "sem observação"
    (NaN) e nunca são apresentados como um valor.
    """
    residuos_por_camera: dict[str, ResiduoCamera] = {}

    for camera_id, observacoes in observacoes_por_camera.items():
        camara_dados = cameras_por_camera.get(camera_id, {})
        pose_dados = poses_por_camera.get(camera_id, {})

        camara = rasterizador.ParametrosCamara(
            modelo=camara_dados.get("modelo", "SIMPLE_PINHOLE"),
            largura=int(camara_dados.get("largura", largura)),
            altura=int(camara_dados.get("altura", altura)),
            params=[float(v) for v in camara_dados.get("params", [])],
        )
        pose = rasterizador.PoseCamara(
            rotacao=[[float(v) for v in linha]
                     for linha in pose_dados.get("rotacao",
                                                 [[1.0, 0.0, 0.0],
                                                  [0.0, 1.0, 0.0],
                                                  [0.0, 0.0, 1.0]])],
            translacao=[float(v) for v in
                        pose_dados.get("translacao", [0.0, 0.0, 5.0])],
        )

        # Constrói listas para o rasterizador: pontos, observações com
        # o resíduo como valor, e valores por ponto.
        pontos_rast: list[rasterizador.Ponto3D] = []
        obs_rast: list[rasterizador.Observacao] = []
        valores_rast: list[float] = []

        for idx, obs in enumerate(observacoes):
            # obs = [ponto_id, u_medido, v_medido]
            ponto_id = int(obs[0])
            u_medido = float(obs[1])
            v_medido = float(obs[2])

            if ponto_id >= len(pontos_3d):
                continue

            ponto_3d = pontos_3d[ponto_id]
            ponto_rast = rasterizador.Ponto3D(
                x=float(ponto_3d[0]),
                y=float(ponto_3d[1]),
                z=float(ponto_3d[2]),
            )

            try:
                u_proj, v_proj = rasterizador.projetar_ponto(
                    ponto_rast, pose, camara
                )
            except rasterizador.ErroRasterizador:
                # Ponto atrás da câmara ou fora da grelha: ignora.
                continue

            # Resíduo = distância euclidiana entre projetado e medido, em píxeis.
            residuo = math.hypot(u_proj - u_medido, v_proj - v_medido)

            pontos_rast.append(ponto_rast)
            obs_rast.append(
                rasterizador.Observacao(
                    ponto_id=len(pontos_rast) - 1,
                    u=u_proj,
                    v=v_proj,
                )
            )
            valores_rast.append(residuo)

        # Rasteriza os resíduos.
        if pontos_rast:
            raster = rasterizador.rasterizar_pontos_observados(
                pontos_rast,
                obs_rast,
                camara,
                pose,
                largura,
                altura,
                valores_rast,
                agregacao="media",
            )
        else:
            raster = rasterizador.Raster(
                largura=largura,
                altura=altura,
                valores=[float("nan")] * (largura * altura),
                transformacao=[0.0, 1.0, 0.0, 0.0, 0.0, -1.0],
                crs=None,
                nodata=None,
            )

        # Calcula métricas ignorando a classe "sem observação" (NaN).
        valores_arr = np.asarray(raster.valores, dtype=float)
        validos = valores_arr[np.isfinite(valores_arr)]

        if validos.size > 0:
            media_px = float(np.mean(validos))
            p95_px = float(np.percentile(validos, 95))
            maximo_px = float(np.max(validos))
            num_observacoes = int(validos.size)
        else:
            media_px = float("nan")
            p95_px = float("nan")
            maximo_px = float("nan")
            num_observacoes = 0

        num_sem_observacao = int(valores_arr.size - validos.size)

        residuos_por_camera[camera_id] = ResiduoCamera(
            camera_id=camera_id,
            largura=largura,
            altura=altura,
            valores=raster.valores,
            media_px=media_px,
            p95_px=p95_px,
            maximo_px=maximo_px,
            num_observacoes=num_observacoes,
            num_sem_observacao_px=num_sem_observacao,
        )

    return CampoResiduos(
        residuos_por_camera=residuos_por_camera,
        versao_rasterizador="1.0.0",
    )


def campo_residuos_para_dict(
    campo: CampoResiduos,
) -> dict[str, Any]:
    """Serializa o campo de resíduos para dicionário JSON."""
    return {
        "versao_rasterizador": campo.versao_rasterizador,
        "residuos_por_camera": {
            camera_id: {
                "camera_id": rc.camera_id,
                "largura": rc.largura,
                "altura": rc.altura,
                "valores": rc.valores,
                "media_px": rc.media_px,
                "p95_px": rc.p95_px,
                "maximo_px": rc.maximo_px,
                "num_observacoes": rc.num_observacoes,
                "num_sem_observacao_px": rc.num_sem_observacao_px,
            }
            for camera_id, rc in campo.residuos_por_camera.items()
        },
    }


__all__ = [
    "ErroResiduos",
    "ResiduoCamera",
    "CampoResiduos",
    "calcular_residuos_reprojecao",
    "campo_residuos_para_dict",
]
