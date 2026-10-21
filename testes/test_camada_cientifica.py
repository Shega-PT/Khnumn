"""Testes da camada científica.

Os testes correm sobre as fixtures sintéticas de `testes/fixtures/imagens`,
geradas por `testes/fixtures/gerar.py`. São pequenas de propósito: o
orçamento de memória do ambiente de referência é de 500 MiB, e um conjunto de
testes que precisa de gigabytes não é executável no ambiente que se quer
verificar.

Uso: `.venv/bin/python -m pytest testes/ -q`
"""

from __future__ import annotations

import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "python"))

from khnumn import geo, metadados, qualidade, worker  # noqa: E402
from khnumn.adaptadores.colmap import ErroAdaptador, ParametrosMotor  # noqa: E402

FIXTURES = RAIZ / "testes" / "fixtures" / "imagens"


@pytest.fixture(scope="session", autouse=True)
def fixtures():
    """Garante que as fixtures existem."""
    if not FIXTURES.exists() or not any(FIXTURES.glob("*.jpg")):
        subprocess.run(
            [sys.executable, str(RAIZ / "testes" / "fixtures" / "gerar.py"), str(FIXTURES)],
            check=True,
        )
    return FIXTURES


# -- metadados ---------------------------------------------------------------


def test_o_exif_com_gps_e_lido(fixtures):
    registo = metadados.extrair(fixtures / "com_gps_00.jpg")

    assert registo["media_type"] == "image/jpeg"
    assert registo["width"] == 640
    assert registo["height"] == 480

    captura = registo["capture"]
    assert captura["clock_source"] == "gnss_timestamp"
    assert captura["capture_time_utc"] == "2026-05-12T10:24:31Z"

    posicao = captura["position"]
    assert posicao is not None
    assert posicao["crs"] == "EPSG:4979"
    assert posicao["coordinates"][0] == pytest.approx(-1.2345, abs=1e-4)
    assert posicao["coordinates"][1] == pytest.approx(43.2100, abs=1e-4)
    assert posicao["coordinates"][2] == pytest.approx(120.5, abs=0.01)
    assert posicao["vertical_datum"] == "elipsoidal_wgs84"


def test_a_posicao_ausente_e_registada_como_ausente(fixtures):
    registo = metadados.extrair(fixtures / "sem_gps_00.jpg")

    assert registo["capture"]["position"] is None
    assert "position" in registo["campos_ausentes"]
    # A ausência de um campo e um dado, e nao uma omissao.
    assert registo["capture"]["capture_time_utc"] is not None


def test_a_exposicao_e_lida_com_racionais(fixtures):
    registo = metadados.extrair(fixtures / "com_gps_00.jpg")

    exposicao = registo["exposure"]
    assert exposicao["exposure_time_s"] == pytest.approx(0.002)
    assert exposicao["aperture"] == pytest.approx(2.8)
    assert exposicao["iso"] == 100
    assert exposicao["focal_length_mm"] == pytest.approx(24.0)


def test_um_ficheiro_que_nao_e_imagem_nao_e_um_erro(fixtures):
    registo = metadados.extrair(fixtures / "notas.txt")

    assert registo["media_type"] == "application/octet-stream"
    assert registo["width"] is None
    assert "imagem" in registo["campos_ausentes"]


def test_a_incerteza_nao_e_inventada_a_partir_do_dop(fixtures):
    """O DOP do receptor nao e uma incerteza, e nao pode ser declarado como tal."""
    registo = metadados.extrair(fixtures / "com_gps_00.jpg")

    posicao = registo["capture"]["position"]
    assert posicao["uncertainty_horizontal"] is None
    assert posicao["uncertainty_vertical"] is None


def test_o_carimbo_do_ficheiro_nao_e_tempo_de_captura(fixtures, tmp_path):
    """Uma imagem sem qualquer carimbo fica com o instante de captura nulo."""
    from PIL import Image

    caminho = tmp_path / "sem_carimbo.jpg"
    Image.new("RGB", (32, 24), (10, 20, 30)).save(caminho, "JPEG")

    registo = metadados.extrair(caminho)
    assert registo["capture"]["capture_time_utc"] is None
    assert registo["capture"]["clock_source"] == "ausente"
    assert "capture_time_utc" in registo["campos_ausentes"]


# -- qualidade ---------------------------------------------------------------


def test_o_quality_gate_avalia_e_nao_decide(fixtures):
    avaliacao = qualidade.avaliar(fixtures / "com_gps_00.jpg")

    assert avaliacao["metrics"]["largura"] == 640.0
    assert avaliacao["metrics"]["altura"] == 480.0
    assert "nitidez" in avaliacao["criterios"]
    assert "Nenhuma metrica isolada decide" in avaliacao["nota"]


