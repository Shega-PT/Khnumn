"""Testes do diagnóstico do modelo e da declaração do gauge.

O diagnóstico é o que distingue um modelo de um resultado plausível, e a
declaração do gauge é o que torna a covariância estimada fiável. Nenhum dos
dois é verificável por olhar para o resultado.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "python"))

from khnumn.adaptadores.colmap import (  # noqa: E402
    AdaptadorColmap,
    ErroAdaptador,
    ParametrosMotor,
    diagnosticar,
)


class ImagemFalsa:
    """Uma imagem, do ponto de vista do diagnóstico."""

    def __init__(self, image_id: int, registada: bool = True):
        self.image_id = image_id
        self.name = f"img_{image_id}.jpg"
        self.has_pose = registada


class ElementoRastroFalso:
    """Um elemento de rasto: uma imagem e o ponto que observa."""

    def __init__(self, image_id: int):
        self.image_id = image_id


class RastroFalso:
    """O rasto de um ponto 3D, com as imagens que o observam."""

    def __init__(self, image_ids: list[int]):
        self.elements = [ElementoRastroFalso(i) for i in image_ids]


class PontoFalso:
    """Um ponto 3D, com o seu rasto."""

    def __init__(self, image_ids: list[int]):
        self.track = RastroFalso(image_ids)


class ReconstrucaoFalsa:
    """Uma reconstrução mínima, para exercitar o diagnóstico."""

    def __init__(self, cameras_registadas: int, observacoes: int, componentes: int):
        self.cameras = {i: object() for i in range(cameras_registadas)}
        self.images = {i: ImagemFalsa(i) for i in range(cameras_registadas)}
        # Cada ponto é observado por duas imagens consecutivas, o que dá uma
        # componente conexa.
        self.points3D = {
            i: PontoFalso([i % cameras_registadas, (i + 1) % cameras_registadas])
            for i in range(observacoes)
        }

    def num_reg_images(self) -> int:
        return len(self.images)

    def num_points3D(self) -> int:
        return len(self.points3D)

    def compute_num_observations(self) -> int:
        return self._observacoes

    def compute_mean_reprojection_error(self) -> float:
        return 0.5

    def compute_mean_track_length(self) -> float:
        return self._comprimento

    def summary(self) -> str:
        return "resumo"


def _reconstrucao(observacoes=100, comprimento=3.0):
    r = ReconstrucaoFalsa(4, 100, 1)
    r._observacoes = observacoes
    r._comprimento = comprimento
    return r


def test_o_diagnostico_declara_o_gauge():
    gauge = {"fixado": True, "par_inicial": ["a.jpg", "b.jpg"], "metodo": "declarado"}
    resultado = diagnosticar(_reconstrucao(), gauge)

    assert resultado["gauge"]["fixado"] is True
    assert "gauge nao fixado" not in " ".join(resultado["indicadores_de_degenerescencia"])


def test_o_gauge_nao_fixado_e_um_indicador():
    resultado = diagnosticar(_reconstrucao(), {"fixado": False})

    indicadores = " ".join(resultado["indicadores_de_degenerescencia"])
    assert "gauge nao fixado" in indicadores


def test_a_observabilidade_fraca_e_um_indicador():
    resultado = diagnosticar(_reconstrucao(observacoes=40), {"fixado": True})

    indicadores = " ".join(resultado["indicadores_de_degenerescencia"])
    assert "observabilidade" in indicadores


def test_o_erro_de_reprojecao_e_declarado_como_diagnostico():
    resultado = diagnosticar(_reproducao := _reconstrucao(), {"fixado": True})

    assert "Nao diz nada sobre escala" in resultado["erro_reprojecao_e_diagnostico"]
    assert _reproducao.num_reg_images() == 4


def test_o_par_inicial_tem_de_ser_um_par():
    with pytest.raises(ErroAdaptador):
        ParametrosMotor.de_dict({"par_inicial": ["so-uma.jpg"]})


def test_o_par_inicial_e_registado_nos_parametros():
    parametros = ParametrosMotor.de_dict({"par_inicial": ["a.jpg", "b.jpg"]})

    assert parametros.par_inicial == ("a.jpg", "b.jpg")
    assert parametros.para_dict()["par_inicial"] == ["a.jpg", "b.jpg"]
    assert parametros.para_dict()["fixar_gauge"] is True


def test_o_adaptador_declara_o_gauge_por_omissao():
    assert AdaptadorColmap().parametros.fixar_gauge is True
    assert AdaptadorColmap().parametros.semente == 0


def test_as_observacoes_rejeitadas_sao_calculadas_quando_ha_base_de_dados(tmp_path):
    """As observações rejeitadas são a diferença entre o verificado e o que sobreviveu."""
    import sqlite3

    base = tmp_path / "database.db"
    ligacao = sqlite3.connect(base)
    ligacao.execute(
        "CREATE TABLE two_view_geometries (rows INTEGER)"
    )
    ligacao.execute("INSERT INTO two_view_geometries VALUES (100)")
    ligacao.execute("INSERT INTO two_view_geometries VALUES (50)")
    ligacao.commit()
    ligacao.close()

    resultado = diagnosticar(_reconstrucao(observacoes=40), {"fixado": True}, base)

    # 150 correspondencias verificadas, das quais 2 x 40 entraram no modelo.
    assert resultado["observacoes_rejeitadas"] == 70


def test_as_observacoes_rejeitadas_desconhecidas_nao_sao_inventadas(tmp_path):
    resultado = diagnosticar(_reconstrucao(), {"fixado": True}, tmp_path / "inexistente.db")

    assert resultado["observacoes_rejeitadas"] is None
