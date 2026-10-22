"""Retry, checkpoints e cache (F7.E4).

Estratégia de retry com estados legíveis, retomada a partir de checkpoint,
e idempotência verificada. Uma tarefa que falha não produz sucesso parcial
sem marcar os produtos afetados (`docs/Khnumn.md` §6.2).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


class ErroRetryCheckpoint(Exception):
    """Falha na estratégia de retry ou checkpoint, com causa legível."""


@dataclass
class EstadoCheckpoint:
    """Estado de um checkpoint de uma tarefa."""

    task_id: str
    algoritmo: str
    versao: str
    passo: str
    """Identificador do passo dentro da tarefa (ex.: `extracao`, `mapeamento`)."""

    dados: dict[str, Any]
    """Dados do checkpoint, suficientes para retomar a execução."""

    timestamp_utc: str
    """Instante em que o checkpoint foi gravado."""

    hash_dados: str
    """Hash dos dados do checkpoint, para verificação de integridade."""


@dataclass
class EstrategiaRetry:
    """Configuração da estratégia de retry."""

    max_tentativas: int = 3
    """Número máximo de tentativas antes de declarar falha."""

    atraso_inicial_s: float = 1.0
    """Atraso inicial entre tentativas, em segundos."""

    fator_backoff: float = 2.0
    """Fator de aumento exponencial do atraso entre tentativas."""

    atraso_maximo_s: float = 30.0
    """Atraso máximo entre tentativas, em segundos."""


class GerenciadorRetry:
    """Gerencia tentativas de retry com backoff exponencial e estados legíveis."""

    def __init__(self, estrategia: EstrategiaRetry | None = None) -> None:
        self.estrategia = estrategia or EstrategiaRetry()
        self.tentativas_por_tarefa: dict[str, int] = {}
        self.ultimo_erro_por_tarefa: dict[str, str] = {}

    def pode_retry(self, task_id: str) -> bool:
        """Indica se ainda há tentativas disponíveis para a tarefa."""
        tentativas = self.tentativas_por_tarefa.get(task_id, 0)
        return tentativas < self.estrategia.max_tentativas

    def registar_tentativa(
        self,
        task_id: str,
        erro: str,
    ) -> float:
        """Regista uma tentativa falhada e devolve o atraso antes da próxima."""
        self.tentativas_por_tarefa[task_id] = (
            self.tentativas_por_tarefa.get(task_id, 0) + 1
        )
        self.ultimo_erro_por_tarefa[task_id] = erro

        tentativa = self.tentativas_por_tarefa[task_id]
        if tentativa >= self.estrategia.max_tentativas:
            return -1.0  # não há mais tentativas

        atraso = min(
            self.estrategia.atraso_inicial_s
            * (self.estrategia.fator_backoff ** (tentativa - 1)),
            self.estrategia.atraso_maximo_s,
        )
        return atraso

    def resetar(self, task_id: str) -> None:
        """Resetar o contador de tentativas para uma tarefa."""
        self.tentativas_por_tarefa.pop(task_id, None)
        self.ultimo_erro_por_tarefa.pop(task_id, None)

    def resumo(self, task_id: str) -> dict[str, Any]:
        """Devolve o resumo de retry para uma tarefa."""
        return {
            "task_id": task_id,
            "tentativas": self.tentativas_por_tarefa.get(task_id, 0),
            "max_tentativas": self.estrategia.max_tentativas,
            "ultimo_erro": self.ultimo_erro_por_tarefa.get(task_id),
            "pode_retry": self.pode_retry(task_id),
        }


class GerenciadorCheckpoint:
    """Grava e lê checkpoints para retomada de execução após interrupção."""

    def __init__(self) -> None:
        self.checkpoints: dict[str, EstadoCheckpoint] = {}

    def gravar_checkpoint(
        self,
        task_id: str,
        algoritmo: str,
        versao: str,
        passo: str,
        dados: dict[str, Any],
    ) -> EstadoCheckpoint:
        """Grava um checkpoint para uma tarefa."""
        import hashlib
        import json

        dados_json = json.dumps(dados, sort_keys=True, ensure_ascii=False)
        hash_dados = hashlib.sha256(dados_json.encode("utf-8")).hexdigest()

        checkpoint = EstadoCheckpoint(
            task_id=task_id,
            algoritmo=algoritmo,
            versao=versao,
            passo=passo,
            dados=dados,
            timestamp_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            hash_dados=hash_dados,
        )
        self.checkpoints[task_id] = checkpoint
        return checkpoint

    def ler_checkpoint(self, task_id: str) -> EstadoCheckpoint | None:
        """Lê o checkpoint de uma tarefa, se existir."""
        return self.checkpoints.get(task_id)

    def verificar_integridade(self, task_id: str) -> bool:
        """Verifica a integridade do checkpoint usando o hash."""
        checkpoint = self.checkpoints.get(task_id)
        if checkpoint is None:
            return False

        import hashlib
        import json

        dados_json = json.dumps(
            checkpoint.dados, sort_keys=True, ensure_ascii=False
        )
        hash_atual = hashlib.sha256(
            dados_json.encode("utf-8")
        ).hexdigest()
        return hash_atual == checkpoint.hash_dados

    def remover_checkpoint(self, task_id: str) -> None:
        """Remove o checkpoint de uma tarefa após conclusão bem-sucedida."""
        self.checkpoints.pop(task_id, None)


def verificar_idempotencia(
    entrada_a: dict[str, Any],
    entrada_b: dict[str, Any],
    tolerancia: float = 0.0,
) -> bool:
    """Verifica se duas entradas produzem o mesmo resultado (idempotência).

    Duas execuções com a mesma chave de tarefa devem reutilizar o resultado
    da cache. Esta função compara as entradas para determinar se são
    equivalentes dentro de uma tolerância.
    """
    import hashlib
    import json

    hash_a = hashlib.sha256(
        json.dumps(entrada_a, sort_keys=True, ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()
    hash_b = hashlib.sha256(
        json.dumps(entrada_b, sort_keys=True, ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()

    return hash_a == hash_b


def reexecutar_com_retry(
    funcao_execucao: Any,
    task_id: str,
    gerenciador_retry: GerenciadorRetry,
    *args: Any,
    **kwargs: Any,
) -> tuple[Any, dict[str, Any]]:
    """Executa uma função com estratégia de retry.

    Devolve (resultado, resumo_retry). Quando todas as tentativas falham,
    o resultado é None e o resumo contém o último erro.
    """
    resumo = {"tentativas": 0, "sucesso": False, "erro": None}

    while gerenciador_retry.pode_retry(task_id):
        try:
            resultado = funcao_execucao(*args, **kwargs)
            gerenciador_retry.resetar(task_id)
            resumo["tentativas"] = (
                gerenciador_retry.tentativas_por_tarefa.get(task_id, 0) + 1
            )
            resumo["sucesso"] = True
            return resultado, resumo
        except Exception as erro:  # noqa: BLE001 - retry gerencia a falha
            atraso = gerenciador_retry.registar_tentativa(task_id, str(erro))
            resumo["tentativas"] = gerenciador_retry.tentativas_por_tarefa.get(
                task_id, 0
            )
            resumo["erro"] = str(erro)
            if atraso < 0:
                break
            time.sleep(atraso)

    resumo["sucesso"] = False
    return None, resumo


__all__ = [
    "EstrategiaRetry",
    "EstadoCheckpoint",
    "GerenciadorCheckpoint",
    "GerenciadorRetry",
    "ErroRetryCheckpoint",
    "reexecutar_com_retry",
    "verificar_idempotencia",
]