def test_a_hash_perceptual_agrupa_imagens_iguais(fixtures):
    a = qualidade.hash_perceptual(fixtures / "com_gps_00.jpg")
    b = qualidade.hash_perceptual(fixtures / "duplicado_exacto.jpg")
    c = qualidade.hash_perceptual(fixtures / "com_gps_03.jpg")

    assert qualidade.distancia_hamming(a, b) <= qualidade.LIMIAR_QUASE_DUPLICADO
    assert qualidade.distancia_hamming(a, c) > qualidade.LIMIAR_QUASE_DUPLICADO


def test_o_quase_duplicado_e_detectado(fixtures):
    resultado = qualidade.quase_duplicados(
        [fixtures / "com_gps_00.jpg", fixtures / "duplicado_exacto.jpg"]
    )

    assert resultado["grupos"], "a imagem quase igual tem de ser agrupada"
    assert resultado["grupos"][0]["distancia_hamming"] <= qualidade.LIMIAR_QUASE_DUPLICADO


# -- geodesia ----------------------------------------------------------------


def test_o_desvio_de_segundos_intercalares_por_data():
    assert geo.desvio_leap_second(_dt.date(2016, 1, 1)) == 17
    assert geo.desvio_leap_second(_dt.date(2017, 7, 1)) == 18
    assert geo.desvio_leap_second(_dt.date(2026, 10, 21)) == 18


def test_a_conversao_para_utc_aplica_o_desvio():
    gps = _dt.datetime(2026, 5, 12, 10, 24, 31)
    assert geo.para_utc(gps) == _dt.datetime(2026, 5, 12, 10, 24, 13)


def test_a_conversao_entre_crs_passa_pelo_proj():
    """O ponto de controlo do terreno de ensaio, em UTM.

    A longitude de -1,2345 está na zona 30, cujo meridiano central é -3°.
    O easting tem de sair próximo de 643 km, e não de zero: uma conversão
    que ignora a zona produz um resultado com a magnitude errada, e com a
    escala certa.
    """
    coordenadas = geo.para_enu([-1.2345, 43.21, 120.5], "EPSG:4326", "EPSG:32630")

    assert coordenadas[0] == pytest.approx(643_000, abs=3_000)
    assert coordenadas[1] == pytest.approx(4_785_000, abs=5_000)
    assert coordenadas[2] == pytest.approx(120.5, abs=0.01)


def test_o_referencial_local_tem_origem_declarada():
    local = geo.referencial_local(-1.2345, 43.21, 120.5)

    assert local["origem"]["longitude"] == pytest.approx(-1.2345)
    assert local["unidades"]["horizontal"] == "m"


# -- contrato ----------------------------------------------------------------


def _pedido(algoritmo: str, **parametros) -> dict:
    return {
        "contrato": worker.VERSAO_CONTRATO,
        "algoritmo": algoritmo,
        "versao": "1.0.0",
        "parametros": parametros,
        "entradas": [],
    }


def test_o_contrato_desconhecido_e_recusado():
    pedido = _pedido("metadados.extrair", caminho="x")
    pedido["contrato"] = "outro-contrato"

    resposta = worker.processar(pedido)
    assert resposta["estado"] == "FAILED"
    assert "contrato" in resposta["erro"]


def test_o_algoritmo_desconhecido_e_recusado():
    resposta = worker.processar(_pedido("algoritmo.inventado"))

    assert resposta["estado"] == "FAILED"
    assert "algoritmo desconhecido" in resposta["erro"]


def test_a_fronteira_responde_sempre_com_json():
    """Um erro nao pode perder-se num traceback."""
    resposta = worker.processar(_pedido("metadados.extrair", caminho="/nao/existe.jpg"))

    assert resposta["estado"] == "FAILED"
    assert resposta["erro"]
    json.dumps(resposta)  # tem de ser serializável


def test_o_algoritmo_de_metadados_devolve_o_registo(fixtures):
    resposta = worker.processar(
        _pedido("metadados.extrair", caminho=str(fixtures / "com_gps_00.jpg"))
    )

    assert resposta["estado"] == "SUCCEEDED"
    assert resposta["metricas"]["metadados"]["media_type"] == "image/jpeg"


def test_um_ficheiro_que_nao_e_imagem_produz_um_aviso(fixtures):
    resposta = worker.processar(
        _pedido("metadados.extrair", caminho=str(fixtures / "notas.txt"))
    )

    assert resposta["estado"] == "SUCCEEDED_WITH_WARNINGS"
    assert any("nao e uma imagem" in aviso for aviso in resposta["avisos"])


# -- adaptador ---------------------------------------------------------------


def test_o_adaptador_recusa_parametros_desconhecidos():
    with pytest.raises(ErroAdaptador) as erro:
        ParametrosMotor.de_dict({"max_image_size": 1600, "parametro_inventado": 1})

    assert "parametro_inventado" in str(erro.value)


def test_o_adaptador_regista_a_versao_do_motor():
    from khnumn.adaptadores.colmap import AdaptadorColmap

    estado = AdaptadorColmap().inspect()

    assert estado["motor"] == "COLMAP"
    assert estado["versao_motor"]
    assert estado["parametros"]["max_image_size"] == 1600
    assert estado["parametros"]["use_gpu"] is False
