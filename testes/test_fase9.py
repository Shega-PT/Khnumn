"""Testes da Fase 9: rasterização de superfície e registo de produtos."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "python"))

from khnumn import (
    catalogo,
    cog,
    rasterizador,
    renderizacao,
    residuos,
    worker,
)  # noqa: E402


# ============================================================================
# F9.E1 — Registo de produtos no catálogo
# ============================================================================

def test_catalogo_registar_e_consultar_produto(tmp_path):
    """Regista e consulta um produto no catálogo (F9.E1)."""
    caminho = tmp_path / "catalogo.sqlite"
    cat = catalogo.Catalogo(caminho)
    cat.abrir()

    registo = catalogo.RegistoProduto(
        product_id="p-001",
        tipo="nuvem_esparsa",
        formato="ply",
        source_uri="dados/nuvem_esparsa.ply",
        sha256="a" * 64,
        crs="EPSG:3763",
        crs_declaracao="CRS projetado nacional",
        unidades={"horizontal": "m", "vertical": "m"},
        resolucao={"horizontal": 0.05, "vertical": 0.05, "unit": "m"},
        data_kind="estimado",
        incerteza=catalogo.IncertezaProduto(
            estimada=True,
            valor=0.15,
            unidade="m",
            metodo="ensemble",
        ),
        proveniencia={
            "source_uri": "dados/imagens/",
            "operacoes": [
                catalogo.RegistoProveniente(
                    task_id="t-abc123",
                    algoritmo="sfm.mapear",
                    versao="1.0.0",
                    entradas=["dados/imagem1.jpg", "dados/imagem2.jpg"],
                )
            ],
            "versoes": {"khnumn": "0.1.0", "colmap": "3.8"},
        },
    )
    cat.gravar_produto(registo)

    lido = cat.produto("p-001")
    assert lido is not None
    assert lido.product_id == "p-001"
    assert lido.tipo == "nuvem_esparsa"
    assert lido.formato == "ply"
    assert lido.crs == "EPSG:3763"
    assert lido.incerteza is not None
    assert lido.incerteza.estimada is True
    assert lido.incerteza.valor == 0.15
    assert len(lido.proveniencia["operacoes"]) == 1

    todos = cat.listar_produtos()
    assert len(todos) == 1
    cat.fechar()


def test_catalogo_produto_sem_crs_declara_ausencia(tmp_path):
    """Produto sem CRS deve declarar a ausência (F9.E1)."""
    caminho = tmp_path / "catalogo2.sqlite"
    cat = catalogo.Catalogo(caminho)
    cat.abrir()

    registo = catalogo.RegistoProduto(
        product_id="p-raster",
        tipo="mapa_cobertura",
        formato="cog",
        source_uri="dados/mapa_cobertura.tif",
        sha256="b" * 64,
        crs=None,
        crs_declaracao="raster em grelha de camara, sem CRS geográfico",
        unidades={"horizontal": "píxeis", "vertical": "píxeis"},
        resolucao={"horizontal": 1.0, "vertical": 1.0, "unit": "px"},
        campo="cobertura",
        legenda=[{"valor": 0.0, "cor": "ffffff", "rotulo": "sem dados"}],
        data_kind="estimado",
        incerteza=catalogo.IncertezaProduto(
            estimada=False,
            declaracao="incerteza não estimada para este produto",
        ),
    )
    cat.gravar_produto(registo)

    lido = cat.produto("p-raster")
    assert lido is not None
    assert lido.crs is None
    assert lido.crs_declaracao is not None
    assert lido.incerteza is not None
    assert lido.incerteza.estimada is False
    assert lido.campo == "cobertura"
    assert len(lido.legenda) == 1
    cat.fechar()


def test_catalogo_validacao_erros():
    """Validação de registos inválidos (F9.E1)."""
    # product_id vazio
    registo = catalogo.RegistoProduto(
        product_id="",
        tipo="nuvem_esparsa",
        formato="ply",
        source_uri="dados/x.ply",
        sha256="a" * 64,
        crs="EPSG:3763",
        crs_declaracao="ok",
        unidades={"horizontal": "m", "vertical": "m"},
        resolucao={"horizontal": 0.1, "vertical": 0.1, "unit": "m"},
    )
    erros = catalogo.validar_registo_produto(registo)
    assert any("product_id" in e for e in erros)

    # CRS nulo sem declaração
    registo2 = catalogo.RegistoProduto(
        product_id="p-1",
        tipo="raster",
        formato="tiff",
        source_uri="dados/x.tif",
        sha256="a" * 64,
        crs=None,
        crs_declaracao=None,
        unidades={"horizontal": "m", "vertical": "m"},
        resolucao={"horizontal": 0.1, "vertical": 0.1, "unit": "m"},
    )
    erros2 = catalogo.validar_registo_produto(registo2)
    assert any("crs_declaracao" in e for e in erros2)

    # Incerteza não estimada sem declaração
    registo3 = catalogo.RegistoProduto(
        product_id="p-2",
        tipo="raster",
        formato="tiff",
        source_uri="dados/x.tif",
        sha256="a" * 64,
        crs="EPSG:3763",
        crs_declaracao="ok",
        unidades={"horizontal": "m", "vertical": "m"},
        resolucao={"horizontal": 0.1, "vertical": 0.1, "unit": "m"},
        incerteza=catalogo.IncertezaProduto(estimada=False),
    )
    erros3 = catalogo.validar_registo_produto(registo3)
    assert any("declaracao" in e for e in erros3)


def test_worker_catalogo_registar(tmp_path):
    """Registo de produto via worker (F9.E1)."""
    caminho = tmp_path / "cat.sqlite"
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "catalogo.registar_produto",
        "versao": "1.0.0",
        "parametros": {
            "caminho_catalogo": str(caminho),
            "registo": {
                "product_id": "p-w1",
                "tipo": "ortoimagem",
                "formato": "cog",
                "source_uri": "dados/orto.tif",
                "sha256": "c" * 64,
                "crs": "EPSG:3763",
                "crs_declaracao": "CRS projetado",
                "unidades": {"horizontal": "m", "vertical": "m"},
                "resolucao": {"horizontal": 0.1, "vertical": 0.1, "unit": "m"},
                "data_kind": "estimado",
                "incerteza": {
                    "estimated": True,
                    "value": 0.2,
                    "unit": "m",
                    "method": "ensemble",
                },
                "proveniencia": {
                    "source_uri": "dados/",
                    "operacoes": [
                        {
                            "task_id": "t-1",
                            "algoritmo": "ortoimagem.gerar",
                            "versao": "1.0.0",
                            "entradas": ["dados/imagem1.jpg"],
                        }
                    ],
                    "versoes": {"khnumn": "0.1.0"},
                },
            },
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"
    assert resp["metricas"]["catalogo"]["product_id"] == "p-w1"
    assert resp["metricas"]["catalogo"]["registado"] is True


def test_worker_catalogo_consultar(tmp_path):
    """Consulta de produto via worker (F9.E1)."""
    caminho = tmp_path / "cat2.sqlite"
    # Primeiro registar
    cat = catalogo.Catalogo(caminho)
    cat.abrir()
    cat.gravar_produto(
        catalogo.RegistoProduto(
            product_id="p-consulta",
            tipo="dsm",
            formato="cog",
            source_uri="dados/dsm.tif",
            sha256="d" * 64,
            crs="EPSG:3763",
            crs_declaracao="ok",
            unidades={"horizontal": "m", "vertical": "m"},
            resolucao={"horizontal": 1.0, "vertical": 1.0, "unit": "m"},
        )
    )
    cat.fechar()

    # Depois consultar via worker
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "catalogo.consultar_produto",
        "versao": "1.0.0",
        "parametros": {
            "caminho_catalogo": str(caminho),
            "product_id": "p-consulta",
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"
    assert resp["metricas"]["catalogo"]["encontrado"] is True
    assert resp["metricas"]["catalogo"]["product_id"] == "p-consulta"

    # Produto inexistente
    pedido2 = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "catalogo.consultar_produto",
        "versao": "1.0.0",
        "parametros": {
            "caminho_catalogo": str(caminho),
            "product_id": "nao-existe",
        },
        "entradas": [],
    }
    resp2 = worker.processar(pedido2)
    assert resp2["estado"] == "SUCCEEDED"
    assert resp2["metricas"]["catalogo"]["encontrado"] is False


# ============================================================================
# F9.E2 — Rasterizador de software
# ============================================================================

def test_rasterizador_projetar_ponto():
    """Projeção de ponto 3D para imagem (F9.E2)."""
    camara = rasterizador.ParametrosCamara(
        modelo="SIMPLE_PINHOLE",
        largura=640,
        altura=480,
        params=[500.0, 320.0, 240.0],
    )
    pose = rasterizador.PoseCamara(
        rotacao=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        translacao=[0.0, 0.0, 5.0],
    )
    ponto = rasterizador.Ponto3D(x=0.0, y=0.0, z=5.0)
    u, v = rasterizador.projetar_ponto(ponto, pose, camara)
    assert u == pytest.approx(320.0)
    assert v == pytest.approx(240.0)


def test_rasterizador_ponto_atras_da_camara():
    """Ponto atrás da câmera gera erro (F9.E2)."""
    camara = rasterizador.ParametrosCamara(
        modelo="SIMPLE_PINHOLE",
        largura=640,
        altura=480,
        params=[500.0, 320.0, 240.0],
    )
    pose = rasterizador.PoseCamara(
        rotacao=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        translacao=[0.0, 0.0, 5.0],
    )
    # z=-10 com camera em z=5 => zc = -10 + 5 = -5 <= 0 (atras da camara)
    ponto = rasterizador.Ponto3D(x=0.0, y=0.0, z=-10.0)
    with pytest.raises(rasterizador.ErroRasterizador):
        rasterizador.projetar_ponto(ponto, pose, camara)


def test_rasterizar_pontos_classe_sem_dados():
    """Rasterização com classe sem dados explícita (F9.E2)."""
    camara = rasterizador.ParametrosCamara(
        modelo="SIMPLE_PINHOLE",
        largura=640,
        altura=480,
        params=[500.0, 320.0, 240.0],
    )
    pose = rasterizador.PoseCamara(
        rotacao=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        translacao=[0.0, 0.0, 5.0],
    )
    pontos = [rasterizador.Ponto3D(x=0.0, y=0.0, z=5.0)]
    observacoes = [rasterizador.Observacao(ponto_id=0, u=320.0, v=240.0)]
    valores = [1.0]

    raster = rasterizador.rasterizar_pontos_observados(
        pontos, observacoes, camara, pose, 640, 480, valores, "media"
    )

    # O pixel projetado tem o valor 1.0
    idx = 240 * 640 + 320
    assert raster.valores[idx] == pytest.approx(1.0)

    # Todos os outros são NaN (sem dados)
    sem_dados = sum(1 for v in raster.valores if np.isnan(v))
    assert sem_dados == (640 * 480) - 1


def test_raster_hash_deterministico():
    """Hash de raster é determinístico (F9.E2)."""
    camara = rasterizador.ParametrosCamara(
        modelo="SIMPLE_PINHOLE",
        largura=640,
        altura=480,
        params=[500.0, 320.0, 240.0],
    )
    pose = rasterizador.PoseCamara(
        rotacao=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        translacao=[0.0, 0.0, 5.0],
    )
    pontos = [rasterizador.Ponto3D(x=1.0, y=2.0, z=5.0)]
    observacoes = [rasterizador.Observacao(ponto_id=0, u=420.0, v=340.0)]
    valores = [3.14]

    r1 = rasterizador.rasterizar_pontos_observados(
        pontos, observacoes, camara, pose, 640, 480, valores, "media"
    )
    r2 = rasterizador.rasterizar_pontos_observados(
        pontos, observacoes, camara, pose, 640, 480, valores, "media"
    )
    assert rasterizador.hash_raster(r1) == rasterizador.hash_raster(r2)


def test_worker_rasterizar_pontos():
    """Rasterização de pontos via worker (F9.E2)."""
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "rasterizador.pontos",
        "versao": "1.0.0",
        "parametros": {
            "pontos": [{"x": 0.0, "y": 0.0, "z": 5.0}],
            "observacoes": [{"ponto_id": 0, "u": 320.0, "v": 240.0}],
            "camara": {
                "modelo": "SIMPLE_PINHOLE",
                "largura": 640,
                "altura": 480,
                "params": [500.0, 320.0, 240.0],
            },
            "pose": {
                "rotacao": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                "translacao": [0.0, 0.0, 5.0],
            },
            "largura": 640,
            "altura": 480,
            "valor_por_ponto": [1.0],
            "agregacao": "media",
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"
    ras = resp["metricas"]["rasterizador"]
    assert ras["largura"] == 640
    assert ras["altura"] == 480


# ============================================================================
# F9.E3 — Publicação de COG
# ============================================================================

def test_cog_publicar_sem_rasterio(tmp_path):
    """Publicação de COG sem rasterido retorna NOT_AVAILABLE (F9.E3)."""
    caminho_cog = tmp_path / "saida.cog"
    interm = cog.RasterIntermediario(
        caminho=tmp_path / "inter.tif",
        hash_sha256="e" * 64,
        largura=100,
        altura=100,
        crs="EPSG:3763",
        nodata=-9999.0,
        campos={},
    )
    publicado = cog.publicar_cog(interm, caminho_cog)
    assert publicado.caminho == caminho_cog
    assert publicado.largura == 100
    assert publicado.altura == 100
    assert "erro" in publicado.linhagem
    assert "rasterio nao instalado" in publicado.linhagem["erro"]


def test_worker_cog_publicar(tmp_path):
    """Publicação de COG via worker (F9.E3)."""
    caminho_cog = tmp_path / "saida.cog"
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "cog.publicar",
        "versao": "1.0.0",
        "parametros": {
            "raster_intermediario": {
                "caminho": str(tmp_path / "inter.tif"),
                "hash_sha256": "e" * 64,
                "largura": 100,
                "altura": 100,
                "crs": "EPSG:3763",
                "nodata": -9999.0,
                "campos": {},
            },
            "caminho_cog": str(caminho_cog),
            "compressao": "DEFLATE",
            "overviews": [2, 4, 8],
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"
    cog_resp = resp["metricas"]["cog"]
    assert cog_resp["largura"] == 100
    assert cog_resp["altura"] == 100
    assert "linhagem" in cog_resp


# ============================================================================
# F9.E4 — Renderização multivista determinística
# ============================================================================

def test_renderizar_sequencia_deterministica():
    """Renderização multivista é determinística (F9.E4)."""
    poses = [
        {"timestamp_s": 0.0, "translacao": [0.0, 0.0, 5.0]},
        {"timestamp_s": 0.1, "translacao": [0.1, 0.0, 5.0]},
    ]

    def funcao_profundidade(indice, pose, res):
        largura, altura = res
        return [[5.0 for _ in range(largura)] for _ in range(altura)]

    seq1 = renderizacao.renderizar_sequencia(
        poses, (64, 64), funcao_profundidade, semente=42
    )
    seq2 = renderizacao.renderizar_sequencia(
        poses, (64, 64), funcao_profundidade, semente=42
    )

    assert seq1.hash_sequencia == seq2.hash_sequencia
    assert seq1.deterministico is True
    assert len(seq1.frames) == 2


def test_verificar_determinismo():
    """Verificação de determinismo entre sequências (F9.E4)."""
    poses = [{"timestamp_s": 0.0, "translacao": [0.0, 0.0, 5.0]}]

    def fp(indice, pose, res):
        largura, altura = res
        return [[5.0 for _ in range(largura)] for _ in range(altura)]

    seq1 = renderizacao.renderizar_sequencia(poses, (32, 32), fp, semente=1)
    seq2 = renderizacao.renderizar_sequencia(poses, (32, 32), fp, semente=1)
    assert renderizacao.verificar_determinismo(seq1, seq2) is True


def test_worker_renderizar_sequencia():
    """Renderização multivista via worker (F9.E4)."""
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "renderizacao.sequencia",
        "versao": "1.0.0",
        "parametros": {
            "poses": [
                {"timestamp_s": 0.0, "translacao": [0.0, 0.0, 5.0]},
                {"timestamp_s": 0.1, "translacao": [0.1, 0.0, 5.0]},
            ],
            "resolucao": [64, 64],
            "semente": 42,
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"
    ren = resp["metricas"]["renderizacao"]
    assert ren["num_frames"] == 2
    assert ren["deterministico"] is True
    assert "hash_sequencia" in ren


# ============================================================================
# F9.E2 — Rasterizador via worker
# ============================================================================

def test_worker_raster_hash():
    """Hash de raster via worker (F9.E2)."""
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "rasterizador.hash",
        "versao": "1.0.0",
        "parametros": {
            "raster": {
                "largura": 4,
                "altura": 4,
                "valores": [1.0, 2.0, 3.0, 4.0] * 4,
                "transformacao": [0.0, 1.0, 0.0, 0.0, 0.0, -1.0],
            }
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"
    assert "hash" in resp["metricas"]["rasterizador"]


# ============================================================================
# Etapas desbloqueadas pela Fase 9
# ============================================================================

# --- F3.E13 — Campo de resíduos de reprojeção por câmara ---

def test_residuos_calcular():
    """Campo de resíduos de reprojeção por câmara (F3.E13)."""
    pontos_3d = [
        [0.0, 0.0, 5.0],
        [1.0, 0.0, 5.0],
        [0.0, 1.0, 5.0],
    ]
    observacoes_por_camera = {
        "cam1": [
            [0, 320.0, 240.0],  # ponto 0 projetado para (320, 240)
            [1, 420.0, 240.0],  # ponto 1 projetado para (420, 240)
            [2, 320.0, 340.0],  # ponto 2 projetado para (320, 340)
        ]
    }
    cameras_por_camera = {
        "cam1": {
            "modelo": "SIMPLE_PINHOLE",
            "largura": 640,
            "altura": 480,
            "params": [500.0, 320.0, 240.0],
        }
    }
    poses_por_camera = {
        "cam1": {
            "rotacao": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "translacao": [0.0, 0.0, 5.0],
        }
    }

    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "residuos.calcular",
        "versao": "1.0.0",
        "parametros": {
            "pontos_3d": pontos_3d,
            "observacoes_por_camera": observacoes_por_camera,
            "cameras_por_camera": cameras_por_camera,
            "poses_por_camera": poses_por_camera,
            "largura": 640,
            "altura": 480,
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"
    res = resp["metricas"]["residuos"]
    assert "cam1" in res["residuos_por_camera"]
    cam1 = res["residuos_por_camera"]["cam1"]
    assert cam1["num_observacoes"] == 3
    assert cam1["media_px"] >= 0.0


# --- F4.E11 — Mapa de cobertura como COG ---

def test_cobertura_gerar_cog(tmp_path):
    """Mapa de cobertura e contagem de furos como COG (F4.E11, F9.E3)."""
    caminho_cog = tmp_path / "cobertura.cog"
    caminho_catalogo = tmp_path / "catalogo.sqlite"

    coords = [(10.0, 10.0), (20.0, 20.0), (30.0, 30.0)]

    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "cobertura.gerar_cog",
        "versao": "1.0.0",
        "parametros": {
            "coords": coords,
            "largura": 64,
            "altura": 64,
            "caminho_cog": str(caminho_cog),
            "caminho_catalogo": str(caminho_catalogo),
            "crs": "EPSG:3763",
            "crs_declaracao": "CRS projetado nacional",
            "product_id": "cobertura-teste",
            "task_id": "cobertura-teste-001",
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"
    cov = resp["metricas"]["cobertura"]
    assert "cobertura_percent" in cov
    assert "furos_contagem" in cov
    assert "furos_area_m2" in cov
    assert "cog" in cov
    assert cov["registado_em_catalogo"] is True


# --- F4.E12 — Mapa de incerteza com legenda e decomposição ---

def test_cobertura_gerar_incerteza_cog(tmp_path):
    """Mapa de incerteza com decomposição (F4.E12, F9.E3)."""
    caminho_cog = tmp_path / "incerteza.cog"
    caminho_catalogo = tmp_path / "catalogo2.sqlite"

    coords = [(10.0, 10.0), (20.0, 20.0)]
    valores = [0.5, 1.0]

    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "cobertura.gerar_incerteza_cog",
        "versao": "1.0.0",
        "parametros": {
            "coords": coords,
            "valores": valores,
            "largura": 64,
            "altura": 64,
            "caminho_cog": str(caminho_cog),
            "caminho_catalogo": str(caminho_catalogo),
            "crs": "EPSG:3763",
            "crs_declaracao": "CRS projetado nacional",
            "incerteza_controlo": 0.1,
            "incerteza_cena": 0.2,
            "product_id": "incerteza-teste",
            "task_id": "incerteza-teste-001",
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"
    inc = resp["metricas"]["cobertura"]
    assert "incerteza_total" in inc
    assert "fracao_controlo" in inc
    assert "fracao_cena" in inc
    assert "cog" in inc
    assert inc["registado_em_catalogo"] is True


# --- F8.E6 — Verificação multivista por acumulação de profundidade ---

def test_verificacao_multivista_verificar_completa():
    """Verificação multivista completa (F8.E6, F9.E4)."""
    rasters = [
        {
            "dados": [[10.0, 10.0], [10.0, 10.0]],
            "transformacao": [0.0, 1.0, 0.0, 0.0, 0.0, -1.0],
        },
        {
            "dados": [[10.1, 10.0], [10.0, 10.0]],
            "transformacao": [0.0, 1.0, 0.0, 0.0, 0.0, -1.0],
        },
    ]
    sub_regioes = [
        {
            "identificador": "sr1",
            "coordenadas": [0.0, 0.0, 2.0, 2.0],
            "num_vistas_observadoras": 0,
            "estado": "sem_dados",
        }
    ]

    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "verificacao_multivista.verificar_completa",
        "versao": "1.0.0",
        "parametros": {
            "rasters_profundidade": rasters,
            "sub_regioes": sub_regioes,
            "referencia_laser": {
                "profundidade_por_regiao": {"sr1": 10.05},
                "limiar_inconsistencia_m": 0.1,
            },
            "semente": 42,
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"
    ver = resp["metricas"]["verificacao_multivista"]
    assert "num_regioes_inconsistentes" in ver
    assert "num_regioes_validas" in ver
    assert "semente" in ver
    assert ver["semente"] == 42


# --- Testes diretos do módulo residuos ---

def test_residuos_modulo_direto():
    """Teste direto do módulo residuos (F3.E13)."""
    from khnumn import residuos

    pontos_3d = [
        [0.0, 0.0, 5.0],
        [1.0, 0.0, 5.0],
    ]
    observacoes_por_camera = {
        "cam1": [
            [0, 320.0, 240.0],
            [1, 420.0, 240.0],
        ]
    }
    cameras_por_camera = {
        "cam1": {
            "modelo": "SIMPLE_PINHOLE",
            "largura": 640,
            "altura": 480,
            "params": [500.0, 320.0, 240.0],
        }
    }
    poses_por_camera = {
        "cam1": {
            "rotacao": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "translacao": [0.0, 0.0, 5.0],
        }
    }

    campo = residuos.calcular_residuos_reprojecao(
        pontos_3d,
        observacoes_por_camera,
        cameras_por_camera,
        poses_por_camera,
        640,
        480,
    )
    assert "cam1" in campo.residuos_por_camera
    cam1 = campo.residuos_por_camera["cam1"]
    assert cam1.num_observacoes == 2
    assert campo.versao_rasterizador == "1.0.0"

    dicio = residuos.campo_residuos_para_dict(campo)
    assert "residuos_por_camera" in dicio
    assert dicio["residuos_por_camera"]["cam1"]["num_observacoes"] == 2
