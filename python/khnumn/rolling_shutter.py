"""Modelação de rolling shutter (F6.E4).

Implementa um modelo por tempo de linha para câmaras com obturador enrolado
(rolling shutter). A modelação só é executada quando existe um caso de uso
claro e um teste de referência; caso contrário, o risco é sinalizado e não se
produz uma corretção silenciosa da geometria.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ErroRollingShutter(Exception):
    """Falha na modelação de rolling shutter, com causa legível."""


@dataclass
class ParametrosRollingShutter:
    """Parâmetros do modelo de rolling shutter."""

    tempo_leitura_linha_s: float
    """Tempo de leitura de uma única linha do sensor, em segundos."""

    altura_sensor_px: int
    """Altura do sensor, em píxeis."""

    direcao_leitura: str = "topo_para_baixo"
    """Direção de leitura do sensor: `topo_para_baixo` ou `baixo_para_topo`."""

    versao_algoritmo: str = "1.0.0"
    """Versão do algoritmo de modelação."""


@dataclass
class CorretcaoRollingShutter:
    """Resultado da corretção de rolling shutter para um ponto da imagem."""

    linha: int
    """Linha do píxel na imagem."""

    instante_desvio_s: float
    """Desvio temporal da linha relativamente ao instante de referência, em
    segundos."""

    corrigido: bool
    """Verdadeiro quando a corretção foi aplicada."""

    motivo: str | None = None
    """Causa, quando a corretção não pôde ser aplicada."""


def modelo_tempo_linha(
    linha: int,
    tempo_exposicao_s: float,
    velocidade_leitura_s_por_linha: float,
    altura_sensor_px: int,
    direcao: str = "topo_para_baixo",
) -> CorretcaoRollingShutter:
    """Calcula o desvio temporal de uma linha devido ao rolling shutter.

    O obturador enrolado lê as linhas sequencialmente, de modo que cada linha
    é capturada num instante ligeiramente diferente. O desvio temporal é
    proporcional ao número de linhas lidas antes da linha em questão.

    Este modelo é apenas um primeiro passo: não corrigi automaticamente a
    geometria sem um caso de uso claro e um teste de referência que valide a
    precisão da corretção.
    """
    if linha < 0 or linha >= altura_sensor_px:
        return CorretcaoRollingShutter(
            linha=linha,
            instante_desvio_s=0.0,
            corrigido=False,
            motivo=(
                f"linha {linha} fora do intervalo [0, {altura_sensor_px})"
            ),
        )

    if direcao not in ("topo_para_baixo", "baixo_para_topo"):
        raise ErroRollingShutter(
            f"direção de leitura inválida {direcao!r}; use 'topo_para_baixo' "
            "ou 'baixo_para_topo'"
        )

    if direcao == "topo_para_baixo":
        indice_leitura = linha
    else:
        indice_leitura = altura_sensor_px - 1 - linha

    instante_desvio_s = indice_leitura * velocidade_leitura_s_por_linha

    return CorretcaoRollingShutter(
        linha=linha,
        instante_desvio_s=float(instante_desvio_s),
        corrigido=False,
        motivo=(
            "modelo calculado; corretção geométrica requer caso de uso e "
            "teste de referência"
        ),
    )


def necessita_corretcao_rolling_shutter(
    tempo_leitura_total_s: float,
    velocidade_plataforma_m_s: float,
    distancia_terreno_m: float,
    limiar_desvio_px: float = 0.5,
) -> bool:
    """Indica se a corretção de rolling shutter é necessária para uma cena.

    Estima se o desvio temporal entre a primeira e a última linha introduz
    um deslocamento geométrico significativo no terreno, com base na
    velocidade da plataforma e na distância ao terreno.

    Returns:
        True quando o desvio estimado excede o limiar e a corretção deve ser
        considerada; False caso contrário.
    """
    if tempo_leitura_total_s <= 0 or velocidade_plataforma_m_s <= 0:
        return False

    deslocamento_plataforma_m = (
        velocidade_plataforma_m_s * tempo_leitura_total_s
    )
    # Aproximação simples: desvio proporcional ao deslocamento da plataforma
    # sobre a distância ao terreno.
    desvio_relativo = deslocamento_plataforma_m / max(distancia_terreno_m, 1.0)
    return desvio_relativo > (limiar_desvio_px / 1000.0)


__all__ = [
    "ErroRollingShutter",
    "CorretcaoRollingShutter",
    "ParametrosRollingShutter",
    "modelo_tempo_linha",
    "necessita_corretcao_rolling_shutter",
]
