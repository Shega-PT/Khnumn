from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "python"))

from khnumn import superficie, ortoimagem, dtm, validacao_denso, cobertura, cenario, planeador, worker  # noqa: E402


def test_triangulacao_esparsa_sem_colmap():
    r = superficie.triangulacao_esparsa("/tmp/modelo", "/tmp/saida")
    assert r["estado"] in ("NOT_AVAILABLE", "FAILED", "SUCCEEDED")


def test_reconstrucao_densa_sem_gpu():
    r = superficie.reconstrucao_densa("/tmp/base")
    assert r["estado"] in ("NOT_AVAILABLE", "FAILED", "SUCCEEDED")


def test_fundir_nuvens():
    a = np.array([[0, 0, 0], [1, 1, 1]], dtype=float)
    b = np.array([[0.1, 0.1, 0.1]], dtype=float)
    r = superficie.fundir_nuvens([a, b])
    assert r.shape[1] == 3


def test_processar_blocos():
    dados = np.arange(64, dtype=float).reshape(8, 8)
    out = superficie.processar_blocos(dados, 4, lambda b: b * 2, margem=1)
    assert out.shape == dados.shape


def test_refinamento_iterativo():
    def passagem(i):
        return {"ganho_densidade": 0.02 if i == 0 else 0.0, "taxa_outliers": 0.05}
    r = superficie.refinamento_iterativo(passagem, 5, 0.01, 0.1)
    assert r["iteracoes"] >= 1
    assert r["motivo_paragem"] in ("autoconvergencia", "max_iteracoes", "outliers")


def test_ortoimagem_sem_rasterio():
    r = ortoimagem.gerar_ortoimagem("mds.tif", "EPSG:3763")
    assert r["estado"] in ("NOT_AVAILABLE", "SUCCEEDED")


def test_dtm():
    pts = np.array([[0, 0, 0], [1, 1, 1], [2, 2, 0.1]], dtype=float)
    r = dtm.gerar_dtm(pts)
    assert r["estado"] == "SUCCEEDED"
    assert r["num_solo"] >= 1


def test_validacao_denso():
    a = np.array([[0, 0, 0], [1, 0, 0]], dtype=float)
    b = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]], dtype=float)
    r = validacao_denso.comparar_com_referencia(a, b)
    assert "estado" in r


def test_cobertura():
    coords = [(1.0, 1.0), (2.0, 2.0)]
    r = cobertura.gerar_mapa_cobertura(coords, 4, 4)
    assert r["cobertura_percent"] > 0
    assert r["furos_contagem"] >= 0


def test_cenario_classificar():
    meta = {"capture": {"position": {"source": "GNSS_EXIF"}}, "media_type": "image/tiff"}
    r = cenario.classificar_cenario(meta)
    assert r["classe"] in cenario.CLASSES
    assert r["confianca"] > 0


def test_cenario_corrigir():
    c = {"classe": "unknown", "confianca": 0.1, "razoes": []}
    r = cenario.corrigir_cenario(c, "aerial_nadir", "operador")
    assert r["classe_final"] == "aerial_nadir"
    assert r["correcao_manual"] is True


def test_planeador():
    r = planeador.planear("aerial_nadir", True, "alta", 5, 2)
    assert r["dense_path"] in ("denso_acelerador", "denso_cpu", "esparsa_delaunay")
    assert r["escolhido"] is not None
    assert r["fallback"] is not None or r["dense_path"] == "esparsa_delaunay"


def test_worker_superficie():
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "superficie.triangulacao_esparsa",
        "versao": "1.0.0",
        "parametros": {"modelo": "/tmp/m", "destino": "/tmp/s"},
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"


def test_worker_cenario():
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "cenario.classificar",
        "versao": "1.0.0",
        "parametros": {"metadados": {"capture": {"position": {"source": "GNSS_EXIF"}}}},
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"


def test_worker_planeador():
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "planeador.planear",
        "versao": "1.0.0",
        "parametros": {"cenario": "aerial_nadir", "hardware_gpu": True},
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"


def test_desvio_lod():
    a = __import__("numpy").array([[0,0,0],[1,0,0]], dtype=float)
    b = __import__("numpy").array([[0,0,0],[1.1,0,0]], dtype=float)
    r = superficie.desvio_lod(a, b)
    assert r["max_m"] > 0


