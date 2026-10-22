"""Planeador de execução com registo persistente de decisões (Fase 5).

Implementa F5.E4, F5.E5 e F5.E6: escolha de pipeline com fallback e razões
de rejeição registadas, escolha do caminho de superfície com orçamento
fixado *antes* da execução, e função multiobjetivo com registo persistente
de todas as decisões e a sua razão.

O registo de decisões é feito por escrito, não por convenção: cada decisão
fica acompanhada do motivo que a justifica, para que um auditor possa
reconstruir por que razão um caminho foi escolhido e outro rejeitado.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import cenario, planeador


class ErroPlanoExecucao(Exception):
    """Falha na elaboração do plano de execução, com causa legível."""


@dataclass
class DecisaoRegistada:
    """Uma decisão de planeamento, com o seu motivo."""

    decisao: str
    """Nome da decisão (ex.: 'cenario', 'caminho_denso', 'pipeline')."""

    valor: Any
    """Valor escolhido."""

    motivo: str
    """Razão pela qual este valor foi escolhido."""

    alternativas_rejeitadas: list[dict[str, Any]] = field(default_factory=list)
    """Alternativas consideradas e rejeitadas, com o motivo de rejeição."""


@dataclass
class PlanoExecucao:
    """Plano de execução completo, com todas as decisões registadas.

    O plano é materializado antes de qualquer tarefa do grafo ser iniciada,
    e o orçamento (memória, ensemble, iterações) é fixado antecipadamente,
    não aferido a posteriori.
    """

    versao_algoritmo: str = "1.0.0"
    """Versão do algoritmo de planeamento."""

    cenario: str = "unknown"
    """Cenário classificado."""

    caminho_denso: str = "esparsa_delaunay"
    """Caminho de superfície escolhido."""

    pipeline: str | None = None
    """Pipeline de reconstrução escolhido."""

    candidatos: list[str] = field(default_factory=list)
    """Pipelines compatíveis com o cenário."""

    custo_escolhido: float = 0.0
    """Custo relativo do pipeline escolhido."""

    ensemble_samples: int = 10
    """Número de amostras do ensemble, fixado antes da execução."""

    iteracoes_refino: int = 3
    """Número de iterações de refinamento, fixado antes da execução."""

    limite_memoria_mb: int | None = None
    """Orçamento de memória declarado, em megabytes."""

    decisoes: list[DecisaoRegistada] = field(default_factory=list)
    """Todas as decisões de planeamento, com motivo e alternativas rejeitadas."""

    fallback: str | None = None
    """Caminho de fallback, quando o escolhido não está disponível."""

    estado: str = "planeado"
    """Estado do plano: `planeado`, `aprovado` ou `rejeitado`."""

    motivo_rejecao: str | None = None
    """Causa da rejeição, quando o estado é `rejeitado`."""


def _registar_decisao(
    plano: PlanoExecucao,
    nome: str,
    valor: Any,
    motivo: str,
    alternativas: list[dict[str, Any]] | None = None,
) -> None:
    """Acrescenta uma decisão ao plano de execução."""
    plano.decisoes.append(
        DecisaoRegistada(
            decisao=nome,
            valor=valor,
            motivo=motivo,
            alternativas_rejeitadas=alternativas or [],
        )
    )


def classificar_e_planejar(
    metadados: dict[str, Any],
    qualidade: dict[str, Any] | None,
    hardware_gpu: bool,
    requisito_densidade: str,
    ensemble_samples: int,
    iteracoes_refino: int,
    limite_memoria_mb: int | None = None,
    manual_override: str | None = None,
    correcao_cenario: str | None = None,
    motivo_correcao: str | None = None,
) -> dict[str, Any]:
    """Elabora o plano de execução com todas as decisões registadas (F5.E4-E6).

    1. Classifica o cenário (F5.E1).
    2. Aplica correcção manual, quando solicitada, com prioridade sobre a
       sugestão (F5.E3).
    3. Escolhe o pipeline compatível com fallback e razões de rejeição (F5.E4).
    4. Escolhe o caminho de superfície segundo a capacidade do host e o
       requisito de densidade, com orçamento fixado antecipadamente (F5.E5).
    5. Calcula a função multiobjetivo e regista todas as decisões (F5.E6).

    O orçamento de memória e os parâmetros do ensemble/refinamento são
    fixados antes de qualquer execução, e constam do plano.
    """
    plano = PlanoExecucao(
        versao_algoritmo="1.0.0",
        ensemble_samples=ensemble_samples,
        iteracoes_refino=iteracoes_refino,
        limite_memoria_mb=limite_memoria_mb,
    )

    # F5.E1 — Classificação do cenário a partir de sinais observáveis.
    classificacao = cenario.classificar_cenario(metadados, qualidade)
    plano.cenario = classificacao.get("classe", "unknown")
    _registar_decisao(
        plano,
        "cenario",
        plano.cenario,
        (
            f"classificado a partir de sinais observáveis com confiança "
            f"{classificacao.get('confianca', 0.0):.2f}; "
            f"razões: {'; '.join(classificacao.get('razoes', [])) or 'nenhuma'}"
        ),
        [
            {"classe": c, "confianca": conf, "motivo": "não selecionada pelo classificador"}
            for c, conf in classificacao.get("classes_candidatas", [])
        ],
    )

    # F5.E3 — Correcção manual, com prioridade sobre a sugestão.
    if manual_override or correcao_cenario:
        classe_corrigida = manual_override or correcao_cenario
        motivo = motivo_correcao or "correção manual do operador"
        classe_original = plano.cenario
        plano.cenario = classe_corrigida
        _registar_decisao(
            plano,
            "correcao_cenario",
            classe_corrigida,
            motivo,
            [{"classe_original": classe_original, "motivo": "substituída por decisão do operador"}],
        )
        if correcao_cenario:
            classificacao["classe_final"] = classe_corrigida
            classificacao["correcao_manual"] = True
            classificacao["motivo"] = motivo

    # F5.E4 — Escolha de pipeline compatível, com fallback e razões de rejeição.
    candidatos = planeador.pipelines_compativeis(plano.cenario)
    plano.candidatos = list(candidatos)
    if not candidatos:
        plano.estado = "rejeitado"
        plano.motivo_rejecao = f"nenhum pipeline compatível com o cenário {plano.cenario}"
        return _plano_para_dict(plano)

    # O pipeline escolhido é o de menor custo entre os compatíveis.
    custos = {}
    for cand in candidatos:
        custo = planeador.estimar_custo(
            cand, plano.caminho_denso, ensemble_samples, iteracoes_refino
        )
        custos[cand] = custo["custo_relativo"]

    pipeline_escolhido = min(custos, key=custos.get)
    plano.pipeline = pipeline_escolhido
    plano.custo_escolhido = custos[pipeline_escolhido]

    alternativas_rejeitadas = [
        {
            "pipeline": cand,
            "custo": custos[cand],
            "motivo": "custo relativo superior ao pipeline escolhido",
        }
        for cand in candidatos
        if cand != pipeline_escolhido
    ]
    _registar_decisao(
        plano,
        "pipeline",
        pipeline_escolhido,
        (
            f"menor custo relativo entre os candidatos compatíveis "
            f"({custos[pipeline_escolhido]:.4f})"
        ),
        alternativas_rejeitadas,
    )

    # Fallback: quando o caminho denso não é esparsa, a esparsa é o fallback.
    if plano.caminho_denso != "esparsa_delaunay":
        plano.fallback = "esparsa_delaunay"
    else:
        plano.fallback = None

    # F5.E5 — Escolha do caminho de superfície com orçamento fixado antecipadamente.
    caminho = planeador.escolher_caminho_denso(hardware_gpu, requisito_densidade)
    plano.caminho_denso = caminho
    motivo_caminho = (
        f"host com GPU={hardware_gpu}, requisito de densidade={requisito_densidade}; "
        f"orçamento de ensemble={ensemble_samples} amostras, "
        f"iterações de refinamento={iteracoes_refino}"
    )
    if limite_memoria_mb is not None:
        motivo_caminho += f", limite de memória={limite_memoria_mb} MiB"
    _registar_decisao(
        plano,
        "caminho_denso",
        caminho,
        motivo_caminho,
        [
            {"caminho": alt, "motivo": "não selecionado pelo planeador de caminho"}
            for alt in ("denso_acelerador", "denso_cpu", "esparsa_delaunay")
            if alt != caminho
        ],
    )

    # F5.E6 — Função multiobjetivo sobre os custos estimados, com registo
    # persistente de todas as decisões e a sua razão.
    pesos = {
        "tempo": 1.0,
        "memoria": 1.0,
        "qualidade": 1.0,
    }
    custo_objetivo = planeador.funcao_multiobjetivo(custos, pesos)
    _registar_decisao(
        plano,
        "funcao_multiobjetivo",
        custo_objetivo,
        (
            "soma ponderada dos custos de tempo, memória e qualidade, "
            f"com pesos {pesos}"
        ),
        [],
    )

    plano.estado = "aprovado"
    return _plano_para_dict(plano)


def _plano_para_dict(plano: PlanoExecucao) -> dict[str, Any]:
    """Serializa o plano de execução para dicionário JSON."""
    return {
        "versao_algoritmo": plano.versao_algoritmo,
        "estado": plano.estado,
        "motivo_rejecao": plano.motivo_rejecao,
        "cenario": plano.cenario,
        "caminho_denso": plano.caminho_denso,
        "pipeline": plano.pipeline,
        "candidatos": plano.candidatos,
        "custo_escolhido": plano.custo_escolhido,
        "ensemble_samples": plano.ensemble_samples,
        "iteracoes_refino": plano.iteracoes_refino,
        "limite_memoria_mb": plano.limite_memoria_mb,
        "fallback": plano.fallback,
        "decisoes": [
            {
                "decisao": d.decisao,
                "valor": d.valor,
                "motivo": d.motivo,
                "alternativas_rejeitadas": d.alternativas_rejeitadas,
            }
            for d in plano.decisoes
        ],
    }


def guardar_plano(caminho: str | Path, plano: dict[str, Any]) -> None:
    """Guarda o plano de execução num ficheiro JSON, para registo persistente."""
    Path(caminho).write_text(
        json.dumps(plano, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def carregar_plano(caminho: str | Path) -> dict[str, Any] | None:
    """Carrega um plano de execução previamente guardado."""
    p = Path(caminho)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


__all__ = [
    "ErroPlanoExecucao",
    "DecisaoRegistada",
    "PlanoExecucao",
    "classificar_e_planejar",
    "guardar_plano",
    "carregar_plano",
]
