"""Benchmarks contra baselines (F8.E5).

Compara resultados de fusão com baselines estabelecidos em conjuntos
públicos e próprios, aplicando o critério de inovação própria. Nenhuma
melhoria é integrada como padrão sem mostrar benefício mensurável.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ErroBenchmark(Exception):
    """Falha no benchmark de fusão, com causa legível."""


@dataclass
class Baseline:
    """Um baseline estabelecido para comparação."""

    nome: str
    conjunto_dados: str
    metrica_primaria: str
    """Nome da métrica primária (ex.: `rmse_horizontal_m`, `densidade_pontos`)."""

    valor_referencia: float
    """Valor de referência do baseline."""

    unidade: str = "não_declarada"
    """Unidade da métrica."""

    fonte: str = "não_declarada"
    """Fonte do baseline (publicação, conjunto público, etc.)."""


@dataclass
class ResultadoBenchmark:
    """Resultado da comparação com um baseline."""

    baseline: str
    metrica: str
    valor_obtido: float
    valor_referencia: float
    diferenca_absoluta: float
    diferenca_percentual: float
    melhoria: bool
    """Verdadeiro quando o valor obtido é melhor que o referência."""

    critério_inovacao_propria: bool
    """Verdadeiro quando o critério de inovação própria está satisfeito."""

    estado: str = "SUCCEEDED"
    motivo: str | None = None


def comparar_com_baseline(
    valor_obtido: float,
    baseline: Baseline,
    direcao_melhoria: str = "menor_e_melhor",
) -> ResultadoBenchmark:
    """Compara um valor obtido com um baseline estabelecido.

    `direcao_melhoria` pode ser `menor_e_melhor` (ex.: RMSE, erro) ou
    `maior_e_melhor` (ex.: densidade, completude).
    """
    valor_ref = baseline.valor_referencia
    diferenca_absoluta = valor_obtido - valor_ref

    if valor_ref != 0:
        diferenca_percentual = (diferenca_absoluta / abs(valor_ref)) * 100.0
    else:
        diferenca_percentual = float("inf") if diferenca_absoluta != 0 else 0.0

    if direcao_melhoria == "menor_e_melhor":
        melhoria = valor_obtido < valor_ref
    elif direcao_melhoria == "maior_e_melhor":
        melhoria = valor_obtido > valor_ref
    else:
        raise ErroBenchmark(
            f"direção de melhoria inválida: {direcao_melhoria}"
        )

    # Critério de inovação própria: a melhoria deve ser estatisticamente
    # relevante, não apenas um pequeno ruído numérico.
    limiar_inovacao_percentual = 5.0
    criterio_inovacao = melhoria and abs(diferenca_percentual) >= limiar_inovacao_percentual

    estado = "SUCCEEDED" if melhoria else "FAILED"
    motivo: str | None = None
    if not melhoria:
        motivo = (
            f"valor obtido {valor_obtido} não supera o baseline "
            f"{valor_ref} ({direcao_melhoria})"
        )
    elif not criterio_inovacao:
        motivo = (
            f"melhoria de {abs(diferenca_percentual):.2f}% abaixo do "
            f"limiar de inovação própria ({limiar_inovacao_percentual}%)"
        )

    return ResultadoBenchmark(
        baseline=baseline.nome,
        metrica=baseline.metrica_primaria,
        valor_obtido=float(valor_obtido),
        valor_referencia=float(valor_ref),
        diferenca_absoluta=float(diferenca_absoluta),
        diferenca_percentual=float(diferenca_percentual),
        melhoria=melhoria,
        critério_inovacao_propria=criterio_inovacao,
        estado=estado,
        motivo=motivo,
    )


def aplicar_criterio_inovacao_propria(
    comparacao: ResultadoBenchmark,
    limiar_percentual: float = 5.0,
) -> bool:
    """Aplica o critério de inovação própria a uma comparação.

    Uma melhoria só é considerada inovação própria quando excede um limiar
    percentual, evitando que variações de ruído sejam aceites como avanços.
    """
    return (
        comparacao.melhoria
        and abs(comparacao.diferenca_percentual) >= limiar_percentual
    )


def comparar_conjunto_baselines(
    resultados: dict[str, float],
    baselines: list[Baseline],
    direcoes_melhoria: dict[str, str] | None = None,
) -> list[ResultadoBenchmark]:
    """Compara múltiplas métricas contra múltiplos baselines.

    `resultados` mapeia nomes de métrica para valores obtidos.
    `baselines` é a lista de baselines de referência.
    `direcoes_melhoria` mapeia nomes de métrica para a direção de melhoria.
    """
    direcoes_melhoria = direcoes_melhoria or {}
    comparacoes: list[ResultadoBenchmark] = []

    for baseline in baselines:
        metrica = baseline.metrica_primaria
        if metrica not in resultados:
            continue

        valor_obtido = resultados[metrica]
        direcao = direcoes_melhoria.get(metrica, "menor_e_melhor")

        comparacao = comparar_com_baseline(
            valor_obtido, baseline, direcao
        )
        comparacoes.append(comparacao)

    return comparacoes


def resumo_benchmark(
    comparacoes: list[ResultadoBenchmark],
) -> dict[str, Any]:
    """Devolve um resumo de todos os benchmarks executados."""
    total = len(comparacoes)
    melhorias = sum(1 for c in comparacoes if c.melhoria)
    inovacao = sum(1 for c in comparacoes if c.critério_inovacao_propria)

    return {
        "total_comparacoes": total,
        "melhorias": melhorias,
        "inovacao_propria": inovacao,
        "taxa_melhoria": float(melhorias / total) if total > 0 else 0.0,
        "detalhes": [
            {
                "baseline": c.baseline,
                "metrica": c.metrica,
                "valor_obtido": c.valor_obtido,
                "valor_referencia": c.valor_referencia,
                "diferenca_percentual": c.diferenca_percentual,
                "melhoria": c.melhoria,
                "inovacao_propria": c.critério_inovacao_propria,
                "estado": c.estado,
                "motivo": c.motivo,
            }
            for c in comparacoes
        ],
    }


def resultado_para_dict(
    resultado: ResultadoBenchmark,
) -> dict[str, Any]:
    """Serializa o resultado de benchmark para dicionário JSON."""
    return {
        "baseline": resultado.baseline,
        "metrica": resultado.metrica,
        "valor_obtido": resultado.valor_obtido,
        "valor_referencia": resultado.valor_referencia,
        "diferenca_absoluta": resultado.diferenca_absoluta,
        "diferenca_percentual": resultado.diferenca_percentual,
        "melhoria": resultado.melhoria,
        "criterio_inovacao_propria": resultado.critério_inovacao_propria,
        "estado": resultado.estado,
        "motivo": resultado.motivo,
    }


__all__ = [
    "Baseline",
    "ErroBenchmark",
    "ResultadoBenchmark",
    "aplicar_criterio_inovacao_propria",
    "comparar_com_baseline",
    "comparar_conjunto_baselines",
    "resultado_para_dict",
    "resumo_benchmark",
]
