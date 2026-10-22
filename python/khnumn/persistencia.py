"""Persistência do DAG e recuperação após interrupção (F7.E1).

Serializa o grafo acíclico dirigido de tarefas para disco, incluindo estados
de tarefa, entradas/saídas por hash, e permite retomar a execução após
interrupção sem perder produtos intermediários.

O modelo de dados não é alterado: a persistência é uma camada sobre o DAG
em memória existente desde as fases anteriores (`docs/Khnumn.md` §22). O
formato serializado é um dicionário Python compatível com a estrutura do
`Grafo` e `Tarefa` do núcleo Rust, para que a recuperação seja possível
sem perda de informação.
"""

from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ErroPersistencia(Exception):
    """Falha na persistência ou recuperação do DAG, com causa legível."""


@dataclass
class EstadoSerializado:
    """Estado serializado de uma tarefa para persistência."""

    task_id: str
    algoritmo: str
    versao: str
    estado: str
    motivo: str | None = None
    limite_memoria_mb: int | None = None
    pico_memoria_mb: int | None = None
    inicio_utc: str | None = None
    fim_utc: str | None = None
    semente: int | None = None


def serializar_estado_tarefa(
    task_id: str,
    algoritmo: str,
    versao: str,
    estado: str,
    motivo: str | None = None,
    limite_memoria_mb: int | None = None,
    pico_memoria_mb: int | None = None,
    inicio_utc: str | None = None,
    fim_utc: str | None = None,
    semente: int | None = None,
) -> EstadoSerializado:
    """Cria um estado serializado de uma tarefa."""
    return EstadoSerializado(
        task_id=task_id,
        algoritmo=algoritmo,
        versao=versao,
        estado=estado,
        motivo=motivo,
        limite_memoria_mb=limite_memoria_mb,
        pico_memoria_mb=pico_memoria_mb,
        inicio_utc=inicio_utc,
        fim_utc=fim_utc,
        semente=semente,
    )


def serializar_grafo(
    nos: list[dict[str, Any]],
) -> dict[str, Any]:
    """Serializa uma lista de nós do grafo para dicionário JSON.

    Cada nó contém a tarefa (algoritmo, versão, parâmetros, entradas,
    saídas, estado, métricas) e as suas dependências. O formato é
    compatível com a estrutura do `Grafo` do núcleo Rust.
    """
    nos_serializados: list[dict[str, Any]] = []
    for no in nos:
        tarefa = no.get("tarefa", {})
        nos_serializados.append(
            {
                "task_id": tarefa.get("task_id", ""),
                "algoritmo": tarefa.get("algoritmo", ""),
                "versao": tarefa.get("versao", "1.0.0"),
                "parametros": tarefa.get("parametros", {}),
                "entradas": [
                    {
                        "papel": e.get("papel", ""),
                        "uri": e.get("uri", ""),
                        "sha256": e.get("sha256"),
                    }
                    for e in tarefa.get("entradas", [])
                ],
                "saidas": [
                    {
                        "papel": s.get("papel", ""),
                        "uri": s.get("uri", ""),
                        "sha256": s.get("sha256"),
                        "bytes": s.get("bytes"),
                    }
                    for s in tarefa.get("saidas", [])
                ],
                "estado": tarefa.get("estado", "Pending"),
                "motivo": tarefa.get("motivo"),
                "metricas": tarefa.get("metricas", {}),
                "limite_memoria_mb": tarefa.get("limite_memoria_mb"),
                "pico_memoria_mb": tarefa.get("pico_memoria_mb"),
                "inicio_utc": tarefa.get("inicio_utc"),
                "fim_utc": tarefa.get("fim_utc"),
                "semente": tarefa.get("semente"),
                "versao_ambiente": tarefa.get("versao_ambiente", "desconhecido"),
                "depende_de": list(no.get("depende_de", [])),
            }
        )

    return {
        "versao_formato": "1.0.0",
        "data_serializacao_utc": _dt.datetime.utcnow().isoformat() + "Z",
        "nos": nos_serializados,
    }


def persistir_grafo(
    nos: list[dict[str, Any]],
    caminho: str | Path,
) -> None:
    """Escreve o grafo serializado num ficheiro JSON.

    O ficheiro contém toda a informação necessária para reconstruir o DAG
    e retomar a execução a partir do ponto de interrupção.
    """
    caminho = Path(caminho)
    dados = serializar_grafo(nos)
    caminho.write_text(
        json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def recuperar_grafo(caminho: str | Path) -> dict[str, Any]:
    """Lê um grafo serializado de um ficheiro JSON e devolve a estrutura.

    Os produtos intermediários são preservados: as saídas de cada tarefa
    são mantidas como entradas potenciais para tarefas dependentes.
    """
    caminho = Path(caminho)
    if not caminho.is_file():
        raise ErroPersistencia(f"ficheiro de grafo inexistente: {caminho}")

    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as erro:
        raise ErroPersistencia(
            f"não foi possível ler o grafo de {caminho}: {erro}"
        ) from erro

    versao = dados.get("versao_formato")
    if versao != "1.0.0":
        raise ErroPersistencia(
            f"versão de formato não suportada: {versao}; esperada 1.0.0"
        )

    return {
        "versao_formato": dados.get("versao_formato"),
        "data_serializacao_utc": dados.get("data_serializacao_utc"),
        "nos": dados.get("nos", []),
    }


def estado_para_dict(estado: EstadoSerializado) -> dict[str, Any]:
    """Serializa um estado de tarefa para dicionário JSON."""
    return {
        "task_id": estado.task_id,
        "algoritmo": estado.algoritmo,
        "versao": estado.versao,
        "estado": estado.estado,
        "motivo": estado.motivo,
        "limite_memoria_mb": estado.limite_memoria_mb,
        "pico_memoria_mb": estado.pico_memoria_mb,
        "inicio_utc": estado.inicio_utc,
        "fim_utc": estado.fim_utc,
        "semente": estado.semente,
    }


__all__ = [
    "ErroPersistencia",
    "EstadoSerializado",
    "estado_para_dict",
    "persistir_grafo",
    "recuperar_grafo",
    "serializar_estado_tarefa",
    "serializar_grafo",
]
