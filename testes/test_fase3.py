"""Testes da Fase 3: controlo, marcas e validação."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "python"))

from khnumn import controle, marcas, validacao, worker, raster  # noqa: E402


def test_ponto_sem_covariancia_e_erro():
    ponto = {
        "id": "cp1", "role": "control", "crs": "EPSG:3763",
        "coordinates": [0.0, 0.0, 0.0], "units": {"horizontal": "m", "vertical": "m"},
        "method": "RTK", "instrument": "X", "measured_utc": "2026-01-01T00:00:00Z",
        "operator": "t",
    }
    with pytest.raises(controle.ErroControle):
        controle._validar_ponto(ponto)


def test_ingerir_pontos_valida(tmp_path):
    dados = [{
        "id": "cp1", "role": "control", "crs": "EPSG:3763",
        "coordinates": [1.0, 2.0, 3.0], "units": {"horizontal": "m", "vertical": "m"},
        "covariance": {"units": "m2", "matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
        "method": "RTK", "instrument": "X", "measured_utc": "2026-01-01T00:00:00Z",
        "operator": "t",
    }, {
        "id": "ck1", "role": "checkpoint", "crs": "EPSG:3763",
        "coordinates": [4.0, 5.0, 6.0], "units": {"horizontal": "m", "vertical": "m"},
        "covariance": {"units": "m2", "matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
        "method": "RTK", "instrument": "X", "measured_utc": "2026-01-01T00:00:00Z",
        "operator": "t",
    }]
    caminho = tmp_path / "pontos.json"
    caminho.write_text(json.dumps(dados))
    pontos = controle.ingerir_pontos(caminho)
    assert len(pontos) == 2
    controlo, checkpoints = controle.separar_papeis(pontos)
    assert len(controlo) == 1
    assert len(checkpoints) == 1
    # Exclusão imposta por carregamento.
    assert controle.pontos_para_ajuste(pontos) == controlo


def test_similaridade_identidade():
    pts = np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.], [1., 1., 1.]])
    r, s, t = controle.similaridade_7_parametros(pts, pts)
    assert s == pytest.approx(1.0)
    np.testing.assert_allclose(r, np.eye(3), atol=1e-9)
    np.testing.assert_allclose(t, np.zeros(3), atol=1e-9)


def test_ransac_similaridade():
    origem = np.array([[0.,0,0],[1,0,0],[0,1,0],[1,1,0],[5,5,5]])
    destino = origem.copy()
    destino[:4] += np.array([10., 20, 30])
    res = controle.ransac_similaridade(origem, destino)
    assert res["num_inliers"] >= 4


def test_ensemble_propaga():
    pontos = [{
        "id": "cp1", "role": "control", "crs": "EPSG:3763",
        "coordinates": [1.0, 2.0, 3.0], "units": {"horizontal": "m", "vertical": "m"},
        "covariance": {"units": "m2", "matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
        "method": "RTK", "instrument": "X", "measured_utc": "2026-01-01T00:00:00Z",
        "operator": "t",
    }]

    def ajuste(pts):
        return [p["coordinates"] for p in pts]

    res = controle.propagar_ensemble(pontos, ajuste, n_amostras=5, semente=1)
    assert res["n_amostras"] == 5
    assert len(res["resultados"]) == 5


def test_projetar_ponto():
    K = np.array([[500., 0, 320], [0, 500, 240], [0, 0, 1]])
    R = np.eye(3)
    t = np.array([0., 0., 5.])
    u, v = marcas.projetar_ponto(np.array([1., 1., 0.]), R, t, K)
    assert u == pytest.approx(320 + 500 * 1/5)
    assert v == pytest.approx(240 + 500 * 1/5)


def test_refinar_centroide_retorna_erro():
    img = np.zeros((32, 32), dtype=np.uint8)
    img[14:18, 14:18] = 200
    u, v, erro = marcas.refinar_centroide(img, 16, 16, raio=8)
    assert isinstance(erro, float)


def test_verificar_acquisibilidade_fora():
    img = np.zeros((32, 32), dtype=np.uint8)
    res = marcas.verificar_acquisibilidade(img, (100, 100))
    assert res["utilizavel"] is False


def test_metricas_exatidao():
    est = np.array([[0., 0, 0], [1., 0, 0]])
    ref = np.array([[0., 0, 0], [0., 0, 0]])
    m = validacao.metricas_exatidao(est, ref)
    assert m["n"] == 2
    assert m["rmse_horizontal_m"] > 0


def test_estado_aceitacao_pass():
    m = {"rmse_horizontal_m": 0.5, "rmse_vertical_m": 0.5, "erro_medio_horizontal_m": 0.0,
         "num_blunders": 0}
    e = validacao.estado_aceitacao(m, 1.0, 1.0)
    assert e["estado"] == "PASS"


def test_decompor_incerteza():
    r = validacao.decompor_incerteza(1.0, 1.0)
    assert r["incerteza_total"] == pytest.approx(np.sqrt(2))
    assert r["fracao_controlo"] == pytest.approx(1 / (2**0.5))


def test_worker_controlo_ingerir(tmp_path):
    dados = [{
        "id": "cp1", "role": "control", "crs": "EPSG:3763",
        "coordinates": [1.0, 2.0, 3.0], "units": {"horizontal": "m", "vertical": "m"},
        "covariance": {"units": "m2", "matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
        "method": "RTK", "instrument": "X", "measured_utc": "2026-01-01T00:00:00Z",
        "operator": "t",
    }]
    caminho = tmp_path / "p.json"
    caminho.write_text(__import__("json").dumps(dados))
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "controlo.ingerir",
        "versao": "1.0.0",
        "parametros": {"caminho": str(caminho)},
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"


def test_revisar_deteccoes():
    det = [{"posicao_refinada": [1, 1], "aceite": True}, {"posicao_refinada": [2, 2], "aceite": False}]
    rev = marcas.revisar_deteccoes(det, {0: False, 1: True})
    assert rev[0]["aceite_final"] is False
    assert rev[1]["aceite_final"] is True
    assert rev[0]["revisao_humana"] == "rejeitada"


def test_raster_metricas():
    coords = [(1.0, 1.0), (2.0, 2.0), (2.0, 2.0)]
    valores = [1.0, 2.0, 4.0]
    r = raster.rasterizar_pontos(coords, valores, 4, 4)
    m = raster.metricas_raster(r)
    assert m["n"] == 2  # dois pixeis distintos
    assert m["maximo"] == 3.0  # media de 2 e 4
    assert m["sem_observacao_px"] == 14


def test_worker_raster(tmp_path):
    import json
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "raster.residuos",
        "versao": "1.0.0",
        "parametros": {"coords": [[1, 1], [2, 2]], "valores": [1.0, 2.0], "largura": 4, "altura": 4},
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"


def test_validar_ponto_schema():
    ponto = {
        "id": "cp1", "role": "control", "crs": "EPSG:3763",
        "coordinates": [1.0, 2.0, 3.0], "units": {"horizontal": "m", "vertical": "m"},
        "covariance": {"units": "m2", "matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
        "method": "RTK", "instrument": "X", "measured_utc": "2026-01-01T00:00:00Z",
        "operator": "t",
    }
    controle.validar_ponto_schema(ponto)  # não deve lançar


def test_ransac_usa_pesos():
    origem = np.array([[0., 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]], dtype=float)
    destino = origem + np.array([10., 0, 0])
    covs = np.array([np.eye(3) * 0.01 for _ in range(4)])
    res = controle.ransac_similaridade(origem, destino, covariancias=covs)
    assert res["num_inliers"] >= 3


def test_aplicar_priors_gnss(tmp_path):
    import os
    base = tmp_path / "base"
    base.mkdir()
    db_path = base / "database.db"
    # criar base de dados mínima com imagem
    import pycolmap
    db = pycolmap.Database.open(str(db_path))
    cam = pycolmap.Camera(model=pycolmap.CameraModelId.SIMPLE_PINHOLE, width=8, height=8, params=[5, 4, 4])
    cam.camera_id = 1
    db.write_camera(cam)
    img = pycolmap.Image(name="a.jpg", camera_id=1)
    db.write_image(img)
    db.close()
    priors = [{"imagem": "a.jpg", "posicao": [1.0, 2.0, 3.0],
               "covariancia": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}]
    n = controle.aplicar_priors_gnss(str(base), priors)
    assert n == 1


def test_ajuste_constragido_pontos_constantes():
    """Ajuste constrangido fixa pontos como constantes e devolve sucesso."""
    import numpy as np
    from khnumn import ajuste
    pontos = np.array([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.], [1., 1., 0.]], dtype=float)
    obs = np.array([[0, 0., 0.], [1, 1., 0.], [2, 0., 1.], [3, 1., 1.]], dtype=float)
    param = ajuste.ParametrosAjuste(
        versao_algoritmo="1.0.0",
        pontos_constantes_ids=[0],
        gauge_pontos=[0, 1, 2],
        fixar_gauge=True,
    )
    res = ajuste.ajustar_constragido(pontos, obs, param)
    assert res.estado == "SUCCEEDED"
    assert res.num_pontos_constantes == 1
    assert res.gauge_fixado is True


def test_ajuste_constragido_sem_incognitas():
    """Quando todos os pontos sao constantes, nada a ajustar."""
    import numpy as np
    from khnumn import ajuste
    pontos = np.array([[0., 0., 0.], [1., 0., 0.]], dtype=float)
    obs = np.array([[0, 0., 0.], [1, 1., 0.]], dtype=float)
    param = ajuste.ParametrosAjuste(pontos_constantes_ids=[0, 1])
    res = ajuste.ajustar_constragido(pontos, obs, param)
    assert res.estado == "SUCCEEDED"
    assert res.num_pontos_constantes == 2


def test_worker_controlo_ajustar():
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "controlo.ajustar",
        "versao": "1.0.0",
        "parametros": {
            "modelo": "/tmp/modelo",
            "versao_algoritmo": "1.0.0",
            "pontos_controlo": [
                {"coordinates": [0.0, 0.0, 0.0]},
                {"coordinates": [1.0, 0.0, 0.0]},
            ],
            "pontos_constantes_ids": [0],
            "gauge_pontos": [0, 1],
            "fixar_gauge": True,
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"
    assert resp["metricas"]["controlo"]["ajuste"]["motor"] in ("pycolmap", "numerico")


def test_worker_controlo_ensemble_ajuste_real():
    """Ensemble usa funcao de ajuste real, nao identidade."""
    pontos = [{
        "id": "cp1", "role": "control", "crs": "EPSG:3763",
        "coordinates": [1.0, 2.0, 3.0], "units": {"horizontal": "m", "vertical": "m"},
        "covariance": {"units": "m2", "matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
        "method": "RTK", "instrument": "X", "measured_utc": "2026-01-01T00:00:00Z",
        "operator": "t",
    }]
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "controlo.ensemble",
        "versao": "1.0.0",
        "parametros": {"pontos": pontos, "n_amostras": 3, "semente": 1},
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"
    ens = resp["metricas"]["controlo"]["ensemble"]
    assert ens["n_amostras"] == 3
    assert "dispersao" in ens
