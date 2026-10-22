"""Testes da Fase 8: fusão heterogénea avançada (continuação)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "python"))

from khnumn import (
    alinhamento,
    benchmark_fusao,
    compatibilidade_temporal,
    decisao_evidencia,
    verificacao_multivista,
    worker,
)  # noqa: E402


# ============================================================================
# F8.E2 — Alinhamento de fontes
# ============================================================================

def test_alinhar_fontes_similaridade():
    origem = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float)
    destino = np.array([[10, 20, 30], [11, 20, 30], [10, 21, 30]], dtype=float)
    r = alinhamento.alinhar_fontes(origem.tolist(), destino.tolist())
    assert r.estado == "SUCCEEDED"
    assert r.pontos_usados == 3


def test_alinhar_fontes_pontos_insuficientes():
    origem = [[0, 0, 0], [1, 0, 0]]
    destino = [[0, 0, 0], [1, 0, 0]]
    r = alinhamento.alinhar_fontes(origem, destino, modelo_tipo="similaridade_7p")
    assert r.estado == "DEGENERADO"


def test_detetar_deformacao_nao_rigida():
    from khnumn.alinhamento import ResultadoAlinhamento, ModeloGeometricoAlinhamento
    r = ResultadoAlinhamento(
        fonte_origem="a",
        fonte_destino="b",
        modelo=ModeloGeometricoAlinhamento(tipo="similaridade_7p", parametros={}),
        erro_residual_medio=5.0,
        pontos_usados=3,
    )
    assert alinhamento.detetar_deformacao_nao_rigida(r, limiar_deformacao_m=1.0) is True


# ============================================================================
# F8.E3 — Compatibilidade temporal
# ============================================================================

def test_calcular_janela_compatibilidade_dentro():
    j = compatibilidade_temporal.calcular_janela_compatibilidade(
        "2026-01-01T12:00:00Z",
        "2026-01-01T12:00:30Z",
        tolerancia_temporal_s=60.0,
    )
    assert j.dentro_da_janela is True
    assert j.mudança_provavel is False


def test_calcular_janela_compatibilidade_fora():
    j = compatibilidade_temporal.calcular_janela_compatibilidade(
        "2026-01-01T12:00:00Z",
        "2026-01-01T13:00:00Z",
        tolerancia_temporal_s=60.0,
    )
    assert j.dentro_da_janela is False
    assert j.mudança_provavel is True


def test_marcar_mudancas_provaveis():
    fontes = [
        compatibilidade_temporal.FonteTemporal("f1", "2026-01-01T12:00:00Z", "imagem"),
        compatibilidade_temporal.FonteTemporal("f2", "2026-01-01T13:00:00Z", "lidar"),
    ]
    r = compatibilidade_temporal.marcar_mudancas_provaveis(fontes, 60.0)
    assert "f2" in r["mudancas_provaveis"]
    assert "f1" in r["fontes_compatíveis"]


# ============================================================================
# F8.E4 — Regra de decisão sobre evidência
# ============================================================================

def test_aplicar_regras_aceitacao():
    regras = decisao_evidencia.RegrasDecisao()
    regras.adicionar_regra_aceitacao("consistencia_minima", 0.5, "consistencia")
    decisao = decisao_evidencia.aplicar_regras_decisao(
        {"consistencia": 0.8}, regras
    )
    assert decisao.estado == "aceito"


def test_aplicar_regras_rejeicao():
    regras = decisao_evidencia.RegrasDecisao()
    regras.adicionar_regra_rejeicao("consistencia_baixa", 0.5, "consistencia", "muito baixa")
    decisao = decisao_evidencia.aplicar_regras_decisao(
        {"consistencia": 0.2}, regras
    )
    assert decisao.estado == "rejeitado"


def test_testar_contra_referencia():
    regras = decisao_evidencia.RegrasDecisao()
    regras.adicionar_regra_aceitacao("c", 0.5, "consistencia")
    ref = [
        {"evidencia": {"consistencia": 0.8}, "estado_esperado": "aceito"},
        {"evidencia": {"consistencia": 0.2}, "estado_esperado": "rejeitado"},
    ]
    r = decisao_evidencia.testar_contra_referencia(regras, ref)
    assert r["total_casos"] == 2


# ============================================================================
# F8.E5 — Benchmarks contra baselines
# ============================================================================

def test_comparar_com_baseline_melhoria():
    base = benchmark_fusao.Baseline(
        nome="sfm_referencia",
        conjunto_dados="ETH3D",
        metrica_primaria="rmse_horizontal_m",
        valor_referencia=0.5,
    )
    r = benchmark_fusao.comparar_com_baseline(0.3, base, "menor_e_melhor")
    assert r.melhoria is True
    assert r.critério_inovacao_propria is True


def test_comparar_com_baseline_sem_melhoria():
    base = benchmark_fusao.Baseline(
        nome="sfm_referencia",
        conjunto_dados="ETH3D",
        metrica_primaria="rmse_horizontal_m",
        valor_referencia=0.5,
    )
    r = benchmark_fusao.comparar_com_baseline(0.8, base, "menor_e_melhor")
    assert r.melhoria is False


# ============================================================================
# F8.E6 — Verificação multivista
# ============================================================================

def test_acumular_profundidade_sem_rasters():
    sr = verificacao_multivista.SubRegiao(
        identificador="sr1",
        coordenadas=[0, 0, 10, 10],
        num_vistas_observadoras=0,
    )
    resultado = verificacao_multivista.acumular_profundidade_por_subregiao(
        [], [sr]
    )
    assert resultado[0].estado == "sem_dados"


def test_comparar_referencia_laser():
    import numpy as np
    # Rasters com dados de profundidade que coincidem com a referência laser
    rasters = [
        {
            "dados": np.full((100, 100), 10.0, dtype=float).tolist(),
            "transformacao": {"scale": [1, 1]},
        },
        {
            "dados": np.full((100, 100), 10.0, dtype=float).tolist(),
            "transformacao": {"scale": [1, 1]},
        },
    ]
    ref = verificacao_multivista.ReferenciaLaser(
        profundidade_por_regiao={"sr1": 10.0},
        limiar_inconsistencia_m=0.05,
    )
    res = verificacao_multivista.comparar_referencia_laser(
        verificacao_multivista.acumular_profundidade_por_subregiao(
            rasters,
            [
                verificacao_multivista.SubRegiao(
                    identificador="sr1",
                    coordenadas=[0, 0, 10, 10],
                    num_vistas_observadoras=0,
                    profundidade_media_m=None,
                    estado="sem_dados",
                )
            ],
        ),
        ref,
    )
    assert res.num_regioes_validas >= 1
    assert res.estado == "SUCCEEDED"


# ============================================================================
# Testes via worker (contrato)
# ============================================================================

def test_worker_alinhamento_fontes():
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "alinhamento.fontes",
        "versao": "1.0.0",
        "parametros": {
            "pontos_origem": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
            "pontos_destino": [[10, 20, 30], [11, 20, 30], [10, 21, 30]],
            "modelo_tipo": "similaridade_7p",
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"


def test_worker_benchmark_comparar():
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "benchmark_fusao.comparar",
        "versao": "1.0.0",
        "parametros": {
            "valor_obtido": 0.3,
            "baseline": {
                "nome": "ref",
                "conjunto_dados": "ETH3D",
                "metrica_primaria": "rmse",
                "valor_referencia": 0.5,
            },
            "direcao_melhoria": "menor_e_melhor",
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"


def test_worker_verificacao_multivista():
    import numpy as np
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "verificacao_multivista.acumular",
        "versao": "1.0.0",
        "parametros": {
            "rasters_profundidade": [
                {
                    "dados": np.full((100, 100), 10.0, dtype=float).tolist(),
                    "transformacao": {"scale": [1, 1]},
                },
                {
                    "dados": np.full((100, 100), 10.0, dtype=float).tolist(),
                    "transformacao": {"scale": [1, 1]},
                },
            ],
            "sub_regioes": [
                {
                    "identificador": "sr1",
                    "coordenadas": [0, 0, 10, 10],
                    "num_vistas_observadoras": 0,
                    "estado": "sem_dados",
                }
            ],
            "referencia_laser": {
                "profundidade_por_regiao": {"sr1": 10.0},
                "limiar_inconsistencia_m": 0.05,
            },
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"
