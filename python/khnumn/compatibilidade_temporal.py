"""Compatibilidade temporal (F8.E3).

Calcula janelas de compatibilidade entre fontes de diferentes épocas e
marca mudanças prováveis sem fusão silenciosa. Quando a diferença temporal
indica mudança real da cena, as fontes são mantidas separadas.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any


class ErroCompatibilidadeTemporal(Exception):
    """Falha na análise de compatibilidade temporal, com causa legível."""


@dataclass
class JanelaCompatibilidade:
    """Janela temporal de compatibilidade entre duas fontes."""

    epoca_a_utc: str
    epoca_b_utc: str
    diferenca_temporal_s: float
    """Diferença temporal entre as épocas, em segundos."""

    dentro_da_janela: bool
    """Verdadeiro quando as épocas estão dentro da janela de compatibilidade."""

    tolerancia_temporal_s: float
    """Tolerância temporal declarada, em segundos."""

    mudança_provavel: bool
    """Verdadeiro quando a diferença temporal sugere mudança real da cena."""

    motivo: str | None = None
    """Causa, quando as fontes não são compatíveis."""


@dataclass
class FonteTemporal:
    """Uma fonte de dados com a sua época."""

    identificador: str
    epoca_utc: str
    """Época da captura, em UTC (ISO 8601)."""

    tipo: str = "não_declarada"
    """Tipo da fonte: `imagem`, `lidar`, `satélite`, `gnss_imu`, etc."""


def calcular_janela_compatibilidade(
    epoca_a: str | _dt.datetime,
    epoca_b: str | _dt.datetime,
    tolerancia_temporal_s: float,
) -> JanelaCompatibilidade:
    """Calcula a janela de compatibilidade temporal entre duas épocas.

    Quando a diferença excede a tolerância, as fontes são marcadas como
    incompatíveis e a mudança é sinalizada como provável.
    """
    if isinstance(epoca_a, str):
        try:
            dt_a = _dt.datetime.fromisoformat(
                epoca_a.replace("Z", "+00:00")
            )
        except ValueError:
            dt_a = _dt.datetime.utcnow()
    else:
        dt_a = epoca_a

    if isinstance(epoca_b, str):
        try:
            dt_b = _dt.datetime.fromisoformat(
                epoca_b.replace("Z", "+00:00")
            )
        except ValueError:
            dt_b = _dt.datetime.utcnow()
    else:
        dt_b = epoca_b

    diferenca_s = abs((dt_a - dt_b).total_seconds())
    dentro = diferenca_s <= tolerancia_temporal_s
    mudança_provavel = diferenca_s > tolerancia_temporal_s

    motivo: str | None = None
    if not dentro:
        motivo = (
            f"diferença temporal {diferenca_s:.1f} s excede tolerância "
            f"{tolerancia_temporal_s:.1f} s; mudança de cena provável"
        )

    return JanelaCompatibilidade(
        epoca_a_utc=dt_a.isoformat(),
        epoca_b_utc=dt_b.isoformat(),
        diferenca_temporal_s=float(diferenca_s),
        dentro_da_janela=dentro,
        tolerancia_temporal_s=float(tolerancia_temporal_s),
        mudança_provavel=mudança_provavel,
        motivo=motivo,
    )


def marcar_mudancas_provaveis(
    fontes: list[FonteTemporal],
    tolerancia_temporal_s: float,
    epoca_referencia: str | _dt.datetime | None = None,
) -> dict[str, Any]:
    """Marca mudanças prováveis entre fontes de diferentes épocas.

    Compara cada fonte com a época de referência (ou com a primeira fonte)
    e sinaliza aquelas cuja diferença temporal excede a tolerância. As
    fontes marcadas não são fundidas silenciosamente.
    """
    if epoca_referencia is None:
        epoca_referencia = fontes[0].epoca_utc if fontes else None

    if epoca_referencia is None:
        return {
            "janelas": [],
            "mudancas_provaveis": [],
            "fontes_compatíveis": [],
            "motivo": "sem época de referência",
        }

    janelas: list[JanelaCompatibilidade] = []
    mudancas: list[str] = []
    compatíveis: list[str] = []

    for fonte in fontes:
        janela = calcular_janela_compatibilidade(
            fonte.epoca_utc,
            epoca_referencia,
            tolerancia_temporal_s,
        )
        janelas.append(janela)

        if janela.dentro_da_janela:
            compatíveis.append(fonte.identificador)
        else:
            mudancas.append(fonte.identificador)

    return {
        "janelas": [
            {
                "epoca_a": j.epoca_a_utc,
                "epoca_b": j.epoca_b_utc,
                "diferenca_temporal_s": j.diferenca_temporal_s,
                "dentro_da_janela": j.dentro_da_janela,
                "tolerancia_temporal_s": j.tolerancia_temporal_s,
                "mudança_provavel": j.mudança_provavel,
                "motivo": j.motivo,
            }
            for j in janelas
        ],
        "mudancas_provaveis": mudancas,
        "fontes_compatíveis": compatíveis,
        "motivo": None,
    }


def janela_para_dict(janela: JanelaCompatibilidade) -> dict[str, Any]:
    """Serializa uma janela de compatibilidade para dicionário JSON."""
    return {
        "epoca_a_utc": janela.epoca_a_utc,
        "epoca_b_utc": janela.epoca_b_utc,
        "diferenca_temporal_s": janela.diferenca_temporal_s,
        "dentro_da_janela": janela.dentro_da_janela,
        "tolerancia_temporal_s": janela.tolerancia_temporal_s,
        "mudança_provavel": janela.mudança_provavel,
        "motivo": janela.motivo,
    }


__all__ = [
    "ErroCompatibilidadeTemporal",
    "FonteTemporal",
    "JanelaCompatibilidade",
    "calcular_janela_compatibilidade",
    "janela_para_dict",
    "marcar_mudancas_provaveis",
]
