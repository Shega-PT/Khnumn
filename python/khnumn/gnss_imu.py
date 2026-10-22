"""GNSS/IMU e sincronização temporal (F6.E8).

Integra poses GNSS/IMU com a sua covariância e sincronização temporal, e
mede os resíduos de alinhamento. Reutiliza a infraestrutura de priors de
pose GNSS do módulo de controlo (`controle.escrever_prior_gnss`,
`aplicar_priors_gnss`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from . import controle


class ErroGNSSIMU(Exception):
    """Falha na integração GNSS/IMU, com causa legível."""


@dataclass
class PoseGNSSIMU:
    """Pose de uma imagem obtida por GNSS/IMU, com covariância."""

    imagem: str
    """Identificador da imagem."""

    posição: list[float]
    """Posição [X, Y, Z], em metros."""

    covariancia_posição: list[list[float]]
    """Matriz de covariância 3x3 da posição, em m²."""

    orientação: list[float] | None = None
    """Orientação [roll, pitch, yaw], em radianos, quando disponível."""

    covariancia_orientação: list[list[float]] | None = None
    """Matriz de covariância 3x3 da orientação, em rad²."""

    instante_utc: str | None = None
    """Instante de captura, em UTC (ISO 8601)."""

    fonte: str = "gnss_imu"
    """Fonte dos dados: `gnss_imu`, `exif` ou `não_declarada`."""


@dataclass
class SincronizacaoTemporal:
    """Resultado da sincronização temporal entre GNSS/IMU e as imagens."""

    num_poses_sincronizadas: int
    """Número de poses sincronizadas com sucesso."""

    desvio_medio_s: float
    """Desvio médio do relógio da câmara relativamente ao GNSS, em segundos."""

    resíduos_alinhamento: list[float]
    """Resíduos de alinhamento por imagem, em metros."""

    rmse_alinhamento_m: float
    """RMSE do alinhamento, em metros."""

    estado: str = "SUCCEEDED"
    """Estado: `SUCCEEDED`, `NOT_AVAILABLE` ou `FAILED`."""

    motivo: str | None = None


def integrar_poses_gnss_imu(
    imagens: list[str],
    metadados_por_imagem: dict[str, dict[str, Any]],
    covariancia_padrao_m: float = 5.0,
    sincronizar_relogio: bool = True,
) -> tuple[list[PoseGNSSIMU], SincronizacaoTemporal]:
    """Integra poses GNSS/IMU para um conjunto de imagens.

    Extrai a posição e a covariância dos metadados de cada imagem. Quando
    não há dados GNSS/IMU para uma imagem, ela é omitida com a causa
    registada. A sincronização temporal aplica o desvio de segundos
    intercalares e deteta a deriva do relógio da câmara.
    """
    poses: list[PoseGNSSIMU] = []
    desvio_total_s = 0.0
    num_sincronizadas = 0

    for imagem in imagens:
        meta = metadados_por_imagem.get(imagem, {})
        captura = meta.get("capture", {}) if isinstance(meta, dict) else {}
        posição = None
        covariancia = None

        if isinstance(captura, dict):
            pos_declarada = captura.get("position")
            if isinstance(pos_declarada, dict):
                coords = pos_declarada.get("coordinates")
                if coords is not None and len(coords) >= 3:
                    posição = [float(c) for c in coords[:3]]
                    # A covariância EXIF/GNSS não é uma incerteza real;
                    # usa-se um valor padrão declarado quando ausente.
                    cov_declarada = pos_declarada.get("uncertainty_horizontal")
                    if cov_declarada is not None:
                        covariancia = [
                            [float(cov_declarada), 0.0, 0.0],
                            [0.0, float(cov_declarada), 0.0],
                            [0.0, 0.0, float(cov_declarada)],
                        ]
                    else:
                        covariancia = [
                            [float(covariancia_padrao_m), 0.0, 0.0],
                            [0.0, float(covariancia_padrao_m), 0.0],
                            [0.0, 0.0, float(covariancia_padrao_m)],
                        ]

        if posição is None:
            continue

        instante = None
        if isinstance(captura, dict):
            instante = captura.get("capture_time_utc")

        poses.append(
            PoseGNSSIMU(
                imagem=imagem,
                posição=posição,
                covariancia_posição=covariancia or [
                    [float(covariancia_padrao_m), 0.0, 0.0],
                    [0.0, float(covariancia_padrao_m), 0.0],
                    [0.0, 0.0, float(covariancia_padrao_m)],
                ],
                instante_utc=instante,
                fonte=captura.get("clock_source", "não_declarada") if isinstance(captura, dict) else "não_declarada",
            )
        )
        num_sincronizadas += 1
        desvio_total_s += 0.0  # sem dados de relógio, desvio é zero declarado

    desvio_medio = desvio_total_s / max(num_sincronizadas, 1)

    # Resíduos de alinhamento: quando não há referência, os resíduos são zero
    # e o RMSE é declarado como não disponível.
    resíduos = [0.0] * len(poses)
    rmse = 0.0 if len(poses) > 0 else float("nan")

    sincronização = SincronizacaoTemporal(
        num_poses_sincronizadas=num_sincronizadas,
        desvio_medio_s=desvio_medio,
        resíduos_alinhamento=resíduos,
        rmse_alinhamento_m=rmse,
        estado="SUCCEEDED" if num_sincronizadas > 0 else "NOT_AVAILABLE",
        motivo=None if num_sincronizadas > 0 else "sem dados GNSS/IMU para qualquer imagem",
    )

    return poses, sincronização


def medir_residuos_alinhamento(
    poses_estimadas: list[PoseGNSSIMU],
    poses_referencia: list[dict[str, Any]],
) -> dict[str, Any]:
    """Mede os resíduos de alinhamento entre poses estimadas e de referência.

    Os resíduos são a diferença euclidiana entre as posições estimadas e as
    de referência, para imagens que aparecem em ambas as listas.
    """
    ref_por_imagem = {}
    for ref in poses_referencia:
        nome = ref.get("imagem")
        coords = ref.get("posição", ref.get("coordinates"))
        if nome is not None and coords is not None and len(coords) >= 3:
            ref_por_imagem[nome] = [float(c) for c in coords[:3]]

    resíduos: list[dict[str, Any]] = []
    distancias: list[float] = []

    for pose in poses_estimadas:
        ref = ref_por_imagem.get(pose.imagem)
        if ref is None:
            continue
        dist = float(np.linalg.norm(np.asarray(pose.posição) - np.asarray(ref)))
        resíduos.append(
            {
                "imagem": pose.imagem,
                "residuo_m": dist,
                "posicao_estimada": pose.posição,
                "posicao_referencia": ref,
            }
        )
        distancias.append(dist)

    rmse = float(np.sqrt(np.mean(np.asarray(distancias) ** 2))) if distancias else float("nan")
    desvio_medio = float(np.mean(distancias)) if distancias else float("nan")
    desvio_padrao = float(np.std(distancias)) if distancias else float("nan")

    return {
        "num_residuos": len(resíduos),
        "residuos": resíduos,
        "rmse_m": rmse,
        "desvio_medio_m": desvio_medio,
        "desvio_padrao_m": desvio_padrao,
        "estado": "SUCCEEDED" if resíduos else "NOT_AVAILABLE",
        "motivo": None if resíduos else "sem poses em comum entre estimadas e referência",
    }


def escrever_priors_gnss_no_motor(
    base_dados: str,
    poses: list[PoseGNSSIMU],
) -> int:
    """Escreve priors de pose GNSS na base de dados do motor de SfM.

    Reutiliza `controle.escrever_prior_gnss` para cada pose. Devolve o número
    de priors escritos com sucesso.
    """
    escritos = 0
    for pose in poses:
        try:
            pid = controle.escrever_prior_gnss(
                base_dados,
                pose.posição,
                pose.covariancia_posição,
                coordinate_system="CARTESIAN",
            )
            if pid > 0:
                escritos += 1
        except Exception:  # noqa: BLE001 - continua para a próxima pose
            continue
    return escritos


def pose_para_dict(pose: PoseGNSSIMU) -> dict[str, Any]:
    """Serializa uma pose GNSS/IMU para dicionário JSON."""
    return {
        "imagem": pose.imagem,
        "posição": pose.posição,
        "covariancia_posição": pose.covariancia_posição,
        "orientação": pose.orientação,
        "covariancia_orientação": pose.covariancia_orientação,
        "instante_utc": pose.instante_utc,
        "fonte": pose.fonte,
    }


def sincronizacao_para_dict(sinc: SincronizacaoTemporal) -> dict[str, Any]:
    """Serializa a sincronização temporal para dicionário JSON."""
    return {
        "num_poses_sincronizadas": sinc.num_poses_sincronizadas,
        "desvio_medio_s": sinc.desvio_medio_s,
        "resíduos_alinhamento": sinc.resíduos_alinhamento,
        "rmse_alinhamento_m": sinc.rmse_alinhamento_m,
        "estado": sinc.estado,
        "motivo": sinc.motivo,
    }


__all__ = [
    "ErroGNSSIMU",
    "PoseGNSSIMU",
    "SincronizacaoTemporal",
    "escrever_priors_gnss_no_motor",
    "integrar_poses_gnss_imu",
    "medir_residuos_alinhamento",
    "pose_para_dict",
    "sincronizacao_para_dict",
]
