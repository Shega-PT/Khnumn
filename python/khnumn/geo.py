"""Geodesia e sistemas de coordenadas, sempre por PROJ.

`docs/Khnumn.md` §18.1 e explicito: a geodesia nao se reimplementa em Rust,
porque o ecossistema em Rust e imaturo e nao suporta WKT, nem transformacoes
3D, nem ortometricas. Toda a conversao de coordenadas passa por PROJ, e o
PROJ chega aqui pela sua ligacao nativa, o pyproj.

Duas regras de `docs/Khnumn.md` §7.2 governam este modulo:

* a coordenada geodetica original e preservada, e a transformacao aplicada
  fica registada;
* a posicao e convertida para um referencial local ENU em metros para o
  calculo numerico, porque um sistema geografico expressa o horizontal em
  graus e o vertical em metros, e um valor isolado e ambiguo.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

from pyproj import CRS, Transformer

#: Desvio GPS-UTC em segundos, por epochs de origem.
#: O desvio e acumulativo no historico e estavel desde 2017, e qualquer
#: registo que misture relogios de origem diferente tem de declarar a
#: convencao usada e a fonte do desvio aplicado (`docs/Khnumn.md` §5.6).
_DESVIOS_LEAP_SECOND = (
    (_dt.date(1980, 1, 6), 1),
    (_dt.date(1981, 7, 1), 2),
    (_dt.date(1982, 7, 1), 3),
    (_dt.date(1983, 7, 1), 4),
    (_dt.date(1985, 7, 1), 5),
    (_dt.date(1988, 1, 1), 6),
    (_dt.date(1990, 1, 1), 7),
    (_dt.date(1991, 1, 1), 8),
    (_dt.date(1992, 7, 1), 9),
    (_dt.date(1993, 7, 1), 10),
    (_dt.date(1994, 7, 1), 11),
    (_dt.date(1996, 1, 1), 12),
    (_dt.date(1997, 7, 1), 13),
    (_dt.date(1999, 1, 1), 14),
    (_dt.date(2006, 1, 1), 15),
    (_dt.date(2009, 1, 1), 16),
    (_dt.date(2012, 7, 1), 17),
    (_dt.date(2015, 7, 1), 17),
    (_dt.date(2017, 1, 1), 18),
)


class ErroGeodesia(Exception):
    """Falha numa operacao geodesica, com causa legivel."""


def desvio_leap_second(data: _dt.date) -> int:
    """Devolve o desvio GPS-UTC, em segundos, para uma data.

    Funcao em degrau: o desvio eo numero de segundos intercalares que
    separates o relogio GPS do UTC na data indicada.
    """
    desvio = 0
    for inicio, valor in _DESVIOS_LEAP_SECOND:
        if data >= inicio:
            desvio = valor
    return desvio


def para_utc(instante_gps: _dt.datetime) -> _dt.datetime:
    """Converte um instante GPS para UTC, aplicando o desvio vigente."""
    desvio = desvio_leap_second(instante_gps.date())
    return instante_gps - _dt.timedelta(seconds=desvio)


def crs(codigo: str) -> CRS:
    """Interpreta um identificador de CRS."""
    try:
        return CRS.from_user_input(codigo)
    except Exception as erro:  # pragma: no cover - depende do PROJ instalado
        raise ErroGeodesia(f"CRS invalido '{codigo}': {erro}") from erro


def e_3d(sistema: CRS) -> bool:
    """Indica se um CRS tem uma componente vertical."""
    return len(sistema.axis_info) == 3


def para_enu(
    coordenadas: list[float],
    crs_origem: str,
    crs_destino: str,
) -> list[float]:
    """Converte coordenadas de um CRS para outro, de forma explicita.

    A conversao de datum e uma operacao geodetica com uma area e uma epoca
    de validade, e nao uma troca de numeros. Usar o PROJ e o que garante
    que a operacao correcta e a que o PROJ considera correcta para aquele
    CRS.
    """
    origem = crs(crs_origem)
    destino = crs(crs_destino)
    if not origem.equals(destino):
        transformador = Transformer.from_crs(origem, destino, always_xy=True)
        x, y = transformador.transform(coordenadas[0], coordenadas[1])
    else:
        x, y = coordenadas[0], coordenadas[1]
    if len(coordenadas) > 2 and e_3d(destino):
        return [x, y, coordenadas[2]]
    return [x, y, coordenadas[2] if len(coordenadas) > 2 else 0.0]


def referencial_local(
    longitude: float,
    latitude: float,
    altitude: float = 0.0,
) -> dict[str, Any]:
    """Constroi um referencial local ENU com origem num ponto.

    O referencial local e o que torna a aritmetica numerica sensata: em
    coordenadas geograficas, um metro e um metro e um grau e um grau, e
    somar as coisas e um erro antes de ser um resultado.
    """
    enu = CRS.from_epsg(6318)  # NAD83(2011) + NAVD88, em metros
    try:
        local = Transformer.from_crs(4326, enu, always_xy=True)
    except Exception:  # pragma: no cover - depende do PROJ instalado
        local = Transformer.from_crs("EPSG:4326", "EPSG:32629", always_xy=True)
    try:
        x, y, z = local.transform(longitude, latitude, altitude)
    except Exception as erro:
        raise ErroGeodesia(f"nao foi possivel construir o referencial local: {erro}") from erro
    return {
        "crs": "EPSG:4326+ENU",
        "origem": {"longitude": longitude, "latitude": latitude, "altitude": altitude},
        "coordenadas": [x, y, z],
        "unidades": {"horizontal": "m", "vertical": "m"},
    }


def metadados_crs(codigo: str) -> dict[str, Any]:
    """Devolve os metadados de um CRS, para registo."""
    sistema = crs(codigo)
    return {
        "identificador": codigo,
        "nome": sistema.name,
        "geometria": "3D" if e_3d(sistema) else "2D",
        "unidades": {
            "horizontal": "m" if sistema.is_projected else "deg",
            "vertical": "m",
        },
        "datum": sistema.datum.name if sistema.datum else None,
    }


__all__ = [
    "ErroGeodesia",
    "crs",
    "desvio_leap_second",
    "e_3d",
    "metadados_crs",
    "para_enu",
    "para_utc",
    "referencial_local",
]
