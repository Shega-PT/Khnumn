"""Representação de evidência por célula (F8.E1).

Cada elemento espacial declara: estimativa geométrica, covariância,
contagem e diversidade de observações, proveniência, época e indicadores
de consistência. Nunca fusão silenciosa: quando os dados são insuficientes,
o estado é explícito.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


class ErroEvidencia(Exception):
    """Falha na representação de evidência, com causa legível."""


@dataclass
class ElementoEvidencia:
    """Elemento de evidência para uma célula espacial."""

    celula_id: str
    """Identificador da célula espacial."""

    geometria: list[float]
    """Estimativa geométrica [x, y, z], em metros."""

    covariancia: list[list[float]]
    """Matriz de covariância 3x3 da estimativa, em m²."""

    contagem_observacoes: int
    """Número de observações que contribuem para esta célula."""

    diversidade_observacoes: float
    """Diversidade das observações (0.0 a 1.0): 1.0 = fontes independentes."""

    proveniencia: dict[str, Any]
    """Proveniência: origem, operações, versões."""

    epoca_utc: str
    """Época dos dados, em UTC (ISO 8601)."""

    consistencia: float
    """Indicador de consistência (0.0 a 1.0): quão concordantes são as
    observações entre si."""

    incerteza_total_m: float | None = None
    """Incerteza total da estimativa, em metros, quando disponível."""

    estado: str = "valido"
    """Estado: `valido`, `insuficiente` ou `invalido`."""


def calcular_diversidade_observacoes(
    fontes: list[str],
) -> float:
    """Calcula a diversidade de observações com base nas fontes.

    A diversidade é 1.0 quando todas as fontes são diferentes (independentes)
    e 0.0 quando todas são a mesma fonte.
    """
    if not fontes:
        return 0.0
    fontes_unicas = len(set(fontes))
    return fontes_unicas / len(fontes)


def calcular_consistencia(
    observacoes: list[list[float]],
    covariancias: list[list[list[float]]] | None = None,
) -> float:
    """Calcula o indicador de consistência entre observações.

    Quando não há covariâncias, usa o desvio padrão relativo como proxy.
    Retorna 1.0 quando todas as observações coincidem, 0.0 quando são
    muito divergentes.
    """
    if not observacoes:
        return 0.0
    if len(observacoes) == 1:
        return 1.0

    import numpy as np

    obs_array = np.asarray(observacoes, dtype=float)
    media = np.mean(obs_array, axis=0)
    desvios = np.linalg.norm(obs_array - media, axis=1)
    desvio_medio = float(np.mean(desvios))

    # Normaliza: consistência decai com o desvio médio.
    consistencia = math.exp(-desvio_medio / max(1.0, desvio_medio + 1.0))
    return float(max(0.0, min(1.0, consistencia)))


def incerteza_total_de_celula(
    covariancia: list[list[float]],
) -> float:
    """Calcula a incerteza total de uma célula a partir da covariância.

    É a raiz quadrada do traço da matriz de covariância (desvio padrão
    combinado nas três dimensões), em metros.
    """
    import numpy as np

    cov = np.asarray(covariancia, dtype=float)
    traco = float(np.trace(cov))
    return math.sqrt(max(0.0, traco))


def agrupar_evidencia_por_celula(
    elementos: list[ElementoEvidencia],
    resolucao_m: float = 1.0,
) -> dict[str, ElementoEvidencia]:
    """Agrupa elementos de evidência por célula espacial.

    Elementos que caem na mesma célula (mesma coordenada inteira após
    divisão pela resolução) são fundidos: a geometria é a média ponderada
    pela inversa da covariância, e as covariâncias são combinadas.
    """
    celulas: dict[str, list[ElementoEvidencia]] = {}

    for elemento in elementos:
        x, y, z = elemento.geometria[:3]
        cx = int(math.floor(x / resolucao_m))
        cy = int(math.floor(y / resolucao_m))
        cz = int(math.floor(z / resolucao_m))
        chave = f"{cx}_{cy}_{cz}"
        celulas.setdefault(chave, []).append(elemento)

    resultado: dict[str, ElementoEvidencia] = {}
    for chave, lista in celulas.items():
        if len(lista) == 1:
            resultado[chave] = lista[0]
            continue

        # Fusão: média ponderada pela inversa da covariância.
        import numpy as np

        geometricas = []
        pesos = []
        covariancias = []
        proveniencias = []
        epocas = []

        for elem in lista:
            geom = np.asarray(elem.geometria[:3], dtype=float)
            cov = np.asarray(elem.covariancia, dtype=float)
            # Peso = inverso do traço da covariância (maior certeza = mais peso).
            peso = 1.0 / max(float(np.trace(cov)), 1e-12)
            geometricas.append(geom)
            pesos.append(peso)
            covariancias.append(cov)
            proveniencias.append(elem.proveniencia)
            epocas.append(elem.epoca_utc)

        soma_pesos = sum(pesos)
        geometria_fundida = sum(
            g * p for g, p in zip(geometricas, pesos)
        ) / soma_pesos

        # Covariância combinada: inversa da soma das informações.
        info_total = sum(
            np.linalg.inv(c) for c in covariancias
        )
        try:
            covariancia_fundida = np.linalg.inv(info_total).tolist()
        except np.linalg.LinAlgError:
            covariancia_fundida = covariancias[0].tolist()

        # Diversidade: média das diversidades individuais.
        diversidade = float(np.mean([
            e.diversidade_observacoes for e in lista
        ]))

        # Consistência: média das consistências individuais.
        consistencia = float(np.mean([
            e.consistencia for e in lista
        ]))

        resultado[chave] = ElementoEvidencia(
            celula_id=chave,
            geometria=[float(v) for v in geometria_fundida],
            covariancia=covariancia_fundida,
            contagem_observacoes=sum(
                e.contagem_observacoes for e in lista
            ),
            diversidade_observacoes=diversidade,
            proveniencia={
                "fontes": proveniencias,
                "operacao": "fusao_por_celula",
                "resolucao_m": resolucao_m,
            },
            epoca_utc=epocas[0] if epocas else "",
            consistencia=consistencia,
            incerteza_total_m=incerteza_total_de_celula(covariancia_fundida),
            estado="valido" if consistencia > 0.5 else "insuficiente",
        )

    return resultado


def elemento_para_dict(elemento: ElementoEvidencia) -> dict[str, Any]:
    """Serializa um elemento de evidência para dicionário JSON."""
    return {
        "celula_id": elemento.celula_id,
        "geometria": elemento.geometria,
        "covariancia": elemento.covariancia,
        "contagem_observacoes": elemento.contagem_observacoes,
        "diversidade_observacoes": elemento.diversidade_observacoes,
        "proveniencia": elemento.proveniencia,
        "epoca_utc": elemento.epoca_utc,
        "consistencia": elemento.consistencia,
        "incerteza_total_m": elemento.incerteza_total_m,
        "estado": elemento.estado,
    }


__all__ = [
    "ElementoEvidencia",
    "ErroEvidencia",
    "agrupar_evidencia_por_celula",
    "calcular_consistencia",
    "calcular_diversidade_observacoes",
    "elemento_para_dict",
    "incerteza_total_de_celula",
]
