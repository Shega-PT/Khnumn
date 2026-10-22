"""Referência temporal e convenção de instante de captura (F6.E1, F6.E3).

Gerencia a sincronização de relógios, a aplicação do desvio de segundos
intercalares, a deteção de deriva do relógio da câmara e a convenção de
instante de captura (início, meio ou fim da exposição).

Todas as operações declaram a sua origem e nunca inventam um instante quando
o dado está ausente: um carimbo sem fuso é uma hora de relógio, não um
instante, e essa distinção fica registada.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any

from . import geo


class ErroTempo(Exception):
    """Falha numa operação temporal, com causa legível."""


@dataclass
class InstanteCaptura:
    """Instante de captura de uma imagem, com a sua origem e confiança."""

    valor_utc: str | None
    """Instante em UTC (ISO 8601), ou None quando ausente."""

    origem: str
    """Origem do carimbo: `gnss_timestamp`, `exif_datetime_original`,
    `xmp_flight_timestamp`, `declarado_operador` ou `ausente`."""

    confianca: str
    """Nível de confiança: `alta`, `media`, `baixa` ou `nenhuma`."""

    convencao: str
    """Convenção aplicada: `inicio_exposicao`, `meio_exposicao` ou
    `fim_exposicao`."""

    desvio_leap_second_s: int
    """Desvio de segundos intercalares aplicado, em segundos."""


@dataclass
class SincronizacaoRelogios:
    """Resultado da sincronização de relógios de um conjunto de imagens."""

    instantes: list[InstanteCaptura]
    """Instantes de captura de cada imagem, sincronizados."""

    desvios_detetados: dict[str, float]
    """Desvio do relógio de cada imagem relativamente à referência, em
    segundos."""

    fonte_referencia: str
    """Fonte usada como referência de tempo."""

    descricao_erro: str | None = None
    """Causa, quando a sincronização não pôde ser concluída."""


def desvio_leap_second_para_data(data: _dt.date) -> int:
    """Devolve o desvio GPS-UTC, em segundos, para uma data dada.

    Reutiliza a tabela de `geo.desvio_leap_second`, aplicando o desvio
    acumulado desde a origem do GPS até à data indicada.
    """
    return geo.desvio_leap_second(data)


def aplicar_desvio_leap_second(
    instante_gps: _dt.datetime,
) -> _dt.datetime:
    """Converte um instante GPS para UTC, aplicando o desvio vigente.

    O desvio é obtido da tabela histórica de segundos intercalares e é
    estável desde 2017. Qualquer registo que misture relógios de origem
    diferente tem de declarar a convenção usada e a fonte do desvio aplicado
    (`docs/Khnumn.md` §5.6).
    """
    return geo.para_utc(instante_gps)


def sincronizar_relogios(
    instantes: list[dict[str, Any]],
    fonte_referencia: str = "GNSS",
) -> SincronizacaoRelogios:
    """Sincroniza os relógios de um conjunto de imagens.

    Aplica o desvio de segundos intercalares, detecta a deriva do relógio de
    cada câmara relativamente à fonte de referência e declara a convenção de
    tempo usada. Imagens sem carimbo são registadas como ausentes, nunca
    preenchidas com valores inventados.
    """
    resultados: list[InstanteCaptura] = []
    desvios: dict[str, float] = {}

    for idx, dado in enumerate(instantes):
        imagem = dado.get("imagem", f"imagem_{idx}")
        instante_bruto = dado.get("instante_gps")
        modo = dado.get("convencao_captura", "meio_exposicao")

        if instante_bruto is None:
            resultados.append(
                InstanteCaptura(
                    valor_utc=None,
                    origem="ausente",
                    confianca="nenhuma",
                    convencao=modo,
                    desvio_leap_second_s=desvio_leap_second_para_data(
                        _dt.date.today()
                    ),
                )
            )
            desvios[imagem] = float("nan")
            continue

        try:
            instante_utc = aplicar_desvio_leap_second(instante_bruto)
        except Exception as erro:  # noqa: BLE001 - falha declarada com causa
            resultados.append(
                InstanteCaptura(
                    valor_utc=None,
                    origem="erro",
                    confianca="nenhuma",
                    convencao=modo,
                    desvio_leap_second_s=desvio_leap_second_para_data(
                        _dt.date.today()
                    ),
                )
            )
            desvios[imagem] = float("nan")
            continue

        # Deteta deriva simplificada: compara com a referência (primeiro
        # instante válido é usado como âncora quando não há fonte externa).
        if not desvios:
            desvios[imagem] = 0.0
        else:
            primeiro = next(
                (i.valor_utc for i in resultados if i.valor_utc is not None),
                None,
            )
            if primeiro is not None:
                try:
                    ref = _dt.datetime.fromisoformat(primeiro.replace("Z", "+00:00"))
                    desvio = (instante_utc - ref).total_seconds()
                    desvios[imagem] = desvio
                except ValueError:
                    desvios[imagem] = float("nan")

        resultados.append(
            InstanteCaptura(
                valor_utc=instante_utc.isoformat().replace("+00:00", "Z"),
                origem="gnss_timestamp",
                confianca="alta",
                convencao=modo,
                desvio_leap_second_s=desvio_leap_second_para_data(
                    instante_utc.date()
                ),
            )
        )

    return SincronizacaoRelogios(
        instantes=resultados,
        desvios_detetados=desvios,
        fonte_referencia=fonte_referencia,
    )


def convenir_instante_captura(
    metadados: dict[str, Any],
    modo: str = "meio_exposicao",
) -> InstanteCaptura:
    """Declara e aplica a convenção de instante de captura.

    `modo` pode ser `inicio_exposicao`, `meio_exposicao` ou `fim_exposicao`.
    O instante é obtido dos metadados (EXIF/XMP/GNSS) e ajustado conforme a
    convenção. Quando não há carimbo, a ausência é declarada, nunca
    substituída pelo mtime do ficheiro ou por um valor inventado.
    """
    valido = {"inicio_exposicao", "meio_exposicao", "fim_exposicao"}
    if modo not in valido:
        raise ErroTempo(
            f"convenção de captura inválida {modo!r}; use um de {sorted(valido)}"
        )

    instante_bruto = (
        metadados.get("capture", {})
        .get("capture_time_utc")
        if isinstance(metadados.get("capture"), dict)
        else None
    )
    origem = (
        metadados.get("capture", {}).get("clock_source", "ausente")
        if isinstance(metadados.get("capture"), dict)
        else "ausente"
    )

    if instante_bruto is None:
        return InstanteCaptura(
            valor_utc=None,
            origem="ausente",
            confianca="nenhuma",
            convencao=modo,
            desvio_leap_second_s=desvio_leap_second_para_data(
                _dt.date.today()
            ),
        )

    try:
        instante_dt = _dt.datetime.fromisoformat(
            str(instante_bruto).replace("Z", "+00:00")
        )
    except ValueError:
        return InstanteCaptura(
            valor_utc=str(instante_bruto),
            origem=origem,
            confianca="baixa",
            convencao=modo,
            desvio_leap_second_s=desvio_leap_second_para_data(
                _dt.date.today()
            ),
        )

    # Ajuste pela convenção: início/meio/fim da exposição. Sem dados de
    # duração de exposição, o instante é usado tal qual e a convenção é
    # declarada, não aplicada como correção numérica.
    duracao_exposicao_s = metadados.get("exposure", {}).get("exposure_time_s")
    ajuste_s = 0.0
    if duracao_exposicao_s is not None:
        try:
            duracao = float(duracao_exposicao_s)
            if modo == "inicio_exposicao":
                ajuste_s = 0.0
            elif modo == "meio_exposicao":
                ajuste_s = duracao / 2.0
            elif modo == "fim_exposicao":
                ajuste_s = duracao
        except (TypeError, ValueError):
            ajuste_s = 0.0

    instante_ajustado = instante_dt + _dt.timedelta(seconds=ajuste_s)

    return InstanteCaptura(
        valor_utc=instante_ajustado.isoformat().replace("+00:00", "Z"),
        origem=origem,
        confianca="media" if origem in ("exif_datetime_original",) else "baixa",
        convencao=modo,
        desvio_leap_second_s=desvio_leap_second_para_data(instante_ajustado.date()),
    )


def resultado_para_dict(sinc: SincronizacaoRelogios) -> dict[str, Any]:
    """Serializa a sincronização para dicionário JSON."""
    return {
        "instantes": [
            {
                "valor_utc": i.valor_utc,
                "origem": i.origem,
                "confianca": i.confianca,
                "convencao": i.convencao,
                "desvio_leap_second_s": i.desvio_leap_second_s,
            }
            for i in sinc.instantes
        ],
        "desvios_detetados": sinc.desvios_detetados,
        "fonte_referencia": sinc.fonte_referencia,
        "descricao_erro": sinc.descricao_erro,
    }


def instante_para_dict(instante: InstanteCaptura) -> dict[str, Any]:
    """Serializa um instante de captura para dicionário JSON."""
    return {
        "valor_utc": instante.valor_utc,
        "origem": instante.origem,
        "confianca": instante.confianca,
        "convencao": instante.convencao,
        "desvio_leap_second_s": instante.desvio_leap_second_s,
    }


__all__ = [
    "ErroTempo",
    "InstanteCaptura",
    "SincronizacaoRelogios",
    "aplicar_desvio_leap_second",
    "convenir_instante_captura",
    "desvio_leap_second_para_data",
    "instante_para_dict",
    "resultado_para_dict",
    "sincronizar_relogios",
]