def test_processar_blocos_com_orcamento_dentro():
    """Blocos processados dentro do orçamento devolvem sucesso."""
    import numpy as np
    from khnumn import superficie
    dados = np.arange(64, dtype=float).reshape(8, 8)
    res = superficie.processar_blocos_com_orcamento(
        dados, 4, lambda b: b * 2, margem=1, limite_memoria_mb=1000
    )
    assert res["excedeu_orcamento"] is False
    assert res["blocos_processados"] == 4
    assert res["pico_memoria_mb"] is not None


def test_processar_blocos_com_orcamento_excedido():
    """Alocação grande dentro da função excede o orçamento e é interrompida."""
    import numpy as np
    from khnumn import superficie
    dados = np.zeros((8, 8), dtype=float)
    def alocar(b):
        _ = np.zeros((1000, 1000), dtype=float)  # ~8 MiB por bloco
        return b
    res = superficie.processar_blocos_com_orcamento(
        dados, 4, alocar, margem=0, limite_memoria_mb=1
    )
    assert res["excedeu_orcamento"] is True
    assert res["motivo"] is not None
    assert "orçamento de memória" in res["motivo"]


def test_worker_superficie_blocos_orcado():
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "superficie.processar_blocos_orcado",
        "versao": "1.0.0",
        "parametros": {
            "dados": [[0, 1], [2, 3]],
            "tamanho_bloco": 2,
            "limite_memoria_mb": 1000,
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"
    sup = resp["metricas"]["superficie"]
    assert sup["excedeu_orcamento"] is False


def test_planeador_com_orcamento():
    """Plano de execução com orçamento fixado e decisões registadas."""
    from khnumn import plano_execucao
    plano = plano_execucao.classificar_e_planejar(
        metadados={"capture": {"position": {"source": "GNSS_EXIF"}}},
        qualidade=None,
        hardware_gpu=False,
        requisito_densidade="media",
        ensemble_samples=5,
        iteracoes_refino=2,
        limite_memoria_mb=500,
    )
    assert plano["estado"] == "aprovado"
    assert plano["limite_memoria_mb"] == 500
    assert plano["ensemble_samples"] == 5
    assert plano["iteracoes_refino"] == 2
    assert any(d["decisao"] == "caminho_denso" for d in plano["decisoes"])
    assert any(d["decisao"] == "pipeline" for d in plano["decisoes"])
    assert any(d["decisao"] == "cenario" for d in plano["decisoes"])
    # Todas as decisões têm motivo.
    for d in plano["decisoes"]:
        assert d["motivo"], f"decisão {d['decisao']} sem motivo"


def test_planeador_guardar_e_carregar(tmp_path):
    """Registo persistente do plano de execução (F5.E6)."""
    from khnumn import plano_execucao
    plano = plano_execucao.classificar_e_planejar(
        metadados={},
        qualidade=None,
        hardware_gpu=True,
        requisito_densidade="alta",
        ensemble_samples=10,
        iteracoes_refino=3,
    )
    caminho = tmp_path / "plano.json"
    plano_execucao.guardar_plano(caminho, plano)
    carregado = plano_execucao.carregar_plano(caminho)
    assert carregado is not None
    assert carregado["estado"] == plano["estado"]
    assert carregado["caminho_denso"] == plano["caminho_denso"]


def test_worker_planeador_com_orcamento():
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "planeador.com_orcamento",
        "versao": "1.0.0",
        "parametros": {
            "metadados": {"capture": {"position": {"source": "GNSS_EXIF"}}},
            "hardware_gpu": False,
            "requisito_densidade": "media",
            "ensemble_samples": 5,
            "iteracoes_refino": 2,
            "limite_memoria_mb": 500,
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"
    plano = resp["metricas"]["planeador"]
    assert plano["estado"] == "aprovado"
    assert plano["limite_memoria_mb"] == 500


def test_worker_planeador_guardar_plano(tmp_path):
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "planeador.guardar_plano",
        "versao": "1.0.0",
        "parametros": {
            "caminho": str(tmp_path / "plano.json"),
            "plano": {"estado": "aprovado", "cenario": "aerial_nadir"},
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"
