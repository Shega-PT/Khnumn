"""Testes da Fase 6: vídeo e sensores auxiliares."""

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
    cenario,
    compatibilidade_temporal,
    cobertura,
    controle,
    decisao_evidencia,
    dtm,
    evidencia,
    gnss_imu,
    lidar,
    marcas,
    metadados,
    ortoimagem,
    planeador,
    plano_execucao,
    qualidade,
    radiometria,
    raster,
    rolling_shutter,
    seguranca,
    scheduler,
    satelite,
    superficie,
    tempo,
    validacao,
    validacao_denso,
    video,
    worker,
    worker_remoto,
)  # noqa: E402


# ============================================================================
# F6.E1 — Sincronização de relógios
# ============================================================================

def test_sincronizar_relogios_aplica_desvio():
    instantes = [
        {"imagem": "img1", "instante_gps": __import__("datetime").datetime(2026, 1, 1, 12, 0, 0)},
        {"imagem": "img2", "instante_gps": None},
    ]
    sinc = tempo.sincronizar_relogios(instantes, "GNSS")
    assert sinc.fonte_referencia == "GNSS"
    assert sinc.instantes[0].valor_utc is not None
    assert sinc.instantes[1].valor_utc is None
    assert sinc.instantes[1].origem == "ausente"


def test_convenir_instante_captura_meio_exposicao():
    meta = {
        "capture": {
            "capture_time_utc": "2026-01-01T12:00:00Z",
            "clock_source": "gnss_timestamp",
        },
        "exposure": {"exposure_time_s": 0.02},
    }
    inst = tempo.convenir_instante_captura(meta, "meio_exposicao")
    assert inst.convencao == "meio_exposicao"
    assert inst.valor_utc is not None


def test_convenir_instante_captura_ausente():
    meta = {"capture": {"capture_time_utc": None, "clock_source": "ausente"}}
    inst = tempo.convenir_instante_captura(meta, "inicio_exposicao")
    assert inst.valor_utc is None
    assert inst.origem == "ausente"


# ============================================================================
# F6.E2 — Extração adaptativa de fotogramas
# ============================================================================

def test_selecionar_fotogramas_vazio():
    r = video.selecionar_fotogramas([])
    assert r["num_originais"] == 0
    assert r["num_selecionados"] == 0


def test_selecionar_fotogramas_com_politica():
    import tempfile, os
    from PIL import Image
    import numpy as np
    caminhos = []
    for i in range(3):
        f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        # Imagem com ruído para ter nitidez alta
        arr = np.random.randint(0, 256, (100, 100), dtype=np.uint8)
        img = Image.fromarray(arr, mode="L")
        img.save(f.name)
        caminhos.append(f.name)
    try:
        politica = video.PoliticaMemoria(max_fotogramas=10, max_memoria_mb=500)
        r = video.selecionar_fotogramas(caminhos, politica)
        assert r["num_selecionados"] > 0
        assert r["num_selecionados"] <= r["num_originais"]
    finally:
        for c in caminhos:
            os.unlink(c)


# ============================================================================
# F6.E4 — Rolling shutter
# ============================================================================

def test_modelo_tempo_linha():
    corr = rolling_shutter.modelo_tempo_linha(
        linha=100,
        tempo_exposicao_s=0.02,
        velocidade_leitura_s_por_linha=0.0001,
        altura_sensor_px=1000,
        direcao="topo_para_baixo",
    )
    assert corr.linha == 100
    assert corr.instante_desvio_s == pytest.approx(0.01)
    assert corr.corrigido is False  # requer caso de uso e teste de referência


def test_necessita_corretcao_rolling_shutter():
    assert rolling_shutter.necessita_corretcao_rolling_shutter(
        tempo_leitura_total_s=0.1,
        velocidade_plataforma_m_s=10.0,
        distancia_terreno_m=100.0,
    ) is True


# ============================================================================
# F6.E5 — LiDAR
# ============================================================================

def test_ingerir_nuvem_lidar_json(tmp_path):
    import json
    dados = {"pontos": [[0, 0, 0], [1, 1, 1], [2, 2, 2]]}
    f = tmp_path / "lidar.json"
    f.write_text(json.dumps(dados))
    nuvem = lidar.ingerir_nuvem_lidar(f, "EPSG:4979")
    assert nuvem.pontos.shape == (3, 3)
    assert nuvem.crs == "EPSG:4979"


def test_aplicar_calibracao_inter_sensor():
    nuvem = lidar.NuvemLiDAR(
        pontos=np.array([[0, 0, 0], [1, 1, 1]], dtype=float),
        crs="EPSG:4979",
    )
    cal = lidar.CalibracaoInterSensor(
        sensor_origem="lidar",
        sensor_destino="camera",
        translacao_m=[1.0, 2.0, 3.0],
        rotacao_rad=[0.0, 0.0, 0.0],
        escala=1.0,
    )
    nv = lidar.aplicar_calibracao_inter_sensor(nuvem, cal)
    assert nv.pontos.shape == (2, 3)


