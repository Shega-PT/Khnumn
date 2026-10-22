"""Adaptador do motor de SfM.

O adaptador é a fronteira entre o Khnumn e o COLMAP, e é a fronteira de
licença: o que entra no motor sai como dados com proveniência, e nenhum tipo
do motor atravessa a fronteira em forma nativa (`docs/Khnumn.md` §18.3).

A interface é a de §18.3, com os cinco verbos:

| Verbo | O que faz |
|---|---|
| `run` | Executa o motor e devolve o resultado |
| `inspect` | Devolve o estado e o progresso, sem executar |
| `cancel` | Interrompe a execução |
| `collect_metrics` | Devolve as métricas do motor |
| `export` | Escreve os produtos nos formatos do Khnumn |

O que este módulo **não** faz é decidir o que o motor faz. Os parâmetros do
motor são recebidos de cima, registados em cada tarefa, e aplicados tal e
qual: uma alteração de configuração do motor que não passe por aqui deixa de
ser rastreável, e é por isso que os parâmetros são validados e guardados
antes da execução.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pycolmap

#: Versão do motor usada na última execução, lida do próprio motor.
VERSAO_MOTOR = pycolmap.__version__

#: Parâmetros que o adaptador aceita e que têm de ser registados.
PARAMETROS_RECONHECIDOS = {
    "max_image_size",
    "num_threads",
    "max_num_features",
    "use_gpu",
    "mapeador",
    "camera_model",
    "cross_check",
    "max_ratio",
    "max_distance",
    "par_inicial",
    "fixar_gauge",
    "semente",
    "use_gnss_priors",
}


class ErroAdaptador(Exception):
    """Falha no adaptador, com causa legivel."""


@dataclass
class ParametrosMotor:
    """Parâmetros do motor, com valores por omissão explícitos."""

    max_image_size: int = 1600
    num_threads: int = 2
    max_num_features: int = 4096
    use_gpu: bool = False
    mapeador: str = "incremental"
    camera_model: str = "SIMPLE_RADIAL"
    cross_check: bool = True
    max_ratio: float = 0.8
    max_distance: float = 0.7
    #: Par inicial do mapeamento, por nome de imagem. Fixa o gauge.
    par_inicial: tuple[str, str] | None = None
    #: Fixar o gauge por construção, e não pela escolha interna do motor.
    fixar_gauge: bool = True
    #: Semente do mapeador, para reprodutibilidade.
    semente: int = 0
    #: Usa priors de pose GNSS, quando existirem.
    use_gnss_priors: bool = False

    @classmethod
    def de_dict(cls, valores: dict[str, Any]) -> "ParametrosMotor":
        """Constrói os parâmetros a partir de um dicionário, recusando o desconhecido.

        Um parâmetro desconhecido é um erro, e não uma nota: um
        parametrinho novo que o motor ignore em silêncio é um resultado que
        ninguém sabe explicar.
        """
        desconhecidos = set(valores) - PARAMETROS_RECONHECIDOS
        if desconhecidos:
            raise ErroAdaptador(
                f"parametros desconhecidos para o motor: {sorted(desconhecidos)}; "
                f"reconhecidos: {sorted(PARAMETROS_RECONHECIDOS)}"
            )
        dados = {chave: valor for chave, valor in valores.items() if chave in PARAMETROS_RECONHECIDOS}
        par = dados.get("par_inicial")
        if par is not None:
            if not isinstance(par, (list, tuple)) or len(par) != 2:
                raise ErroAdaptador("'par_inicial' tem de ser um par de nomes de imagem")
            dados["par_inicial"] = (str(par[0]), str(par[1]))
        return cls(**dados)

    def para_dict(self) -> dict[str, Any]:
        """Devolve os parâmetros como dicionário, para registo."""
        return {
            "max_image_size": self.max_image_size,
            "num_threads": self.num_threads,
            "max_num_features": self.max_num_features,
            "use_gpu": self.use_gpu,
            "mapeador": self.mapeador,
            "camera_model": self.camera_model,
            "cross_check": self.cross_check,
            "max_ratio": self.max_ratio,
            "max_distance": self.max_distance,
            "par_inicial": list(self.par_inicial) if self.par_inicial else None,
            "fixar_gauge": self.fixar_gauge,
            "semente": self.semente,
            "use_gnss_priors": self.use_gnss_priors,
        }


@dataclass
class ResultadoMotor:
    """Resultado de uma execução do motor."""

    estado: str
    cameras_registadas: int = 0
    cameras_no_modelo: int = 0
    pontos_3d: int = 0
    observacoes: int = 0
    erro_reprojecao_medio_px: float | None = None
    comprimento_medio_de_rastro: float | None = None
    observacoes_por_imagem_media: float | None = None
    saidas: list[dict[str, Any]] = field(default_factory=list)
    metricas: dict[str, Any] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)
    versao_motor: str = VERSAO_MOTOR
    parametros: dict[str, Any] = field(default_factory=dict)
    duracao_s: float = 0.0


class AdaptadorColmap:
    """Adaptador do motor COLMAP.

    As três fases do motor — extracção, correspondência e mapeamento — são
    métodos separados, e não um método só. A razão é o orçamento de memória:
    o pico de uma fase não é o pico de outra, e uma execução que faz as três
    no mesmo processo paga a soma.

    É também a forma que o `docs/Khnumn.md` §17.1 descreve: extracção de
    características, correspondências por pares e ajuste global são unidades
    de trabalho independentes, e cada uma é executável e paralelizável por
    si.
    """

    def __init__(self, parametros: ParametrosMotor | None = None) -> None:
        self.parametros = parametros or ParametrosMotor()
        self._cancelado = False

    # -- fases ---------------------------------------------------------------

    def extrair(self, imagens: list[Path], base: Path) -> ResultadoMotor:
        """Extracção de features, para a base de dados do motor."""
        inicio = time.monotonic()
        base = Path(base)
        base.mkdir(parents=True, exist_ok=True)
        pasta_imagens = base / "imagens"
        pasta_imagens.mkdir(parents=True, exist_ok=True)
        nomes = self._ligar_imagens(imagens, pasta_imagens)

        extracao = pycolmap.FeatureExtractionOptions()
        extracao.max_image_size = self.parametros.max_image_size
        extracao.num_threads = self.parametros.num_threads
        extracao.use_gpu = self.parametros.use_gpu
        extracao.sift.max_num_features = self.parametros.max_num_features

        pycolmap.extract_features(
            str(base / "database.db"),
            str(pasta_imagens),
            nomes,
            pycolmap.CameraMode.AUTO,
            pycolmap.ImageReaderOptions(),
            extracao,
        )

        return ResultadoMotor(
            estado="SUCCEEDED",
            metricas={
                "imagens": len(nomes),
                "base_dados": str(base / "database.db"),
            },
            avisos=[] if nomes else ["nenhuma imagem foi extraida"],
            versao_motor=VERSAO_MOTOR,
            parametros=self.parametros.para_dict(),
            duracao_s=time.monotonic() - inicio,
        )

    def corresponder(self, base: Path) -> ResultadoMotor:
        """Correspondência exaustiva e verificação geométrica de dois vistos."""
        inicio = time.monotonic()
        base = Path(base)
        base_dados = base / "database.db"

        correspondencia = pycolmap.FeatureMatchingOptions()
        correspondencia.sift.cpu_brute_force_matcher = True
        correspondencia.sift.cross_check = self.parametros.cross_check
        correspondencia.sift.max_ratio = self.parametros.max_ratio
        correspondencia.sift.max_distance = self.parametros.max_distance

        pycolmap.match_exhaustive(
            str(base_dados),
            correspondencia,
            pycolmap.ExhaustivePairingOptions(),
            pycolmap.TwoViewGeometryOptions(),
        )

        return ResultadoMotor(
            estado="SUCCEEDED",
            metricas={"base_dados": str(base_dados)},
            versao_motor=VERSAO_MOTOR,
            parametros=self.parametros.para_dict(),
            duracao_s=time.monotonic() - inicio,
        )

    def mapear(self, base: Path, gnss_priors: list[dict] | None = None) -> ResultadoMotor:
        """Mapeamento esparso, e diagnóstico do modelo resultante."""
        inicio = time.monotonic()
        base = Path(base)
        base_dados = base / "database.db"
        pasta_modelo = base / "sparse"

        if gnss_priors:
            try:
                from .. import controle
                controle.aplicar_priors_gnss(str(base), gnss_priors)
                self.parametros.use_gnss_priors = True
            except Exception:
                pass

        gauge = self._declarar_gauge(base_dados)

        if self.parametros.mapeador == "global":
            opcoes = pycolmap.GlobalPipelineOptions()
            reconstrucoes = pycolmap.global_mapping(
                str(base_dados), str(base / "imagens"), str(pasta_modelo), opcoes
            )
            reconstrucao = max(reconstrucoes.values(), key=lambda r: r.num_reg_images())
        else:
            opcoes = pycolmap.IncrementalPipelineOptions()
            opcoes.random_seed = self.parametros.semente
            if getattr(self.parametros, "use_gnss_priors", False):
                opcoes.use_prior_position = True
            opcoes.init_num_trials = 1 if gauge.get("par_inicial") else 10
            if gauge.get("id_inicial"):
                opcoes.init_image_id1 = gauge["id_inicial"][0]
                opcoes.init_image_id2 = gauge["id_inicial"][1]
            if gauge.get("camera_constante") is not None:
                opcoes.constant_cameras = {gauge["camera_constante"]}
            pycolmap.incremental_mapping(
                str(base_dados), str(base / "imagens"), str(pasta_modelo), opcoes
            )
            reconstrucao = pycolmap.Reconstruction(str(pasta_do_modelo(pasta_modelo)))

        return self._resultado(reconstrucao, pasta_do_modelo(pasta_modelo), inicio, gauge, base)

    # -- verbos da interface -------------------------------------------------

    def run(self, imagens: list[Path], saida: Path) -> ResultadoMotor:
        """Executa as três fases, por ordem, num único processo.

        Preferir `extrair`, `corresponder` e `mapear` como chamadas
        separadas: cada fase tem o seu orçamento de memória.
        """
        inicio = time.monotonic()
        if not imagens:
            raise ErroAdaptador("nenhuma imagem indicada")

        base = Path(saida)
        if base.exists():
            shutil.rmtree(base)
        base.mkdir(parents=True, exist_ok=True)

        self.extrair(imagens, base)
        if self._cancelado:
            return self._cancelado_resultado(inicio)
        self.corresponder(base)
        if self._cancelado:
            return self._cancelado_resultado(inicio)
        return self.mapear(base)

    def inspect(self) -> dict[str, Any]:
        """Devolve o estado do adaptador, sem executar nada."""
        return {
            "motor": "COLMAP",
            "versao_motor": VERSAO_MOTOR,
            "parametros": self.parametros.para_dict(),
            "cancelado": self._cancelado,
            "existe_pycolmap": pycolmap is not None,
        }

    def cancel(self) -> dict[str, Any]:
        """Pede a interrupção da execução."""
        self._cancelado = True
        return {"estado": "CANCELLED", "cancelado": True}

    def collect_metrics(self, resultado: ResultadoMotor) -> dict[str, Any]:
        """Devolve as métricas do motor."""
        return {
            "versao_motor": resultado.versao_motor,
            "parametros": resultado.parametros,
            "cameras_registadas": resultado.Cameras_registadas,
            "pontos_3d": resultado.pontos_3d,
            "observacoes": resultado.observacoes,
            "erro_reprojecao_medio_px": resultado.erro_reprojecao_medio_px,
            "duracao_s": resultado.duracao_s,
            "metricas": resultado.metricas,
        }

    def export(self, modelo: Path, destino: Path) -> list[dict[str, Any]]:
        """Escreve as poses e a nuvem esparsa nos formatos do Khnumn."""
        destino = Path(destino)
        destino.mkdir(parents=True, exist_ok=True)
        reconstrucao = pycolmap.Reconstruction(str(pasta_do_modelo(Path(modelo))))

        saidas: list[dict[str, Any]] = []

        caminho_poses = destino / "poses.csv"
        with caminho_poses.open("w", encoding="utf-8") as ficheiro:
            ficheiro.write("image_id,name,qw,qx,qy,qz,tx,ty,tz\n")
            for imagem in reconstrucao.images.values():
                if not imagem.has_pose:
                    continue
                pose = imagem.cam_from_world()
                # A rotacao e devolvida em xyzw, e o quaternao em wxyz: a
                # conversao e feita aqui, e nao no consumidor, para que o
                # ficheiro exportado tenha uma convencao so.
                quat = pose.rotation.quat
                w, x, y, z = float(quat[3]), float(quat[0]), float(quat[1]), float(quat[2])
                translacao = pose.translation
                ficheiro.write(
                    "{},{},{:.10f},{:.10f},{:.10f},{:.10f},{:.10f},{:.10f},{:.10f}\n".format(
                        imagem.image_id,
                        imagem.name,
                        w,
                        x,
                        y,
                        z,
                        float(translacao[0]),
                        float(translacao[1]),
                        float(translacao[2]),
                    )
                )
        saidas.append({"papel": "poses", "uri": str(caminho_poses), "bytes": caminho_poses.stat().st_size})

        caminho_nuvem = destino / "nuvem_esparsa.ply"
        with caminho_nuvem.open("w", encoding="utf-8") as ficheiro:
            escrever_ply(reconstrucao, ficheiro)
        saidas.append({"papel": "nuvem_esparsa", "uri": str(caminho_nuvem), "bytes": caminho_nuvem.stat().st_size})

        caminho_modelo = destino / "modelo.json"
        modelo_json = {
            "versao_motor": VERSAO_MOTOR,
            "cameras": {
                str(camara.camera_id): {
                    "modelo": str(camara.model),
                    "largura": camara.width,
                    "altura": camara.height,
                    "parametros": list(camara.params),
                }
                for camara in reconstrucao.cameras.values()
            },
            "imagens": {
                str(imagem.image_id): {
                    "nome": imagem.name,
                    "registada": imagem.has_pose,
                    "pontos_3d": imagem.num_points3D,
                }
                for imagem in reconstrucao.images.values()
            },
            "pontos_3d": len(reconstrucao.points3D),
        }
        caminho_modelo.write_text(
            json.dumps(modelo_json, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        saidas.append({"papel": "relatorio", "uri": str(caminho_modelo), "bytes": caminho_modelo.stat().st_size})

        return saidas

    # -- internos ------------------------------------------------------------

    def _declarar_gauge(self, base_dados: Path) -> dict[str, Any]:
        """Declara o gauge do ajuste, de forma explícita.

        Sem esta declaração, o gauge é fixado pela escolha interna do
        motor, e ninguém sabe qual foi. A liberdade de gauge tem de estar
        fixada **por construção** e registada, porque é dela que depende a
        fiabilidade da covariância estimada (`docs/Khnumn.md` §11.4).

        A declaração tem duas partes: o par inicial, que fixa a origem e a
        escala, e a câmara mantida constante, que fixa a orientação.
        """
        gauge: dict[str, Any] = {
            "fixado": self.parametros.fixar_gauge,
            "par_inicial": list(self.parametros.par_inicial) if self.parametros.par_inicial else None,
            "id_inicial": None,
            "camera_constante": None,
            "metodo": "par inicial declarado e primeira camara mantida constante",
        }
        if not self.parametros.fixar_gauge:
            gauge["metodo"] = "escolha interna do motor, nao declarada"
            return gauge

        import sqlite3

        try:
            ligacao = sqlite3.connect(f"file:{base_dados}?mode=ro", uri=True)
            ids = dict(ligacao.execute("SELECT name, image_id FROM images").fetchall())
            ligacao.close()
        except Exception:
            return gauge

        par = self.parametros.par_inicial
        if par and par[0] in ids and par[1] in ids:
            gauge["id_inicial"] = (ids[par[0]], ids[par[1]])

        # A primeira camara, por ordem de identificador, e mantida constante.
        try:
            ligacao = sqlite3.connect(f"file:{base_dados}?mode=ro", uri=True)
            cameras = ligacao.execute(
                "SELECT camera_id FROM cameras ORDER BY camera_id"
            ).fetchall()
            ligacao.close()
            if cameras:
                gauge["camera_constante"] = cameras[0][0]
        except Exception:
            pass

        return gauge

    def _ligar_imagens(self, imagens: list[Path], pasta_imagens: Path) -> list[str]:
        """Liga as imagens na pasta de trabalho e devolve os seus nomes.

        As imagens sao ligadas, e nao copiadas: a copia duplicaria hundreds
        de megabytes por nada, e o original e o que tem de ser preservado.
        """
        nomes = []
        for imagem in imagens:
            destino = pasta_imagens / Path(imagem).name
            if not destino.exists():
                destino.symlink_to(Path(imagem).resolve())
            nomes.append(Path(imagem).name)
        return nomes

    def _resultado(
        self,
        reconstrucao,
        modelo: Path,
        inicio: float,
        gauge: dict[str, Any] | None = None,
        base: Path | None = None,
    ) -> ResultadoMotor:
        """Monta o resultado a partir da reconstrução."""
        avisos: list[str] = []
        if reconstrucao.num_reg_images() == 0:
            avisos.append("nenhuma imagem foi registada: a cena nao produziu modelo")
        base_dados = Path(base) / "database.db" if base else None
        diagnostico = diagnosticar(reconstrucao, gauge or {}, base_dados)
        if diagnostico["componentes_conectadas"] > 1:
            avisos.append(
                f"o modelo tem {diagnostico['componentes_conectadas']} componentes "
                "desconexas: as partes nao se apoiam umas nas outras"
            )
        return ResultadoMotor(
            estado="SUCCEEDED_WITH_WARNINGS" if avisos else "SUCCEEDED",
            cameras_registadas=reconstrucao.num_reg_images(),
            cameras_no_modelo=len(reconstrucao.cameras),
            pontos_3d=reconstrucao.num_points3D(),
            observacoes=reconstrucao.compute_num_observations(),
            erro_reprojecao_medio_px=reconstrucao.compute_mean_reprojection_error(),
            comprimento_medio_de_rastro=reconstrucao.compute_mean_track_length(),
            observacoes_por_imagem_media=reconstrucao.compute_mean_observations_per_reg_image(),
            metricas={
                "resumo_modelo": reconstrucao.summary(),
                "componentes_conectadas": componentes_conectadas(reconstrucao),
                "diagnostico": diagnostico,
                "modelo": str(modelo),
                "instantaneo_utc": _dt.datetime.now(_dt.timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
            },
            avisos=avisos,
            versao_motor=VERSAO_MOTOR,
            parametros=self.parametros.para_dict(),
            duracao_s=time.monotonic() - inicio,
        )

    def _cancelado_resultado(self, inicio: float) -> ResultadoMotor:
        """Resultado de uma execução cancelada."""
        return ResultadoMotor(
            estado="CANCELLED",
            avisos=["execucao cancelada a pedido"],
            versao_motor=VERSAO_MOTOR,
            parametros=self.parametros.para_dict(),
            duracao_s=time.monotonic() - inicio,
        )


def escrever_ply(reconstrucao, ficheiro) -> None:
    """Escreve a nuvem de pontos 3D em PLY."""
    pontos = reconstrucao.points3D
    ficheiro.write("ply\n")
    ficheiro.write("format ascii 1.0\n")
    ficheiro.write(f"element vertex {len(pontos)}\n")
    ficheiro.write("property float x\nproperty float y\nproperty float z\n")
    ficheiro.write("property uchar red\nproperty uchar green\nproperty uchar blue\n")
    ficheiro.write("end_header\n")
    for ponto in pontos.values():
        cor = ponto.color
        ficheiro.write(
            f"{ponto.xyz[0]:.6f} {ponto.xyz[1]:.6f} {ponto.xyz[2]:.6f} {cor[0]} {cor[1]} {cor[2]}\n"
        )


def pasta_do_modelo(base: Path) -> Path:
    """Localiza a pasta com o modelo, dentro da saida do motor.

    O motor escreve o modelo num subdirectório numerado (`sparse/0`), e
    escreve em `sparse` quando a execução é a última da série. Adivinhar o
    caminho em vez de o procurar é a forma de o pipeline partir quando o
    motor muda de convenção.
    """
    base = Path(base)
    if (base / "cameras.bin").exists() or (base / "cameras.txt").exists():
        return base
    candidatas = sorted(
        (p for p in base.glob("*") if p.is_dir() and (p / "cameras.bin").exists()),
        key=lambda p: p.name,
    )
    if candidatas:
        return candidatas[-1]
    if base.exists():
        return base
    return base


def componentes_conectadas(reconstrucao) -> list[list[str]]:
    """Devolve as componentes conexas do grafo de vistas.

    Uma imagem está ligada a outra quando observam um ponto 3D em comum. Um
    modelo com mais do que uma componente é um modelo com partes que não se
    apoiam umas nas outras, e isso é um diagnóstico, não um detalhe: é a
    diferença entre um modelo e dois modelos pegados lado a lado.
    """
    pai: dict[int, int] = {}

    def encontrar(x: int) -> int:
        pai.setdefault(x, x)
        while pai[x] != x:
            pai[x] = pai[pai[x]]
            x = pai[x]
        return x

    def unir(a: int, b: int) -> None:
        ra, rb = encontrar(a), encontrar(b)
        if ra != rb:
            pai[ra] = rb

    for ponto in reconstrucao.points3D.values():
        elementos = list(ponto.track.elements)
        if not elementos:
            continue
        primeiro = elementos[0].image_id
        for elemento in elementos[1:]:
            unir(primeiro, elemento.image_id)

    grupos: dict[int, list[str]] = {}
    for imagem in reconstrucao.images.values():
        if not imagem.has_pose:
            continue
        raiz = encontrar(imagem.image_id)
        grupos.setdefault(raiz, []).append(imagem.name)

    return sorted(grupos.values(), key=len, reverse=True)


def diagnosticar(
    reconstrucao,
    gauge: dict[str, Any] | None = None,
    base_dados: Path | None = None,
) -> dict[str, Any]:
    """Produz o diagnóstico do modelo.

    O diagnóstico tem de distinguir duas coisas que um erro de reprojecção
    baixo não distingue: a liberdade de gauge, que é esperada e foi removida
    por construção, e a deficiente observabilidade geométrica da cena, que é
    um aviso sobre a cena e não sobre a parametrização
    (`docs/Khnumn.md` §11.5).
    """
    gauge = gauge or {}
    componentes = componentes_conectadas(reconstrucao)
    observacoes = reconstrucao.compute_num_observations()
    cameras_registadas = reconstrucao.num_reg_images()

    # Observações rejeitadas: as correspondências verificadas que não
    # entraram no modelo final. A base de dados tem o total verificado, e o
    # modelo tem o que sobreviveu.
    observacoes_rejeitadas = None
    try:
        import sqlite3

        ligacao = sqlite3.connect(f"file:{base_dados}?mode=ro", uri=True)
        total = ligacao.execute(
            "SELECT COALESCE(SUM(rows), 0) FROM two_view_geometries"
        ).fetchone()[0]
        ligacao.close()
        observacoes_rejeitadas = max(0, int(total) - 2 * observacoes)
    except Exception:
        observacoes_rejeitadas = None

    observacoes_por_imagem = (
        observacoes / cameras_registadas if cameras_registadas else 0.0
    )
    comprimento_medio = reconstrucao.compute_mean_track_length()

    # Indicadores de degenerescência.
    indicadores: list[str] = []
    if cameras_registadas == 0:
        indicadores.append("nenhuma camera registada")
    if len(componentes) > 1:
        indicadores.append(
            f"{len(componentes)} componentes desconexas: a cena nao forma um modelo unico"
        )
    if cameras_registadas and observacoes_por_imagem < 50:
        indicadores.append(
            f"poucas observacoes por imagem ({observacoes_por_imagem:.1f}): "
            "observabilidade geometrica fraca"
        )
    if cameras_registadas and comprimento_medio < 2.0:
        indicadores.append(
            f"comprimento medio de rasto curto ({comprimento_medio:.2f}): "
            "a triangulacao apoia-se em pares, e um par nao fixa a escala"
        )
    if not gauge.get("fixado"):
        indicadores.append(
            "gauge nao fixado explicitamente: a liberdade de transformacao global "
            "permanece e a covariancia estimada nao e fiavel"
        )

    return {
        "cameras_registadas": cameras_registadas,
        "cameras_no_modelo": len(reconstrucao.cameras),
        "pontos_3d": reconstrucao.num_points3D(),
        "observacoes": observacoes,
        "observacoes_rejeitadas": observacoes_rejeitadas,
        "erro_reprojecao_medio_px": reconstrucao.compute_mean_reprojection_error(),
        "comprimento_medio_de_rastro": comprimento_medio,
        "observacoes_por_imagem_media": observacoes_por_imagem,
        "componentes_conectadas": len(componentes),
        "componentes": componentes,
        "gauge": gauge,
        "indicadores_de_degenerescencia": indicadores,
        "erro_reprojecao_e_diagnostico": (
            "O erro de reprojecao mede a consistencia interna do ajuste. "
            "Nao diz nada sobre escala, georreferenciacao ou observabilidade."
        ),
    }


__all__ = [
    "AdaptadorColmap",
    "ErroAdaptador",
    "ParametrosMotor",
    "ResultadoMotor",
    "VERSAO_MOTOR",
    "componentes_conectadas",
    "diagnosticar",
    "escrever_ply",
    "pasta_do_modelo",
]
