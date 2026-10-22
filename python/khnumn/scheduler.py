"""Scheduler CPU-first com backpressure (F7.E2).

Impõe limites globais de memória e CPU, aplica backpressure quando os
recursos estão esgotados, e não executa tarefas de memória elevada em excesso.
O scheduler trabalha sobre o DAG em ordem topológica, respeitando as
dependências entre tarefas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ErroScheduler(Exception):
    """Falha no scheduler, com causa legível."""


@dataclass
class RecursosDisponiveis:
    """Recursos disponíveis para execução de tarefas."""

    memoria_total_mb: int
    """Memória total disponível, em megabytes."""

    memoria_orcamento_mb: int
    """Orçamento de memória por tarefa, em megabytes."""

    max_workers: int = 2
    """Número máximo de workers em paralelo."""

    cpu_maximo_percent: float = 100.0
    """Percentagem máxima de CPU utilizável."""


@dataclass
class TarefaAgendada:
    """Uma tarefa agendada para execução."""

    task_id: str
    algoritmo: str
    prioridade: int = 0
    """Prioridade da tarefa (maior = executada primeiro)."""

    memoria_estimada_mb: int = 0
    """Memória estimada que a tarefa vai consumir, em megabytes."""

    dependencias: list[str] = field(default_factory=list)
    """Identificadores das tarefas de que depende."""

    dependencias_satisfeitas: bool = False
    """Verdadeiro quando todas as dependências foram executadas com sucesso."""

    estado: str = "PENDING"
    """Estado atual: PENDING, READY, RUNNING, SUCCEEDED, FAILED, BLOCKED."""


class SchedulerCPUFirst:
    """Scheduler que prioriza execução em CPU com controlo de backpressure.

    Nunca inicia uma tarefa se o pico de memória projetado exceder o
    orçamento declarado. Aplica backpressure: quando os recursos estão
    esgotados, as tarefas ficam em espera (READY) em vez de serem iniciadas
    e falharem por falta de memória.
    """

    def __init__(
        self,
        recursos: RecursosDisponiveis,
    ) -> None:
        self.recursos = recursos
        self.memoria_em_uso_mb: int = 0
        self.tarefas: dict[str, TarefaAgendada] = {}
        self.ordem_execucao: list[str] = []
        self.executadas: int = 0
        self.reutilizadas_da_cache: int = 0
        self.falhadas: int = 0
        self.bloqueadas: int = 0

    def registar_tarefa(
        self,
        task_id: str,
        algoritmo: str,
        memoria_estimada_mb: int = 0,
        dependencias: list[str] | None = None,
    ) -> None:
        """Regista uma tarefa no scheduler."""
        self.tarefas[task_id] = TarefaAgendada(
            task_id=task_id,
            algoritmo=algoritmo,
            memoria_estimada_mb=memoria_estimada_mb,
            dependencias=list(dependencias or []),
            dependencias_satisfeitas=len(dependencias or []) == 0,
        )

    def marcar_dependencia_satisfeita(self, task_id: str) -> None:
        """Marca que uma dependência de uma tarefa foi satisfeita."""
        tarefa = self.tarefas.get(task_id)
        if tarefa is not None:
            # Uma dependência é satisfeita quando a tarefa dependente tem
            # todas as suas dependências em estado SUCCEEDED.
            todas_satisfeitas = all(
                self.tarefas.get(d, TarefaAgendada(task_id=d, algoritmo="")).estado
                == "SUCCEEDED"
                for d in tarefa.dependencias
            )
            tarefa.dependencias_satisfeitas = todas_satisfeitas

    def proxima_tarefa_pronta(self) -> str | None:
        """Devolve o ID da próxima tarefa pronta para execução.

        Uma tarefa está pronta quando as dependências estão satisfeitas e
        há memória disponível para a sua execução (respeitando backpressure).
        """
        candidatos = [
            (tid, t)
            for tid, t in self.tarefas.items()
            if t.estado == "PENDING"
            and t.dependencias_satisfeitas
        ]

        if not candidatos:
            return None

        # Ordena por prioridade (maior primeiro), depois por ordem de registo.
        candidatos.sort(key=lambda x: (-x[1].prioridade, x[0]))

        for tid, tarefa in candidatos:
            # Backpressure: não iniciar se não houver memória suficiente.
            memoria_projetada = self.memoria_em_uso_mb + tarefa.memoria_estimada_mb
            if memoria_projetada > self.recursos.memoria_orcamento_mb:
                continue
            return tid

        return None

    def iniciar_tarefa(self, task_id: str) -> bool:
        """Marca uma tarefa como em execução, se houver recursos."""
        tarefa = self.tarefas.get(task_id)
        if tarefa is None or tarefa.estado != "PENDING":
            return False

        memoria_projetada = self.memoria_em_uso_mb + tarefa.memoria_estimada_mb
        if memoria_projetada > self.recursos.memoria_orcamento_mb:
            tarefa.estado = "BLOCKED"
            self.bloqueadas += 1
            return False

        tarefa.estado = "RUNNING"
        self.memoria_em_uso_mb += tarefa.memoria_estimada_mb
        return True

    def concluir_tarefa(
        self,
        task_id: str,
        sucesso: bool,
        memoria_real_mb: int | None = None,
    ) -> None:
        """Marca uma tarefa como concluída e liberta os seus recursos."""
        tarefa = self.tarefas.get(task_id)
        if tarefa is None:
            return

        # Liberta a memória estimada e, se conhecida, aplica a real.
        self.memoria_em_uso_mb = max(
            0, self.memoria_em_uso_mb - tarefa.memoria_estimada_mb
        )
        if memoria_real_mb is not None:
            self.memoria_em_uso_mb += memoria_real_mb

        if sucesso:
            tarefa.estado = "SUCCEEDED"
            self.executadas += 1
        else:
            tarefa.estado = "FAILED"
            self.falhadas += 1

        self.ordem_execucao.append(task_id)

        # Atualiza o estado de dependências das tarefas pendentes.
        for outra in self.tarefas.values():
            if outra.estado == "PENDING":
                self.marcar_dependencia_satisfeita(outra.task_id)

    def bloquear_dependentes(self, task_id_falhou: str) -> list[str]:
        """Marca como BLOCKED todas as tarefas que dependem de uma falhada."""
        bloqueadas: list[str] = []
        for tid, tarefa in self.tarefas.items():
            if (
                tarefa.estado == "PENDING"
                and task_id_falhou in tarefa.dependencias
            ):
                tarefa.estado = "BLOCKED"
                self.bloqueadas += 1
                bloqueadas.append(tid)
        return bloqueadas

    def resumo(self) -> dict[str, Any]:
        """Devolve um resumo do estado do scheduler."""
        return {
            "total_tarefas": len(self.tarefas),
            "executadas": self.executadas,
            "reutilizadas_da_cache": self.reutilizadas_da_cache,
            "falhadas": self.falhadas,
            "bloqueadas": self.bloqueadas,
            "memoria_em_uso_mb": self.memoria_em_uso_mb,
            "memoria_orcamento_mb": self.recursos.memoria_orcamento_mb,
            "ordem_execucao": list(self.ordem_execucao),
        }


def agendar(
    tarefas: list[dict[str, Any]],
    recursos: RecursosDisponiveis | None = None,
) -> dict[str, Any]:
    """Agenda uma lista de tarefas usando o scheduler CPU-first.

    Devolve a ordem de execução e o resumo do scheduler. As tarefas são
    processadas em ordem topológica, respeitando dependências e limites
    de memória.
    """
    recursos = recursos or RecursosDisponiveis(
        memoria_total_mb=1024,
        memoria_orcamento_mb=500,
    )

    scheduler = SchedulerCPUFirst(recursos=recursos)

    for tarefa in tarefas:
        scheduler.registar_tarefa(
            task_id=tarefa.get("task_id", ""),
            algoritmo=tarefa.get("algoritmo", ""),
            memoria_estimada_mb=tarefa.get("memoria_estimada_mb", 0),
            dependencias=tarefa.get("depende_de", []),
        )

    # Execução simplificada: processa tarefas prontas até não haver mais.
    max_iteracoes = len(tarefas) * 2 + 1
    for _ in range(max_iteracoes):
        proxima = scheduler.proxima_tarefa_pronta()
        if proxima is None:
            break
        scheduler.iniciar_tarefa(proxima)
        # Simula conclusão bem-sucedida (o executor real trata o resultado).
        scheduler.concluir_tarefa(proxima, sucesso=True)

    return scheduler.resumo()


__all__ = [
    "ErroScheduler",
    "RecursosDisponiveis",
    "SchedulerCPUFirst",
    "TarefaAgendada",
    "agendar",
]
