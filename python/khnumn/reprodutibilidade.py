"""Consistência numérica e tolerâncias (F7.E5).

Declara o nível de reprodutibilidade exigido, com a tolerância explícita
por backend de ajuste, e compara execuções para verificar consistência
numérica entre backends (CPU local, CPU distribuído, GPU).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np


class ErroReprodutibilidade(Exception):
    """Falha na verificação de reprodutibilidade, com causa legível."""


@dataclass
class NivelReprodutibilidade:
    """Nível de reprodutibilidade exigido para uma execução."""

    nivel: str
    """Nível: `exato`, `aproximado` ou `estatistico`."""

    tolerancia_absoluta: float = 1e-6
    """Tolerância absoluta para comparação de valores de ponto flutuante."""

    tolerancia_relativa: float = 1e-6
    """Tolerância relativa para comparação de valores de ponto flutuante."""

    semente_obrigatoria: bool = True
    """Quando verdadeiro, uma semente é obrigatória para reprodutibilidade."""

    versao_backend: str | None = None
    """Versão do backend de ajuste usada, para rastreabilidade."""


@dataclass
class ResultadoComparacao:
    """Resultado da comparação de duas execuções."""

    consistentes: bool
    """Verdadeiro quando as execuções são consistentes dentro da tolerância."""

    diferenca_maxima: float
    """Diferença máxima absoluta entre os valores comparados."""

    diferenca_relativa_maxima: float
    """Diferença relativa máxima entre os valores comparados."""

    num_valores_comparados: int
    """Número de valores comparados."""

    num_diferencas_acima_tolerancia: int
    """Número de valores cuja diferença excede a tolerância."""

    motivo: str | None = None
    """Causa, quando as execuções não são consistentes."""


def nivel_reprodutibilidade(
    backend_ajuste: str,
    versao: str | None = None,
) -> NivelReprodutibilidade:
    """Declara o nível de reprodutibilidade exigido por backend de ajuste.

    Cada backend tem características numéricas diferentes: CPU local é
    determinístico, CPU distribuído pode ter variações por ordem de
    redução, e GPU pode ter diferenças por precisão de ponto flutuante.
    """
    tolerancias_por_backend: dict[str, dict[str, float]] = {
        "cpu_local": {"absoluta": 1e-9, "relativa": 1e-9},
        "cpu_distribuido": {"absoluta": 1e-6, "relativa": 1e-6},
        "gpu_cuda": {"absoluta": 1e-4, "relativa": 1e-4},
        "gpu_rocm": {"absoluta": 1e-4, "relativa": 1e-4},
        "pycolmap": {"absoluta": 1e-6, "relativa": 1e-6},
    }

    config = tolerancias_por_backend.get(
        backend_ajuste,
        {"absoluta": 1e-6, "relativa": 1e-6},
    )

    nivel = "exato" if backend_ajuste == "cpu_local" else "aproximado"

    return NivelReprodutibilidade(
        nivel=nivel,
        tolerancia_absoluta=config["absoluta"],
        tolerancia_relativa=config["relativa"],
        semente_obrigatoria=True,
        versao_backend=versao,
    )


def comparar_valores(
    valor_a: float,
    valor_b: float,
    tolerancia_absoluta: float,
    tolerancia_relativa: float,
) -> bool:
    """Compara dois valores de ponto flutuante dentro de tolerâncias."""
    diferenca_absoluta = abs(valor_a - valor_b)
    if diferenca_absoluta <= tolerancia_absoluta:
        return True
    valor_referencia = max(abs(valor_a), abs(valor_b))
    if valor_referencia == 0:
        return diferenca_absoluta <= tolerancia_absoluta
    diferenca_relativa = diferenca_absoluta / valor_referencia
    return diferenca_relativa <= tolerancia_relativa


def comparar_execucoes(
    resultados_a: dict[str, Any],
    resultados_b: dict[str, Any],
    nivel: NivelReprodutibilidade | None = None,
) -> ResultadoComparacao:
    """Compara duas execuções para verificar consistência numérica.

    Percorre as métricas de ambas as execuções e compara valores numéricos
    dentro das tolerâncias declaradas pelo nível de reprodutibilidade.
    """
    nivel = nivel or NivelReprodutibilidade(
        nivel="aproximado",
        tolerancia_absoluta=1e-6,
        tolerancia_relativa=1e-6,
    )

    chaves_a = set(resultados_a.keys())
    chaves_b = set(resultados_b.keys())
    chaves_comuns = chaves_a & chaves_b

    diferenca_maxima = 0.0
    diferenca_relativa_maxima = 0.0
    num_comparados = 0
    num_acima_tolerancia = 0
    motivos: list[str] = []

    for chave in chaves_comuns:
        val_a = resultados_a[chave]
        val_b = resultados_b[chave]

        if isinstance(val_a, (int, float)) and isinstance(
            val_b, (int, float)
        ):
            num_comparados += 1
            diferenca = abs(float(val_a) - float(val_b))
            if diferenca > diferenca_maxima:
                diferenca_maxima = diferenca

            ref = max(abs(float(val_a)), abs(float(val_b)))
            if ref > 0:
                diff_rel = diferenca / ref
                if diff_rel > diferenca_relativa_maxima:
                    diferenca_relativa_maxima = diff_rel

            if not comparar_valores(
                float(val_a),
                float(val_b),
                nivel.tolerancia_absoluta,
                nivel.tolerancia_relativa,
            ):
                num_acima_tolerancia += 1
                motivos.append(
                    f"{chave}: {val_a} vs {val_b} (dif={diferenca:.2e})"
                )
        elif isinstance(val_a, dict) and isinstance(val_b, dict):
            # Comparação recursiva para dicionários aninhados.
            sub = comparar_execucoes(val_a, val_b, nivel)
            num_comparados += sub.num_valores_comparados
            num_acima_tolerancia += sub.num_diferencas_acima_tolerancia
            if sub.diferenca_maxima > diferenca_maxima:
                diferenca_maxima = sub.diferenca_maxima
            if sub.diferenca_relativa_maxima > diferenca_relativa_maxima:
                diferenca_relativa_maxima = sub.diferenca_relativa_maxima
            if sub.motivo:
                motivos.append(f"{chave}: {sub.motivo}")
        elif val_a != val_b:
            num_comparados += 1
            num_acima_tolerancia += 1
            motivos.append(
                f"{chave}: {val_a!r} vs {val_b!r} (tipos ou valores diferentes)"
            )

    consistentes = num_acima_tolerancia == 0
    motivo = "; ".join(motivos) if motivos else None

    return ResultadoComparacao(
        consistentes=consistentes,
        diferenca_maxima=diferenca_maxima,
        diferenca_relativa_maxima=diferenca_relativa_maxima,
        num_valores_comparados=num_comparados,
        num_diferencas_acima_tolerancia=num_acima_tolerancia,
        motivo=motivo,
    )


def verificar_consistencia_entre_backends(
    resultado_cpu: dict[str, Any],
    resultado_outro: dict[str, Any],
    backend_outro: str,
) -> ResultadoComparacao:
    """Verifica consistência numérica entre execução CPU local e outro backend.

    Declara a tolerância explícita por backend de ajuste, conforme exigido
    por `docs/Khnumn.md` §17.5.
    """
    nivel_cpu = nivel_reprodutibilidade("cpu_local")
    nivel_outro = nivel_reprodutibilidade(backend_outro)

    # Usa a tolerância mais restritiva dos dois backends.
    tolerancia_absoluta = min(
        nivel_cpu.tolerancia_absoluta, nivel_outro.tolerancia_absoluta
    )
    tolerancia_relativa = min(
        nivel_cpu.tolerancia_relativa, nivel_outro.tolerancia_relativa
    )

    nivel_conjunto = NivelReprodutibilidade(
        nivel="aproximado",
        tolerancia_absoluta=tolerancia_absoluta,
        tolerancia_relativa=tolerancia_relativa,
        versao_backend=backend_outro,
    )

    return comparar_execucoes(resultado_cpu, resultado_outro, nivel_conjunto)


def resultado_comparacao_para_dict(
    resultado: ResultadoComparacao,
) -> dict[str, Any]:
    """Serializa o resultado de comparação para dicionário JSON."""
    return {
        "consistentes": resultado.consistentes,
        "diferenca_maxima": resultado.diferenca_maxima,
        "diferenca_relativa_maxima": resultado.diferenca_relativa_maxima,
        "num_valores_comparados": resultado.num_valores_comparados,
        "num_diferencas_acima_tolerancia": resultado.num_diferencas_acima_tolerancia,
        "motivo": resultado.motivo,
    }


__all__ = [
    "ErroReprodutibilidade",
    "NivelReprodutibilidade",
    "ResultadoComparacao",
    "comparar_execucoes",
    "comparar_valores",
    "nivel_reprodutibilidade",
    "resultado_comparacao_para_dict",
    "verificar_consistencia_entre_backends",
]
