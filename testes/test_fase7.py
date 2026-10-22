"""Testes da Fase 7: distribuição."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "python"))

from khnumn import (
    persistencia,
    reprodutibilidade,
    retry_checkpoint,
    seguranca,
    scheduler,
    worker,
    worker_remoto,
)  # noqa: E402


# ============================================================================
# F7.E1 — Persistência do DAG
# ============================================================================

def test_persistir_e_recuperar_grafo(tmp_path):
    nos = [
        {
            "tarefa": {
                "task_id": "t-1",
                "algoritmo": "metadados.extrair",
                "versao": "1.0.0",
                "parametros": {},
                "entradas": [],
                "saidas": [],
                "estado": "SUCCEEDED",
                "motivo": None,
                "metricas": {},
                "limite_memoria_mb": 500,
                "pico_memoria_mb": 100,
                "inicio_utc": "2026-01-01T00:00:00Z",
                "fim_utc": "2026-01-01T00:01:00Z",
                "semente": 0,
                "versao_ambiente": "ref",
            },
            "depende_de": [],
        }
    ]
    caminho = tmp_path / "grafo.json"
    persistencia.persistir_grafo(nos, caminho)
    dados = persistencia.recuperar_grafo(caminho)
    assert dados["versao_formato"] == "1.0.0"
    assert len(dados["nos"]) == 1
    assert dados["nos"][0]["task_id"] == "t-1"


# ============================================================================
# F7.E2 — Scheduler CPU-first
# ============================================================================

def test_scheduler_respeita_orcamento_memoria():
    recursos = scheduler.RecursosDisponiveis(
        memoria_total_mb=1024,
        memoria_orcamento_mb=100,
        max_workers=2,
    )
    sch = scheduler.SchedulerCPUFirst(recursos)
    sch.registar_tarefa("t1", "alg1", memoria_estimada_mb=50, dependencias=[])
    sch.registar_tarefa("t2", "alg2", memoria_estimada_mb=80, dependencias=[])
    assert sch.proxima_tarefa_pronta() == "t1"
    sch.iniciar_tarefa("t1")
    # t2 não cabe com t1 em uso (50 + 80 = 130 > 100)
    assert sch.proxima_tarefa_pronta() is None


# ============================================================================
# F7.E3 — Workers remotos
# ============================================================================

def test_pool_workers_escolhe_worker():
    pool = worker_remoto.PoolWorkers()
    pool.registar_worker(
        "w1", 1024, 500, 2, tem_acelerador=False
    )
    pool.registar_worker(
        "w2", 2048, 1500, 4, tem_acelerador=False
    )
    wid = pool.escolher_worker(memoria_estimada_mb=100, requer_acelerador=False)
    assert wid in ("w1", "w2")


def test_pool_workers_nao_bloqueia_sem_acelerador():
    pool = worker_remoto.PoolWorkers()
    pool.registar_worker("w_cpu", 1024, 500, 2, tem_acelerador=False)
    # Tarefa sem requerimento de acelerador deve ser despachada.
    wid = pool.despachar_para_worker("t-1", memoria_estimada_mb=100, requer_acelerador=False)
    assert wid == "w_cpu"


# ============================================================================
# F7.E4 — Retry e checkpoints
# ============================================================================

def test_retry_max_tentativas():
    ger = retry_checkpoint.GerenciadorRetry(
        retry_checkpoint.EstrategiaRetry(max_tentativas=2)
    )
    assert ger.pode_retry("t1") is True
    ger.registar_tentativa("t1", "erro 1")
    assert ger.pode_retry("t1") is True
    ger.registar_tentativa("t1", "erro 2")
    assert ger.pode_retry("t1") is False


def test_checkpoint_gravar_e_verificar():
    ger = retry_checkpoint.GerenciadorCheckpoint()
    cp = ger.gravar_checkpoint("t1", "alg", "1.0.0", "passo1", {"dado": 1})
    assert cp.task_id == "t1"
    assert ger.verificar_integridade("t1") is True


def test_verificar_idempotencia():
    a = {"algoritmo": "a", "parametros": {"x": 1}}
    b = {"algoritmo": "a", "parametros": {"x": 1}}
    c = {"algoritmo": "a", "parametros": {"x": 2}}
    assert retry_checkpoint.verificar_idempotencia(a, b) is True
    assert retry_checkpoint.verificar_idempotencia(a, c) is False


# ============================================================================
# F7.E5 — Reprodutibilidade
# ============================================================================

def test_nivel_reprodutibilidade_cpu_local():
    nivel = reprodutibilidade.nivel_reprodutibilidade("cpu_local")
    assert nivel.nivel == "exato"
    assert nivel.tolerancia_absoluta == 1e-9


def test_comparar_execucoes_consistentes():
    a = {"rmse": 0.5, "pontos": 100}
    b = {"rmse": 0.5000001, "pontos": 100}
    nivel = reprodutibilidade.NivelReprodutibilidade(
        nivel="aproximado",
        tolerancia_absoluta=1e-4,
        tolerancia_relativa=1e-4,
    )
    r = reprodutibilidade.comparar_execucoes(a, b, nivel)
    assert r.consistentes is True


def test_comparar_execucoes_inconsistentes():
    a = {"rmse": 0.5}
    b = {"rmse": 1.0}
    nivel = reprodutibilidade.NivelReprodutibilidade(
        nivel="aproximado",
        tolerancia_absoluta=1e-4,
        tolerancia_relativa=1e-4,
    )
    r = reprodutibilidade.comparar_execucoes(a, b, nivel)
    assert r.consistentes is False


# ============================================================================
# F7.E6 — Segurança
# ============================================================================

def test_autenticar_pedido_sucesso():
    ger = seguranca.GerenciadorSeguranca()
    ger.registar_credenciais("operador", "segredo123", ["ler_projeto"])
    pedido = ger.autenticar_pedido("operador", "segredo123", "ler_projeto")
    assert pedido.autenticado is True
    assert pedido.identificador == "operador"


def test_autenticar_pedido_falha_permissao():
    ger = seguranca.GerenciadorSeguranca()
    ger.registar_credenciais("operador", "segredo123", ["ler_projeto"])
    pedido = ger.autenticar_pedido("operador", "segredo123", "escrever_produto")
    assert pedido.autenticado is False
    assert pedido.motivo is not None


def test_proteger_e_verificar_transporte():
    ger = seguranca.GerenciadorSeguranca()
    pacote = ger.proteger_transporte(b"mensagem secreta")
    msg = ger.verificar_transporte(pacote)
    assert msg == b"mensagem secreta"


# ============================================================================
# Testes via worker (contrato)
# ============================================================================

def test_worker_scheduler_agendar():
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "scheduler.agendar",
        "versao": "1.0.0",
        "parametros": {
            "tarefas": [
                {"task_id": "t1", "algoritmo": "a", "memoria_estimada_mb": 50, "depende_de": []},
                {"task_id": "t2", "algoritmo": "b", "memoria_estimada_mb": 50, "depende_de": ["t1"]},
            ],
            "recursos": {"memoria_total_mb": 1024, "memoria_orcamento_mb": 500},
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"


def test_worker_worker_remoto_despachar():
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "worker_remoto.despachar",
        "versao": "1.0.0",
        "parametros": {
            "task_id": "t-1",
            "memoria_estimada_mb": 100,
            "requer_acelerador": False,
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"


def test_worker_checkpoint_gravar():
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "checkpoint.gravar",
        "versao": "1.0.0",
        "parametros": {
            "task_id": "t1",
            "algoritmo": "metadados.extrair",
            "versao": "1.0.0",
            "passo": "inicial",
            "dados": {"progresso": 0.5},
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"


def test_worker_reprodutibilidade_comparar():
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "reprodutibilidade.comparar",
        "versao": "1.0.0",
        "parametros": {
            "resultado_a": {"rmse": 0.5, "pontos": 100},
            "resultado_b": {"rmse": 0.5000001, "pontos": 100},
            "backend_outro": "cpu_distribuido",
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"


def test_worker_seguranca_autenticar():
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "seguranca.autenticar",
        "versao": "1.0.0",
        "parametros": {
            "identificador": "op",
            "segredo": "segredo123",
            "permissao_necessaria": "ler_projeto",
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"