# ============================================================================
# F6.E6 — Radiometria
# ============================================================================

def test_aplicar_perfil_icc_sem_perfil():
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    r = radiometria.aplicar_perfil_icc(img, None)
    assert r.estado == "NOT_AVAILABLE"


def test_aplicar_perfil_icc_com_perfil():
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    perfil = radiometria.PerfilICC(nome="sRGB", espaco_cor="sRGB")
    r = radiometria.aplicar_perfil_icc(img, perfil)
    assert r.estado == "SUCCEEDED"


def test_corrigir_vinheta_sem_calibracao():
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    r = radiometria.corrigir_vinheta_sombreamento(img, None)
    assert r.estado == "NOT_AVAILABLE"


def test_calibrar_reflectancia_sem_bandas():
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    r = radiometria.calibrar_reflectancia_multibanda(img, None)
    assert r.estado == "NOT_AVAILABLE"


# ============================================================================
# F6.E7 — Satélite
# ============================================================================

def test_identificar_modelo_geometrico_rpc():
    meta = {
        "sensor": {"modelo_geometrico": "rpc", "versao": "1.0"},
        "rpc_coeficientes": {"a": 1.0, "b": 2.0},
    }
    m = satelite.identificar_modelo_geometrico(meta)
    assert m.tipo == "rpc"


def test_estimar_corrigir_rpc_sem_checkpoints():
    c = satelite.estimar_corrigir_viés_rpc({}, None)
    assert c.estado == "NOT_AVAILABLE"


def test_estimar_corrigir_rpc_com_checkpoints():
    meta = {}
    cps = [{"desvio_rpc": [0.1, 0.2, 0.3]}, {"desvio_rpc": [0.2, 0.3, 0.4]}]
    c = satelite.estimar_corrigir_viés_rpc(meta, cps)
    assert c.estado == "SUCCEEDED"
    assert c.num_checkpoints_usados == 2


# ============================================================================
# F6.E8 — GNSS/IMU
# ============================================================================

def test_integrar_poses_gnss_imu():
    imgs = ["a.jpg", "b.jpg"]
    meta = {
        "a.jpg": {
            "capture": {
                "position": {
                    "coordinates": [1.0, 2.0, 3.0],
                    "uncertainty_horizontal": 2.0,
                    "clock_source": "gnss_timestamp",
                    "capture_time_utc": "2026-01-01T12:00:00Z",
                }
            }
        },
        "b.jpg": {
            "capture": {
                "position": {
                    "coordinates": [4.0, 5.0, 6.0],
                    "clock_source": "gnss_timestamp",
                }
            }
        },
    }
    poses, sinc = gnss_imu.integrar_poses_gnss_imu(imgs, meta)
    assert len(poses) == 2
    assert sinc.num_poses_sincronizadas == 2


def test_medir_residuos_alinhamento():
    poses = [
        gnss_imu.PoseGNSSIMU(
            imagem="a.jpg",
            posição=[1.0, 2.0, 3.0],
            covariancia_posição=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
        )
    ]
    ref = [{"imagem": "a.jpg", "posição": [1.1, 2.1, 3.1]}]
    r = gnss_imu.medir_residuos_alinhamento(poses, ref)
    assert r["num_residuos"] == 1
    assert r["estado"] == "SUCCEEDED"


# ============================================================================
# Testes via worker (contrato)
# ============================================================================

def test_worker_tempo_sincronizar():
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "tempo.sincronizar_relogios",
        "versao": "1.0.0",
        "parametros": {
            "instantes": [
                {"imagem": "a", "instante_gps": __import__("datetime").datetime(2026, 1, 1, 12, 0, 0)}
            ],
            "fonte_referencia": "GNSS",
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"


def test_worker_lidar_ingerir(tmp_path):
    import json
    f = tmp_path / "l.json"
    f.write_text(json.dumps({"pontos": [[0, 0, 0]]}))
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "lidar.ingerir_nuvem",
        "versao": "1.0.0",
        "parametros": {"caminho": str(f), "crs": "EPSG:4979"},
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"


def test_worker_gnss_imu_integrar():
    pedido = {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": "gnss_imu.integrar_poses",
        "versao": "1.0.0",
        "parametros": {
            "imagens": ["a.jpg"],
            "metadados_por_imagem": {
                "a.jpg": {
                    "capture": {
                        "position": {
                            "coordinates": [1.0, 2.0, 3.0],
                            "clock_source": "gnss_timestamp",
                        }
                    }
                }
            },
        },
        "entradas": [],
    }
    resp = worker.processar(pedido)
    assert resp["estado"] == "SUCCEEDED"
