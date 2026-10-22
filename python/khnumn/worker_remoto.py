"""Workers remotos com capacidade anunciada (F7.E3).

Cada worker anuncia a sua capacidade (memória, CPU, presença de acelerador)
e o scheduler usa essa informação para escolher onde executar cada tarefa.
A ausência de acelerador nunca bloqueia tarefas com via em CPU.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ErroWorkerRemoto(Exception):
    """Falha no despacho para worker remoto, com causa legível."""


@dataclass
class CapacidadeWorker:
    """Capacidade anunciada por um worker remoto."""

    worker_id: str
    memoria_total_mb: int
    memoria_disponivel_mb: int
    num_cpu: int
    tem_acelerador: bool = False
    tipo_acelerador: str | None = None
    """Tipo de acelerador: `cuda`, `rocm` ou `None`."""

    carga_atual_percent: float = 0.0
    """Percentagem de carga atual do worker."""

    def pode_executar(
        self,
        memoria_estimada_mb: int,
        requer_acelerador: bool = False,
    ) -> bool:
        """Indica se o worker pode executar uma tarefa com os requisitos dados."""
        if requer_acelerador and not self.tem_acelerador:
            return False
        memoria_projetada = self.memoria_disponivel_mb - memoria_estimada_mb
        return memoria_projetada >= 0 and self.carga_atual_percent < 95.0

    def memoria_livre_estimada_mb(self) -> int:
        """Devolve a memória livre estimada, em megabytes."""
        return max(0, self.memoria_disponivel_mb)


@dataclass
class WorkerRemoto:
    """Worker remoto com capacidade anunciada."""

    capacidade: CapacidadeWorker
    estado: str = "disponível"
    """Estado: `disponível`, `ocupado`, `indisponível`."""

    tarefas_em_execucao: list[str] = field(default_factory=list)
    """Identificadores das tarefas atualmente em execução neste worker."""

    def anunciar_capacidade(self) -> dict[str, Any]:
        """Devolve a capacidade do worker em formato serializável."""
        return {
            "worker_id": self.capacidade.worker_id,
            "memoria_total_mb": self.capacidade.memoria_total_mb,
            "memoria_disponivel_mb": self.capacidade.memoria_disponivel_mb,
            "num_cpu": self.capacidade.num_cpu,
            "tem_acelerador": self.capacidade.tem_acelerador,
            "tipo_acelerador": self.capacidade.tipo_acelerador,
            "carga_atual_percent": self.capacidade.carga_atual_percent,
        }

    def pode_executar_tarefa(
        self,
        memoria_estimada_mb: int,
        requer_acelerador: bool = False,
    ) -> bool:
        """Indica se este worker pode executar a tarefa."""
        if self.estado != "disponível":
            return False
        return self.capacidade.pode_executar(
            memoria_estimada_mb, requer_acelerador
        )

    def atribuir_tarefa(self, task_id: str) -> None:
        """Marca uma tarefa como atribuída a este worker."""
        self.tarefas_em_execucao.append(task_id)
        self.estado = "ocupado"

    def libertar_tarefa(self, task_id: str) -> None:
        """Marca uma tarefa como concluída neste worker."""
        if task_id in self.tarefas_em_execucao:
            self.tarefas_em_execucao.remove(task_id)
        if not self.tarefas_em_execucao:
            self.estado = "disponível"


class PoolWorkers:
    """Pool de workers remotos com seleção por capacidade."""

    def __init__(self) -> None:
        self.workers: dict[str, WorkerRemoto] = {}

    def registar_worker(
        self,
        worker_id: str,
        memoria_total_mb: int,
        memoria_disponivel_mb: int,
        num_cpu: int,
        tem_acelerador: bool = False,
        tipo_acelerador: str | None = None,
    ) -> None:
        """Regista um novo worker no pool."""
        capacidade = CapacidadeWorker(
            worker_id=worker_id,
            memoria_total_mb=memoria_total_mb,
            memoria_disponivel_mb=memoria_disponivel_mb,
            num_cpu=num_cpu,
            tem_acelerador=tem_acelerador,
            tipo_acelerador=tipo_acelerador,
        )
        self.workers[worker_id] = WorkerRemoto(capacidade=capacidade)

    def escolher_worker(
        self,
        memoria_estimada_mb: int,
        requer_acelerador: bool = False,
    ) -> str | None:
        """Escolhe o worker mais adequado para uma tarefa.

        Critérios: prioriza workers com acelerador quando requerido, depois
        o que tem mais memória livre, depois o com menos carga.
        """
        candidatos = [
            (wid, w)
            for wid, w in self.workers.items()
            if w.pode_executar_tarefa(memoria_estimada_mb, requer_acelerador)
        ]

        if not candidatos:
            return None

        def chave_candidato(
            item: tuple[str, WorkerRemoto],
        ) -> tuple[bool, int, float]:
            wid, w = item
            memoria_livre = w.capacidade.memoria_livre_estimada_mb()
            return (
                not (requer_acelerador and w.capacidade.tem_acelerador),
                -memoria_livre,
                w.capacidade.carga_atual_percent,
            )

        candidatos.sort(key=chave_candidato)
        return candidatos[0][0]

    def despachar_para_worker(
        self,
        task_id: str,
        memoria_estimada_mb: int,
        requer_acelerador: bool = False,
    ) -> str | None:
        """Despacha uma tarefa para o worker mais adequado.

        Devolve o ID do worker escolhido, ou None se nenhum estiver
        disponível. A ausência de acelerador nunca bloqueia tarefas com
        via em CPU.
        """
        worker_id = self.escolher_worker(memoria_estimada_mb, requer_acelerador)
        if worker_id is None:
            return None
        self.workers[worker_id].atribuir_tarefa(task_id)
        return worker_id

    def libertar_worker(self, worker_id: str, task_id: str) -> None:
        """Liberta uma tarefa de um worker."""
        if worker_id in self.workers:
            self.workers[worker_id].libertar_tarefa(task_id)

    def resumo(self) -> dict[str, Any]:
        """Devolve um resumo do estado de todos os workers."""
        return {
            "num_workers": len(self.workers),
            "workers": {
                wid: {
                    "estado": w.estado,
                    "capacidade": w.anunciar_capacidade(),
                    "tarefas_em_execucao": list(w.tarefas_em_execucao),
                }
                for wid, w in self.workers.items()
            },
        }


def despachar_para_worker(
    pool: PoolWorkers,
    task_id: str,
    memoria_estimada_mb: int,
    requer_acelerador: bool = False,
) -> str | None:
    """Função de conveniência para despachar uma tarefa para um worker."""
    return pool.despachar_para_worker(
        task_id, memoria_estimada_mb, requer_acelerador
    )


__all__ = [
    "CapacidadeWorker",
    "ErroWorkerRemoto",
    "PoolWorkers",
    "WorkerRemoto",
    "despachar_para_worker",
]
