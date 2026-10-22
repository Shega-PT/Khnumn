"""Adaptador LiDAR e calibração entre sensores (F6.E5).

Ingere nuvens de pontos LiDAR com sistema de coordenadas, calibração entre
sensores, densidade, padrão de varrimento e incerteza registados. A
calibração entre sensores é feita de forma explícita, nunca assumida.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


class ErroLiDAR(Exception):
    """Falha na ingestão ou calibração LiDAR, com causa legível."""


@dataclass
class CalibracaoInterSensor:
    """Parâmetros de calibração entre o sensor LiDAR e outra fonte (câmara,
    GNSS/IMU, etc.)."""

    sensor_origem: str
    """Identificador do sensor de origem (ex.: `lidar`, `camera`, `gnss_imu`)."""

    sensor_destino: str
    """Identificador do sensor de destino."""

    translacao_m: list[float]
    """Translação [tx, ty, tz] entre os sensores, em metros."""

    rotacao_rad: list[float]
    """Rotação [rx, ry, rz] entre os sensores, em radianos."""

    escala: float = 1.0
    """Fator de escala entre os sensores."""

    incerteza_translacao_m: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    """Incerteza da translação, em metros."""

    incerteza_rotacao_rad: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    """Incerteza da rotação, em radianos."""

    metodo: str = "não declarada"
    """Método usado para a calibração."""

    data_calibracao_utc: str | None = None
    """Data da calibração, em UTC (ISO 8601)."""

    operador: str | None = None
    """Operador responsável pela calibração."""


@dataclass
class NuvemLiDAR:
    """Nuvem de pontos LiDAR com metadados completos."""

    pontos: np.ndarray
    """Pontos como matriz Nx3 (X, Y, Z), em metros."""

    crs: str
    """Sistema de coordenadas de referência."""

    densidade_pontos_por_m2: float | None = None
    """Densidade de pontos, em pontos por metro quadrado."""

    padrao_varrimento: str | None = None
    """Padrão de varrimento do sensor (ex.: `linhas`, `espiral`, `aleatorio`)."""

    incerteza_horizontal_m: float | None = None
    """Incerteza horizontal declarada, em metros."""

    incerteza_vertical_m: float | None = None
    """Incerteza vertical declarada, em metros."""

    epoca_captura_utc: str | None = None
    """Época da captura, em UTC (ISO 8601)."""

    proveniencia: dict[str, Any] = field(default_factory=dict)
    """Proveniência da nuvem: origem, operações, versões."""


def ingerir_nuvem_lidar(
    caminho: str | Path,
    crs: str,
    calibracao_inter_sensor: CalibracaoInterSensor | None = None,
    densidade_pontos_por_m2: float | None = None,
    padrao_varrimento: str | None = None,
    incerteza_horizontal_m: float | None = None,
    incerteza_vertical_m: float | None = None,
    epoca_captura_utc: str | None = None,
    proveniencia: dict[str, Any] | None = None,
) -> NuvemLiDAR:
    """Lê uma nuvem de pontos LiDAR de um ficheiro e valida os metadados.

    Suporta ficheiros JSON com a forma `{"pontos": [[x, y, z], ...]}`.
    Outros formatos (LAS, LAZ, PLY) são declarados como não suportados nesta
    versão, com uma mensagem de erro accionável.
    """
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroLiDAR(f"ficheiro inexistente: {caminho}")

    sufixo = caminho.suffix.lower()
    if sufixo == ".json":
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as erro:
            raise ErroLiDAR(
                f"não foi possível ler o ficheiro JSON {caminho}: {erro}"
            ) from erro

        pontos_brutos = dados.get("pontos", [])
        if not isinstance(pontos_brutos, list):
            raise ErroLiDAR("o campo 'pontos' tem de ser uma lista")
        pontos = np.asarray(pontos_brutos, dtype=float)
        if pontos.ndim != 2 or pontos.shape[1] != 3:
            raise ErroLiDAR("os pontos têm de ser uma matriz Nx3")
    elif sufixo in (".las", ".laz", ".ply"):
        raise ErroLiDAR(
            f"formato {sufixo} não suportado nesta versão; use JSON com "
            "matriz Nx3"
        )
    else:
        raise ErroLiDAR(f"extensão não reconhecida: {sufixo}")

    if pontos.shape[0] == 0:
        raise ErroLiDAR("a nuvem de pontos está vazia")

    # Calcula densidade aproximada quando não fornecida.
    if densidade_pontos_por_m2 is None and pontos.shape[0] > 1:
        range_x = float(np.max(pontos[:, 0]) - np.min(pontos[:, 0]))
        range_y = float(np.max(pontos[:, 1]) - np.min(pontos[:, 1]))
        area_m2 = range_x * range_y
        if area_m2 > 0:
            densidade_pontos_por_m2 = float(pontos.shape[0] / area_m2)

    return NuvemLiDAR(
        pontos=pontos,
        crs=crs,
        densidade_pontos_por_m2=densidade_pontos_por_m2,
        padrao_varrimento=padrao_varrimento,
        incerteza_horizontal_m=incerteza_horizontal_m,
        incerteza_vertical_m=incerteza_vertical_m,
        epoca_captura_utc=epoca_captura_utc,
        proveniencia=proveniencia or {},
    )


def aplicar_calibracao_inter_sensor(
    nuvem: NuvemLiDAR,
    calibracao: CalibracaoInterSensor,
) -> NuvemLiDAR:
    """Aplica a calibração entre sensores à nuvem de pontos.

    A transformação (translação, rotação, escala) é aplicada a todos os
    pontos. A incerteza da calibração é propagada para a incerteza da nuvem.
    """
    pontos = np.asarray(nuvem.pontos, dtype=float).copy()

    translacao = np.asarray(calibracao.translacao_m, dtype=float).reshape(3)
    rotacao = np.asarray(calibracao.rotacao_rad, dtype=float).reshape(3)
    escala = float(calibracao.escala)

    # Matriz de rotação (ângulos de Euler, ordem ZYX).
    rx, ry, rz = float(rotacao[0]), float(rotacao[1]), float(rotacao[2])
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)

    R = np.array([
        [cy * cz, -cy * sz, sy],
        [cx * sz + sx * sy * cz, cx * cz - sx * sy * sz, -sx * cy],
        [sx * sz - cx * sy * cz, sx * cz + cx * sy * sz, cx * cy],
    ], dtype=float)

    pontos = escala * (pontos @ R.T) + translacao

    # Propaga a incerteza da calibração.
    incerteza_h = nuvem.incerteza_horizontal_m
    incerteza_v = nuvem.incerteza_vertical_m
    if incerteza_h is not None and calibracao.incerteza_translacao_m:
        incerteza_h = math.sqrt(
            incerteza_h ** 2
            + max(calibracao.incerteza_translacao_m) ** 2
        )
    if incerteza_v is not None and calibracao.incerteza_translacao_m:
        incerteza_v = math.sqrt(
            incerteza_v ** 2
            + calibracao.incerteza_translacao_m[2] ** 2
        )

    proveniencia = dict(nuvem.proveniencia)
    proveniencia["calibracao_inter_sensor"] = {
        "sensor_origem": calibracao.sensor_origem,
        "sensor_destino": calibracao.sensor_destino,
        "metodo": calibracao.metodo,
        "data_calibracao_utc": calibracao.data_calibracao_utc,
        "operador": calibracao.operador,
    }

    return NuvemLiDAR(
        pontos=pontos,
        crs=nuvem.crs,
        densidade_pontos_por_m2=nuvem.densidade_pontos_por_m2,
        padrao_varrimento=nuvem.padrao_varrimento,
        incerteza_horizontal_m=incerteza_h,
        incerteza_vertical_m=incerteza_v,
        epoca_captura_utc=nuvem.epoca_captura_utc,
        proveniencia=proveniencia,
    )


def nuvem_para_dict(nuvem: NuvemLiDAR) -> dict[str, Any]:
    """Serializa a nuvem LiDAR para dicionário JSON."""
    return {
        "num_pontos": int(nuvem.pontos.shape[0]),
        "crs": nuvem.crs,
        "densidade_pontos_por_m2": nuvem.densidade_pontos_por_m2,
        "padrao_varrimento": nuvem.padrao_varrimento,
        "incerteza_horizontal_m": nuvem.incerteza_horizontal_m,
        "incerteza_vertical_m": nuvem.incerteza_vertical_m,
        "epoca_captura_utc": nuvem.epoca_captura_utc,
        "proveniencia": nuvem.proveniencia,
        "pontos": nuvem.pontos.tolist(),
    }


__all__ = [
    "ErroLiDAR",
    "CalibracaoInterSensor",
    "NuvemLiDAR",
    "aplicar_calibracao_inter_sensor",
    "ingerir_nuvem_lidar",
    "nuvem_para_dict",
]
